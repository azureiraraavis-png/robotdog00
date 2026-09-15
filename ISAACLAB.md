# Isaac Lab 에 우리가 고친 곳

★ 이 파일이 왜 있는가 ★

Isaac Lab 은 **우리 저장소가 아닙니다.** `C:\Users\<사용자>\IsaacLab` 에
따로 받아둔 남의 코드고, 거기서 무엇을 고쳤는지는 우리 `git` 이
봐주지 않습니다.

그래서 이런 일이 생깁니다 —

- Isaac Lab 을 다시 받거나 업데이트하면 **고친 것이 통째로 날아갑니다.**
- 몇 주 뒤에 "학습이 왜 이 속도로 됐더라" 를 되짚을 근거가 없습니다.
- 다른 사람이 같은 것을 재현할 수 없습니다.

그래서 **고친 줄을 그대로** 여기에 옮겨 적습니다. 요약하지 않습니다.
이 파일만 있으면 새로 깐 Isaac Lab 에 붙여넣어 복원됩니다.

기준 판: Isaac Lab `release/3.0.0-beta2` · Isaac Sim 6.0.1 · 2026-09-15

---

## 왜 고쳤는가

NVIDIA 가 내준 학습된 Go2 정책은 **1 m/s 근처**에서 걷도록 배웠습니다.
안내견이 복도에서 내는 속도는 **0.31 m/s** 입니다. 그 바깥에서 돌리면
보폭만 줄고 걸음 박자는 그대로라, 1 m 갈 때 10 cm 씩 옆으로
미끄러집니다 (README 33-6).

그래서 **명령 속도 범위를 우리 속도로 좁혀** 다시 학습시킵니다.

원래 과제(`Isaac-Velocity-Flat-Unitree-Go2-v0`)는 **그대로 둡니다.**
견줄 기준선이 필요하기 때문입니다. 우리 것은 이름을 따로 답니다.

```
Isaac-Velocity-Flat-Unitree-Go2-Guide-v0        학습용
Isaac-Velocity-Flat-Unitree-Go2-Guide-Play-v0   확인·내보내기용
```

---

## 고친 곳 1 — 환경 설정

**파일**

```
<IsaacLab>\source\isaaclab_tasks\isaaclab_tasks\manager_based\
  locomotion\velocity\config\go2\flat_env_cfg.py
```

**맨 끝에 이어 붙임** (기존 내용은 건드리지 않음)

```python
# ─────────────────────────────────────────────────────────────
#  robotdog00 — 안내견 속도대로 좁힌 환경
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
        #          하고, 그 자세에서 무너지는 것을 봤습니다
        self.commands.base_velocity.rel_standing_envs = 0.15


class UnitreeGo2GuideEnvCfg_PLAY(UnitreeGo2GuideEnvCfg):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False
        self.events.base_external_force_torque = None
        self.events.push_robot = None
```

**`_PLAY` 에 `@configclass` 를 안 붙인 것은 일부러입니다.** 바로 위
`UnitreeGo2FlatEnvCfg_PLAY` 가 그렇게 돼 있습니다. 돌아가는 파일을
흉내내는 쪽이 안전합니다.

**안 건드린 것 — `ang_vel_z`**

```python
heading_command = True
rel_heading_envs = 1.0
```

모든 환경이 "이 방향을 바라봐라" 형태로 명령받고, 회전 속도는 방향
오차에서 계산됩니다. **`ang_vel_z` 범위는 쓰이지 않습니다.** 고쳐봐야
아무 일도 안 일어납니다.

`heading` 도 −π~π 그대로 뒀습니다. 안내견은 복도를 돌아야 하니
온 방향을 배우는 편이 맞고, 한 번에 한 가지만 바꿔야 무엇이
효과였는지 압니다.

---

## 고친 곳 2 — 학습 설정

**파일**

```
<IsaacLab>\source\isaaclab_tasks\isaaclab_tasks\manager_based\
  locomotion\velocity\config\go2\agents\rsl_rl_ppo_cfg.py
```

**맨 끝에 이어 붙임**

```python
@configclass
class UnitreeGo2GuidePPORunnerCfg(UnitreeGo2FlatPPORunnerCfg):
    """robotdog00 — 안내견 속도대 학습. 평지 설정을 그대로 물려받고
    로그 이름만 가릅니다 (섞이면 나중에 어느 것이 어느 것인지 모릅니다)."""

    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "unitree_go2_guide"
```

`max_iterations` 는 평지 것 그대로 **300** 입니다.

---

## 고친 곳 3 — 과제 등록

**파일**

```
<IsaacLab>\source\isaaclab_tasks\isaaclab_tasks\manager_based\
  locomotion\velocity\config\go2\__init__.py
```

**맨 끝에 이어 붙임**

```python
gym.register(
    id="Isaac-Velocity-Flat-Unitree-Go2-Guide-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.flat_env_cfg:UnitreeGo2GuideEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:UnitreeGo2GuidePPORunnerCfg",
        "skrl_cfg_entry_point": f"{agents.__name__}:skrl_flat_ppo_cfg.yaml",
    },
)

gym.register(
    id="Isaac-Velocity-Flat-Unitree-Go2-Guide-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.flat_env_cfg:UnitreeGo2GuideEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:UnitreeGo2GuidePPORunnerCfg",
        "skrl_cfg_entry_point": f"{agents.__name__}:skrl_flat_ppo_cfg.yaml",
    },
)
```

`skrl` 쪽은 평지 것을 그대로 가리킵니다. 우리는 rsl_rl 로 돌리니
쓰이지 않지만, 비워두면 그 도구로 열 때 터집니다.

---

## 돌리는 법

```powershell
cd C:\Users\<사용자>\IsaacLab

# 30초짜리 확인 — 이름이 틀렸으면 몇 초 만에 떨어집니다
.\isaaclab.bat train --rl_library rsl_rl `
    --task Isaac-Velocity-Flat-Unitree-Go2-Guide-v0 `
    --num_envs 64 --max_iterations 2

# 진짜 판
.\isaaclab.bat train --rl_library rsl_rl `
    --task Isaac-Velocity-Flat-Unitree-Go2-Guide-v0 `
    --num_envs 4096
```

- PowerShell 에서는 `.\` 를 붙여야 합니다.
- 끊을 때는 **Ctrl+Break**. Ctrl+C 로는 잘 안 죽습니다.
- 50번마다 체크포인트가 남으니 중간에 끊어도 버려지지 않습니다.
- `--headless` 는 3.0 에서 없어졌습니다. 화면 없는 것이 기본이고,
  보고 싶으면 `--viz kit` 을 붙입니다.

---

## ★ 넣었다고 들어간 게 아닙니다 — 확인하는 법 ★

화면에 뜨는 「Active Command Terms」 표에는 **이름과 종류만** 나오고
범위는 안 찍힙니다. 그래서 눈으로는 확인이 안 됩니다.

Isaac Lab 은 풀어낸 설정을 로그 폴더에 통째로 떨어뜨립니다.
거기서 보면 확실합니다.

```powershell
Get-ChildItem C:\Users\<사용자>\IsaacLab\logs\rsl_rl\unitree_go2_guide `
    -Recurse -Filter env.yaml |
  Sort-Object LastWriteTime | Select-Object -Last 1 |
  Select-String -Pattern 'rel_standing_envs' -Context 0,14
```

이렇게 나와야 맞습니다.

```yaml
    rel_standing_envs: 0.15
    rel_heading_envs: 1.0
    ranges:
      lin_vel_x: !!python/tuple
      - 0.2
      - 0.5
      lin_vel_y: !!python/tuple
      - 0.0
      - 0.0
```

`Sort-Object` 를 꼭 넣으세요. 시험판과 진짜 판이 같은 폴더에 쌓이고,
**어느 판을 보는지 헷갈린 채로 넘어가면** 나중에 결과를 엉뚱한 설정에
붙이게 됩니다.

---

## 곁다리로 알아낸 것 — 이득이 물리 엔진에 없습니다

학습을 걸면 관절 표가 이렇게 나옵니다.

```
Stiffness 0.000 · Damping 0.000 · Effort Limits 1.0e+09
```

고장이 아닙니다. Isaac Lab 의 Go2 는 `DCMotor` 라는 **명시적 구동기**를
씁니다 — 물리 엔진에게 PD 를 맡기지 않고, 매 걸음 파이썬에서 토크를
셈해 직접 넣습니다. 그래서 PhysX 쪽 드라이브는 비워둡니다.

★ 그런데 `sim_go2.py --gains` 가 넣는 자리가 바로 그 비워둔 자리입니다 ★

같은 이름의 **다른 자리**에 넣은 것입니다. 이득을 넣었더니 3초에
2.339 → 2.013 m 로 14% 느려진 것이 이걸로 설명됩니다. 없던 용수철을
하나 더 매단 셈이니까요.

그러니 **`--gains` 없이 재는 쪽이 원래 학습 조건에 가깝습니다.**
(아직 넣고/빼고 나란히 재보지는 않았습니다. 확인 대상으로 남깁니다.)

---

## Isaac Lab 을 다시 깔았다면

위의 「고친 곳 1·2·3」 을 순서대로 다시 붙여넣으면 끝입니다.
셋 다 **파일 맨 끝에 덧붙이는 것**이라 기존 내용과 부딪히지 않습니다.

그리고 설치에서 걸렸던 것들은 README 33-4 에 적어뒀습니다 —
`_isaac_sim` 심볼릭 링크, `-i "rl[rsl-rl]"` (`-i rsl_rl` 은 조용히
거부됩니다), PowerShell 의 `.\` 등입니다.
