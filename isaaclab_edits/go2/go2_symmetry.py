# go2_symmetry.py — 99-13: 좌우 대칭 가르치기 (README 99-13) — rsl_rl PPO 의 symmetry_cfg (거울 경험 더하기) 에 넘기는 함수.
#   거울 = 몸통의 xz 면 (왼 ↔ 오른) 에 비춤. 학습 때 미니배치마다 "왼쪽 오른쪽을 바꾼 경험" 을 하나씩 더해 배운다 (Mittal 2024).
#   **짐작하지 않고 이름 · 센서로 찾는다** — 관절 짝은 관절 이름 (FL ↔ FR · RL ↔ RR) 으로, 관측의 칸 자리는 관측 관리자의
#   항 이름 · 칸 수로, 스캔 65점의 거울 자리는 센서의 광선 자리 (ray_starts · 없으면 닿은 자리) 로. 모르는 항이 있으면 멈춘다.
#   첫 호출 때 "[대칭] …" 줄들을 찍는다 (train99s.ps1 · probe99d.ps1 이 확인).
#
#   비추는 법 (몸통 틀 · y → −y):
#     선속도 · 중력 (x, y, z) → (x, −y, z)        각속도 (x, y, z) → (−x, y, −z)  (축 벡터)
#     명령 (앞, 옆, 회전) → (앞, −옆, −회전)
#     관절 (위치 · 속도 · 직전 행동): 왼 ↔ 오른 다리를 바꾸고, 엉덩이 (옆 벌림 · x 축) 만 부호를 뒤집음 · 허벅지 · 종아리 (y 축) 는 그대로
#     스캔: (x, y) 의 점 ↔ (x, −y) 의 점
import math

import torch

_M = None


def _tt(x):
    if x is None:
        return None
    if hasattr(x, "torch"):
        return x.torch
    if isinstance(x, torch.Tensor):
        return x
    try:
        import warp as wp
        return wp.to_torch(x)
    except Exception:
        return torch.as_tensor(x)


def _unwrap(env):
    u = env
    for _ in range(12):
        if hasattr(u, "observation_manager") and hasattr(u, "scene"):
            return u
        nxt = getattr(u, "unwrapped", None)
        if nxt is None or nxt is u:
            nxt = getattr(u, "env", None)
        if nxt is None:
            break
        u = nxt
    raise RuntimeError("[대칭] ✖ 환경에서 observation_manager 를 못 찾았습니다")


def _mirror_name(n):
    for a, b in (("FL_", "FR_"), ("FR_", "FL_"), ("RL_", "RR_"), ("RR_", "RL_")):
        if n.startswith(a):
            return b + n[len(a):]
    raise ValueError(f"[대칭] ✖ 관절 이름 {n} 에 FL_/FR_/RL_/RR_ 가 없습니다")


def _joint_map(names):
    names = [str(n) for n in names]
    perm, sign = [], []
    for n in names:
        m = _mirror_name(n)
        if m not in names:
            raise ValueError(f"[대칭] ✖ {n} 의 짝 {m} 이 없습니다")
        perm.append(names.index(m))
        sign.append(-1.0 if "hip" in n else 1.0)
    return perm, sign


class _Mirror:
    def __init__(self, env):
        u = _unwrap(env)
        self.lines = []
        robot = u.scene["robot"]
        jn = [str(n) for n in robot.joint_names]
        if len(jn) != 12:
            raise ValueError(f"[대칭] ✖ 관절이 {len(jn)} 개 (12 이어야 함)")
        self.jperm, self.jsign = _joint_map(jn)
        try:
            an = [str(n) for n in u.action_manager.get_term("joint_pos")._joint_names]
        except Exception:
            an = jn
            self.lines.append("[대칭] (행동 항의 관절 이름을 못 읽어 몸의 관절 차례를 씀)")
        if len(an) != 12:
            raise ValueError(f"[대칭] ✖ 행동 칸이 {len(an)} 개 (12 이어야 함)")
        self.aperm, self.asign = _joint_map(an)
        pairs = []
        for i, n in enumerate(jn):
            j = self.jperm[i]
            if i < j:
                pairs.append(f"{n.replace('_joint', '')}↔{jn[j].replace('_joint', '')}{'(−)' if self.jsign[i] < 0 else ''}")
        self.lines.append("[대칭] 관절 짝 (이름으로) " + " · ".join(pairs) + f" · 행동 차례 {'= 관절 차례' if an == jn else '≠ 관절 차례 (따로 맞춤)'}")
        # 스캔의 거울 자리
        self.sperm = None
        om = u.observation_manager
        self.groups = {}
        for g in om.active_terms:
            names = list(om.active_terms[g])
            dims = list(om.group_obs_term_dim[g])
            spec, k = [], 0
            for n, d in zip(names, dims):
                if len(d) != 1:
                    raise ValueError(f"[대칭] ✖ {g}/{n} 의 모양 {d} — 한 줄 (히스토리 없음) 이어야 함")
                w = int(d[0])
                spec.append((n, k, k + w))
                k += w
            self.groups[g] = (spec, k)
            for n, a, b in spec:
                if n == "height_scan" and self.sperm is None:
                    self.sperm, how = self._scan_perm(u, b - a)
                    self.lines.append(f"[대칭] 스캔 {b - a}점의 거울 자리 — {how}")
            self.lines.append(f"[대칭] 관측 {g} {k}칸 = " + " · ".join(f"{n} {b - a}" for n, a, b in spec))
        self._dev = {}

    def _scan_perm(self, u, n):
        sensor = u.scene.sensors["see_scanner"]
        xy, how = None, ""
        rs = getattr(sensor, "ray_starts", None)
        if rs is not None:
            rs = _tt(rs).float()
            if rs.dim() == 3:
                rs = rs[0]
            if rs.shape[0] == n:
                xy, how = rs[:, :2].cpu(), "센서의 광선 자리 (ray_starts)"
        if xy is None:
            pos = _tt(sensor.data.pos_w).reshape(-1, 3).float()
            hits = _tt(sensor.data.ray_hits_w).reshape(pos.shape[0], -1, 3).float()
            yaw = _tt(u.scene["robot"].data.heading_w).reshape(-1).float()
            d = hits[..., :2] - pos[:, None, :2]
            c, s = torch.cos(yaw)[:, None], torch.sin(yaw)[:, None]
            lx = c * d[..., 0] + s * d[..., 1]
            ly = -s * d[..., 0] + c * d[..., 1]
            loc = torch.stack([lx, ly], -1)
            loc = torch.where(torch.isfinite(loc), loc, torch.full_like(loc, float("nan")))
            xy = torch.nanmedian(loc, 0).values.cpu()
            how = "닿은 자리를 몸통 틀로 돌려서 (ray_starts 없음)"
        if xy.shape[0] != n:
            raise ValueError(f"[대칭] ✖ 스캔 점 {xy.shape[0]} 개 ≠ 관측 {n} 칸")
        perm, worst = [], 0.0
        for i in range(n):
            dd = (xy[:, 0] - xy[i, 0]).abs() + (xy[:, 1] + xy[i, 1]).abs()
            j = int(torch.argmin(dd))
            worst = max(worst, float(dd[j]))
            perm.append(j)
        if worst > 2e-3 or sorted(perm) != list(range(n)):
            raise ValueError(f"[대칭] ✖ 스캔의 거울 자리를 못 맞춤 (가장 큰 어긋남 {worst:.4f} m)")
        moved = sum(1 for i, j in enumerate(perm) if i != j)
        return perm, how + f" · 가장 큰 어긋남 {worst * 1000:.2f} mm · 자리 바뀌는 점 {moved} · 제자리 (y=0) {n - moved}"

    def _t(self, dev):
        if dev not in self._dev:
            T = lambda v, dt=torch.float32: torch.tensor(v, device=dev, dtype=dt)  # noqa: E731
            self._dev[dev] = dict(
                jp=T(self.jperm, torch.long), js=T(self.jsign), ap=T(self.aperm, torch.long), as_=T(self.asign),
                sp=(T(self.sperm, torch.long) if self.sperm is not None else None),
                lin=T([1.0, -1.0, 1.0]), ang=T([-1.0, 1.0, -1.0]), cmd=T([1.0, -1.0, -1.0]))
        return self._dev[dev]

    def obs(self, g, x):
        if g not in self.groups:
            raise ValueError(f"[대칭] ✖ 관측 묶음 {g} 를 모릅니다 (아는 것: {list(self.groups)})")
        spec, k = self.groups[g]
        if x.shape[-1] != k:
            raise ValueError(f"[대칭] ✖ 관측 {g} 가 {x.shape[-1]} 칸 (바라는 값 {k})")
        t = self._t(x.device)
        y = torch.empty_like(x)
        for n, a, b in spec:
            v = x[..., a:b]
            if n in ("base_lin_vel", "projected_gravity") and b - a == 3:
                y[..., a:b] = v * t["lin"]
            elif n == "base_ang_vel" and b - a == 3:
                y[..., a:b] = v * t["ang"]
            elif n == "velocity_commands" and b - a == 3:
                y[..., a:b] = v * t["cmd"]
            elif n in ("joint_pos", "joint_vel") and b - a == 12:
                y[..., a:b] = v[..., t["jp"]] * t["js"]
            elif n == "actions" and b - a == 12:
                y[..., a:b] = v[..., t["ap"]] * t["as_"]
            elif n == "height_scan" and t["sp"] is not None and b - a == t["sp"].numel():
                y[..., a:b] = v[..., t["sp"]]
            else:
                raise ValueError(f"[대칭] ✖ 관측 항 {n} ({b - a}칸) 을 어떻게 비출지 모릅니다 — 멈춥니다")
        return y

    def act(self, a):
        t = self._t(a.device)
        return a[..., t["ap"]] * t["as_"]


def compute_symmetric_states(env=None, obs=None, actions=None, **kw):
    """rsl_rl 의 data_augmentation_func — (원래 + 거울) 로 두 배 늘린 (관측, 행동). 첫 줄 = 원래 (rsl_rl 이 그렇게 가정)."""
    global _M
    if _M is None:
        _M = _Mirror(env)
        for ln in _M.lines:
            print(ln, flush=True)
        _M.checked = False
    obs_aug = act_aug = None
    if obs is not None:
        from tensordict import TensorDict
        d = {}
        for k in obs.keys():
            v = obs[k]
            d[k] = torch.cat([v, _M.obs(k, v)], 0)
            if not _M.checked:
                e = float((_M.obs(k, _M.obs(k, v)) - v).abs().max())
                print(f"[대칭] 스스로 시험 — {k}: 두 번 비추면 제자리 {'✔' if e == 0.0 else '✖'} (가장 큰 차 {e:.2e}) · "
                      f"한 번 비추면 달라짐 {float((_M.obs(k, v) - v).abs().mean()):.3f} (0 이 아니어야 함)", flush=True)
                if e != 0.0:
                    raise ValueError("[대칭] ✖ 두 번 비춰도 제자리가 아닙니다")
        _M.checked = True
        obs_aug = TensorDict(d, batch_size=[2 * obs.batch_size[0]], device=obs.device)
    if actions is not None:
        act_aug = torch.cat([actions, _M.act(actions)], 0)
    return obs_aug, act_aug


def install():
    """rsl_rl PPO 가 symmetry_cfg 를 이 함수로 채우게 함 (에이전트 설정 파일은 그대로 · 이 학습 과정 안에서만)."""
    import rsl_rl.algorithms.ppo as _ppo
    if getattr(_ppo, "_robotdog_sym99", False):
        return
    _orig = _ppo.resolve_symmetry_config

    def _resolve(alg_cfg, env):
        alg_cfg["symmetry_cfg"] = dict(use_data_augmentation=True, use_mirror_loss=False,
                                       data_augmentation_func=compute_symmetric_states, mirror_loss_coeff=0.0)
        print("[대칭 99] rsl_rl PPO 에 거울 경험 더하기를 넣음 (use_data_augmentation=True · mirror loss 끔 · 미니배치 두 배)", flush=True)
        return _orig(alg_cfg, env)

    _ppo.resolve_symmetry_config = _resolve
    _ppo._robotdog_sym99 = True
