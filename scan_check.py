# -*- coding: utf-8 -*-
"""눈(높이 스캔)의 시험대를 시험합니다 — README 48-2.

 묻는 것은 하나입니다:
   "sim_go2.py 가 셈해서 주는 스캔이, 학습 환경이 정책에 주는 스캔과 같은가?"

 sim_go2.py 의 see_scan() 은 원본을 읽고 짠 것입니다 (격자 · 순서 · yaw · 값의 식).
 읽은 것이 맞는지를 **학습 환경에서 직접 재서** 확인합니다. 광선이 실제로 닿은
 자리와 정책이 실제로 받은 값을, 같은 식으로 셈한 것과 견줍니다.

   ① 스캐너 자리 = 몸통 자리인가               (pos_w 가 20 m 위가 아닌가)
   ② 광선이 닿은 (x, y) = 몸통 + yaw 로 돌린 격자인가   (격자 · 순서 · 앞으로 +0.3 · yaw)
   ③ 정책이 받은 값 = 몸통 z − 닿은 z − 0.5 를 ±1 로 자른 것인가   (식 · 자리 · 칸 수)

 돌리는 법 (Isaac Lab 폴더에서):
   .\\isaaclab.bat -p D:\\workspace_raraavis\\robotdog00\\scan_check.py

 ※ 로봇(실기체)과는 아무 상관 없습니다. 시뮬레이터 안에서만 돕니다.
"""
import argparse
import contextlib
import math
import sys

import gymnasium as gym
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

parser = argparse.ArgumentParser(description="height-scan rig check")
parser.add_argument("--task", type=str,
                    default="Isaac-Velocity-Rough-Unitree-Go2-GuideSee-v0")
parser.add_argument("--num_envs", type=int, default=8)
parser.add_argument("--settle", type=int, default=40,
                    help="재기 전에 걷게 둘 걸음 수 (0.02초씩)")
add_launcher_args(parser)
args_cli, hydra_args = setup_preset_cli(parser)
sys.argv = [sys.argv[0]] + hydra_args

# ── sim_go2.py 와 **글자 그대로 같아야 하는** 값들 ──
SEE_NX, SEE_NY = 13, 5
SEE_X0, SEE_Y0, SEE_STEP, SEE_FWD = -0.6, -0.2, 0.1, 0.3
SEE_N = SEE_NX * SEE_NY


def tt(x):
    """ProxyArray · warp · torch 무엇이 오든 torch 로."""
    if hasattr(x, "torch"):
        return x.torch
    if isinstance(x, torch.Tensor):
        return x
    import warp as wp
    return wp.to_torch(x)


def main():
    env_cfg, _ = resolve_task_config(args_cli.task, "")
    with launch_simulation(env_cfg, args_cli):
        env_cfg.scene.num_envs = args_cli.num_envs
        if args_cli.device is not None:
            env_cfg.sim.device = args_cli.device
        env_cfg.observations.policy.enable_corruption = False   # 잡음 없이 잽니다
        env = gym.make(args_cli.task, cfg=env_cfg)
        u = env.unwrapped
        env.reset()
        actions = torch.zeros(env.action_space.shape, device=u.device)
        obs = None
        with torch.inference_mode():
            for _ in range(args_cli.settle):
                obs = env.step(actions)[0]
        ob = obs["policy"] if isinstance(obs, dict) else obs

        sensor = u.scene.sensors["see_scanner"]
        robot = u.scene["robot"]
        pos = tt(sensor.data.pos_w).reshape(-1, 3)
        hits = tt(sensor.data.ray_hits_w).reshape(pos.shape[0], -1, 3)
        root = tt(robot.data.root_pos_w).reshape(-1, 3)
        yaw = tt(robot.data.heading_w).reshape(-1)

        print()
        print("=" * 70)
        print(" 눈의 시험대 시험 — 학습 환경이 주는 것 vs 같은 식으로 셈한 것")
        print("=" * 70)
        n_obs, n_rays = ob.shape[1], hits.shape[1]
        print(f" 관측 칸 수   {n_obs}   (바라는 값 {48 + SEE_N})")
        print(f" 광선 수      {n_rays}   (바라는 값 {SEE_N})")
        ok = (n_obs == 48 + SEE_N) and (n_rays == SEE_N)

        # ① 스캐너 자리 = 몸통 자리
        e1 = float((pos - root).abs().max())
        print(f" ① 스캐너 자리 − 몸통 자리        가장 큰 차 {e1:.4f} m")
        ok = ok and e1 < 1e-3

        if n_rays == SEE_N:
            # ② 닿은 (x, y) = 몸통 + yaw 로 돌린 격자   (y 바깥 · x 안쪽)
            lx = torch.tensor([SEE_X0 + SEE_STEP * i + SEE_FWD for i in range(SEE_NX)],
                              device=pos.device).repeat(SEE_NY)
            ly = torch.tensor([SEE_Y0 + SEE_STEP * j for j in range(SEE_NY)],
                              device=pos.device).repeat_interleave(SEE_NX)
            c, s = torch.cos(yaw).unsqueeze(1), torch.sin(yaw).unsqueeze(1)
            ex = pos[:, 0:1] + c * lx - s * ly
            ey = pos[:, 1:2] + s * lx + c * ly
            good = torch.isfinite(hits).all(dim=-1)
            e2 = float(torch.maximum((hits[..., 0] - ex).abs(),
                                     (hits[..., 1] - ey).abs())[good].max())
            print(f" ② 닿은 (x,y) − 셈한 (x,y)        가장 큰 차 {e2:.4f} m"
                  f"   (빗나간 광선 {int((~good).sum())}개)")
            ok = ok and e2 < 2e-3

            # ③ 정책이 받은 값 = 몸통 z − 닿은 z − 0.5, ±1 로 자름  (관측의 맨 끝 65칸)
            want = (pos[:, 2:3] - hits[..., 2] - 0.5).clamp(-1.0, 1.0)
            got = ob[:, -SEE_N:]
            e3 = float((got - want)[good].abs().max())
            print(f" ③ 받은 값 − 셈한 값              가장 큰 차 {e3:.4f}")
            ok = ok and e3 < 2e-3

            i = 0
            print()
            print(f" 본보기 (0번 개) — 몸통 ({float(pos[i,0]):+.2f}, {float(pos[i,1]):+.2f}, "
                  f"{float(pos[i,2]):.3f}) · yaw {math.degrees(float(yaw[i])):+.1f}도")
            print("   가운데 줄 (뒤 −0.3 → 앞 +0.9):")
            mid = got[i, (SEE_NY // 2) * SEE_NX:(SEE_NY // 2 + 1) * SEE_NX]
            print("   " + " ".join(f"{float(v):+.2f}" for v in mid))
            print(f"   값의 범위 (모든 개)  {float(got.min()):+.3f} ~ {float(got.max()):+.3f}"
                  f"   (평지에서 키 0.30 이면 −0.20)")

        print()
        print(" >>> SCAN CHECK : " + ("같습니다" if ok else "★ 다릅니다 — sim_go2.py 의 see_scan 을 믿지 마십시오 ★"))
        print("=" * 70)
        env.close()


if __name__ == "__main__":
    main()
