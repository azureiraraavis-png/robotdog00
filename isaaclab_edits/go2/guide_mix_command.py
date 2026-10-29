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
#
#  78-3: 개마다 어느 몫인지 (mix_mode: 0 앞 · 1 뒤로 · 2 거의 0) 를 들고 있고,
#      mix_sharp = (뒤로 또는 거의 0) 이면서 서 있는 개가 아님 → track_lin_vel_xy_exp_mix 가 이 개들만 σ² 를 작게 씁니다.
#      학습 로그에 뒤로 개만 따로 적습니다 (보기만 · 학습은 안 바꿈):
#        Metrics/base_velocity/back_steps   뒤로 개의 걸음 수 (에피소드 합의 평균)
#        Metrics/base_velocity/back_vx_sum  그동안 실제 앞뒤 속도의 합
#        Metrics/base_velocity/back_cmd_sum 그동안 명령한 앞뒤 속도의 합
#        → back_vx_sum ÷ back_cmd_sum = 명령의 몇 배를 갔나 (1 = 명령대로 · 0 = 서 있음)
import torch

from isaaclab.envs.mdp.commands.velocity_command import UniformVelocityCommand as _UniformVelocityCommand
from isaaclab.managers import SceneEntityCfg

MIX_P_BACK, MIX_BACK = 0.15, (-0.30, -0.10)
MIX_P_SLOW, MIX_SLOW = 0.15, (-0.05, 0.05)


class GuideMixVelocityCommand(_UniformVelocityCommand):
    """UniformVelocityCommand 와 같되, 앞 명령의 일부를 뒤로 · 거의 0 으로 바꿈 (README 77-1)."""

    def __init__(self, cfg, env):
        super().__init__(cfg, env)
        self.mix_mode = torch.zeros(self.num_envs, dtype=torch.long, device=self.device)      # 0 앞 · 1 뒤로 · 2 거의 0 (78-3)
        self.mix_sharp = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)     # 날카로운 상을 쓸 개 (78-3)
        self.mix_ever = torch.zeros(self.num_envs, dtype=torch.bool, device=self.device)      # 이 판에 한 번이라도 뒤로 · 거의 0 을 뽑았나 (82-4)
        for _k in ("back_steps", "back_vx_sum", "back_cmd_sum"):                               # 보기만 (78-3)
            self.metrics[_k] = torch.zeros(self.num_envs, device=self.device)
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
        mode = torch.zeros(n, dtype=torch.long, device=self.device)
        mode = torch.where(back, torch.ones_like(mode), mode)
        mode = torch.where(slow, torch.full_like(mode, 2), mode)
        self.mix_mode[ids] = mode
        self.mix_sharp[ids] = (mode > 0) & ~self.is_standing_env[ids]
        self.mix_ever[ids] |= mode > 0                                   # 82-4: 판 끝의 커리큘럼이 읽고 지움

    def _update_metrics(self):
        super()._update_metrics()
        b = ((self.mix_mode == 1) & ~self.is_standing_env).float()
        self.metrics["back_steps"] += b
        self.metrics["back_vx_sum"] += b * self.robot.data.root_lin_vel_b.torch[:, 0]
        self.metrics["back_cmd_sum"] += b * self.vel_command_b[:, 0]


_SHARP_SAID = [False]


def track_lin_vel_xy_exp_mix(env, std: float, std_mix: float, command_name: str,
                             asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """isaaclab.envs.mdp.track_lin_vel_xy_exp 와 같은 식 — 다만 mix_sharp 인 개 (뒤로 · 거의 0 · 서 있기 아님) 는 std_mix 를 씀 (78-3)."""
    asset = env.scene[asset_cfg.name]
    cmd = env.command_manager.get_command(command_name)
    err = torch.sum(torch.square(cmd[:, :2] - asset.data.root_lin_vel_b.torch[:, :2]), dim=1)
    term = env.command_manager.get_term(command_name)
    sharp = getattr(term, "mix_sharp", None)
    if not _SHARP_SAID[0]:
        _SHARP_SAID[0] = True
        print(f"[상 날카롭게] track_lin_vel_xy_exp_mix · 섞인 개 σ² {std_mix ** 2:.4f} · 나머지 σ² {std ** 2:.4f} · "
              f"명령 클래스 {type(term).__name__} · mix_sharp {'있음' if sharp is not None else '없음 (✖ 모두 기본 σ)'}", flush=True)
    if sharp is None:
        return torch.exp(-err / std ** 2)
    s2 = torch.where(sharp, torch.full_like(err, std_mix ** 2), torch.full_like(err, std ** 2))
    return torch.exp(-err / s2)


# ─────────────────────────────────────────────────────────────
#  82-4: 강등 멈추기 — 이 판에 뒤로 · 거의 0 명령을 한 번이라도 뽑은 개는 줄 (난이도) 을 안 바꿈 (승급도 강등도 없음).
#  왜 (82-3): 뒤로 개는 계단 끝에서 서면 중심에서 1~1.5 m — 강등선 (|명령| × 20초 × 0.5 = 약 2 m) 보다 짧아 늘 강등되고,
#      높은 계단에서 뒤로를 연습할 일이 준다. 나머지 개는 terrain_levels_vel (velocity/mdp/curriculums.py) 그대로.
#  판 끝 (_reset_idx) 에서 커리큘럼은 명령을 다시 뽑기 **전에** 불리므로, 끝난 판의 mix_ever 를 읽을 수 있다.
#  읽은 뒤 지우고, 곧 다시 뽑히는 명령이 새 판의 값을 채운다.
# ─────────────────────────────────────────────────────────────
_HOLD_SAID = [False]


def terrain_levels_vel_hold_mix(env, env_ids, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    """terrain_levels_vel 과 같되 mix_ever 인 개는 move_up · move_down 을 모두 끔 (82-4)."""
    asset = env.scene[asset_cfg.name]
    terrain = env.scene.terrain
    command = env.command_manager.get_command("base_velocity")
    distance = torch.linalg.norm(asset.data.root_pos_w.torch[env_ids, :2] - env.scene.env_origins[env_ids, :2], dim=1)
    move_up = distance > terrain.cfg.terrain_generator.size[0] / 2
    move_down = distance < torch.linalg.norm(command[env_ids, :2], dim=1) * env.max_episode_length_s * 0.5
    move_down *= ~move_up
    term = env.command_manager.get_term("base_velocity")
    ever = getattr(term, "mix_ever", None)
    hold = None
    if ever is not None:
        hold = ever[env_ids]
        move_up = move_up & ~hold
        move_down = move_down & ~hold
        ever[env_ids] = False
    if not _HOLD_SAID[0]:
        _HOLD_SAID[0] = True
        _n = int(move_up.numel())
        print(f"[강등 멈추기] terrain_levels_vel_hold_mix · 명령 클래스 {type(term).__name__} · mix_ever "
              + (f"있음 · 이번에 끝난 개 {_n} 중 줄을 안 바꾼 개 {int(hold.sum())}" if ever is not None else "없음 (✖ 모두 원래대로)"), flush=True)
    terrain.update_env_origins(env_ids, move_up, move_down)
    return torch.mean(terrain.terrain_levels.float())
