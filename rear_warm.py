# -*- coding: utf-8 -*-
"""뒤 눈의 따뜻한 출발 — README 80-1 · 80-2.

 65점 정책 (입력 113) 의 체크포인트를 95점 (입력 143) 으로 늘립니다.
   · 행위자 · 비평자의 첫 층 (512 × 113) 에 새 30칸을 **0** 으로 끼워 넣습니다.
   · Adam 의 기억 (exp_avg · exp_avg_sq) 도 같은 자리에 0 으로 늘립니다.
   · 나머지 (뒤 층들 · log_std · 학습률 · iter) 는 한 비트도 안 바꿉니다.
 그래서 처음에는 뒤 눈을 안 쓰고, 2600 과 **같은 셈**을 합니다.

 칸의 자리 (학습 쪽 · sim_go2.py · scan_check.py 와 같음):
   0..47            몸 느낌 48칸 — 그대로
   옛 48 + iy·13 + ix   →   새 48 + iy·19 + ix + 6      (iy 0..4 · ix 0..12)
   새 48 + iy·19 + 0..5   = 뒤 30칸 (몸 뒤 −0.9 ~ −0.4 m) — 0 으로 시작

 돌리는 법 (Isaac Sim 의 파이썬 — 시뮬레이터는 안 띄웁니다):
   만들기   C:\\isaacsim\\python.bat rear_warm.py make  --src <model_2600.pt> --dst <새 폴더>
   견주기   C:\\isaacsim\\python.bat rear_warm.py check --old <policy_2600.pt> --new <2600w 의 policy_2600.pt>
            (꺼낸 정책 두 개를 같은 관측으로 돌려 내놓는 값이 같은지 — 80-2 의 첫 관문)

 ※ 로봇(실기체)과는 아무 상관 없습니다. 파일만 읽고 새 폴더에 씁니다 (원본은 안 건드림).
"""
import argparse
import hashlib
import os
import sys

import torch

N_PRO = 48
OLD_NX, NEW_NX, NY, REAR = 13, 19, 5, 6
OLD_IN = N_PRO + OLD_NX * NY      # 113
NEW_IN = N_PRO + NEW_NX * NY      # 143


def old_to_new():
    """옛 칸 j 가 새로 가는 자리 (길이 113)."""
    cols = list(range(N_PRO))
    for iy in range(NY):
        for ix in range(OLD_NX):
            cols.append(N_PRO + iy * NEW_NX + ix + REAR)
    return cols


COLS = old_to_new()
REAR_COLS = sorted(set(range(NEW_IN)) - set(COLS))
assert len(COLS) == OLD_IN and len(set(COLS)) == OLD_IN and len(REAR_COLS) == NEW_IN - OLD_IN == 30


def widen(t):
    out = t.new_zeros(t.shape[0], NEW_IN)
    out[:, COLS] = t
    return out


def walk(o, path=""):
    """체크포인트 안의 모든 텐서를 (자리, 텐서) 로."""
    if isinstance(o, torch.Tensor):
        yield path, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, f"{path}/{k}")
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            yield from walk(v, f"{path}[{i}]")


def mlp(sd, x):
    idx = sorted({int(k.split(".")[1]) for k in sd if k.startswith("mlp.") and k.endswith(".weight")})
    for n, i in enumerate(idx):
        x = x @ sd[f"mlp.{i}.weight"].T + sd[f"mlp.{i}.bias"]
        if n < len(idx) - 1:
            x = torch.nn.functional.elu(x)
    return x


def rand_obs(n, gen, dtype):
    old = torch.empty(n, OLD_IN, dtype=dtype)
    old[:, :N_PRO] = torch.randn(n, N_PRO, generator=gen, dtype=dtype)
    old[:, N_PRO:] = torch.rand(n, OLD_IN - N_PRO, generator=gen, dtype=dtype) * 2 - 1
    new = torch.empty(n, NEW_IN, dtype=dtype)
    new[:, COLS] = old
    new[:, REAR_COLS] = torch.rand(n, len(REAR_COLS), generator=gen, dtype=dtype) * 2 - 1   # 뒤 30칸은 아무 값이나
    return old, new


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def make(a):
    ok = True
    src = a.src
    dst = os.path.join(a.dst, os.path.basename(src))
    if os.path.exists(dst):
        print(f" ✖ {dst} 가 이미 있습니다 — 덮어쓰지 않습니다 (지우고 다시 하려면 사이안 님이 직접)")
        return False
    sha0 = sha(src)
    ck = torch.load(src, weights_only=False, map_location="cpu")
    print(f" 원본  {src}  (sha {sha0} · iter {ck.get('iter')})")

    # 113 이 들어간 텐서를 모두 찾습니다 — 첫 층 둘 + Adam 기억 넷 = 여섯이어야 합니다.
    hits = [(p, t) for p, t in walk(ck) if OLD_IN in tuple(t.shape)]
    for p, t in hits:
        print(f"   113 칸: {p}  {tuple(t.shape)}")
    want_model = {"/actor_state_dict/mlp.0.weight", "/critic_state_dict/mlp.0.weight"}
    model_hits = {p for p, t in hits if p.startswith(("/actor_state_dict", "/critic_state_dict"))}
    opt_hits = [p for p, t in hits if p.startswith("/optimizer_state_dict/state/")]
    if model_hits != want_model or len(opt_hits) != 4 or len(hits) != 6 \
            or any(t.dim() != 2 or t.shape[1] != OLD_IN for _, t in hits):
        print(" ✖ 113 칸 텐서가 바라던 여섯 (첫 층 둘 · Adam 넷) 이 아닙니다 — 멈춥니다")
        return False
    if any("normalizer" in p for p, _ in walk(ck)):
        print(" ✖ 관측 정규화 값이 들어 있습니다 (바라는 것: 꺼짐) — 멈춥니다")
        return False

    old_ck = torch.load(src, weights_only=False, map_location="cpu")    # 견줄 원본 (따로 한 벌)
    for sd in ("actor_state_dict", "critic_state_dict"):
        ck[sd]["mlp.0.weight"] = widen(ck[sd]["mlp.0.weight"])
    for st in ck["optimizer_state_dict"]["state"].values():
        for k in ("exp_avg", "exp_avg_sq"):
            if k in st and st[k].dim() == 2 and st[k].shape[1] == OLD_IN:
                st[k] = widen(st[k])

    # ── 같은가: 옮긴 칸은 비트까지 같고 · 뒤 30칸은 0 이고 · 나머지는 손 안 댐
    n_same = n_wide = 0
    old_t = dict(walk(old_ck))
    for p, t in walk(ck):
        o = old_t.get(p)
        if o is None:
            print(f" ✖ 새로 생긴 텐서 {p}"); ok = False; continue
        if tuple(o.shape) == tuple(t.shape):
            if not torch.equal(o, t):
                print(f" ✖ 손 안 대야 할 {p} 가 바뀜"); ok = False
            n_same += 1
        else:
            if not (torch.equal(t[:, COLS], o) and float(t[:, REAR_COLS].abs().max()) == 0.0):
                print(f" ✖ {p} 를 늘린 것이 틀림"); ok = False
            n_wide += 1
    if len(old_t) != n_same + n_wide:
        print(" ✖ 텐서 수가 다릅니다"); ok = False
    print(f" 그대로 {n_same}개 · 늘림 {n_wide}개 (바라는 값 6) · iter {ck.get('iter')}")
    ok = ok and n_wide == 6 and ck.get("iter") == old_ck.get("iter")

    # ── 셈이 같은가 (행위자 · 비평자 · 무작위 관측 4096개 · 뒤 30칸은 아무 값)
    g = torch.Generator().manual_seed(80)
    for dt, tol in ((torch.float64, 1e-9), (torch.float32, 1e-4)):
        xo, xn = rand_obs(4096, g, dt)
        for sd in ("actor_state_dict", "critic_state_dict"):
            so = {k: v.to(dt) for k, v in old_ck[sd].items()}
            sn = {k: v.to(dt) for k, v in ck[sd].items()}
            e = float((mlp(so, xo) - mlp(sn, xn)).abs().max())
            good = e <= tol
            ok = ok and good
            print(f"   {sd[:-11]:6s} {str(dt)[6:]:8s} 가장 큰 차 {e:.3g}  (≤ {tol:g} {'✔' if good else '✖'})")
    if not ok:
        print(" >>> REAR WARM : ★ 틀림 — 쓰지 않습니다 ★")
        return False

    os.makedirs(a.dst, exist_ok=True)
    torch.save(ck, dst)
    back = torch.load(dst, weights_only=False, map_location="cpu")
    for sd in ("actor_state_dict", "critic_state_dict"):
        if not all(torch.equal(back[sd][k], ck[sd][k]) for k in ck[sd]):
            print(" ✖ 다시 읽은 것이 다릅니다"); return False
    with open(os.path.join(a.dst, "rear_warm.txt"), "w", encoding="utf-8") as f:
        f.write(f"원본 {src}\nsha {sha0}\n새 {dst}\nsha {sha(dst)}\n입력 {OLD_IN} → {NEW_IN} · 뒤 30칸 0 (README 80-1 · 80-2)\n")
    print(f" 새것  {dst}  (sha {sha(dst)} · 행위자 첫 층 {tuple(back['actor_state_dict']['mlp.0.weight'].shape)})")
    print(f" 원본 sha 그대로: {'✔' if sha(src) == sha0 else '✖'}")
    print(" >>> REAR WARM : 같습니다 (만듦)")
    return True


def check(a):
    po = torch.jit.load(a.old, map_location="cpu").eval()
    pn = torch.jit.load(a.new, map_location="cpu").eval()
    g = torch.Generator().manual_seed(81)
    xo, xn = rand_obs(4096, g, torch.float32)
    with torch.inference_mode():
        yo, yn = po(xo), pn(xn)
        e = float((yo - yn).abs().max())
        # 하나씩 (시험대처럼) 도 견줍니다
        e1 = max(float((po(xo[i:i + 1]) - pn(xn[i:i + 1])).abs().max()) for i in range(64))
    ok = e <= 1e-4 and e1 <= 1e-4
    print(f" 꺼낸 정책  옛 {a.old}\n            새 {a.new}")
    print(f"   무작위 관측 4096개 · 가장 큰 차 {e:.3g} · 하나씩 64번 {e1:.3g}  (≤ 1e-4 {'✔' if ok else '✖'})")
    print(" >>> REAR JIT : " + ("같습니다" if ok else "★ 다릅니다 ★"))
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="rear-eye warm start (README 80)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make"); m.add_argument("--src", required=True); m.add_argument("--dst", required=True)
    c = sub.add_parser("check"); c.add_argument("--old", required=True); c.add_argument("--new", required=True)
    a = ap.parse_args()
    sys.exit(0 if (make(a) if a.cmd == "make" else check(a)) else 1)
