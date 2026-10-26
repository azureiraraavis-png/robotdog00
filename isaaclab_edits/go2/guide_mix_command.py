# guide_mix_command.py — robotdog00 · 명령 섞기 (2026-10-26, README 77-1 · 77-2)
#
#  flat_env_cfg.py 의 MOVE_MIX = True 일 때 base_velocity 명령으로 씁니다 (cfg 에는 "모듈:클래스" 글자로만 적음).
#  이 파일은 Isaac Lab 이 명령을 만들 때 (시뮬레이터가 뜬 뒤) 불러옵니다 — cfg 를 읽을 때 불러오면
#  pxr 가 먼저 올라와 SimulationApp 이 못 뜹니다 (77-2).
#
#  기본 명령 (UniformVelocityCommand) 을 그대로 뽑은 뒤, 개마다 한 번 더 제비를 뽑아
#      MIX_P_BACK (15 %) 은 앞 명령을 뒤로 (−0.30 ~ −0.10 m/s),
#      MIX_P_SLOW (15 %) 은 앞 명령을 거의 0 (−0.05 ~ +0.05 m/s) 으로 바꿉니다 — 옆 · 돌기는 그대로.
#      나머지 70 % 는 그대로 (앞 0.2~0.5). 서 있으라는 개는 그 위에서 0 이 됩니다 (_update_command).
import torch

from isaaclab.envs.mdp.commands.velocity_command import UniformVelocityCommand as _UniformVelocityCommand

MIX_P_BACK, MIX_BACK = 0.15, (-0.30, -0.10)
MIX_P_SLOW, MIX_SLOW = 0.15, (-0.05, 0.05)


class GuideMixVelocityCommand(_UniformVelocityCommand):
    """UniformVelocityCommand 와 같되, 앞 명령의 일부를 뒤로 · 거의 0 으로 바꿈 (README 77-1)."""

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        print(f"[명령 섞기] GuideMixVelocityCommand · 뒤로 {MIX_P_BACK:.2f} ({MIX_BACK[0]:+.2f}~{MIX_BACK[1]:+.2f})"
              f" · 거의 0 {MIX_P_SLOW:.2f} ({MIX_SLOW[0]:+.2f}~{MIX_SLOW[1]:+.2f}) · 나머지 앞 {cfg.ranges.lin_vel_x}"
              f" · 옆 {cfg.ranges.lin_vel_y} · 서 있기 {cfg.rel_standing_envs}", flush=True)

    def _resample_command(self, env_ids):
        super()._resample_command(env_ids)
        if isinstance(env_ids, slice):
            ids = torch.arange(self.num_envs, device=self.device)[env_ids]
        else:
            ids = torch.as_tensor(env_ids, device=self.device, dtype=torch.long).flatten()
        n = ids.numel()
        if n == 0:
            return
        u = torch.rand(n, device=self.device)
        back = u < MIX_P_BACK
        slow = (u >= MIX_P_BACK) & (u < MIX_P_BACK + MIX_P_SLOW)
        vx = self.vel_command_b[ids, 0].clone()
        vx = torch.where(back, torch.empty(n, device=self.device).uniform_(*MIX_BACK), vx)
        vx = torch.where(slow, torch.empty(n, device=self.device).uniform_(*MIX_SLOW), vx)
        self.vel_command_b[ids, 0] = vx
