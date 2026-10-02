# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from isaaclab_newton.physics import MJWarpSolverCfg, NewtonCfg
from isaaclab_physx.physics import PhysxCfg

from isaaclab.managers import CurriculumTermCfg as CurrTerm
from isaaclab.sim import SimulationCfg
from isaaclab.utils.configclass import configclass

import isaaclab_tasks.manager_based.locomotion.velocity.mdp as vel_mdp

from isaaclab_tasks.utils import PresetCfg

from .rough_env_cfg import UnitreeGo2RoughEnvCfg


@configclass
class PhysicsCfg(PresetCfg):
    default = PhysxCfg(gpu_max_rigid_patch_count=10 * 2**15)
    newton_mjwarp = NewtonCfg(
        solver_cfg=MJWarpSolverCfg(
            njmax=65,
            nconmax=35,
            cone="pyramidal",
            impratio=1,
            integrator="implicitfast",
        ),
        num_substeps=1,
        debug_mode=False,
    )
    physx = default


@configclass
class UnitreeGo2FlatEnvCfg(UnitreeGo2RoughEnvCfg):
    sim: SimulationCfg = SimulationCfg(physics=PhysicsCfg())

    def __post_init__(self):
        # post init of parent
        super().__post_init__()

        # override rewards
        self.rewards.flat_orientation_l2.weight = -2.5
        self.rewards.feet_air_time.weight = 0.25

        # change terrain to flat
        self.scene.terrain.terrain_type = "plane"
        self.scene.terrain.terrain_generator = None
        # no height scan
        self.scene.height_scanner = None
        self.observations.policy.height_scan = None
        # no terrain curriculum
        self.curriculum.terrain_levels = None


class UnitreeGo2FlatEnvCfg_PLAY(UnitreeGo2FlatEnvCfg):
    def __post_init__(self) -> None:
        # post init of parent
        super().__post_init__()

        # make a smaller scene for play
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        # disable randomization for play
        self.observations.policy.enable_corruption = False
        # remove random pushing event
        self.events.base_external_force_torque = None
        self.events.push_robot = None



# ─────────────────────────────────────────────────────────────
#  robotdog00 — 안내견 속도대로 좁힌 환경
#
#  왜: NVIDIA 가 내준 정책은 1 m/s 근처에서 학습됐습니다. 우리가
#      쓰는 0.31 m/s 에서는 보폭만 줄고 걸음 박자는 그대로라,
#      1 m 당 10 cm 씩 옆으로 미끄러집니다 (README 33-6).
#
#  기준선: 원래 과제(Isaac-Velocity-Flat-Unitree-Go2-v0)를 그대로
#      두었으니 언제든 견줄 수 있습니다.
# ─────────────────────────────────────────────────────────────
@configclass
class UnitreeGo2GuideEnvCfg(UnitreeGo2FlatEnvCfg):
    def __post_init__(self):
        super().__post_init__()

        # 앞으로: 안내견이 실제로 내는 속도만
        self.commands.base_velocity.ranges.lin_vel_x = (0.2, 0.5)

        # 옆으로: 안 씁니다. 열어두면 명령의 대부분이 옆걸음이 됩니다
        self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)

        # 서 있기: 2% 는 안내견에게 모자랍니다. 설명하는 동안 서 있어야
        #          하고, 오늘 그 자세에서 무너지는 것을 봤습니다
        self.commands.base_velocity.rel_standing_envs = 0.15


        # 서 있으라고 말해줍니다.
        #
        #   상 열 개 중에 키에 대한 항이 없었습니다. 기울지 말라는 말은
        #   있어도 서 있으라는 말은 없어서, 정책이 배를 깔고 기었습니다
        #   (몸 높이 0.154 m — 제대로 선 것의 절반).
        from isaaclab.envs import mdp
        from isaaclab.managers import RewardTermCfg as RewTerm

        self.rewards.base_height_l2 = RewTerm(
            func=mdp.base_height_l2,
            weight=-30.0,
            params={"target_height": 0.30},
        )


class UnitreeGo2GuideEnvCfg_PLAY(UnitreeGo2GuideEnvCfg):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False
        self.events.base_external_force_torque = None
        self.events.push_robot = None


        

# ─────────────────────────────────────────────────────────────
#  robotdog00 — 우리가 실제로 걸을 곳만 담은 지형 (2026-09-18, README 40)
#
#  왜 새로 짜는가
#  ──────────────
#  기본 ROUGH_TERRAINS_CFG 로 커리큘럼을 4.62 까지 올렸더니, 그 정책이
#  **평지에서 주저앉았습니다.** 20초에 0.43 m (단계 2.31 짜리는 3.64 m).
#  망가진 게 아니라 **거기에만 맞춰진** 것입니다 — 단계 4.62 의 지형은
#  계단 14 cm · 상자 13 cm · 경사 0.2 이고, **평지가 한 칸도 없습니다.**
#
#  terrain_importer.py:348 을 보면 지형 **종류**는 env 마다 처음에
#  정해지고 끝까지 안 바뀝니다. 커리큘럼은 난이도(줄)만 움직입니다.
#  그래서 `flat` 을 한 종류로 넣어두면 **그 열의 개들은 훈련 내내
#  평지를 걷습니다** — 단계가 어디서 평형을 이루든 상관없이.
#
#  우리 목표는 "모든 지형"이 아니라 **복도 평지 + 문턱 + 층간 계단**
#  입니다. 경사와 울퉁불퉁한 땅은 8층 건물 복도에 없습니다. 뺍니다.
#
#  계단 높이를 (0.08, 0.22) 로 잡은 셈
#  ──────────────────────────────────
#    난이도 = (줄 + 무작위 0~1) / 10          (terrain_generator.py:261)
#    계단   = 0.08 + 난이도 × 0.14            (mesh_terrains.py:76)
#      단계 0 →  9 cm      단계 5 → 16 cm
#      단계 3 → 13 cm      단계 9 → 21 cm
#    ★ 층간 계단 15~18 cm 이 단계 4.6~6.5 에 놓입니다 — 오늘 커리큘럼이
#      실제로 평형을 이룬 자리(4.62)가 바로 거기입니다. ★
# ─────────────────────────────────────────────────────────────
import isaaclab.terrains as terrain_gen
from isaaclab.terrains import TerrainGeneratorCfg

# ※ 2026-10-01 (README 41-17): 아래 이름표가 **거꾸로** 입니다.
#   mesh_terrains.py 의 origin 을 보면 —
#     pyramid_stairs          origin z = +(계단수+1)×높이  → 꼭대기 출발, **내려옴**
#     inverted_pyramid_stairs origin z = −(계단수+1)×높이  → 바닥 출발, **올라감**
#     box                     origin z = +높이              → 상자 위 출발, **내려옴**
#   그러니 "stairs_up" 은 내려가는 칸이고 "sill" 도 내려가기만 합니다.
#   이 판의 실제 구성: 평지 30 · 내려가기 45 · 올라가기 25 (%).
#   기록으로 남겨두고 쓰지 않습니다 — 아래 GUIDE_CLIMB_TERRAINS_CFG 를 씁니다.
GUIDE_TERRAINS_CFG = TerrainGeneratorCfg(
    size=(8.0, 8.0),          # ← 승급선이 이것의 절반(4.0 m)입니다. 건드리지 마십시오 (README 39)
    border_width=20.0,
    num_rows=10,              # 난이도 10 단
    num_cols=20,              # 종류를 여기에 나눠 담습니다
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
    sub_terrains={
        # 복도 — 20칸 중 6칸. **이게 빠져서 오늘 개가 평지에서 주저앉았습니다.**
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.30),
        # 문턱 — 올라섰다 내려오는 단 하나 (우리 sim_go2 --sill-deep 시험대와 같은 모양)
        "sill": terrain_gen.MeshBoxTerrainCfg(
            proportion=0.20, box_height_range=(0.02, 0.15), platform_width=2.0
        ),
        # 층간 계단 — 오르는 쪽
        "stairs_up": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=0.25, step_height_range=(0.08, 0.22), step_width=0.30,
            platform_width=3.0, border_width=1.0, holes=False,
        ),
        # 층간 계단 — 내려오는 쪽 (0.15 m 판에서 하산 기울기가 +34도였습니다. 더 위험합니다)
        "stairs_down": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=0.25, step_height_range=(0.08, 0.22), step_width=0.30,
            platform_width=3.0, border_width=1.0, holes=False,
        ),
    },
)


# ─────────────────────────────────────────────────────────────
#  robotdog00 — 오르기를 늘린 지형 (2026-10-01, README 41-17)
#
#  왜: 0.15 · 0.18 실패가 넷 다 같은 모양 — **몸통은 올라서는데 뒷발이
#  못 따라옵니다** (41-16). 그런데 GUIDE_TERRAINS_CFG 는 올라가기가 25% 뿐
#  이었습니다 (위 ※). 기본 ROUGH 의 20% 와 거의 같습니다.
#
#  바꾼 것은 한 칸입니다 — 내려가기만 하던 상자(box, 20%)를
#  **올라서기만 하는 구덩이(pit, 20%)** 로. 구덩이 바닥에서 출발하니
#  승급선(4.0 m)에 닿으려면 반드시 턱 하나를 올라서야 합니다.
#  시험대의 턱과 가장 닮은 모양입니다.
#
#    평지 30  ·  올라가기 45 (계단 25 + 턱 20)  ·  내려가기 25 (계단)
#
#  높이는 계단과 같은 셈으로 맞췄습니다:
#    높이 = 0.08 + 난이도 × 0.14    (단계 3 → 13 cm · 단계 5 → 16 cm)
#  층간 계단 15~18 cm 이 단계 5~7 에 놓입니다.
# ─────────────────────────────────────────────────────────────
GUIDE_CLIMB_TERRAINS_CFG = TerrainGeneratorCfg(
    size=(8.0, 8.0),          # ← 승급선이 이것의 절반(4.0 m)입니다. 건드리지 마십시오 (README 39)
    border_width=20.0,
    num_rows=10,
    num_cols=20,
    horizontal_scale=0.1,
    vertical_scale=0.005,
    slope_threshold=0.75,
    use_cache=False,
    sub_terrains={
        # 복도
        "flat": terrain_gen.MeshPlaneTerrainCfg(proportion=0.30),
        # 턱 올라서기 — 구덩이 바닥에서 출발 (origin z = −깊이)
        "step_up": terrain_gen.MeshPitTerrainCfg(
            proportion=0.20, pit_depth_range=(0.08, 0.22), platform_width=2.0,
            double_pit=False,
        ),
        # 계단 오르기 — inverted 가 **오르는** 쪽입니다 (바닥 출발)
        "climb": terrain_gen.MeshInvertedPyramidStairsTerrainCfg(
            proportion=0.25, step_height_range=(0.08, 0.22), step_width=0.30,
            platform_width=3.0, border_width=1.0, holes=False,
        ),
        # 계단 내려가기 — 피라미드 꼭대기 출발
        "descend": terrain_gen.MeshPyramidStairsTerrainCfg(
            proportion=0.25, step_height_range=(0.08, 0.22), step_width=0.30,
            platform_width=3.0, border_width=1.0, holes=False,
        ),
    },
)


# ─────────────────────────────────────────────────────────────
#  robotdog00 — 제자리에 멈춰 선 개의 비율 (2026-09-18, README 40-7)
#
#  커리큘럼 항의 규약을 그대로 씁니다: (env, env_ids) 를 받고 스칼라
#  하나를 돌려주면 학습 로그에 Curriculum/<이름> 으로 찍힙니다.
#  지형을 건드리지 않으므로 **학습에 아무 영향이 없습니다** — 눈금자입니다.
#
#  재는 것: 판이 끝난 개들 중, 출발 자리에서 STUCK_M(= 1.0 m) 도 못 벗어난 비율.
#  거리 셈은 terrain_levels_vel 과 **똑같이** 합니다 (같은 잣대로 봐야
#  승급선 4.0 m 와 나란히 읽힙니다).
#    isaaclab_tasks/manager_based/locomotion/velocity/mdp/curriculums.py
#
#  읽는 법: 영점은 **0.02 언저리**입니다 (9/18 실측 0.015~0.030).
#    서 있으라고 시키는 비율이 0.15 이지만, 되뽑기 10초 · 한 판 20초라
#    명령을 **두 번** 뽑습니다. 판 내내 제자리이려면 두 번 다 서라는
#    명령을 받아야 하니 0.15 × 0.15 ≈ 0.0225.
#    ⚠ 되뽑기를 20초로 바꾸면 한 번만 뽑으니 영점이 0.15 로 뜁니다.
#    (2026-09-21 고침: 처음엔 "0.15 언저리가 정상"이라고 적었습니다 — 셈을
#     안 한 값이었습니다.)
#
#  ★★ 순서가 중요합니다 — 처음 판이 전부 0.0000 이었습니다 ★★
#
#  커리큘럼 항은 판이 끝난 개들에 대해 **차례대로** 불립니다. 그런데
#  `terrain_levels_vel` 은 마지막에 이렇게 합니다:
#
#      terrain_importer.py:329
#      self.env_origins[env_ids] = self.terrain_origins[levels, types]
#
#  **원점을 다른 지형 조각으로 옮겨버립니다.** 조각 간격이 8 m 라,
#  그 뒤에 도는 항이 `env_origins` 를 읽으면 "새 원점에서의 거리"를
#  재게 되고 언제나 몇 미터가 나옵니다. 그래서 0.5 m 미만이 하나도
#  없어 비율이 정확히 0 으로 찍혔습니다.
#
#  그래서 아래 GuideCurriculumCfg 에서 **눈금자를 먼저, terrain_levels 를
#  나중에** 두었습니다. 항 순서는 선언 순서입니다.
# ─────────────────────────────────────────────────────────────
#  ★★ 문턱을 0.5 → 1.0 으로 올렸습니다 (첫 판을 보고) ★★
#
#  판이 시작될 때 개를 원점에서 흩뿌립니다:
#      velocity_env_cfg.py:253
#      reset_base ... "pose_range": {"x": (-0.5, 0.5), "y": (-0.5, 0.5), ...}
#
#  대각선으로 최대 0.71 m 입니다. **한 걸음도 안 뗀 개가 0.71 m 로
#  읽힐 수 있습니다.** 문턱이 0.5 m 면 얼어붙은 개의 상당수가 "안 멈췄다"
#  로 세어집니다. 첫 판에서 반복 1 이 1.0 이 아니라 0.25 로 나온 이유입니다
#  (무작위 정책이라 0.58초 만에 다 넘어지는데도).
#
#  1.0 m 는 뿌려지는 최대치보다 확실히 위이고, 승급선 4.0 m 의 1/4 이라
#  walk_dist 와 나란히 읽힙니다.
#
#  ※ 반복 0 의 값은 **버리십시오.** 판 시작 때 모든 개가 한 번 리셋되는데,
#    그때는 아직 각자의 지형 조각으로 옮겨지기 전이라 walk_dist 가 수십
#    미터(첫 판 27.07)로 나옵니다. 반복 1부터가 실제 값입니다.
STUCK_M = 1.0             # 이보다 덜 움직였으면 '멈춰 있었다'


def _walked(env, env_ids):
    """출발 자리에서 얼마나 멀어졌나 — terrain_levels_vel 과 같은 셈."""
    import torch

    asset = env.scene["robot"]
    return torch.linalg.norm(
        asset.data.root_pos_w.torch[env_ids, :2]
        - env.scene.env_origins[env_ids, :2], dim=1)


def stuck_fraction(env, env_ids):
    """STUCK_M(1.0 m) 도 못 벗어난 개의 비율. 영점 ≈ 0.0225 (되뽑기 10초)."""
    import torch

    d = _walked(env, env_ids)
    if d.numel() == 0:
        return torch.zeros((), device=d.device)
    return torch.mean((d < STUCK_M).float())


def walked_distance(env, env_ids):
    """간 거리의 평균. 승급선이 4.0 m 라 나란히 읽으면 뜻이 생깁니다.

    ※ 이 줄이 있어야 stuck_frac 이 맞는 값인지 스스로 검산됩니다.
      거리 평균이 8 m 를 넘으면 또 원점이 옮겨진 뒤에 재고 있는 것입니다.
    """
    import torch

    d = _walked(env, env_ids)
    if d.numel() == 0:
        return torch.zeros((), device=d.device)
    return torch.mean(d)


@configclass
class GuideCurriculumCfg:
    """★ 선언 순서 = 실행 순서입니다. 눈금자가 먼저입니다 ★"""

    stuck_frac = CurrTerm(func=stuck_fraction)
    walk_dist = CurrTerm(func=walked_distance)
    terrain_levels = CurrTerm(func=vel_mdp.terrain_levels_vel)


# ─────────────────────────────────────────────────────────────
#  robotdog00 — 거친 지형, 눈 없이
#
#  평지만 배운 정책은 10 cm 턱에서 넘어집니다 (README 35).
#  스캐너를 끄는 이유: 관측을 48차원으로 남겨 sim_go2.py 가 그대로
#  읽게 하고, 실기체에도 지형 지도를 물릴 길이 없기 때문입니다.
# ─────────────────────────────────────────────────────────────
@configclass
class UnitreeGo2GuideRoughEnvCfg(UnitreeGo2RoughEnvCfg):
    def __post_init__(self):
        super().__post_init__()

        # 명령 범위 — 평지 판과 같게 (견주려면 한 가지만 달라야 합니다)
        self.commands.base_velocity.ranges.lin_vel_x = (0.2, 0.5)
        self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)
        self.commands.base_velocity.rel_standing_envs = 0.15

        # ══════════════════════════════════════════════════════════
        #  ★ 2026-09-18 되돌림 — 아래 두 줄은 **정책을 나쁘게 만들었습니다** ★
        #
        #      self.commands.base_velocity.resampling_time_range = (20.0, 20.0)
        #      self.scene.terrain.terrain_generator = GUIDE_TERRAINS_CFG
        #
        #  지우지 않고 남겨둡니다. "이렇게 하면 나빠진다"도 알아낸 것입니다.
        #
        #  무엇을 했는가
        #    ① resampling 10 → 20초: 커리큘럼 승급선이 원점에서 4.0 m 로
        #       **고정**인데 10초마다 가야 할 방향이 바뀌어 상쇄된다는 것을
        #       소스로 확인하고 고쳤습니다. **진단 자체는 맞았습니다** —
        #       지형 단계가 2.31 → 4.62 로 올랐습니다 (README 39).
        #    ② 지형을 평지+문턱+계단만으로 새로 짰습니다 (README 40).
        #
        #  무엇이 나빠졌는가 (같은 시험대, 턱을 2.0 m 에 두고 잰 값)
        #
        #    정책                    1 cm   10 cm   15 cm
        #    ─────────────────────────────────────────────
        #    1100 (아무것도 안 함)    넘음    넘음    넘음
        #    v2   (①만)              넘음     ✖      ✖
        #    v3   (①+②)               ✖      ✖      ✖
        #
        #  1100 은 0.18 에서 판 위까지 올라가고, 0.20~0.23 에서도 25초
        #  내내 **계속 시도합니다.** v2·v3 은 한 번 막히면 소수점 셋째
        #  자리까지 굳어서 다시 안 움직입니다.
        #
        #  왜 그런가 — ★ 가설입니다. 아직 확인 안 했습니다 ★
        #    멈춰 선 개는 **벌을 안 받습니다.** 판 길이 1000/1000,
        #    넘어짐 0. 상만 조금 덜 받습니다. 지형을 어렵게 밀어올리면
        #    "시도하다 넘어지기"보다 "멈춰 서기"가 이득이 되는 선을
        #    넘습니다. 커리큘럼을 올린 것이 **포기를 가르쳤을** 수 있습니다.
        #
        #  다음에 다시 시도한다면 이 순서로:
        #    · 먼저 **"제자리에 멈춰 선 개의 비율"** 을 학습 로그에 넣을 것.
        #      지금 지표(판 길이·넘어짐)로는 막혀 선 개가 안 보입니다.
        #      Metrics/base_velocity/error_vel_xy 가 0.158 이었는데
        #      (명령 평균 0.35) 그게 유일한 힌트였고 저는 넘겼습니다.
        #    · 그다음에 커리큘럼을 올릴 것. 숫자가 안 보이면 또 착시합니다.
        # ══════════════════════════════════════════════════════════

        # ★ 2026-10-01 다시 켭니다 — 지형 **하나만** (README 41-17) ★
        #
        #   9/18 의 v3 은 ①(resampling 20초)과 ②(지형)를 **한꺼번에** 바꿨고,
        #   v2 는 ①만 바꿨습니다. **②만 바꾼 판은 한 번도 없었습니다.**
        #   위에 적어둔 순서의 첫 단계(멈춰 선 개의 비율 = stuck_frac)는
        #   9/21 부터 로그에 있습니다. 이제 두 번째 단계입니다.
        #
        #   바꾸는 것: 지형 → GUIDE_CLIMB_TERRAINS_CFG (오르기 45%)
        #     ※ 처음엔 GUIDE_TERRAINS_CFG 를 그대로 켜려 했으나, 소스를 보니
        #       그 판은 올라가기가 25% 뿐이었습니다 (위 ※). 오늘 실패를
        #       겨냥해 상자(내려가기) 칸만 구덩이(올라서기)로 바꿨습니다.
        #   그대로 두는 것: resampling(기본 10초) · 엉덩이 벌 −0.2 · 그 밖의 전부
        #   지켜볼 것: Curriculum/stuck_frac — 9/21·9/29 판은 0.02~0.03.
        #              뚜렷이 오르면 v2·v3 의 병(멈춰 서기를 배움)이 도진 것.
        #
        # ★ 2026-10-01 되돌림 (README 41-18) — 오르기 판은 **나빠졌습니다** ★
        #   stuck_frac 0.081 (경보) · terrain_levels 3.49 → 0.55 로 무너짐
        #   0.15 턱: 기준판 2/4 → 0/4 (넷 다 앞면 33~39 cm 앞에서 멈춤)
        #   원인(가설): 구덩이 하한 8 cm — 맨 아래 줄도 빠져나갈 수 없는
        #   "갇히는 칸"이라, 커리큘럼이 못하는 개를 거기 모았고 개는
        #   멈춰 서기를 배웠습니다. **하한은 상한만큼 중요합니다.**
        # self.scene.terrain.terrain_generator = GUIDE_CLIMB_TERRAINS_CFG

        # ★ 2026-10-01 (README 41-19) — 기본 ROUGH 에서 **비율만** 바꿉니다 ★
        #
        #   41-18 의 교훈: 커리큘럼의 맨 아래 줄은 빠져나갈 수 있어야 합니다.
        #   그래서 지형을 새로 짜지 않고, super() 가 이미 Go2 몸집에 맞게
        #   줄여둔 ROUGH(상자 2.5~10 cm · 울퉁불퉁 1~6 cm)를 복사해서
        #   **비율만** 고칩니다. 하한(계단 5 cm)과 디딤판은 기준판과 같습니다.
        #
        #                   기준판   이번
        #     내려가는 계단    20  →  10      (pyramid_stairs: 꼭대기 출발)
        #     오르는 계단      20  →  40      (pyramid_stairs_inv: 바닥 출발)
        #     상자 격자        20     20
        #     울퉁불퉁         20     20
        #     경사 내/오     10+10  → 5+5
        #
        #   복사하는 이유: ROUGH_TERRAINS_CFG 는 모듈 전체가 같이 쓰는 객체라
        #   제자리에서 고치면 다른 과제(Flat 이 아닌 기본 Go2 Rough 등)까지 바뀝니다.
        #
        # ★ 2026-10-01 되돌림 (README 41-20) — **효과 없음** ★
        #   0.15: 기준판 2/4 → 2/4 · 0.18: 기준판 0/3 → 0/4 (넷 다 같은 자리에서 걸침)
        #   경보 없음 (stuck_frac 0.050 · terrain_levels 2.80 · 평지 71% · 키 0.313)
        #   지형 길을 접고 기준판 설정(ROUGH 그대로)으로 둡니다.
        # import copy
        # _tg = copy.deepcopy(self.scene.terrain.terrain_generator)
        # _tg.sub_terrains["pyramid_stairs"].proportion = 0.10
        # _tg.sub_terrains["pyramid_stairs_inv"].proportion = 0.40
        # _tg.sub_terrains["boxes"].proportion = 0.20
        # _tg.sub_terrains["random_rough"].proportion = 0.20
        # _tg.sub_terrains["hf_pyramid_slope"].proportion = 0.05
        # _tg.sub_terrains["hf_pyramid_slope_inv"].proportion = 0.05
        # self.scene.terrain.terrain_generator = _tg

        # ★ 2026-10-02 (README 43) — **이어 학습용** 지형 ★
        #
        #   연속 계단 시험(42장): 15 cm 열 칸은 오르고 18 cm 는 아무도 못 오릅니다.
        #   원인은 승급선입니다 — 계단은 한 칸(0.30 m)에 2초라 20초에 3 m,
        #   승급선 4 m 에 못 닿아 학습 내내 12 cm 언저리에 머물렀습니다 (42-7).
        #
        #   승급선은 그대로 두고 **계단 높이의 바닥을 올립니다.**
        #       (0.05, 0.23) → (0.13, 0.23)
        #       단계 0 → 13~14 cm · 단계 3 → 16~17 cm · 단계 5 → 18~19 cm
        #   처음부터 배우는 판에 쓰면 맨 아래 줄이 "갇히는 칸"이 됩니다 (41-18).
        #   **15 cm 를 이미 오르는 정책에서 이어 학습할 때만** 씁니다 —
        #   그 정책에게 13 cm 는 빠져나갈 수 있는 바닥입니다.
        #   비율은 이어받는 판(10/01, 41-19)과 같게 둡니다 — 바뀌는 것은 높이 하나.
        #
        #   ★ 결과 (README 43-3): 400번 이어 학습으로 18 cm 계단 열 칸을 오릅니다 ★
        #     (마지막 세 체크포인트 중 둘 · 이어받은 판은 30칸 중 7칸)
        #
        #   ★ 기본은 **꺼 둡니다** (FINE_TUNE_STAIRS = False) ★
        #     켜진 채로 처음부터 학습하면 맨 아래 줄이 갇히는 칸이 됩니다 (41-18).
        #     이어 학습할 때만 True 로 바꾸고, 끝나면 되돌리십시오.
        #     (return 으로 막으면 안 됩니다 — 아래의 키 상 · 엉덩이 벌 · 눈금이 다 빠집니다)
        FINE_TUNE_STAIRS = False
        if FINE_TUNE_STAIRS:
            import copy
            _tg = copy.deepcopy(self.scene.terrain.terrain_generator)
            _tg.sub_terrains["pyramid_stairs"].proportion = 0.10
            _tg.sub_terrains["pyramid_stairs_inv"].proportion = 0.40
            _tg.sub_terrains["boxes"].proportion = 0.20
            _tg.sub_terrains["random_rough"].proportion = 0.20
            _tg.sub_terrains["hf_pyramid_slope"].proportion = 0.05
            _tg.sub_terrains["hf_pyramid_slope_inv"].proportion = 0.05
            _tg.sub_terrains["pyramid_stairs"].step_height_range = (0.13, 0.23)
            _tg.sub_terrains["pyramid_stairs_inv"].step_height_range = (0.13, 0.23)
            self.scene.terrain.terrain_generator = _tg


        # ★ 정책의 눈만 가립니다 — 스캐너는 남겨둡니다 ★
        #   관측에서만 빼면 정책은 여전히 48차원(장님)이라 sim_go2.py 가
        #   그대로 읽고, 상을 셈할 때는 지형 높이를 쓸 수 있습니다.
        #   학습 중에만 쓰는 정보라 실기체와 상관없습니다.
        self.observations.policy.height_scan = None
        # self.scene.height_scanner 는 건드리지 않습니다.

        # 서 있으라고 말해줍니다 — 지형 높이를 뺀 키로.
        #   처음엔 이 항을 아예 뺐습니다. "거친 지형에서 세계 좌표 높이를
        #   목표로 삼으면 안 된다" 는 이유는 맞았는데, 빼고 나서 대신
        #   넣은 게 없었습니다. 그래서 정책이 배를 깔고 기었습니다
        #   (README 34-3 과 똑같은 일을 하루 만에 다시).
        from isaaclab.envs import mdp
        from isaaclab.managers import RewardTermCfg as RewTerm
        from isaaclab.managers import SceneEntityCfg

        self.rewards.base_height_l2 = RewTerm(
            func=mdp.base_height_l2,
            weight=-30.0,
            params={"target_height": 0.30,
                    "sensor_cfg": SceneEntityCfg("height_scanner")},
        )

        # ★ 다리를 꼬지 말라고 말해줍니다 (2026-09-21, README 40-12) ★
        #
        #   왜: 9/18 정책은 18 cm 턱을 넘었지만 **뒷다리가 판 내내 꼬여**
        #   있었습니다 (벌림 −1.22 rad, 쉴 때는 +0.20). 좌우 다리가 각각
        #   30~37도씩 가운데를 넘어가 있습니다. 시뮬레이터에서는 공짜인데
        #   (`unitree.py:155` `enabled_self_collisions=False` — 다리가 서로를
        #   통과합니다) **진짜 몸이라면 종아리끼리 부딪힙니다.**
        #   즉 그 18 cm 는 "Go2 가 18 cm 를 넘는다"는 증거가 못 됩니다.
        #   (※ 이 정책이 실기체로 갈 일은 원래 없습니다 — README 32-0 ·
        #     34-0. 문제는 배치가 아니라 결과가 **뜻이 있느냐**입니다.)
        #
        #   왜 그랬나: 상 열한 개 중 자세를 나무라는 항이 하나도 없었습니다.
        #     flat_orientation_l2  0.0  ·  dof_pos_limits  0.0
        #     관절이 기본 자세에서 벗어나는 것에 대한 항 — 없음
        #   부딪히지도 않고 나무라지도 않으면 안 쓸 이유가 없습니다.
        #   **정책은 잘못한 게 없습니다. 우리가 안 시켰습니다.**
        #
        #   대조군: NVIDIA 기본 정책은 같은 로봇·같은 물리에서 **안 꼽니다**
        #   (벌림 최소 앞 +0.220 · 뒤 +0.304). 꼬임은 환경의 성질이 아니라
        #   우리 상 설정의 산물입니다 (README 40-12-1).
        #
        #   무게를 −0.2 로 잡은 근거 (짐작이 아니라 셈):
        #     지금 힙 넷의 기본값 대비 벗어난 양의 합 ≈ 1.9 rad
        #       FL +0.33(기본 +0.1) · FR −0.37(−0.1) · RL −0.65(+0.1) · RR +0.52(−0.1)
        #     × 0.2 = 약 −0.37/걸음.  견줄 것은 track_lin_vel_xy_exp ≈ +1.38.
        #     → 추적 상의 **27%**. 무시 못 할 값이되 걷기를 덮지는 않습니다.
        #     너무 세면 개가 다리를 묶은 채 못 걷고, 너무 약하면 안 바뀝니다.
        #
        #   ⚠ 이 항은 **걸을 때 필요한 옆 움직임까지** 같이 벌합니다.
        #     천장이 15~18 cm 아래로 내려갈 수 있습니다. 그래도 이쪽이
        #     맞는 방향입니다 — 몸이 할 수 없는 걸음으로 넘은 18 cm 보다
        #     몸이 할 수 있는 걸음으로 넘은 15 cm 가 뜻이 있습니다.
        #   (2026-09-21 결과: 천장이 안 내려갔습니다 — 18 cm 를 넘습니다. README 41.)
        #   ⚠ 안 되면 다음 수(B안): 벗어남 전체가 아니라 **가운데를 넘는
        #     것만** 벌하는 항을 따로 짭니다 (relu(−벌림)). 이번 판 결과를
        #     보고 정합니다. 한 판에 하나씩.
        self.rewards.hip_deviation = RewTerm(
            func=mdp.joint_deviation_l1,
            weight=-0.2,
            params={"asset_cfg": SceneEntityCfg(
                "robot", joint_names=[".*_hip_joint"])},
        )

        # 광선을 187개 → 4개로 줄입니다.
        #   상은 이 값들의 **평균 하나**만 씁니다. 그런데 4096마리가
        #   357만 면짜리 지형에 187줄씩 쏘느라 초당 걸음이
        #   15만 → 2.7만으로 떨어졌습니다 (17분이 1시간 20분으로).
        #   기본: size [1.6, 1.0] · 간격 0.1 → 17 × 11 = 187
        #   우리: size [0.2, 0.2] · 간격 0.2 →  2 ×  2 = 4
        self.scene.height_scanner.pattern_cfg.resolution = 0.2
        self.scene.height_scanner.pattern_cfg.size = [0.2, 0.2]

        # ★ 멈춰 선 개의 비율을 찍습니다 (2026-09-18, README 40-7·40-11) ★
        #
        #   왜 필요한가: v2 의 학습 로그는 이랬습니다 —
        #       Mean episode length   1000/1000   (아무도 안 넘어짐)
        #       base_contact             3.7 %    (배를 안 깖)
        #       terrain_levels           4.62     (지형도 오름)
        #   셋 다 좋습니다. 그리고 그 정책은 10 cm 턱을 못 넘습니다.
        #   **가만히 서 있는 개도 이 셋이 전부 좋습니다.** 지금 지표로는
        #   막혀 선 개가 한 마리도 안 보입니다.
        #
        #   커리큘럼 항으로 답니다. 판이 끝날 때 불리고, 돌려준 값이
        #   Curriculum/<이름> 으로 그대로 찍히기 때문에 상을 건드리지 않고
        #   **보기만** 할 수 있습니다. (상에 넣으면 학습이 바뀝니다.)
        #
        #   ★ 통째로 갈아끼웁니다 — 항 순서 때문입니다 ★
        #     나중에 붙이면 terrain_levels 뒤로 가고, 그러면 원점이 이미
        #     옮겨진 뒤에 재게 되어 값이 전부 0 으로 나옵니다.
        #     (첫 판이 정확히 그랬습니다 — GuideCurriculumCfg 주석 참고)
        self.curriculum = GuideCurriculumCfg()

class UnitreeGo2GuideRoughEnvCfg_PLAY(UnitreeGo2GuideRoughEnvCfg):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False
        self.events.base_external_force_torque = None
        self.events.push_robot = None

        # ─── 구경용으로만 고칩니다 (2026-09-18, README 40) ───
        #   학습 설정은 위 클래스 그대로입니다. 여기만 바꿉니다.
        #
        #   왜: --viz kit 으로 봤더니 개 몇 마리가 가만히 서 있었습니다.
        #       고장이 아니라 **서 있으라고 시킨 개들**이었습니다
        #       (rel_standing_envs = 0.15 → 32마리 중 다섯쯤).
        #       게다가 명령 주기를 20초로 늘려놔서, 한 번 서면 한 판
        #       내내 서 있습니다. 학습에는 해롭지 않지만 구경은 망칩니다.
        self.commands.base_velocity.rel_standing_envs = 0.0

        #   그리고 가야 할 방향이 −π~π 무작위라 판이 시작될 때마다
        #   제자리에서 도는 시간이 깁니다. 구경할 때는 다 같은 쪽을
        #   보고 걸어야 계단을 오르는지 안 오르는지가 보입니다.
        self.commands.base_velocity.ranges.heading = (-0.3, 0.3)

        #   빠른 쪽만 시켜서 실제로 전진하게 합니다 (학습 범위는 0.2~0.5).
        self.commands.base_velocity.ranges.lin_vel_x = (0.5, 0.5)