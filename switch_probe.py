# -*- coding: utf-8 -*-
"""꺾인 계단 (학습 지형 switch_up · switch_down) 을 앞으로 끝까지 가는가를 잽니다 — README 83-7.

 왜 (83-7): 83c 의 관문 switch_prog (학습 중 · 판이 끝난 꺾인 계단 위 개의 평균) 는
   뒤로 · 거의 0 · 서 있기 명령을 받은 개 · 느린 앞 명령 (0.2~0.5) · 10초마다 다시 뽑기가 모두 섞인 평균이라
   명령을 완벽하게 따르는 개도 평균 3.89 m 밖에 안 됩니다 (관문 5.0 m 는 넘을 수 없는 선이었음).
   그래서 이 탐침은 섞기를 빼고 **앞으로만** 줘서 "꺾인 계단을 끝까지 가는가" 를 줄 (난이도) 마다 잽니다.

 하는 일 (back_probe.py 와 같은 틀):
   · 학습 설정 그대로 (돌리는 쪽에서 83c 의 스위치를 켜 둠 · SWITCH_STAIRS 포함) 환경을 띄우고
   · 개마다 지형 종류 (switch_up · switch_down) · 줄 (0 · 3 · 6 · 9) 을 정해 그 조각의 놓는 자리 (바닥참 가운데) 에 놓고
   · 앞 명령 0.31 (rig 의 기본 빠르기) 고정 · 방향과 옆 명령은 학습 때의 길잡이 그대로 (guide_mix_command.py 의 _update_command)
     · 다시 뽑기 없음 · 밀기 없음 · 잡음 없음 · 45초
   · 개마다 잽니다: 길 따라 간 거리 s (switch_path · 학습 때의 자와 같은 셈) · 가운데 참에 오른 때 (s ≥ 3.35) ·
     건너편 바닥참에 닿은 때 (s ≥ 8.10) · 높이 바뀜 · 넘어졌는가 · 길에서 벗어난 양 (|e_left|) 의 평균.
   끝에 닿은 개는 그 뒤로 앞 명령 0 (벽에 계속 밀지 않게) · 그 뒤의 넘어짐은 세지 않습니다.

 돌리는 법 (Isaac Lab 폴더에서 · 정책은 꺼낸 jit 파일):
   .\\isaaclab.bat -p D:\\workspace_raraavis\\robotdog00\\switch_probe.py --headless --policy <policy_XXXX.pt> --label <이름> --out <tsv>

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

parser = argparse.ArgumentParser(description="switchback-stairs forward probe on training terrain")
parser.add_argument("--task", type=str, default="Isaac-Velocity-Rough-Unitree-Go2-GuideSee-v0")
parser.add_argument("--policy", type=str, required=True, help="꺼낸 정책 (jit)")
parser.add_argument("--label", type=str, required=True, help="tsv 에 적을 이름")
parser.add_argument("--out", type=str, default="", help="개마다 한 줄씩 덧붙일 tsv (기본 없음)")
parser.add_argument("--rows", type=str, default="0,3,6,9", help="난이도 줄 (0~9 · 단 높이 0.13 + 0.10 × (줄 + 0~1) / 10)")
parser.add_argument("--vx", type=float, default=0.31, help="앞 명령 (m/s) — rig 의 기본 빠르기")
parser.add_argument("--reps", type=int, default=16, help="칸마다 개 수")
parser.add_argument("--seconds", type=float, default=45.0)
add_launcher_args(parser)
args_cli, hydra_args = setup_preset_cli(parser)
sys.argv = [sys.argv[0]] + hydra_args

S_LAND = 3.35       # 가운데 참에 올라섬 (첫 단의 끝 u_land 3.05 + 0.30)
S_GOAL = 8.10       # 건너편 바닥참에 닿음 ((u_mid − 0.30) + 1.65 + (u_mid − 0.65))
GUIDE = "isaaclab_tasks.manager_based.locomotion.velocity.config.go2.guide_mix_command"


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
    env_cfg, _ = resolve_task_config(args_cli.task, "")
    with launch_simulation(env_cfg, args_cli):
        import importlib
        gm = importlib.import_module(GUIDE)
        tg = env_cfg.scene.terrain.terrain_generator
        names = list(tg.sub_terrains.keys())
        kinds = [n for n in names if n.startswith("switch_")]
        if sorted(kinds) != ["switch_down", "switch_up"]:
            print(f"[꺾인 탐침] ✖ 지형 조각에 switch_up · switch_down 이 없습니다 ({kinds}) — SWITCH_STAIRS 가 꺼진 설정")
            return
        cells = [(k, r) for k in ("switch_up", "switch_down") for r in rows]
        n_env = len(cells) * args_cli.reps
        env_cfg.scene.num_envs = n_env
        if args_cli.device is not None:
            env_cfg.sim.device = args_cli.device
        env_cfg.observations.policy.enable_corruption = False
        for _ev in ("push_robot", "base_external_force_torque"):
            if hasattr(env_cfg.events, _ev):
                setattr(env_cfg.events, _ev, None)
        for _ct in ("terrain_levels", "switch_prog"):
            if hasattr(env_cfg.curriculum, _ct):
                setattr(env_cfg.curriculum, _ct, None)
        c = env_cfg.commands.base_velocity
        c.resampling_time_range = (1.0e6, 1.0e6)
        c.heading_command = True
        c.rel_heading_envs = 1.0
        c.ranges.heading = (0.0, 0.0)
        c.rel_standing_envs = 0.0
        if hasattr(env_cfg.events, "reset_base") and env_cfg.events.reset_base is not None:
            pr_ = env_cfg.events.reset_base.params["pose_range"]
            pr_["yaw"] = (0.0, 0.0)
            pr_["x"] = (-0.1, 0.1)          # 바닥참 폭 1.25 m — 학습의 ±0.5 는 벽에 붙여 놓을 수 있어 좁힘
            pr_["y"] = (-0.1, 0.1)
        env_cfg.episode_length_s = args_cli.seconds + 10.0

        env = gym.make(args_cli.task, cfg=env_cfg)
        u = env.unwrapped
        dev = u.device
        terrain = u.scene.terrain
        tgu = terrain.cfg.terrain_generator
        names_u = list(tgu.sub_terrains.keys())
        pr = np.array([s.proportion for s in tgu.sub_terrains.values()], dtype=float)
        pr /= pr.sum()
        col_kind = [names_u[int(np.min(np.where(i / tgu.num_cols + 0.001 < np.cumsum(pr))[0]))] for i in range(tgu.num_cols)]
        cols_of = {n: [i for i, k in enumerate(col_kind) if k == n] for n in names_u}
        lv, ty, cell_e = [], [], []
        for ci, (k, r) in enumerate(cells):
            cs = cols_of.get(k, [])
            if not cs:
                print(f"[꺾인 탐침] ✖ {k} 열이 없습니다")
                env.close()
                return
            for j in range(args_cli.reps):
                lv.append(r)
                ty.append(cs[j % len(cs)])
                cell_e.append(ci)
        terrain.terrain_levels = torch.tensor(lv, device=dev, dtype=torch.long)
        terrain.terrain_types = torch.tensor(ty, device=dev, dtype=torch.long)
        terrain.env_origins[:] = terrain.terrain_origins[terrain.terrain_levels, terrain.terrain_types]
        cmd = u.command_manager.get_term("base_velocity")
        if hasattr(cmd, "_sw_state"):
            del cmd._sw_state                # 개를 옮겼으니 길잡이의 셈을 새로
        print(f"[꺾인 탐침] {args_cli.label} · 개 {n_env} · 종류 switch_up · switch_down · 줄 {rows} · 앞 {args_cli.vx:.2f} · "
              f"칸마다 {args_cli.reps} · {args_cli.seconds:.0f}초 · 참 s ≥ {S_LAND} · 끝 s ≥ {S_GOAL}", flush=True)

        env.reset()
        robot = u.scene["robot"]
        VX = torch.full((n_env,), float(args_cli.vx), device=dev)

        def setcmd():                        # 앞 명령만 — 방향 · 옆은 길잡이가 셈함
            cmd.vel_command_b[:, 0] = VX

        setcmd()
        obs = u.observation_manager.compute()
        pol = torch.jit.load(args_cli.policy, map_location=dev)
        pol.eval()
        st = gm._switch_state(u)
        if st is None or int(st["ids"].numel()) != n_env:
            print(f"[꺾인 탐침] ✖ 길잡이가 본 꺾인 계단 위의 개 {0 if st is None else int(st['ids'].numel())} / {n_env} — 멈춥니다")
            env.close()
            return
        order = torch.empty(n_env, dtype=torch.long, device=dev)
        order[st["ids"]] = torch.arange(n_env, device=dev)
        p0 = tt(robot.data.root_pos_w).clone()
        alive = torch.ones(n_env, dtype=torch.bool, device=dev)
        goal = torch.zeros(n_env, dtype=torch.bool, device=dev)
        fell_t = torch.full((n_env,), -1.0, device=dev)
        t_land = torch.full((n_env,), -1.0, device=dev)
        t_goal = torch.full((n_env,), -1.0, device=dev)
        s_last = torch.zeros(n_env, device=dev)
        s_max = torch.full((n_env,), -9.0, device=dev)
        z_last = p0[:, 2].clone()
        e_sum = torch.zeros(n_env, device=dev)
        e_n = torch.zeros(n_env, device=dev)
        n_step = int(round(args_cli.seconds / u.step_dt))
        with torch.inference_mode():
            for k in range(n_step):
                ob = obs["policy"] if isinstance(obs, dict) else obs
                act = pol(ob)
                setcmd()
                obs, _rew, term, trunc, _info = env.step(act)
                tnow = (k + 1) * u.step_dt
                done = (term | trunc).reshape(-1).to(torch.bool)
                newly = alive & ~goal & done
                if bool(newly.any()):
                    fell_t[newly] = tnow
                alive &= ~done
                p = tt(robot.data.root_pos_w)
                ids = st["ids"]
                _h, e_left, s = gm.switch_path(p[ids, :2], u.scene.env_origins[ids, :2], st["dy"], st["u_mid"])
                s = s[order]
                e_left = e_left[order]
                live = alive & ~goal
                s_last[live] = s[live]
                z_last[live] = p[live, 2]
                s_max = torch.where(live, torch.maximum(s_max, s), s_max)
                e_sum[live] += e_left[live].abs()
                e_n[live] += 1.0
                hit_land = live & (t_land < 0) & (s >= S_LAND)
                t_land[hit_land] = tnow
                hit_goal = live & (s >= S_GOAL)
                t_goal[hit_goal] = tnow
                goal |= hit_goal
                VX = torch.where(goal, torch.zeros_like(VX), VX)     # 끝에 닿으면 섬
                setcmd()
        fell = fell_t >= 0.0
        dz = z_last - p0[:, 2]
        e_avg = e_sum / torch.clamp(e_n, min=1.0)
        rows_out = []
        for i in range(n_env):
            kk, r = cells[cell_e[i]]
            rows_out.append((args_cli.label, kk, r, float(args_cli.vx), float(s_last[i]), float(s_max[i]), float(t_land[i]),
                             float(t_goal[i]), float(dz[i]), int(bool(fell[i])), float(fell_t[i]), float(e_avg[i])))
        if args_cli.out:
            new = not os.path.exists(args_cli.out)
            with open(args_cli.out, "a", encoding="utf-8") as f:
                if new:
                    f.write("label\tkind\trow\tvx\ts_end\ts_max\tt_land\tt_goal\tdz\tfell\tfell_t\te_avg\n")
                for rr in rows_out:
                    f.write("\t".join(f"{x:.3f}" if isinstance(x, float) else str(x) for x in rr) + "\n")
        print()
        print("=" * 78)
        print(f" [꺾인 탐침] {args_cli.label} — 칸마다 (개 {args_cli.reps})")
        print("   종류 · 줄 (단 높이) : 끝까지 · 참까지 · 넘어짐 · s 가운데 · 끝까지 걸린 초 가운데 · 길 벗어남 평균 가운데")
        for ci, (kk, r) in enumerate(cells):
            sel = [rr for i, rr in enumerate(rows_out) if cell_e[i] == ci]
            n = len(sel)
            ng = sum(1 for rr in sel if rr[7] >= 0)
            nl = sum(1 for rr in sel if rr[6] >= 0)
            nf = sum(rr[9] for rr in sel)
            sm = sorted(rr[4] for rr in sel)[n // 2]
            tg_ = sorted(rr[7] for rr in sel if rr[7] >= 0)
            tgm = f"{tg_[len(tg_) // 2]:.0f}초" if tg_ else "-"
            em = sorted(rr[11] for rr in sel)[n // 2]
            h0, h1 = 0.13 + 0.10 * r / 10, 0.13 + 0.10 * (r + 1) / 10
            print(f"   {kk:11s} · {r} ({h0:.2f}~{h1:.2f} m) : 끝까지 {ng}/{n} · 참까지 {nl}/{n} · 넘어짐 {nf} · s {sm:.2f} m · {tgm} · 벗어남 {em:.2f} m")
        print(" >>> SWITCH PROBE DONE : " + args_cli.label)
        print("=" * 78)
        env.close()


if __name__ == "__main__":
    main()
