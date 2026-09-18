# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

from isaaclab.utils.configclass import configclass

from isaaclab_rl.rsl_rl import RslRlMLPModelCfg, RslRlOnPolicyRunnerCfg, RslRlPpoAlgorithmCfg


@configclass
class UnitreeGo2RoughPPORunnerCfg(RslRlOnPolicyRunnerCfg):
    num_steps_per_env = 24
    max_iterations = 1500
    save_interval = 50
    experiment_name = "unitree_go2_rough"
    actor = RslRlMLPModelCfg(
        hidden_dims=[512, 256, 128],
        activation="elu",
        obs_normalization=False,
        distribution_cfg=RslRlMLPModelCfg.GaussianDistributionCfg(init_std=1.0),
    )
    critic = RslRlMLPModelCfg(
        hidden_dims=[512, 256, 128],
        activation="elu",
        obs_normalization=False,
    )
    algorithm = RslRlPpoAlgorithmCfg(
        value_loss_coef=1.0,
        use_clipped_value_loss=True,
        clip_param=0.2,
        entropy_coef=0.01,
        num_learning_epochs=5,
        num_mini_batches=4,
        learning_rate=1.0e-3,
        schedule="adaptive",
        gamma=0.99,
        lam=0.95,
        desired_kl=0.01,
        max_grad_norm=1.0,
    )


@configclass
class UnitreeGo2FlatPPORunnerCfg(UnitreeGo2RoughPPORunnerCfg):
    def __post_init__(self):
        super().__post_init__()

        self.max_iterations = 300
        self.experiment_name = "unitree_go2_flat"
        self.actor.hidden_dims = [128, 128, 128]
        self.critic.hidden_dims = [128, 128, 128]





@configclass
class UnitreeGo2GuidePPORunnerCfg(UnitreeGo2FlatPPORunnerCfg):
    """robotdog00 — 안내견 속도대 학습. 평지 설정을 그대로 물려받고
    로그 이름만 가릅니다 (섞이면 나중에 어느 것이 어느 것인지 모릅니다)."""

    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "unitree_go2_guide"


        

@configclass
class UnitreeGo2GuideRoughPPORunnerCfg(UnitreeGo2RoughPPORunnerCfg):
    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "unitree_go2_guide_rough"

        # ★ 탐색 폭을 로그로 저장합니다 ★
        #   2026-09-16, 236번째에서 "normal expects all elements of
        #   std >= 0.0" 로 죽었습니다. Mean action std 가 1.00 → 0.52 로
        #   줄고 있었고, 그대로 두면 0 을 지나 음수가 됩니다.
        #   "log" 면 exp 를 씌우니 항상 양수입니다.
        #   (어제 평지 판이 300번에서 끝난 건 운이 좋았던 겁니다.
        #    그때 std 가 0.26 이었으니 더 돌았으면 같은 자리에서 터졌습니다.)
        self.actor.distribution_cfg.std_type = "log"