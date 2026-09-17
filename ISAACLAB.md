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

## 고친 곳 4 — 거친 지형 (2026-09-16)

평지만 배운 정책은 **4 cm 턱부터 넘어집니다** (README 35-2).
그래서 같은 명령 범위를 거친 지형 위에 얹습니다.

> ## ⚠ 아래 판은 **기어다니는 정책**을 만듭니다
>
> 이대로 1500번을 돌렸더니 배를 깔고 다니는 개가 나왔습니다
> (README 36). 스캐너를 통째로 끄면서 `base_height_l2` 를 빼고
> **대신 넣은 것이 없어서**, 자세에 대해 아무 말도 안 하는 설정이
> 됐기 때문입니다. 거친 지형 쪽은 `flat_orientation_l2` 도 0 입니다.
>
> 아래를 그대로 붙여넣지 마시고, **맨 밑의 「고칠 것」까지 읽고**
> 함께 넣으십시오.

```
Isaac-Velocity-Rough-Unitree-Go2-Guide-v0        학습용
Isaac-Velocity-Rough-Unitree-Go2-Guide-Play-v0   확인·내보내기용
```

**`flat_env_cfg.py` 맨 끝에 이어 붙임**

거친 지형인데 파일 이름이 flat 인 것은 어색합니다만, `UnitreeGo2RoughEnvCfg`
를 이미 여기서 불러오고 있고 **우리가 고친 것을 한 파일에 모아두는 편**이
남의 저장소에서는 낫습니다.

```python
@configclass
class UnitreeGo2GuideRoughEnvCfg(UnitreeGo2RoughEnvCfg):
    def __post_init__(self):
        super().__post_init__()

        # 명령 범위 — 평지 판과 같게 (견주려면 한 가지만 달라야 합니다)
        self.commands.base_velocity.ranges.lin_vel_x = (0.2, 0.5)
        self.commands.base_velocity.ranges.lin_vel_y = (0.0, 0.0)
        self.commands.base_velocity.rel_standing_envs = 0.15

        # ★ 2026-09-17 추가 (README 39) ★
        #   커리큘럼 승급선은 판 크기의 절반 = 4.0 m 로 **고정**인데,
        #   10초마다 가야 할 방향이 무작위로 바뀌어 원점 거리가 상쇄됩니다.
        #   위에서 속도를 절반으로 깎아놨으므로 상쇄를 버틸 여유가 없습니다.
        #   (0.2 m/s × 20 s = 정확히 4.00 m — 승급이 산술적으로 불가능)
        #   속도는 그대로 두고, 한 판에 한 방향만 주도록 바꿉니다.
        self.commands.base_velocity.resampling_time_range = (20.0, 20.0)

        # ★ 눈을 뗍니다 ★ — 관측 48차원 유지
        self.scene.height_scanner = None
        self.observations.policy.height_scan = None

        # base_height_l2 는 넣지 않습니다.
        #   거친 지형에서는 땅 높이가 자리마다 달라서, 세계 좌표 높이를
        #   목표로 삼으면 언덕에서 몸을 낮추라고 시키게 됩니다.


class UnitreeGo2GuideRoughEnvCfg_PLAY(UnitreeGo2GuideRoughEnvCfg):
    def __post_init__(self) -> None:
        super().__post_init__()
        self.scene.num_envs = 50
        self.scene.env_spacing = 2.5
        self.observations.policy.enable_corruption = False
        self.events.base_external_force_torque = None
        self.events.push_robot = None
```

**★ 왜 스캐너를 끄는가 ★**

  · 관측이 48차원으로 남아 `sim_go2.py` 가 그대로 읽습니다. 켜두면
    235차원이 되어, 17분을 돌린 뒤에야 **우리 잣대에 못 넣는 정책**
    이라는 걸 알게 됩니다.
  · 실기체에도 지형 지도를 정책에 물려줄 길이 없습니다 (32-0).

**`agents\rsl_rl_ppo_cfg.py` 맨 끝에 이어 붙임**

```python
@configclass
class UnitreeGo2GuideRoughPPORunnerCfg(UnitreeGo2RoughPPORunnerCfg):
    def __post_init__(self):
        super().__post_init__()
        self.experiment_name = "unitree_go2_guide_rough"
```

`max_iterations` 는 거친 지형 것 그대로 **1500** 입니다 (평지는 300).
4096 마리로 17분쯤.

**`__init__.py` 맨 끝에 이어 붙임**

```python
gym.register(
    id="Isaac-Velocity-Rough-Unitree-Go2-Guide-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.flat_env_cfg:UnitreeGo2GuideRoughEnvCfg",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:UnitreeGo2GuideRoughPPORunnerCfg",
        "skrl_cfg_entry_point": f"{agents.__name__}:skrl_rough_ppo_cfg.yaml",
    },
)

gym.register(
    id="Isaac-Velocity-Rough-Unitree-Go2-Guide-Play-v0",
    entry_point="isaaclab.envs:ManagerBasedRLEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": f"{__name__}.flat_env_cfg:UnitreeGo2GuideRoughEnvCfg_PLAY",
        "rsl_rl_cfg_entry_point": f"{agents.__name__}.rsl_rl_ppo_cfg:UnitreeGo2GuideRoughPPORunnerCfg",
        "skrl_cfg_entry_point": f"{agents.__name__}:skrl_rough_ppo_cfg.yaml",
    },
)
```

**★ 30초 확인 — 17분을 걸기 전에 ★**

```powershell
.\isaaclab.bat train --rl_library rsl_rl `
    --task Isaac-Velocity-Rough-Unitree-Go2-Guide-v0 `
    --num_envs 64 --max_iterations 2
```

  · 관측 표가 **`shape: (48,)`** 이고 `height_scan` 줄이 **없어야** 합니다.
  · 상 표에 **`base_height_l2` 가 없어야** 합니다.
  · `Curriculum` 에 `terrain_levels` 가 **있어야** 합니다 (쉬운 데서 시작해
    험해집니다).

물려받은 기본값 때문에 상 두 개가 평지 판과 다릅니다. 알고 가야 합니다 —

```
                      평지 Guide   거친 Guide
 feet_air_time          0.25         0.01
 flat_orientation_l2   −2.50         0.00
```

---

## 고친 곳 4 에 고칠 것 — 돌려봤습니다 (2026-09-17)

2026-09-16 저녁에 알아낸 것들입니다. 다음 날 아침에 돌려봤고,
**결과는 반만 맞았습니다.** 각 항목 아래 결과를 적어뒀습니다.

```
(가) 스캐너를 관측에서만 빼기     → 먹혔습니다. 기어다니지 않습니다.
     광선 187 → 4 로 줄이기       → ★ 헛수고였습니다 (아래 참고)
(나) std_type = "log"             → ★ 크래시를 막지 못했습니다 (아래 참고)
```

**(가) 스캐너를 끄지 말고, 관측에서만 뺍니다**

`flat_env_cfg.py` 의 `UnitreeGo2GuideRoughEnvCfg.__post_init__` 에서
`self.scene.height_scanner = None` 줄을 **지우고**, 대신 —

```python
        # ★ 정책의 눈만 가립니다 — 스캐너는 남겨둡니다 ★
        #   관측에서만 빼면 정책은 여전히 48차원(장님)이라 sim_go2.py 가
        #   그대로 읽고, 상을 셈할 때는 지형 높이를 쓸 수 있습니다.
        #   학습 중에만 쓰는 정보라 실기체와 상관없습니다.
        self.observations.policy.height_scan = None
        # self.scene.height_scanner 는 건드리지 않습니다.

        # 서 있으라고 말해줍니다 — 지형 높이를 뺀 키로.
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
```

> **결과 (2026-09-17):** 관측에서 빼는 부분은 먹혔습니다 — 48차원
> 장님 정책이 나오고, `base_height_l2` 가 붙어서 기어다니지 않습니다.
>
> **광선 줄이기는 헛수고였습니다.**
>
> ```
> 187 → 4 줄     초당 걸음 26,900 → 30,000    (11% 뿐)
> ETA            01:19 → 01:25               (안 줄었습니다)
> ```
>
> 비용은 광선 **개수**가 아니라 RayCaster 를 한 번이라도 돌리는
> **고정 비용**입니다. 없애려면 스캐너를 통째로 빼고 상을
> 다른 방식으로 줘야 합니다 (예: `몸통 z − 발 네 개의 평균 z`).
> 두 줄을 남겨둬도 손해는 없으니 그대로 둡니다.

**(나) 탐색 폭을 로그로 저장합니다**

`agents\rsl_rl_ppo_cfg.py` 의 `UnitreeGo2GuideRoughPPORunnerCfg` 에 —

```python
        # ★ 2026-09-16, 236번째에서 이걸로 죽었습니다 ★
        #   RuntimeError: normal expects all elements of std >= 0.0
        #   Mean action std 가 1.00 → 0.52 로 줄고 있었고, 그대로 두면
        #   0 을 지나 음수가 됩니다. "log" 면 exp 를 씌우니 항상 양수입니다.
        #   (평지 판이 300번에서 끝난 건 운이 좋았던 것입니다 — 그때
        #    std 가 0.26 이었으니 더 돌았으면 같은 자리에서 터졌습니다.)
        self.actor.distribution_cfg.std_type = "log"
```

이름은 `isaaclab_rl\rsl_rl\rl_cfg.py:57` 에서 확인했습니다 —
`GaussianDistributionCfg.std_type: Literal["scalar", "log"]`.

> **결과 (2026-09-17): ★ 이 고침은 크래시를 막지 못했습니다 ★**
>
> ```
> scalar  →  236번째에서 죽음
> log     →  243번째에서 죽음     (같은 오류, 같은 줄)
> ```
>
> `agent.yaml` 에 `std_type: log` 가 찍혔고, `model_200.pt` 안의 이름도
> `distribution.log_std_param` 입니다 — **제대로 걸려 있었습니다.**
> 그런데 `exp()` 의 결과는 음수가 될 수 없으므로, 터진 값은 음수가
> 아니라 **NaN** 입니다. std 파라미터화는 애초에 범인이 아니었습니다.
>
> 이 줄은 그대로 둡니다 (해롭지 않고, log 쪽이 수치적으로 낫습니다).
> 진짜 원인은 아래 「고친 곳 5」 의 감시 장치로 쫓는 중입니다.
> 자세한 추론 과정은 README 37번에 있습니다.

**★ 30초 확인 — 이제 다섯 가지 ★**

```powershell
.\isaaclab.bat train --rl_library rsl_rl `
    --task Isaac-Velocity-Rough-Unitree-Go2-Guide-v0 `
    --num_envs 64 --max_iterations 2
```

```
관측   shape: (48,) · height_scan 없음
상     base_height_l2  −30.0
지형   terrain_levels
탐색   Mean action std 가 첫 줄에 1.00          ← 새로 생긴 항목
속도   Steps per second 가 10만 위             ← 광선 줄이기가 먹었는가
```

마지막 줄이 2.7만 그대로면 엉뚱한 곳을 줄인 것입니다.
**2.7만 그대로였습니다** — 위 (가) 의 결과 상자를 보십시오.

---

## 고친 곳 5 — rsl_rl 의 ppo.py 에 NaN 감시 (2026-09-17)

★ 이건 Isaac Lab 이 아니라 **rsl_rl 라이브러리**를 고친 것입니다. ★
Isaac Sim 을 다시 깔면 함께 사라집니다.

```
C:\isaacsim\kit\python\Lib\site-packages\rsl_rl\algorithms\ppo.py
```

**왜 여기인가**

`normal expects all elements of std >= 0.0` 로 죽습니다. 그런데
`std_type = "log"` 라 std = `exp(log_std)` 이고, exp 는 음수를 못
만듭니다. 그러니 터진 값은 **NaN** 입니다. 파라미터가 NaN 이 되는
길은 `optimizer.step()` 하나뿐이므로, **그 직전**에 봅니다.

★ 반드시 `clip_grad_norm_` **앞**에서 봐야 합니다. NaN 이 하나라도
있으면 clip 계수가 `1.0 / (NaN + 1e-6)` = NaN 이 되어 멀쩡한
기울기까지 전부 물듭니다. 뒤에서 보면 범인을 못 찾습니다.

**고치는 법**

`update()` 안, 이 세 줄을 찾습니다 (원본 374~376줄) —

```python
            # Apply the gradients for PPO
            nn.utils.clip_grad_norm_(self.actor.parameters(), self.max_grad_norm)
            nn.utils.clip_grad_norm_(self.critic.parameters(), self.max_grad_norm)
            self.optimizer.step()
```

이것을 통째로 아래로 바꿉니다 (`chain` 과 `TensorDict` 는 파일 위쪽에
이미 import 되어 있습니다) —

```python
            # ===== robotdog00 고침 (2026-09-17): NaN/inf 기울기 감시 =====
            # 원본은 아래 clip_grad_norm_ 두 줄 + self.optimizer.step() 뿐이었습니다.
            # 되돌리려면 같은 폴더의 ppo.py.robotdog00-orig 를 ppo.py 로 덮어쓰면 됩니다.
            #
            # 왜 여기인가: std 는 exp(log_std) 라 음수가 될 수 없으므로
            # "std >= 0.0" 오류는 log_std 가 NaN 이라는 뜻이고, 파라미터가
            # NaN 이 되는 길은 optimizer.step() 하나뿐입니다. 그 직전에 봅니다.
            # ★ clip_grad_norm_ 앞에서 봐야 합니다. NaN 이 하나라도 있으면
            #    clip 계수가 NaN 이 되어 전부 물들기 때문입니다.
            _bad = []
            for _n, _p in chain(self.actor.named_parameters(), self.critic.named_parameters()):
                if _p.grad is not None and not bool(torch.isfinite(_p.grad).all()):
                    _bad.append((_n, _p.grad))
            if _bad:
                PPO._nan_skips = getattr(PPO, "_nan_skips", 0) + 1
                if PPO._nan_skips <= 5:

                    def _rng(name, t):
                        try:
                            t = t.detach().float().reshape(-1)
                            fin = torch.isfinite(t)
                            n_bad = int((~fin).sum())
                            n_nan = int(torch.isnan(t).sum())
                            if int(fin.sum()) == 0:
                                return "      %-18s ★전부 비정상 (NaN %d)" % (name, n_nan)
                            g = t[fin]
                            return "      %-18s %s min %-11.4g max %-11.4g |최대| %-11.4g 비정상 %d (NaN %d)" % (
                                name,
                                "정상  " if n_bad == 0 else "★나쁨",
                                g.min().item(),
                                g.max().item(),
                                g.abs().max().item(),
                                n_bad,
                                n_nan,
                            )
                        except Exception as _e:  # noqa: BLE001
                            return "      %-18s (검사 실패: %r)" % (name, _e)

                    print("\n[NaN 감시 #%d] 기울기가 비정상입니다. 이번 minibatch 만 버립니다." % PPO._nan_skips, flush=True)
                    print("  -- 나쁜 기울기를 가진 파라미터 --", flush=True)
                    for _n, _g in _bad:
                        print(_rng("grad " + _n, _g), flush=True)
                    print("  -- 순전파 값들 (여기가 전부 정상이면 원인은 역전파/옵티마이저) --", flush=True)
                    with torch.no_grad():
                        print(_rng("ratio", ratio), flush=True)
                        print(_rng("log_prob 새", actions_log_prob), flush=True)
                        print(_rng("log_prob 옛", batch.old_actions_log_prob), flush=True)
                        print(_rng("advantages", batch.advantages), flush=True)
                        print(_rng("entropy", entropy), flush=True)
                        print(_rng("values", values), flush=True)
                        print(_rng("returns", batch.returns), flush=True)
                        print(_rng("actions", batch.actions), flush=True)
                        print(_rng("std", self.actor.output_std), flush=True)
                        try:
                            _obs = batch.observations
                            if isinstance(_obs, TensorDict):
                                for _k in _obs.keys():
                                    print(_rng("obs/" + str(_k), _obs[_k]), flush=True)
                            else:
                                print(_rng("obs", _obs), flush=True)
                        except Exception as _e:  # noqa: BLE001
                            print("      obs 검사 실패: %r" % (_e,), flush=True)
                        print(
                            "      loss %.6g  surrogate %.6g  value %.6g  lr %.3g"
                            % (float(loss), float(surrogate_loss), float(value_loss), self.learning_rate),
                            flush=True,
                        )
                        _pbad = [
                            _n
                            for _n, _p in chain(self.actor.named_parameters(), self.critic.named_parameters())
                            if not bool(torch.isfinite(_p).all())
                        ]
                        print("      파라미터 자체가 비정상인 것: %s" % (_pbad if _pbad else "없음 (아직 깨끗함)"), flush=True)
                elif PPO._nan_skips % 50 == 0:
                    print("[NaN 감시] 누적 %d 번 건너뜀" % PPO._nan_skips, flush=True)
                # 파라미터는 건드리지 않고 이번 minibatch 만 버린다
                self.optimizer.zero_grad(set_to_none=True)
                continue
            # Apply the gradients for PPO
            nn.utils.clip_grad_norm_(self.actor.parameters(), self.max_grad_norm)
            nn.utils.clip_grad_norm_(self.critic.parameters(), self.max_grad_norm)
            self.optimizer.step()
            # ===== 고침 끝 =====
```

**되돌리는 법**

같은 폴더에 원본을 `ppo.py.robotdog00-orig` 로 백업해 뒀습니다.

```powershell
cd C:\isaacsim\kit\python\Lib\site-packages\rsl_rl\algorithms
Copy-Item ppo.py.robotdog00-orig ppo.py -Force
```

**무엇을 기대하는가**

```
[NaN 감시 #1] 기울기가 비정상입니다. 이번 minibatch 만 버립니다.
  -- 나쁜 기울기를 가진 파라미터 --
      grad distribution.log_std_param  ★나쁨 …
  -- 순전파 값들 (여기가 전부 정상이면 원인은 역전파/옵티마이저) --
      ratio            정상   min …  max …
      …
      파라미터 자체가 비정상인 것: 없음 (아직 깨끗함)
```

- 「나쁜 기울기」 목록이 **한 파라미터뿐**이면 그 항(예: 엔트로피)이 범인입니다.
- **전부**면 공통 원인 — 손실 쪽입니다. 그때 `ratio` 의 |최대| 를 보십시오.
- 「순전파 값들」이 전부 정상이면 역전파나 Adam 쪽입니다.

버린 뒤에도 학습은 계속 갑니다. 1500번 중 한두 minibatch 를 버리는
것은 무시할 만합니다. 누적 횟수가 수십 번이 되면 그건 진짜 발산이니
`[NaN 감시] 누적 N 번 건너뜀` 줄을 보십시오.

## Isaac Lab 을 다시 깔았다면

위의 「고친 곳 1·2·3·4」 와 그 아래 「고칠 것」 을 순서대로 다시 붙여넣으면 끝입니다.
넷 다 **파일 맨 끝에 덧붙이는 것**이라 기존 내용과 부딪히지 않습니다.

**「고친 곳 5」 는 Isaac Lab 이 아니라 Isaac Sim 안의 rsl_rl 입니다.**
Isaac Lab 만 다시 깔았다면 5번은 그대로 살아 있습니다. Isaac Sim 을
다시 깔았다면 5번도 다시 붙여야 합니다.

그리고 설치에서 걸렸던 것들은 README 33-4 에 적어뒀습니다 —
`_isaac_sim` 심볼릭 링크, `-i "rl[rsl-rl]"` (`-i rsl_rl` 은 조용히
거부됩니다), PowerShell 의 `.\` 등입니다.
