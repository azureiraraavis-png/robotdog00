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
#  robotdog00 — 제자리에 멈춰 선 개의 비율 (2026-09-18, README 40-7)
#
#  커리큘럼 항의 규약을 그대로 씁니다: (env, env_ids) 를 받고 스칼라
#  하나를 돌려주면 학습 로그에 Curriculum/<이름> 으로 찍힙니다.
#  지형을 건드리지 않으므로 **학습에 아무 영향이 없습니다** — 눈금자입니다.
#
#  재는 것: 판이 끝난 개들 중, 출발 자리에서 0.5 m 도 못 벗어난 비율.
#  거리 셈은 terrain_levels_vel 과 **똑같이** 합니다 (같은 잣대로 봐야
#  승급선 4.0 m 와 나란히 읽힙니다).
#    isaaclab_tasks/manager_based/locomotion/velocity/mdp/curriculums.py
#
#  읽는 법: 0.15 언저리면 정상입니다 (rel_standing_envs = 0.15 —
#  서 있으라고 **시킨** 개들). 그보다 크게 올라가면 시키지도 않았는데
#  멈춘 개가 늘고 있다는 뜻입니다.
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
    """0.5 m 도 못 벗어난 개의 비율. 0.15 언저리가 정상입니다."""
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