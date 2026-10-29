# -*- coding: utf-8 -*-
"""학습 지형에서 뒤로 걷기를 잽니다 — README 82-1.

 묻는 것은 하나입니다:
   "이 정책은 **학습 때 본 계단** (Isaac Lab 의 피라미드 계단) 에서는 뒤로 오르내리는가?"

 rig (sim_go2.py) 의 계단은 시설을 본뜬 꺾인 계단 (벽 · 좁은 폭 · 참) 이고, 학습 지형은 사방이 트인
 피라미드 계단입니다. 80 의 2999 는 rig 의 계단 위에서 뒤로 0/20 이었습니다 (80-7). 그것이
   ① 학습 지형에서도 못 하는 것인지 (→ 학습이 원인)
   ② 학습 지형에서는 하는데 rig 에서만 못 하는 것인지 (→ 계단 모양의 차가 원인)
 를 가릅니다.

 하는 일:
   · 학습 설정 그대로 (돌리는 쪽에서 디딤 섞기 · 내려가기 몫 · 필요하면 뒤 눈 스위치를 켜 둠) 환경을 띄우고
   · 개마다 지형 종류 (피라미드 계단 6종 + 울퉁불퉁) · 난이도 줄 (2 · 6 · 9) · 앞 명령 (−0.2 · +0.2) 을 정해 그 칸 한가운데에 놓고
   · 명령을 고정한 채 (돌기 0 · 옆 0 · 다시 뽑기 없음 · 밀기 없음 · 잡음 없음) 20초 걷게 하고
   · 개마다 잽니다: 처음 바라본 쪽으로 명령 방향으로 간 거리 · 높이 바뀜 · 넘어졌는가 (끝남 = 몸 닿음 등).
   피라미드 계단은 가운데 (폭 3 m 평판) 에서 바깥으로 가면 내려가고 (pyramid_stairs) · 올라갑니다 (_inv).
   개가 놓일 때 방향은 무작위 (reset_base 그대로) — 어느 쪽으로 가든 1.0~2.0 m 뒤에 계단이 시작됩니다.

 돌리는 법 (Isaac Lab 폴더에서 · 정책은 꺼낸 jit 파일):
   .\\isaaclab.bat -p D:\\workspace_raraavis\\robotdog00\\back_probe.py --headless --policy <policy_XXXX.pt> --label <이름> --out <tsv>

 ※ 로봇(실기체)과는 아무 상관 없습니다. 시뮬레이터 안에서만 돕니다.
"""
import argparse
import contextlib
import math
import os
import sys

import gymnasium as gym
import numpy as np
import torch

import isaaclab_tasks  # noqa: F401

with contextlib.suppress(ImportError):
    import isaaclab_tasks_experimental  # noqa: F401
from isaaclab_tasks.utils import (
    add_launcher_args,
    launch_simulation,
    resolve_task_config,
    setup_preset_cli,
)

parser = argparse.ArgumentParser(description="backward-walk probe on training terrain")
parser.add_argument("--task", type=str, default="Isaac-Velocity-Rough-Unitree-Go2-GuideSee-v0")
parser.add_argument("--policy", type=str, required=True, help="꺼낸 정책 (jit)")
parser.add_argument("--label", type=str, required=True, help="tsv 에 적을 이름")
parser.add_argument("--out", type=str, default="", help="개마다 한 줄씩 덧붙일 tsv (기본 없음)")
parser.add_argument("--rows", type=str, default="2,6,9", help="난이도 줄 (0~9 · 계단 높이 0.13 + 0.10 × (줄 + 0~1) / 10)")
parser.add_argument("--vx", type=str, default="-0.2,0.2", help="앞 명령 (m/s)")
parser.add_argument("--reps", type=int, default=8, help="칸마다 개 수")
parser.add_argument("--seconds", type=float, default=20.0)
add_launcher_args(parser)
args_cli, hydra_args = setup_preset_cli(parser)
sys.argv = [sys.argv[0]] + hydra_args

UP_DZ = 0.35        # "계단 두 칸 넘게" — 높이가 이만큼 넘게 바뀜 (한 칸 0.13~0.23 m)


def tt(x):
    """ProxyArray · warp · torch 무엇이 오든 torch 로."""
    if hasattr(x, "torch"):
        return x.torch
    if isinstance(x, torch.Tensor):
        return x
    import warp as wp
    return wp.to_torch(x)


def main():
    rows = [int(v) for v in args_cli.rows.split(",") if v.strip()]
    vxs = [float(v) for v in args_cli.vx.split(",") if v.strip()]
    env_cfg, _ = resolve_task_config(args_cli.task, "")
    with launch_simulation(env_cfg, args_cli):
        tg = env_cfg.scene.terrain.terrain_generator
        names = list(tg.sub_terrains.keys())
        kinds = [n for n in names if n.startswith("pyramid_stairs")] + [n for n in names if n == "random_rough"]
        cells = [(k, r, v) for k in kinds for r in rows for v in vxs]
        n_env = len(cells) * args_cli.reps
        env_cfg.scene.num_envs = n_env
        if args_cli.device is not None:
            env_cfg.sim.device = args_cli.device
        env_cfg.observations.policy.enable_corruption = False
        for _ev in ("push_robot", "base_external_force_torque"):
            if hasattr(env_cfg.events, _ev):
                setattr(env_cfg.events, _ev, None)
        if hasattr(env_cfg.curriculum, "terrain_levels"):
            env_cfg.curriculum.terrain_levels = None
        c = env_cfg.commands.base_velocity
        c.resampling_time_range = (1.0e6, 1.0e6)
        c.heading_command = False
        c.rel_standing_envs = 0.0
        c.rel_heading_envs = 0.0
        env_cfg.episode_length_s = args_cli.seconds + 10.0

        env = gym.make(args_cli.task, cfg=env_cfg)
        u = env.unwrapped
        dev = u.device
        terrain = u.scene.terrain
        # 열마다 지형 종류 — terrain_generator.py (_generate_curriculum_terrains) 와 같은 식
        tgu = terrain.cfg.terrain_generator
        names_u = list(tgu.sub_terrains.keys())
        pr = np.array([s.proportion for s in tgu.sub_terrains.values()], dtype=float)
        pr /= pr.sum()
        col_kind = [names_u[int(np.min(np.where(i / tgu.num_cols + 0.001 < np.cumsum(pr))[0]))] for i in range(tgu.num_cols)]
        cols_of = {n: [i for i, k in enumerate(col_kind) if k == n] for n in names_u}
        lv, ty, vx_e, cell_e = [], [], [], []
        for ci, (k, r, v) in enumerate(cells):
            cs = cols_of.get(k, [])
            if not cs:
                print(f"[탐침] ✖ {k} 열이 없습니다 — 설정 (디딤 섞기) 이 학습 때와 다릅니다")
                env.close()
                return
            for j in range(args_cli.reps):
                lv.append(r)
                ty.append(cs[j % len(cs)])
                vx_e.append(v)
                cell_e.append(ci)
        terrain.terrain_levels = torch.tensor(lv, device=dev, dtype=torch.long)
        terrain.terrain_types = torch.tensor(ty, device=dev, dtype=torch.long)
        terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
        VX = torch.tensor(vx_e, device=dev, dtype=torch.float)
        print(f"[탐침] {args_cli.label} · 개 {n_env} · 종류 {len(kinds)} ({', '.join(kinds)}) · 줄 {rows} · 명령 {vxs} · 칸마다 {args_cli.reps} · {args_cli.seconds:.0f}초")

        env.reset()
        cmd = u.command_manager.get_term("base_velocity")
        robot = u.scene["robot"]

        def setcmd():
            cmd.vel_command_b[:, 0] = VX
            cmd.vel_command_b[:, 1:] = 0.0

        setcmd()
        obs = u.observation_manager.compute()
        pol = torch.jit.load(args_cli.policy, map_location=dev)
        pol.eval()
        p0 = tt(robot.data.root_pos_w).clone()
        h0 = tt(robot.data.heading_w).clone()
        d0 = torch.stack([torch.cos(h0), torch.sin(h0)], dim=1)
        o0 = terrain.env_origins.clone()
        alive = torch.ones(n_env, dtype=torch.bool, device=dev)
        fell_t = torch.full((n_env,), -1.0, device=dev)
        last = p0.clone()
        dz_max = torch.zeros(n_env, device=dev)     # 높이가 가장 크게 바뀐 양 (부호 있음 · 절댓값이 가장 큰 쪽)
        n_step = int(round(args_cli.seconds / u.step_dt))
        with torch.inference_mode():
            for k in range(n_step):
                ob = obs["policy"] if isinstance(obs, dict) else obs
                act = pol(ob)
                setcmd()
                obs, _rew, term, trunc, _info = env.step(act)
                setcmd()
                p = tt(robot.data.root_pos_w)
                done = (term | trunc).reshape(-1).to(torch.bool)
                newly = alive & done
                if bool(newly.any()):
                    fell_t[newly] = (k + 1) * u.step_dt
                    alive &= ~done
                upd = alive
                last[upd] = p[upd]
                dz = p[:, 2] - p0[:, 2]
                bigger = upd & (dz.abs() > dz_max.abs())
                dz_max[bigger] = dz[bigger]
        disp = (last[:, :2] - p0[:, :2])
        along = (disp * d0).sum(dim=1) * torch.sign(VX)            # 명령 쪽으로 간 거리 (+ 면 시킨 쪽)
        side = (disp * torch.stack([-d0[:, 1], d0[:, 0]], dim=1)).sum(dim=1)
        from_c = torch.linalg.norm(last[:, :2] - o0[:, :2], dim=1)
        fell = fell_t >= 0.0
        rows_out = []
        for i in range(n_env):
            k, r, v = cells[cell_e[i]]
            rows_out.append((args_cli.label, k, r, v, float(along[i]), float(side[i]), float(dz_max[i]),
                             float(from_c[i]), int(bool(fell[i])), float(fell_t[i])))
        if args_cli.out:
            new = not os.path.exists(args_cli.out)
            with open(args_cli.out, "a", encoding="utf-8") as f:
                if new:
                    f.write("label\tkind\trow\tvx\talong\tside\tdz\tfrom_center\tfell\tfell_t\n")
                for rr in rows_out:
                    f.write("\t".join(f"{x:.3f}" if isinstance(x, float) else str(x) for x in rr) + "\n")
        print()
        print("=" * 78)
        print(f" [탐침] {args_cli.label} — 칸마다 (개 {args_cli.reps})")
        print("   종류 · 줄 · 명령 : 두 칸 넘게 (|높이| ≥ 0.35 m · 안 넘어짐) · 넘어짐 · 간 거리 가운데 · 높이 바뀜 가운데")
        for ci, (k, r, v) in enumerate(cells):
            sel = [rr for i, rr in enumerate(rows_out) if cell_e[i] == ci]
            ok = sum(1 for rr in sel if abs(rr[6]) >= UP_DZ and not rr[8])
            nf = sum(rr[8] for rr in sel)
            al = sorted(rr[4] for rr in sel)[len(sel) // 2]
            dzm = sorted(rr[6] for rr in sel)[len(sel) // 2]
            print(f"   {k:24s} · {r} · {v:+.1f} : {ok}/{len(sel)} · 넘어짐 {nf} · 간 거리 {al:+.2f} m · 높이 {dzm:+.2f} m")
        print(" >>> PROBE DONE : " + args_cli.label)
        print("=" * 78)
        env.close()


if __name__ == "__main__":
    main()
