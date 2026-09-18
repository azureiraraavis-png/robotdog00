# -*- coding: utf-8 -*-
"""시뮬레이터의 로봇개를 걷게 하고, **실기체와 같은 값**을 잽니다.

  ★ 무엇을 재는가 ★

    실기체에서 2026-09-14 에 잰 것과 같은 셋입니다 —

        앞으로 간 거리 · 옆으로 밀린 양 · 몸이 돌아간 각

    그리고 옆으로 밀린 양을 **둘로 쪼갭니다** —

        돌아서 생긴 휨   몸이 돌았으니 그만큼 옆으로 간 것 (당연한 몫)
        미끄러진 휨      돎으로 설명이 안 되는 나머지 (게걸음)

    이 둘은 고치는 방법이 다릅니다. 앞의 것은 방향을 되먹임으로 잡으면
    되고, 뒤의 것은 발이 땅을 못 붙드는 것이라 걸음 자체를 고쳐야 합니다.
    총량만 보면 하나가 줄고 하나가 늘어도 "좋아졌다" 로 읽힙니다.

  ★ 이 숫자로 실기체를 보정하지 마십시오 ★

    실기체는 유니트리 공장 컨트롤러가 걷습니다. 여기서 걷는 것은 학습된
    정책입니다. **서로 다른 두 보행기의 버릇**이라, 한쪽을 곧게 맞춰도
    다른 쪽은 안 곧아집니다. 실기체의 직진은 walk_straight.py 가 따로
    잡고 있고 (README 32-4), 저수준 제어가 PRO 에 없으니 여기서 배운
    정책이 그 기체로 갈 일도 없습니다 (README 32-0).

    그러면 왜 재는가 — **시뮬레이터가 현실을 얼마나 못 흉내내는지**
    알아야, 나중에 시뮬레이터에서 계단을 오르는 걸 보였을 때 그것이
    무엇을 뜻하고 무엇을 뜻하지 않는지 말할 수 있기 때문입니다.
    보정값을 옮기는 용도가 아닙니다.

  ★ 이 파일은 공식 예제에서 **출발**했습니다 ★

    C:\\isaacsim\\standalone_examples\\api\\isaacsim.robot.policy.examples\\
    spot_standalone.py 의 뼈대를 그대로 두고, 잣대만 얹었습니다.

    왜 그랬는가 —
      처음에는 제가 World 를 만들어 for 문에서 world.step() 을 돌렸습니다.
      로봇이 주저앉았습니다. 공식 예제를 열어 차례를 배운 뒤 "같게" 다시
      썼는데 또 주저앉았습니다. Spot 을 태워봤더니 **공식 예제에서 멀쩡히
      걷던 그 Spot 도** 제 뼈대에선 발라당 넘어졌습니다. 이득은 60으로
      제대로 들어가 있었고, 무대 시계도 돌고 있었고, 관절은 12개가
      읽혔는데, 다리가 한 번도 안 움직였습니다.

      네 번 "예제와 같다"고 판단했고 네 번 다 틀렸습니다. 눈으로 견주는
      것을 그만두고 **돌아가는 파일에서 시작해 최소한만 고치는** 쪽으로
      바꿨습니다. 이게 이 파일이 함수 없이 위에서 아래로 흐르는 이유입니다
      — 보기에 투박하지만, 공식 예제와의 차이를 눈으로 셀 수 있습니다.

  ★ 공식 예제에서 바꾼 것은 이것뿐입니다 ★

      1. 로봇을 고를 수 있게 (go2 / spot)
      2. 걷는 동안 시작·끝 자리를 재서 실기체와 같은 방식으로 셈하기
      3. headless 를 고를 수 있게

  ★ 오늘의 범인 — 제가 넣은 워밍업 ★

    "실기체 시험처럼 1.5초 제자리에 서 있다가 출발" 이라고 워밍업 동안
    [0,0,0] 을 줬습니다. 로봇이 매번 발버둥치다 엎어졌습니다.

    **이 정책에게 '제자리에 서 있기'는 학습된 동작이 아닙니다.**
    걸으라고 하면 걷고, 가만있으라고 하면 무너집니다.

    이걸 찾는 데 열 번 넘게 돌렸습니다. 그 사이 관절 이득을 읽고,
    물리 엔진 이름을 찍고, 무대 시계를 붙이고, 콜백 호출 횟수를 세고,
    로봇을 Spot 으로 바꿔보고, 뼈대를 통째로 두 번 다시 썼습니다.
    전부 멀쩡했습니다. 범인은 제가 **로봇을 배려한다고 넣은 한 줄**
    이었고, 그건 제가 고친 곳이 아니라 제가 더한 곳에 있었습니다.

    교훈: 공식 예제와 다른 곳을 찾을 때, **내가 뺀 것**만 보지 말고
    **내가 더한 것**도 보아야 합니다.

  쓰는 법 (★ Isaac Sim 의 파이썬으로 ★)

      C:\\isaacsim\\python.bat D:\\workspace_raraavis\\robotdog00\\sim_go2.py

      옵션
        --robot spot    Go2 대신 Spot (공식 예제가 쓰는 것 — 견주기용)
        --gui           화면을 띄웁니다
        --seconds 3     몇 초 걸을지 (실기체 시험과 같게)
        --speed 0.31    m/s (실기체가 스틱 0.3 에서 내던 속도)
        --high 0.35     놓는 높이 m (기본: go2 0.4 · spot 0.8)
        --engine newton 물리 엔진을 바꿉니다 (정책 파일도 같이 바뀝니다)
        --look          자산 서버에 어떤 Unitree 로봇이 있는지 보고 끝냅니다
        --usd <경로>    로봇 자산을 바꿔 끼웁니다 (Menagerie 판 대신)
        --policy <경로> 정책 파일을 바꿔 끼웁니다 (Isaac Lab 에서 받은 것)
        --gains 25,0.5,23.5   관절 이득을 Isaac Lab 이 학습한 값으로
        --warm 2.0      걸음이 자리잡기를 몇 초 기다릴지
                        ※ 이 동안에도 **걷습니다.** 서 있으라고 하면
                          이 정책은 무너집니다 (아래 설명).
        --yaw 180       놓을 때 돌려세웁니다 (좌우 비대칭을 가릅니다)
        --hold          ★ 방향 되먹임을 켭니다 — 학습할 때와 같은 조건 ★
                        ※ 이걸 안 켜면 정책이 **배운 적 없는 상황**에서
                          재게 됩니다 (아래 설명).
"""

import argparse
import math
import sys

# ★ 파이프로 넘겨도 한글이 안 깨지게 ★
#
#   2026-09-16 — 문턱 높이를 쓸어보려고 출력을 `| Select-String` 으로
#   걸렀더니 통째로 비었습니다. 화면에 바로 찍을 때는 멀쩡했는데요.
#
#   파이썬은 출력이 **파이프로 가면** 글자표를 윈도 기본(cp949)으로
#   바꿉니다. 그러다 이 파일이 즐겨 쓰는 '—' 에서 터졌고, 오류는
#   `2>$null` 이 삼켜서 빈 화면만 남았습니다.
#
#   쓸어보기는 앞으로도 계속 할 일이라 여기서 못박습니다.
#   (밖에서 $env:PYTHONIOENCODING="utf-8" 로도 되지만, 잊어버립니다.)
for _out in (sys.stdout, sys.stderr):
    try:
        _out.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass            # 아주 옛 파이썬이면 그냥 둡니다

# ── 옵션부터 (SimulationApp 을 만들기 전에) ─────────────────
ap = argparse.ArgumentParser(description="시뮬레이터의 개를 걷게 하고 잽니다")
ap.add_argument("--robot", choices=["go2", "spot"], default="go2")
ap.add_argument("--gui", action="store_true")
ap.add_argument("--seconds", type=float, default=3.0)
ap.add_argument("--speed", type=float, default=0.31)
ap.add_argument("--warm", type=float, default=2.0,
                help="걸음이 자리잡기를 기다리는 초 (이 동안도 걷습니다)")
ap.add_argument("--device", type=str, choices=["cpu", "cuda"], default="cpu")
# ★ 놓는 높이를 만질 수 있게 ★
#   Spot 은 0.8 에서 떨어뜨려도 버티고 일어섰는데 Go2 는 0.4 에서 못
#   일어섭니다. 너무 높아 세게 떨어지는 것인지, 너무 낮아 땅에 낀 것인지
#   코드를 안 고치고 재볼 수 있어야 합니다.
ap.add_argument("--high", type=float, default=None,
                help="놓는 높이 m (기본: go2 0.32 · spot 0.8). 0.38 부터 휨이 망가지고 0.40 이면 서는 정책이 뒤집힙니다")
# ★ 로봇을 돌려세울 수 있게 ★
#
#   2026-09-15, 정책 셋을 쟀더니 **셋 다 오른쪽으로** 돌았습니다
#   (−6.3 · −3.3 · −6.2 도/m). 1판과 2판은 상이 다른 별개의 학습이었는데도
#   부호가 안 바뀝니다. 우연이라기엔 좀 그렇습니다.
#
#   가르는 법은 32-4 에서 실기체에 썼던 그대로입니다 — **돌려세우고 다시
#   잰다.** 재는 값은 이미 몸 기준(출발할 때 본 방향 기준)이라, 돌려세워도
#   숫자의 뜻은 그대로입니다.
#
#       몸 기준으로 여전히 오른쪽   → 로봇이나 정책의 버릇
#       부호가 뒤집힌다             → 시험대나 바닥의 좌우 비대칭
#
#   뒤집히면 지금까지 잰 휨 숫자를 전부 다시 읽어야 합니다.
ap.add_argument("--yaw", type=float, default=0.0,
                help="놓을 때 바라보는 방향 (도). 180 이면 반대로 세웁니다")
# ★ 방향 되먹임 ★
#
#   2026-09-16, --yaw 180 으로 재보니 휨이 **몸을 따라왔습니다**. 바닥도
#   시험대도 아니고 로봇 자신의 버릇입니다. 그런데 왜 그런 버릇이 생겼나 —
#
#   학습 설정에 `heading_command=True`, `rel_heading_envs=1.0` 이 있습니다.
#   정책은 **한 번도 '혼자 힘으로 곧게 가라'는 요구를 받은 적이 없습니다.**
#   늘 "저 방향을 봐라" 를 받았고, 틀어지면 회전 명령이 되돌려줬습니다.
#   그러니 열린 고리에서의 치우침은 벌점을 받지 않습니다. 자유롭게 남은
#   값이고, 학습마다 다른 값으로 굳습니다 (−6.3 · −3.3 · −6.2).
#
#   즉 지금까지 우리는 **정책이 배운 적 없는 상황**에서 재고 있었습니다.
#   실제로 쓸 때도 되먹임은 붙습니다 (실기체의 walk_straight.py 가 그것).
#
#   그래서 학습 설정과 같은 식을 넣습니다 —
#
#       wz = clip(heading_control_stiffness × 방향오차, ang_vel_z 범위)
#          = clip(0.5 × 오차, −1.0, +1.0)
#
#   목표 방향은 **출발할 때 본 방향**입니다. "저 쪽으로 곧게 가라".
ap.add_argument("--hold", action="store_true",
                help="방향 되먹임을 켭니다 (학습할 때와 같은 조건)")
# ★ 문턱 ★
#
#   교수님이 계단보다 먼저 하라고 하신 것. 실측 10 cm 입니다 (README 32-8 —
#   낮은 쪽에서 −0.02, 높은 쪽에서 −0.12). Go2 는 15~20 cm 까지 넘으니
#   물음은 "넘을 수 있는가" 가 아니라 **"멈추지 않고 넘는가"** 입니다.
#
#   sim_world.py 의 3층 전체를 부르지 않고 **턱 하나만** 놓습니다.
#   벽·사물함·계단이 같이 들어오면 무엇이 원인인지 못 가립니다.
#   높이를 바꿔가며 쓸어보면 어디서 무너지는지 나옵니다.
ap.add_argument("--sill", type=float, default=0.0,
                help="앞길에 턱을 놓습니다. 높이 m (실측 문턱은 0.10)")
ap.add_argument("--sill-at", type=float, default=1.0, dest="sill_at",
                help="턱의 앞면이 몇 m 앞인지 (기본 1.0)")
ap.add_argument("--sill-deep", type=float, default=0.30, dest="sill_deep",
                help="턱의 깊이 m — 건너갈 윗면의 길이 (기본 0.30)")
# ★ 자취를 얼마나 촘촘히 찍을지 ★
#   0.5초마다 찍으면 발이 걸렸다 빠지는 일은 줄 사이에서 다 일어납니다.
#   턱을 볼 때는 0.1 로 내려야 무슨 일이 있었는지 보입니다.
ap.add_argument("--feet", action="store_true",
                help="자취에 발 네 개의 x·z 를 함께 찍습니다 (앞쪽부터). 못 읽으면 스스로 끕니다"
                     " ※ go2 에는 발 마디가 없습니다 (calf 에 붙은 충돌 도형) — 안 됩니다")
ap.add_argument("--nosleep", action="store_true",
                help="PhysX 가 로봇을 재우지 못하게 합니다 (굳음이 물리 탓인지 가리는 용도)")
ap.add_argument("--probe", action="store_true",
                help="문턱 앞에서 +x 로 광선을 쏴 **실제로 막히는 자리**를 찍습니다")
ap.add_argument("--trace", type=float, default=0.5,
                help="자취를 몇 초마다 찍을지 (기본 0.5 · 턱 볼 때는 0.1)")
ap.add_argument("--hold-gain", type=float, default=0.5,
                dest="hold_gain",
                help="heading_control_stiffness (설정 기본값 0.5)")
ap.add_argument("--hold-max", type=float, default=1.0,
                dest="hold_max",
                help="회전 명령 한계 rad/s (ang_vel_z 범위 기본값 1.0)")
ap.add_argument("--engine", choices=["auto", "physx", "newton"], default="auto",
                help="물리 엔진. Go2 는 MuJoCo 쪽 자산이라 newton 이 맞을 수 있습니다")
# ★ 자산을 바꿔 끼울 수 있게 ★
#   go2.py 는 기본으로 Mujoco Menagerie 판을 씁니다. NVIDIA 가 직접 만든
#   Unitree 자산이 /Isaac/Robots/Unitree/ 에 따로 있고 (H1 예제가 거기서
#   가져다 씁니다), Go2 도 있을 수 있습니다. 있으면 그걸로 바꿔 끼웁니다.
ap.add_argument("--usd", default=None,
                help="로봇 자산 경로. 자산폴더 뒤부터 (예 /Isaac/Robots/Unitree/Go2/go2.usd)")
ap.add_argument("--look", nargs="?", const="", default=None,
                help="자산 서버를 둘러보고 끝냅니다. 경로를 주면 그 폴더를 봅니다")
# ★ 정책 파일을 바꿔 끼울 수 있게 ★
#   Isaac Sim 에 딸려온 physx_policy.pt 로는 Go2 가 기어다닙니다 (자산을
#   바꿔도 똑같이 0.12 m). Isaac Lab 에서 받은 policy.pt 를 여기에 물립니다.
#   env_config 는 안 건드립니다 — go2.py 는 둘 중 하나만 줘도 나머지는
#   기본값에서 채웁니다. 관절 이득·기본자세·주기는 그대로 쓰겠다는 뜻입니다.
ap.add_argument("--policy", default=None,
                help="정책 파일(.pt)의 전체 경로. Isaac Lab 이 내보낸 것")
# ★ 관절을 미는 힘을 바꿀 수 있게 ★
#   Isaac Lab 의 Go2 는 파이썬에서 모터를 흉내 내 토크를 직접 넣습니다 —
#   DCMotorCfg(stiffness=25, damping=0.5, effort_limit=23.5).
#   토크 법칙을 읽어보니 평범한 PD 에 상한만 씌운 것이라, 엔진 PD 로
#   거의 그대로 흉내 낼 수 있습니다 (상한은 보통 걸음에서 안 닿습니다).
#   그러니 이 셋만 맞춰주면 됩니다.
ap.add_argument("--gains", default=None,
                help="강성,감쇠,힘제한 (예: 25,0.5,23.5). 깨운 직후에 넣습니다")
args, unknown = ap.parse_known_args()

print("=" * 70)
print(" 시뮬레이터의 개 — 실기체와 같은 값을 잽니다")
print("=" * 70)
print(f" {args.robot} · 걸음 잡기 {args.warm:.1f}초 → 재기 {args.seconds:.1f}초"
      f" · {args.speed:.2f} m/s · {args.device}")
print(" ※ 처음 켜면 몇 분 걸릴 수 있습니다.")
print()
sys.stdout.flush()

# ★ SimulationApp 을 **먼저** 만들어야 아래 것들이 가져와집니다 ★
#   Kit 은 앱이 켜질 때 확장을 올립니다. 위에 몰아서 import 하면 죽습니다.
#   공식 예제도 이 모양입니다 — 보기에 이상하지만 이게 맞습니다.
from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": not args.gui})

import carb
import numpy as np
import omni.timeline
from isaacsim.core.deprecation_manager import import_module
from isaacsim.core.experimental.utils.stage import define_prim
from isaacsim.core.rendering_manager import RenderingManager
from isaacsim.core.simulation_manager import SimulationManager
from isaacsim.core.simulation_manager.impl.isaac_events import IsaacEvents
from isaacsim.robot.policy.examples.robots import (Go2FlatTerrainPolicy,
                                                   SpotFlatTerrainPolicy)
from isaacsim.storage.native import get_assets_root_path

torch = import_module("torch")

first_step = True
woke = 0                      # initialize() 를 몇 번 불렀나
drove = 0                     # forward() 를 몇 번 불렀나
hurt = None                   # 콜백 안에서 터진 것 (Kit 이 삼킵니다)


# ── 로봇을 깨우고 움직이는 곳 ───────────────────────────────
#
#   ★ 공식 예제의 reset_needed 를 **걷어냈습니다** ★
#
#     공식 예제는 이렇게 되어 있습니다 —
#
#         if first_step:      robot.initialize()
#         elif reset_needed:  reset_needed = False; first_step = True
#         else:               robot.forward(...)
#
#     그리고 바깥 while 문은 무대가 안 돌 때 reset_needed = True 를 켭니다.
#     사람이 무대를 멈췄다 다시 켜는 것을 받아주는 장치입니다.
#
#     그런데 이게 한 번이라도 어긋나면 —
#       깨우기 → (reset_needed) 건너뛰고 다시 first_step 켜기 → 깨우기 → …
#     이렇게 오가면서 **forward() 가 영영 안 불립니다.** 이득은 제대로
#     들어가 있고, 관절도 읽히고, 무대 시계도 도는데, 명령만 안 닿습니다.
#     2026-09-14 에 본 모든 숫자가 정확히 이 모양이었습니다.
#
#     우리는 무대를 멈췄다 켜는 일이 없습니다. 그러니 그 장치는 우리에게
#     쓸모가 없고, 대신 조용히 망가뜨릴 수만 있습니다. 걷어냅니다.
#
#   ★ 그리고 셉니다 ★
#     '불렸겠지' 라고 여기고 세 판을 헛짚었습니다. 세어두면 다음엔
#     그 자리에서 갈립니다.
def on_physics_step(step_size: float, context: object) -> None:
    """첫 걸음에 깨우고, 그 뒤로는 명령을 넣습니다."""
    global first_step, woke, drove, hurt
    try:
        if first_step:
            robot.initialize()
            first_step = False
            woke += 1
            # ★ 이득은 깨운 **뒤에** 덮어씁니다 ★
            #   initialize() 가 설정 파일의 값을 넣으므로, 그 전에 넣으면
            #   덮어써집니다. 그리고 넣은 뒤 다시 읽어서 정말 들어갔는지
            #   확인합니다 — 오늘 엔진 바꾸기에서 '시킨 것'과 '된 것'이
            #   다른 걸 겪었습니다.
            if args.nosleep:
                no_sleep(robot.robot)
            if args.probe:
                probe_forward()
            if args.gains:
                gains_said.append(put_gains(robot.robot, args.gains))
        else:
            robot.forward(step_size, base_command)
            drove += 1
    except Exception:
        if hurt is None:
            import traceback
            hurt = traceback.format_exc()


gains_said = []


# ─────────────────────────────────────────────────────────────
#  부딪힘판이 **실제로** 어디 있는지 (2026-09-18, README 42)
#
#  왜: 개가 1 cm 짜리 턱 앞에서도 멈춥니다. 상자의 **그림**은 읽어서
#      확인했지만 (BBoxCache), 그건 눈에 보이는 상자입니다.
#      **부딪히는 면은 한 번도 확인한 적이 없습니다.**
#      추론하지 말고 광선을 쏴서 어디서 막히는지 직접 읽습니다.
#
#  쏘는 자리는 턱 앞면에서 1 m 뒤. 그러니 **1.000 이 나와야 맞습니다.**
def probe_forward():
    """턱 앞면에서 1 m 뒤에서 +x 로 쏩니다. 높이별로 처음 막히는 거리."""
    try:
        from omni.physx import get_physx_scene_query_interface
        q = get_physx_scene_query_interface()
    except Exception as e:
        print(" [탐침] ✖ physx 질의 인터페이스를 못 찾았습니다 — 끕니다 (%r)" % e)
        return

    if args.sill <= 0:
        print(" [탐침] 턱이 없습니다 — 바닥만 봅니다.")
    x0 = sill_near - 1.0
    print(" [탐침] x=%.3f 에서 +x 로 쏩니다 (턱 앞면은 %.3f — **1.000 이 맞는 값**)"
          % (x0, sill_near))
    for z in (0.005, 0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
        try:
            hit = q.raycast_closest((float(x0), 0.0, float(z)),
                                    (1.0, 0.0, 0.0), 6.0)
        except Exception as e:
            print("        z %.3f → 쏘다가 실패 (%r)" % (z, e))
            continue
        if isinstance(hit, dict) and hit.get("hit"):
            d = float(hit.get("distance", float("nan")))
            who = str(hit.get("collision", hit.get("rigidBody", "?")))
            mark = ""
            if abs(d - 1.0) > 0.02:
                mark = "   ← 1.000 이 아닙니다"
            print("        z %.3f → %.3f m 앞에서 막힘  %s%s"
                  % (z, d, who.rsplit("/", 1)[-1], mark))
        else:
            print("        z %.3f → 6 m 안에 아무것도 없음  (턱 윗면보다 높음)" % z)


# ─────────────────────────────────────────────────────────────
#  PhysX 가 로봇을 재우지 못하게 (2026-09-18, README 42)
#
#  왜: 턱 앞에서 멎은 판들이 **11초 동안 소수점 셋째 자리까지 완전히
#      같습니다.** 550번의 정책 판단 동안 한 비트도 안 움직입니다.
#      살아 있는 물리라면 마지막 자리는 흔들립니다. PhysX 는 움직임이
#      임계값 아래로 떨어진 물체를 **계산에서 빼버립니다(재웁니다)**.
#      학습판에서는 이런 멎음이 없습니다 (한 판 1000/1000 걸음).
#
#  ★ 이것도 **물어봅니다.** 박아넣지 않습니다 — --yaw · --policy · --feet
#    과 같은 방식입니다. 못 하면 한 줄 말하고 그냥 넘어갑니다.
def no_sleep(art):
    """재우기를 끕니다. 무엇으로 껐는지 찍습니다."""
    # (1) 관절체가 직접 주는 이름
    for name in ("set_sleep_thresholds", "set_sleep_threshold"):
        fn = getattr(art, name, None)
        if fn is None:
            continue
        for val in (0.0, np.zeros(1, dtype=np.float32)):
            try:
                fn(val)
                print(" [잠] 재우기를 껐습니다 — %s(%r)" % (name, val))
                return True
            except Exception:
                continue

    # (2) 안에 든 physx 뷰
    for holder in ("_physics_articulation_view", "_physics_view",
                   "_articulation_view", "_view"):
        view = getattr(art, holder, None)
        if view is None:
            continue
        for name in ("set_sleep_thresholds", "set_sleep_threshold"):
            fn = getattr(view, name, None)
            if fn is None:
                continue
            for val in (np.zeros(1, dtype=np.float32), 0.0):
                try:
                    fn(val)
                    print(" [잠] 재우기를 껐습니다 — %s.%s(%r)"
                          % (holder, name, val))
                    return True
                except Exception:
                    continue

    # (3) USD 속성을 직접
    try:
        from pxr import PhysxSchema
        import isaacsim.core.utils.stage as _stage
        paths = getattr(art, "_link_paths", None) or []
        flat = [p for g in paths for p in (g if isinstance(g, (list, tuple)) else [g])]
        if flat:
            root = flat[0]
            prim = _stage.get_current_stage().GetPrimAtPath(root)
            api = PhysxSchema.PhysxArticulationAPI.Get(prim.GetStage(), prim.GetPath())
            if api:
                api.CreateSleepThresholdAttr().Set(0.0)
                print(" [잠] 재우기를 껐습니다 — USD PhysxArticulationAPI %s" % root)
                return True
    except Exception:
        pass

    names = sorted({n for n in dir(art) if "sleep" in n.lower()})
    print(" [잠] ✖ 재우기를 끄는 법을 못 찾았습니다 — 그냥 갑니다.")
    print("      물어본 것: 관절체 이름 2 · physx 뷰 4곳 · USD 속성")
    print("      %s 에 있는 sleep 관련: %s" % (type(art).__name__, names or "없음"))
    return False


def put_gains(art, spec):
    """강성·감쇠·힘제한을 넣고, **다시 읽어서** 무엇이 들어갔는지 돌려줍니다."""
    import numpy as _np
    want = [float(x) for x in spec.replace(" ", "").split(",")]
    while len(want) < 3:
        want.append(None)
    kp, kd, eff = want[0], want[1], want[2]
    n = None
    try:
        n = int(_np.asarray(art.get_dof_gains()).reshape(-1).size // 2) or None
    except Exception:
        pass
    n = n or 12
    lines = []

    def try_set(names, value, what):
        if value is None:
            return
        for name in names:
            fn = getattr(art, name, None)
            if not callable(fn):
                continue
            for arg in ([_np.full((1, n), value, dtype=_np.float32)],
                        [_np.full(n, value, dtype=_np.float32)],
                        [value]):
                try:
                    fn(*arg)
                    lines.append(f"{what} ← {value:g}  ({name})")
                    return
                except Exception:
                    continue
        lines.append(f"{what} ✖ 넣을 방법을 못 찾았습니다")

    # ★ 이 판은 강성·감쇠를 **하나로 묶어** 다룹니다 ★
    #   2026-09-15: set_dof_stiffnesses / set_dof_dampings 를 짐작해서 썼다가
    #   둘 다 "못 찾았습니다" 가 나왔습니다. 읽는 쪽이 get_dof_gains 하나인
    #   것을 이미 봤으면서 넣는 쪽만 따로 있을 거라고 생각했습니다.
    #   묶음부터 해보고, 안 되면 따로따로 해봅니다.
    done_pair = False
    if kp is not None or kd is not None:
        fn = getattr(art, "set_dof_gains", None)
        if callable(fn):
            kps = None if kp is None else _np.full((1, n), kp, dtype=_np.float32)
            kds = None if kd is None else _np.full((1, n), kd, dtype=_np.float32)
            for call in (lambda: fn(stiffnesses=kps, dampings=kds),
                         lambda: fn(kps, kds),
                         lambda: fn(stiffness=kps, damping=kds)):
                try:
                    call()
                    lines.append(f"강성·감쇠 ← {kp:g} / {kd:g}  (set_dof_gains)")
                    done_pair = True
                    break
                except Exception as e:
                    last = e
            if not done_pair:
                lines.append(f"set_dof_gains 는 있는데 안 먹습니다 — {last}")

    if not done_pair:
        try_set(("set_dof_stiffnesses", "set_dof_stiffness"), kp, "강성")
        try_set(("set_dof_dampings", "set_dof_damping"), kd, "감쇠")
    try_set(("set_dof_max_efforts", "set_dof_max_effort"), eff, "힘제한")

    # 묶음으로 읽는 쪽도 봅니다
    fn = getattr(art, "get_dof_gains", None)
    if callable(fn):
        try:
            got = fn()
            pair = got if isinstance(got, (tuple, list)) else [got]
            for label, one in zip(("강성", "감쇠"), pair):
                a = _np.asarray(one)
                try:
                    a = _np.asarray(one.numpy())
                except Exception:
                    pass
                a = a.reshape(-1)
                lines.append(f"{label} 확인 → {float(a.min()):g} ~ {float(a.max()):g}")
        except Exception as e:
            lines.append(f"get_dof_gains 로 되읽기 실패 — {type(e).__name__}")

    # 다시 읽기 — 시킨 것과 된 것은 다릅니다
    for name, what in (("get_dof_max_efforts", "힘제한"),):
        fn = getattr(art, name, None)
        if not callable(fn):
            continue
        try:
            got = fn()
            for how in (lambda x: x.numpy(),
                        lambda x: x.detach().cpu().numpy(),
                        lambda x: _np.asarray(x)):
                try:
                    got = how(got)
                    break
                except Exception:
                    continue
            arr = _np.asarray(got).reshape(-1)
            lines.append(f"{what} 확인 → {float(arr.min()):g} ~ {float(arr.max()):g}")
        except Exception:
            pass
    return lines


# ── 무대 ────────────────────────────────────────────────────
assets_root_path = get_assets_root_path()
if assets_root_path is None:
    carb.log_error("Could not find Isaac Sim assets folder")

prim = define_prim("/World/Ground", "Xform")
prim.GetReferences().AddReference(
    assets_root_path + "/Isaac/Environments/Grid/default_environment.usd")

define_prim("/World/PhysicsScene", "PhysicsScene")

# ── 문턱 ────────────────────────────────────────────────────
#
#   바닥 위에 상자 하나. 로봇은 원점에서 +x 를 보고 서니, 앞면이
#   sill_at 에 오도록 놓습니다. 윗면의 높이가 정확히 --sill 이 되게
#   가운데를 높이의 절반에 둡니다.
sill_near = args.sill_at
sill_far = args.sill_at + args.sill_deep
if args.sill > 0:
    from pxr import Gf, Usd, UsdGeom, UsdPhysics
    _sill = define_prim("/World/Sill", "Cube")
    _cube = UsdGeom.Cube(_sill)
    _cube.GetSizeAttr().Set(1.0)                   # −0.5 ~ +0.5 짜리를 늘립니다
    # ★ extent 도 같이 고쳐야 합니다 ★
    #   size 만 1 로 바꾸고 extent 를 그대로 두면 기본값 ±1 이 남습니다.
    #   그걸 읽는 쪽에서는 상자가 제가 적어준 것의 **두 배**가 됩니다.
    _cube.GetExtentAttr().Set([Gf.Vec3f(-0.5, -0.5, -0.5),
                               Gf.Vec3f(0.5, 0.5, 0.5)])
    _xf = UsdGeom.Xformable(_sill)
    _xf.ClearXformOpOrder()
    _xf.AddTranslateOp().Set(Gf.Vec3d(
        (sill_near + sill_far) / 2.0, 0.0, args.sill / 2.0))
    _xf.AddScaleOp().Set(Gf.Vec3f(args.sill_deep, 2.0, args.sill))
    UsdPhysics.CollisionAPI.Apply(_sill)           # 움직이지 않는 부딪힘판
    # ★ 적어준 대로 생겼는지 **읽어서** 확인합니다 ★
    #   넣었다고 들어간 게 아니라는 걸 이득에서 한 번, 명령 범위에서
    #   한 번 배웠습니다. 상자도 같습니다.
    _rng = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_]).ComputeWorldBound(_sill).ComputeAlignedRange()
    _lo, _hi = _rng.GetMin(), _rng.GetMax()
    print(f" [문턱] 시킨 것   x {sill_near:.3f}~{sill_far:.3f} · "
          f"z 0.000~{args.sill:.3f}")
    print(f"        생긴 것   x {_lo[0]:.3f}~{_hi[0]:.3f} · "
          f"y {_lo[1]:.3f}~{_hi[1]:.3f} · z {_lo[2]:.3f}~{_hi[2]:.3f}")
    if (abs(_lo[0] - sill_near) > 0.01 or abs(_hi[0] - sill_far) > 0.01
            or abs(_hi[2] - args.sill) > 0.005):
        print("        ✖ 시킨 것과 다릅니다 — 아래 숫자를 믿지 마십시오.")
    if args.yaw:
        print("        ✖ --yaw 와 같이 쓰면 턱을 등지고 걷습니다.")

# ── 물리 엔진 ───────────────────────────────────────────────
#
#   ★ 왜 이걸 만질 수 있게 하는가 ★
#
#     go2.py 원본에 이 줄이 있습니다 —
#
#         is_newton = active_engine == "newton"
#         policy_path = newton_policy.pt  if is_newton else  physx_policy.pt
#
#     **정책 파일이 엔진별로 둘입니다.** 그리고 자산도 엔진별 변형(variant)을
#     골라 씁니다 (_set_physics_variant).
#
#     두 로봇이 온 곳이 다릅니다 —
#       Spot  /Isaac/Robots/...                     NVIDIA 자체 자산
#       Go2   /Isaac/Samples/Mujoco_Menagerie/...   MuJoCo 쪽에서 가져온 것
#
#     Isaac Sim 6.0 의 새 엔진이 Newton 이고 Menagerie 는 원래 MuJoCo 계열이니,
#     Go2 는 Newton 쪽에서 더 손본 물건일 수 있습니다. 우리는 지금 physx 로만
#     돌려봤습니다. 바꿔보지 않고는 모릅니다.
#
#   ★ 이름을 박지 않습니다 ★
#     엔진을 바꾸는 함수 이름을 모릅니다. 있을 만한 것을 찾아 불러보고,
#     **무엇이 실제로 먹혔는지 말합니다.** 못 바꾸면 못 바꿨다고 합니다.
#     2026-09-15: 제 짐작 셋(set_physics_engine · set_active_physics_engine ·
#     use_physics_engine)이 다 빗나갔고, "못 찾으면 있는 것을 보여준다"고
#     해둔 덕에 진짜 이름이 나왔습니다 — **switch_physics_engine**.
#     이름을 박았더라면 '안 됩니다' 한 줄만 보고 끝났을 것입니다.
try:
    print(f" [엔진] 쓸 수 있는 것: "
          f"{SimulationManager.get_available_physics_engines()}")
except Exception as e:
    print(f" [엔진] 목록을 못 물어봤습니다 — {type(e).__name__}")

if args.engine != "auto":
    done = None
    for what in ("switch_physics_engine", "set_physics_engine",
                 "set_active_physics_engine", "use_physics_engine"):
        fn = getattr(SimulationManager, what, None)
        if callable(fn):
            try:
                fn(args.engine)
                done = what
                break
            except Exception as e:
                print(f" [엔진] {what}({args.engine}) 는 안 됩니다 — {e}")
    # ★ 불렀다고 바뀐 게 아닙니다 — 다시 읽어서 확인합니다 ★
    #   2026-09-15: switch_physics_engine 이 예외를 안 던지고 carb 로 오류만
    #   찍었습니다. 저는 '예외가 없으니 성공'으로 읽고 "골랐습니다" 라고
    #   보고했는데, **바로 아래 줄에 physx 라고 찍혀 있었습니다.**
    #   시킨 것과 된 것은 다릅니다. 시켰으면 다시 읽어봐야 합니다.
    if done:
        try:
            now_engine = SimulationManager.get_active_physics_engine()
        except Exception:
            now_engine = None
        if now_engine == args.engine:
            print(f" [엔진] {done} 로 {args.engine} 으로 바뀌었습니다")
        else:
            print(f" [엔진] ✖ {done} 을 불렀지만 **안 바뀌었습니다** — "
                  f"지금도 {now_engine} 입니다")
            print("        (이 판에 그 엔진이 안 깔려 있다는 뜻입니다)")
            done = "실패"
    if done is None:
        print(f" [엔진] ✖ 바꾸는 방법을 못 찾았습니다. 있는 것 중 engine 이")
        print("        들어간 것들: "
              + ", ".join(a for a in dir(SimulationManager)
                          if "engine" in a.lower()))
try:
    print(f" [엔진] 지금 도는 것: {SimulationManager.get_active_physics_engine()}")
except Exception:
    pass

RenderingManager.set_dt(8.0 / 200.0)
SimulationManager.set_physics_sim_device(args.device)
SimulationManager.set_physics_dt(1.0 / 200.0)

# ── 자산 서버 둘러보기 ──────────────────────────────────────
#
#   ★ Go2 자산이 하나뿐인지 확인합니다 ★
#     go2.py 는 Mujoco Menagerie 판을 기본으로 씁니다. 그런데 공식 H1
#     예제는 /Isaac/Robots/Unitree/H1/h1.usd 를 씁니다 — **NVIDIA 가 직접
#     만든 Unitree 자산이 따로 있다**는 뜻입니다. Go2 도 거기 있으면
#     Menagerie 판 대신 그걸 끼워볼 수 있습니다.
def peek(where):
    """자산 서버의 한 폴더에 뭐가 있는지."""
    try:
        import omni.client
        ok, entries = omni.client.list(where)
        if str(ok) != "Result.OK":
            return None
        return sorted(e.relative_path for e in entries)
    except Exception:
        return None


if args.look is not None:
    print()
    print("=" * 70)
    print(" 자산 서버에 있는 것")
    print("=" * 70)
    folders = ([args.look] if args.look else
               ["/Isaac/Robots/Unitree",
                "/Isaac/Robots",
                "/Isaac/Samples/Mujoco_Menagerie"])
    for folder in folders:
        got = peek(assets_root_path + folder)
        print()
        print(f" {folder}")
        if got is None:
            print("   ✖ 못 읽었습니다 (없거나 접근이 안 됩니다)")
        else:
            for name in got[:40]:
                print(f"   · {name}")
            if len(got) > 40:
                print(f"   … 그 밖에 {len(got) - 40}개")
    print()
    print(" ※ 폴더 안을 더 보려면 경로를 주세요:")
    print("   --look /Isaac/Robots/Unitree/Go2")
    print(" ※ 자산을 바꿔 끼우려면:")
    print("   --usd /Isaac/Robots/Unitree/Go2/<파일이름>.usd")
    print()
    print(" 닫습니다…")
    sys.stdout.flush()
    simulation_app.close()
    raise SystemExit(0)

# ── 로봇 ────────────────────────────────────────────────────
# ★ go2 기본값을 0.4 → 0.32 로 내렸습니다 (2026-09-17, README 38) ★
#   0.4 는 제가 한 번도 안 따져본 숫자였고, 재봤더니 결과를 뒤집습니다 —
#
#     0.30~0.35   셋 다 같은 판 (앞으로 1.63~1.74 m · 휨 24~27 cm)
#     0.38        걷긴 하는데 휨이 세 배 (-72.9 cm · -28.2 도)
#     0.40        서는 정책은 뒤집혀서 못 일어남
#
#   ★ 기는 정책은 0.40 에서도 멀쩡합니다 ★ 배를 깔고 다리를 벌린 자세가
#   착지하기 좋은 모양이라서입니다. 그래서 0.40 짜리 시험대는 **기는 개에게
#   유리하고 서는 개에게 불리합니다** — 우리가 원하는 것과 정반대입니다.
#
#   0.32 는 넉넉한 가운데입니다 (아래 벼랑은 0.30 위로 안 재봤고,
#   위 어깨는 0.38). spot 은 안 건드렸습니다 — 0.8 에서 멀쩡했고,
#   한 번에 하나만 바꿉니다.
high = args.high if args.high is not None else (0.8 if args.robot == "spot"
                                                else 0.32)
Kind = SpotFlatTerrainPolicy if args.robot == "spot" else Go2FlatTerrainPolicy
made = {"prim_path": "/World/" + args.robot, "position": [0, 0, high]}
if args.yaw:
    # z 축으로 도는 사원수 (w, x, y, z). 반각을 쓰는 것에 주의.
    half = math.radians(args.yaw) / 2.0
    turned_q = [math.cos(half), 0.0, 0.0, math.sin(half)]
    # ★ 이 클래스가 orientation 을 받는지 **물어보고** 넣습니다 ★
    #   --policy 때와 같은 이유입니다. 박아 넣었다가 TypeError 로 죽느니,
    #   안 받으면 안 받는다고 말하는 편이 낫습니다.
    import inspect as _inspect
    _takes = _inspect.signature(Kind.__init__).parameters
    _name = "orientation" if "orientation" in _takes else (
            "orientations" if "orientations" in _takes else None)
    if _name:
        made[_name] = turned_q
        print(f" [방향] {args.yaw:+.0f} 도 돌려세웁니다 ({_name})")
    else:
        print(" [방향] ✖ 이 클래스는 방향을 안 받습니다 — 그냥 세웁니다")
        print("        받는 것들: " + ", ".join(sorted(_takes)))
        args.yaw = 0.0
if args.usd:
    made["usd_path"] = assets_root_path + args.usd
    print(f" [자산] 기본 대신 이걸 씁니다: {args.usd}")
if args.policy:
    # 이 클래스가 policy_path 를 받는지 **물어보고** 넣습니다.
    #   Spot 쪽은 인자가 다를 수 있습니다. 박아 넣었다가 TypeError 로
    #   죽느니, 안 받으면 안 받는다고 말하는 편이 낫습니다.
    import inspect
    if "policy_path" in inspect.signature(Kind.__init__).parameters:
        made["policy_path"] = args.policy
        print(f" [정책] 기본 대신 이걸 씁니다: {args.policy}")
    else:
        print(f" [정책] ✖ {args.robot} 은 policy_path 를 안 받습니다 — 무시합니다")
robot = Kind(**made)
print(f" [로봇] {args.robot} 을(를) {high:.2f} m 에 놓았습니다")

# ★ 물리 주기를 **정책에게 물어봅니다** ★
#
#   policy_controller.py 원본에 이 줄이 있습니다 —
#
#       self._decimation, self._dt, self.render_interval = \
#           get_physics_properties(self.policy_env_params)
#
#   즉 **정책이 스스로 '나는 이 주기로 배웠다'고 말해줍니다.** 학습할 때와
#   다른 주기로 돌리면, 정책이 내놓는 목표각이 몸이 실제로 움직이는 빠르기와
#   어긋납니다. 걷긴 걷는데 자세가 무너집니다.
#
#   그런데 저는 두 로봇 모두에게 1/200 을 박아서 먹이고 있었습니다.
#   공식 예제가 Spot 에 그 값을 쓰길래 따라 쓴 것인데, **Spot 용 숫자를
#   Go2 에게 준 것**입니다. 물어보면 될 것을 베껴왔습니다.
#
#   2026-09-15: 여기서 실제 값을 찍고, 있으면 그대로 씁니다.
want_dt = getattr(robot, "_dt", None)
deci = getattr(robot, "_decimation", None)
print(f" [정책] 스스로 말하는 주기  dt={want_dt}  decimation={deci}", end="")
if want_dt:
    print(f"  → 정책 판단 {1.0 / want_dt / (deci or 1):.0f} 회/초")
else:
    print()

if want_dt and abs(want_dt - 1.0 / 200.0) > 1e-9:
    print(f" [고침] 제가 박아둔 1/200 ({1/200:.5f}) 대신 "
          f"정책이 말한 {want_dt:.5f} 로 바꿉니다")
    SimulationManager.set_physics_dt(want_dt)
    RenderingManager.set_dt(8.0 * want_dt)
else:
    print(" [확인] 1/200 이 맞습니다 — 주기는 범인이 아닙니다")

base_command = torch.zeros(3, device=args.device)

_physics_callback_id = SimulationManager.register_callback(
    on_physics_step, IsaacEvents.POST_PHYSICS_STEP)

omni.timeline.get_timeline_interface().play()
simulation_app.update()


# ── 잣대 ────────────────────────────────────────────────────
def as_numbers(v):
    """warp·torch·numpy 무엇이 오든 평범한 numpy 배열로.

    get_world_poses 는 warp 배열로 돌려줍니다 — v[0] 이 안 됩니다
    (RuntimeError: Item indexing is not supported on wp.array objects).
    """
    for how in (lambda x: x.numpy(),
                lambda x: x.detach().cpu().numpy(),
                lambda x: np.asarray(x)):
        try:
            return np.asarray(how(v))
        except Exception:
            continue
    return np.asarray(v)


def pose():
    """몸의 자리와 방향. 공식 예제도 이 이름으로 읽습니다."""
    pos, quat = robot.robot.get_world_poses()
    return (as_numbers(pos).reshape(-1, 3)[0],
            as_numbers(quat).reshape(-1, 4)[0])


# ★ 발 네 개의 자리 (2026-09-17, README 38-7-1) ★
#   왜 필요한가: 같은 12 cm 턱이 자리에 따라 넘기도 하고 멎기도 합니다.
#   몸통만 봐서는 왜 갈리는지 못 봅니다 — 발이 어디 놓이는지를 봐야
#   합니다. 그런데 발 자리를 읽는 이름이 판마다 다릅니다.
#   ★ 그래서 박아넣지 않고 **물어봅니다.** --yaw · --policy 와 같은 방식입니다.
#     못 찾으면 한 번 말하고 스스로 꺼집니다 — 판을 망치지 않습니다.
_feet_how = None          # 찾아낸 방법 (한 번만 찾습니다) — 부르면 되는 함수
_feet_name = ""           # 그 방법의 이름 (사람이 읽을 것)
_feet_off = False         # 못 찾았으면 다시 시도하지 않습니다


# ★ 고침 (2026-09-17, README 39-3) ★
#   처음에 넣은 목록 네 개는 **전부 빗나갔습니다.** 실제로 있던 것은
#   `get_link_coms` · `_link_paths` · `_num_links` 뿐이었습니다.
#   ─ 그래서 이름을 더 대보는 것으로는 부족하다고 보고, 세 갈래로 넓힙니다:
#     (1) 관절체가 직접 주는 이름   (2) 그 안에 든 physx 뷰
#     (3) 마디 경로로 XformPrim 을 새로 만들어 읽기
#   ─ 그래도 못 찾으면 **get_ 로 시작하는 이름을 전부** 찍습니다.
#     여덟 개만 잘라 찍는 바람에 한 판을 통째로 날렸습니다.
def _feet_probe(art):
    """(부를 함수, 이름) 을 찾습니다. 못 찾으면 (None, "")."""
    def _ok(out):
        arr = as_numbers(out[0] if isinstance(out, tuple) else out)
        arr = arr.reshape(-1, arr.shape[-1])
        return arr if arr.shape[0] >= 4 and arr.shape[1] >= 3 else None

    # (1) 관절체가 직접 주는 것
    for name in ("get_link_transforms", "get_link_poses", "get_body_poses",
                 "get_link_world_poses", "get_links_state", "get_world_poses"):
        fn = getattr(art, name, None)
        if fn is None:
            continue
        try:
            if _ok(fn()) is not None:
                return fn, name + "()"
        except Exception:
            continue

    # (2) 안에 든 physx 뷰 — 이름이 판마다 다릅니다
    for holder in ("_physics_view", "_physics_articulation_view",
                   "_articulation_view", "physics_view", "_view"):
        view = getattr(art, holder, None)
        if view is None:
            continue
        for name in ("get_link_transforms", "get_link_poses"):
            fn = getattr(view, name, None)
            if fn is None:
                continue
            try:
                if _ok(fn()) is not None:
                    return fn, holder + "." + name + "()"
            except Exception:
                continue

    # (3) 마디 경로가 있으면 XformPrim 을 새로 만들어 읽습니다
    paths = getattr(art, "_link_paths", None)
    if paths:
        flat = [p for grp in paths for p in (grp if isinstance(grp, (list, tuple)) else [grp])]
        if len(flat) >= 4:
            for mod, cls in (("isaacsim.core.experimental.prims", "XformPrim"),
                             ("isaacsim.core.prims", "XFormPrim")):
                try:
                    import importlib
                    P = getattr(importlib.import_module(mod), cls)
                    prims = P(flat)
                    if _ok(prims.get_world_poses()) is not None:
                        return prims.get_world_poses, cls + "(마디 %d개)" % len(flat)
                except Exception:
                    continue
    return None, ""


# ★ 고침 (2026-09-18, README 42) — 흠 14 ★
#   처음엔 "z 가 가장 낮은 네 마디"를 발로 골랐습니다. **틀렸습니다.**
#   걷는 중에는 뜬 다리의 발보다 **선 다리의 무릎**이 더 낮습니다. 그래서
#   `--sill 0` 판에서 네 개가 전부 몸통보다 **앞**에 찍혔습니다
#   (몸통 2.109 · 고른 것 2.43/2.37/2.28/2.28 — 뒷발이라면 몸통 뒤
#    0.3 m 에 있어야 합니다). 그 잘못된 값으로 저는 "네 발이 다 떠 있다,
#   주저앉았다"고 읽었고, 그건 취소합니다.
#   이제 **이름으로** 고릅니다. Go2 는 FL_foot · FR_foot · RL_foot · RR_foot.
_feet_idx = None          # 이름으로 찾은 네 마디의 번호
_feet_label = ""          # 사람이 읽을 이름 (한 번만 찍습니다)


def _find_foot_indices(art):
    """마디 이름에서 발 네 개의 번호. 못 찾으면 (None, "")."""
    names = getattr(art, "_link_names", None)
    if not names:
        return None, ""
    flat = []
    for n in names:
        if isinstance(n, (list, tuple)):
            flat.extend(n)
        else:
            flat.append(n)
    flat = [str(n) for n in flat]
    hits = [(i, n) for i, n in enumerate(flat)
            if "foot" in n.lower() or n.lower().endswith("_toe")]
    if len(hits) != 4:
        # ★ 이름을 **전부** 찍습니다 — 잘라 찍어서 판을 날린 게 흠 12 였습니다.
        msg = ["이름에서 발 %d개를 찾았습니다 (4개가 아닙니다)." % len(hits),
               "      마디 %d개의 이름 전부:" % len(flat)]
        for i in range(0, len(flat), 4):
            msg.append("        " + "  ".join(flat[i:i + 4]))
        return None, "\n".join(msg)
    return [i for i, _ in hits], " · ".join(n for _, n in hits)


def feet_of():
    """네 발의 (x, y, z). 못 읽으면 None."""
    global _feet_how, _feet_name, _feet_off, _feet_idx, _feet_label
    if _feet_off:
        return None
    art = robot.robot
    if _feet_how is None:
        _feet_how, _feet_name = _feet_probe(art)
        if _feet_how is None:
            _feet_off = True
            gets = sorted(n for n in dir(art) if n.startswith("get_"))
            print(" [발] ✖ 발 자리를 읽는 법을 못 찾았습니다 — 끕니다.")
            print("      물어본 것: 관절체 이름 6 · physx 뷰 5 · XformPrim")
            print("      %s 에 있는 get_ 전부 (%d개):" % (type(art).__name__, len(gets)))
            for i in range(0, len(gets), 3):
                print("        " + "  ".join(gets[i:i + 3]))
            return None
        print(" [발] 자리를 %s 으로 읽습니다" % _feet_name)
        _feet_idx, _feet_label = _find_foot_indices(art)
        if _feet_idx is None:
            print(" [발] ✖ 이름으로 발을 못 찾았습니다 — 끕니다.")
            print("      %s" % (_feet_label or "_link_names 가 없습니다"))
            print("      ※ 예전처럼 'z 가 낮은 네 마디'로 때우지 않습니다 —")
            print("        그게 무릎을 발로 읽어서 흠 14 가 됐습니다.")
            _feet_off = True
            return None
        print(" [발] 이름으로 고릅니다: %s" % _feet_label)
    try:
        out = _feet_how()
        arr = as_numbers(out[0] if isinstance(out, tuple) else out)
        arr = arr.reshape(-1, arr.shape[-1])[:, :3]
        feet = arr[_feet_idx]
        return feet[np.argsort(-feet[:, 0])]     # 앞쪽부터
    except Exception as e:
        _feet_off = True
        print(f" [발] ✖ 읽다가 실패했습니다 — 끕니다 ({e!r})")
        return None


def yaw_of(q):
    w, x, y, z = [float(v) for v in q]
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


def clock():
    return omni.timeline.get_timeline_interface().get_current_time()


# ── 돌립니다 (공식 예제의 while 모양 그대로) ────────────────
#
#   ★ 걸음을 세지 않고 **무대 시계**로 때를 가릅니다 ★
#     물리 걸음 수를 세어 1.5초를 맞추려다, 실제 dt 가 제 짐작과 달라서
#     엉뚱한 때에 재고 있었습니다. 시계를 보면 그 문제가 없습니다.
began = None
start = end = None
told = -1.0
told_gains = False        # 이득 줄은 콜백이 뛴 뒤에 생깁니다 — 한 번만 찍습니다

# 방향 되먹임이 쓴 것들 — 얼마나 애썼는지 나중에 찍습니다
aim = None                # 목표 방향 (출발할 때 본 쪽)
turn_asked = []           # 시킨 회전 명령들 (rad/s)
off_worst = 0.0           # 가장 크게 틀어졌던 각 (rad)

# 문턱이 쓴 것들
FRONT_PAW = 0.20          # 몸 중심에서 앞발까지 (Go2, 어림)
# ★ 뒷발은 따로입니다 (2026-09-17, README 38-7-1) ★
#   전에는 뒷발 자리도 FRONT_PAW 로 셈해서 12 cm 가 어긋났습니다.
#   턱 자리를 여섯 곳으로 옮겨가며 잰 결과, 멎는 자리가 언제나
#   턱 뒷면에서 0.32 m 뒤였습니다 (0.317 · 0.321 · 0.328).
#   거기서 뒷발이 모서리에 얹혀 있으려면 0.30 m 여야 합니다.
#   ※ 재서 얻은 게 아니라 **멎는 자리에서 거꾸로 푼 값**입니다.
#     발 자리를 직접 기록하기 전까지는 어림으로 두십시오.
REAR_PAW = 0.30           # 몸 중심에서 뒷발까지 (뒤로 뻗었을 때)
reach_at = None           # 턱 앞면에 닿은 때 (무대시계)
x_at_reach = None         # 그때의 자리 — 평지 속도를 여기서 냅니다
over_at = None            # 몸통이 턱 뒷면을 지난 때
clear_at = None           # 뒷발까지 다 지났을 때 (몸통이 뒷면 + 앞발거리)
z_low = z_high = None     # 턱 언저리에서의 몸 높이 최저·최고
z_ever = None             # 판 전체에서 가장 낮았던 몸 높이
still_from = None         # 이 때부터 안 움직입니다
still_at = None           # 그때의 자리


def wrapped(a):
    """−π ~ +π 로 접습니다. 359도와 −1도가 같은 것이 되도록."""
    return (a + math.pi) % (2 * math.pi) - math.pi

print()
print(f" 걸으면서 {args.warm:.1f}초 자리잡은 뒤부터 잽니다…")
print(f"   {'무대시계':>8} {'x':>8} {'y':>8} {'z':>7}   몸 높이")
sys.stdout.flush()

while simulation_app.is_running():
    simulation_app.update()
    if not SimulationManager.is_simulating():
        continue            # ★ 여기서 reset_needed 를 켜지 않습니다 (위 설명) ★

    if gains_said and not told_gains:
        told_gains = True
        for line in gains_said[0]:
            print(f" [이득] {line}")
        sys.stdout.flush()

    now = clock()
    if began is None:
        began = now
    since = now - began

    # ★ 워밍업에도 **걸으라고** 합니다 ★
    #
    #   2026-09-14 — 여기가 오늘의 범인이었습니다.
    #   처음엔 실기체 시험과 맞추려고 워밍업 동안 [0,0,0] 을 줬습니다.
    #   "1.5초 제자리에 서 있다가 출발" 이라는 뜻이었는데, 로봇이 매번
    #   발버둥치다 엎어졌습니다. 정책·이득·콜백·물리 엔진을 다 뒤지고
    #   뼈대를 두 번 다시 쓴 끝에, --warm 0 으로 돌려보고서야 알았습니다.
    #
    #   **이 정책에게 '제자리에 서 있기'는 학습된 동작이 아닙니다.**
    #   걸으라고 하면 걷고, 가만있으라고 하면 무너집니다. 로봇을 배려한다고
    #   넣은 한 줄이 로봇을 죽이고 있었습니다.
    #
    #   그래서 워밍업의 뜻을 바꿉니다 — '서 있는 시간' 이 아니라
    #   **'걸음이 자리잡을 때까지 기다리는 시간'**. 떨어지고 비틀거리는
    #   첫 1초를 재기 시작점에서 빼는 것이 원래 목적이었고, 그건 이렇게
    #   해도 똑같이 됩니다.
    base_command = torch.tensor([args.speed, 0.0, 0.0], device=args.device)

    # ── 방향 되먹임 (--hold) ────────────────────────────────
    #
    #   학습 설정의 식을 그대로 씁니다 (위 --hold 설명 참고).
    #   여기서 고치는 것은 **명령**뿐입니다. 로봇을 붙잡거나 자리를
    #   바로잡지 않습니다 — 그러면 재는 것이 거짓이 됩니다.
    p_now = q_now = None
    if args.hold or args.sill > 0:
        try:
            p_now, q_now = pose()
        except Exception:
            p_now = q_now = None    # 아직 못 읽습니다 (콜백 전). 다음 바퀴에.

    if args.hold:
        if q_now is not None:
            yaw_now = yaw_of(q_now)
            if aim is None:
                aim = yaw_now       # ★ 출발할 때 본 쪽을 목표로 삼습니다 ★
            off = wrapped(aim - yaw_now)
            wz = max(-args.hold_max,
                     min(args.hold_max, args.hold_gain * off))
            base_command = torch.tensor([args.speed, 0.0, wz],
                                        device=args.device)
            if since >= args.warm:      # 재는 구간만 셉니다
                turn_asked.append(wz)
                off_worst = max(off_worst, abs(off))

    # ── 문턱을 언제 넘었는가 ────────────────────────────────
    #
    #   ★ '넘었다' 를 **뒷발이 아니라 몸통 기준**으로 셉니다 ★
    #     발끝을 따로 읽지 않으니, 몸통이 턱 뒷면을 지난 때를 씁니다.
    #     실제로 발이 걸렸다가 빠져나온 경우도 '넘었다' 로 셉니다 —
    #     그래서 걸린 시간과 몸 높이를 같이 봐야 합니다.
    if args.sill > 0 and p_now is not None:
        x_now, z_now = float(p_now[0]), float(p_now[2])
        # ★ 앞발은 몸통 원점보다 앞에 있습니다 ★
        #   2026-09-16 — 처음엔 몸통 x 로만 판정했더니, 앞발이 턱을 때리고
        #   뒤로 밀려 넘어졌는데도 "턱 앞까지 가지도 못했다" 고 찍혔습니다.
        #   Go2 는 몸 중심에서 앞발까지 20 cm 쯤입니다.
        if reach_at is None and x_now >= sill_near - FRONT_PAW:
            reach_at = now
            x_at_reach = x_now          # 여기까지 온 속도가 '평지 속도'
        if over_at is None and x_now >= sill_far:
            over_at = now                      # 몸통이 뒷면을 지난 때
        if clear_at is None and x_now >= sill_far + FRONT_PAW:
            clear_at = now                     # 뒷발까지 다 지났을 때
        # 멈춤 — 쓸어볼 때 '넘었다/걸렸다/넘어졌다' 를 한 줄로 가르는 것
        if still_from is None:
            still_from = now
            still_at = (x_now, z_now)
        elif (abs(x_now - still_at[0]) > 0.005
              or abs(z_now - still_at[1]) > 0.005):
            still_from = now
            still_at = (x_now, z_now)
        if sill_near - 0.40 <= x_now <= sill_far + 0.40:
            z_low = z_now if z_low is None else min(z_low, z_now)
            z_high = z_now if z_high is None else max(z_high, z_now)
        # ★ 가장 낮았던 높이는 **턱에 닿은 뒤부터** 셉니다 ★
        #   처음 0.40 m 에서 떨어뜨릴 때 다리가 접히며 낮아지는데,
        #   그걸 같이 세면 무엇을 해도 "넘어짐" 으로 찍힙니다.
        if reach_at is not None:
            z_ever = z_now if z_ever is None else min(z_ever, z_now)

    if since >= args.warm:
        if start is None:
            start = pose()
        if since >= args.warm + args.seconds:
            end = pose()
            break

    if now - told >= args.trace:
        told = now
        p, q = pose()
        tail = ("걸음 잡는 중" if since < args.warm else "★ 재는 중")
        if args.sill > 0:
            # 앞뒤로 기운 각 — 앞발을 턱에 올리면 머리가 들립니다
            w, qx, qy, qz = [float(v) for v in q]
            lean = math.degrees(math.asin(
                max(-1.0, min(1.0, 2.0 * (w * qy - qz * qx)))))
            where = ("턱 앞" if float(p[0]) < sill_near else
                     ("턱 위" if float(p[0]) <= sill_far else "턱 뒤"))
            tail = f"{lean:+6.1f}도  {where}"
        if args.feet:
            _f = feet_of()
            if _f is not None:
                tail += "  발x " + " ".join(f"{v[0]:+.2f}" for v in _f)
                tail += " · 발z " + " ".join(f"{v[2]:.3f}" for v in _f)
        print(f"   {now:8.2f} {float(p[0]):+8.3f} {float(p[1]):+8.3f}"
              f" {float(p[2]):7.3f}   " + tail)
        sys.stdout.flush()

# ── 셈합니다 ────────────────────────────────────────────────
print()
print("=" * 70)
print(f" 깨운 횟수 {woke}회 · 명령한 횟수 {drove}회")
if woke > 1:
    print("   ✖ 깨우기가 두 번 이상입니다 — 콜백이 오락가락했습니다.")
if drove == 0:
    print("   ✖ **명령이 한 번도 안 들어갔습니다.** 로봇이 못 서는 게 당연합니다.")
if hurt:
    print()
    print(" ✖ 물리 콜백 안에서 터졌습니다:")
    print(hurt)
print("-" * 70)
if start is None or end is None:
    print(" ✖ 끝까지 못 갔습니다 — 잰 값이 없습니다.")
else:
    p0, q0 = start
    p1, q1 = end
    yaw0, yaw1 = yaw_of(q0), yaw_of(q1)
    dx, dy = float(p1[0] - p0[0]), float(p1[1] - p0[1])
    c, s = math.cos(yaw0), math.sin(yaw0)
    ahead = dx * c + dy * s
    side = -dx * s + dy * c
    turned = math.degrees((yaw1 - yaw0 + math.pi) % (2 * math.pi) - math.pi)

    print(f" 시뮬레이터의 {args.robot}"
          + (f"   (놓을 때 {args.yaw:+.0f} 도 돌려세움)" if args.yaw else ""))
    print(f"   앞으로 간 거리   {ahead:+.3f} m   "
          f"(명령대로면 {args.speed * args.seconds:.2f} m)")
    print(f"   옆으로 밀린 양   {side * 100:+.1f} cm")
    print(f"   몸이 돌아간 각   {turned:+.1f} 도")
    print(f"   몸 높이 (끝)     {float(p1[2]):.3f} m   "
          f"(제대로 서 있으면 0.3 m 안팎)")

    # ── 옆으로 밀린 양을 둘로 쪼갭니다 ──────────────────────
    #
    #   몸이 도는 물건은 가만히 둬도 옆으로 갑니다. 원을 그리니까요.
    #   그 몫을 먼저 빼야, 남은 것이 **미끄러진 양**입니다.
    #
    #   1 m 갈 때 k 라디안씩 돈다고 보면 (매 순간 일정하다고 칩니다),
    #   L 만큼 가는 동안 옆으로 간 거리는
    #
    #       ∫₀ᴸ sin(k·x) dx  =  (1 − cos(k·L)) / k
    #
    #   k 가 0 에 가까우면 0/0 이 되니 그때는 ½·k·L² 로 씁니다
    #   (같은 식의 테일러 첫 항입니다).
    #
    #   ※ 이건 **어림입니다.** 도는 빠르기가 내내 일정했다고 치고
    #     시작과 끝 두 점만으로 셈합니다. 중간에 오락가락했으면
    #     실제와 다릅니다. 그래도 총량만 보는 것보다는 훨씬 낫습니다.
    turn_part = slip_part = None
    if abs(ahead) > 0.15:
        k = math.radians(turned) / ahead          # 1 m 당 도는 라디안
        L = abs(ahead)
        if abs(k * L) < 1e-6:
            turn_part = 0.5 * k * L * L
        else:
            turn_part = (1.0 - math.cos(k * L)) / k
        slip_part = side - turn_part
        print(f"     ├ 돌아서 생긴 휨  {turn_part * 100:+.1f} cm")
        print(f"     └ 미끄러진 휨    {slip_part * 100:+.1f} cm"
              f"   ({slip_part / L * 100:+.1f} cm/m)")
        if abs(side) > 0.02 and abs(slip_part) > abs(turn_part):
            print("       ※ 도는 것보다 **미끄러지는 것**이 큽니다 —")
            print("         방향을 잡아도 안 줄어듭니다. 걸음 자체입니다.")

    if args.hold:
        print()
        if turn_asked:
            mean_wz = sum(turn_asked) / len(turn_asked)
            print(f"   [되먹임] 켜짐 (이득 {args.hold_gain} · 한계 "
                  f"±{args.hold_max} rad/s)")
            print(f"     시킨 회전  평균 {mean_wz:+.3f} rad/s"
                  f" · 가장 센 것 {max(turn_asked, key=abs):+.3f}")
            print(f"     가장 크게 틀어졌던 각  "
                  f"{math.degrees(off_worst):.1f} 도")
            if abs(mean_wz) >= args.hold_max * 0.9:
                print("     ✖ 한계에 붙어 있습니다 — 되먹임이 못 이깁니다.")
            # ★ 쪼갠 값을 곧이곧대로 읽지 마십시오 ★
            #   위의 「돌아서 생긴 휨 / 미끄러진 휨」은 **도는 빠르기가 내내
            #   일정했다**고 치고 셈합니다. 되먹임을 켜면 방향이 0 언저리를
            #   오락가락하므로 그 가정이 깨집니다. 끝의 각이 작으니 거의
            #   전부가 '미끄러짐' 으로 떨어지는데, 실제로는 오락가락하는
            #   동안 옆으로 간 것도 섞여 있습니다.
            print("     ※ 되먹임을 켜면 위의 쪼개기는 못 믿습니다.")
            print("       볼 것은 **옆으로 밀린 양 총합** 입니다.")
        else:
            print("   [되먹임] ✖ 켜졌는데 한 번도 안 셌습니다 — 방향을"
                  " 못 읽었습니다.")

    if args.sill > 0:
        print()
        print(f"   [문턱] 높이 {args.sill:.3f} m · "
              f"{sill_near:.2f}~{sill_far:.2f} m")
        # ★ 견줄 속도는 **턱에 닿기 전** 구간에서 냅니다 ★
        #   처음엔 판 전체 평균을 썼는데, 멈춰 있던 시간까지 들어가서
        #   "평지였다면" 이 저절로 느려졌습니다. 자기 자신을 기준으로
        #   삼은 셈이라 아무것도 못 가립니다.
        went = (x_at_reach / reach_at) if (reach_at and reach_at > 0.5
                                           and x_at_reach) else 0.0
        flat = args.sill_deep / went if went > 0.01 else None
        frozen = (still_from is not None
                  and (clock() - still_from) >= 2.0)
        if reach_at is None:
            print("     ✖ 턱 앞까지 가지도 못했습니다.")
            print(f"       {args.seconds:.0f}초 동안 {ahead:+.3f} m — 턱은 "
                  f"{sill_near:.2f} m 앞입니다 (앞발은 {FRONT_PAW:.2f} m 더).")
            print("       --seconds 를 늘리거나 --sill-at 을 줄이세요.")
        elif over_at is None:
            print(f"     ✖ **못 넘었습니다.** {reach_at:.1f}초에 앞발이 닿았습니다.")
            print(f"       마지막 자리 {float(p1[0]):+.3f} m")
            if z_ever is not None:
                print(f"       판 전체에서 가장 낮았던 몸 높이 {z_ever:.3f} m"
                      + ("   ← 넘어졌습니다" if z_ever < 0.20 else ""))
            if frozen:
                # ★ 고침 (2026-09-18) — 흠 13 ★
                #   예전에는 몸통 높이만 보고 "선 채로"라고 단정했습니다.
                #   몸통이 0.3 m 라고 서 있는 게 아닙니다 — 무릎으로 앉아
                #   있어도 0.3 m 입니다. 이제 자세를 단정하지 않습니다.
                print(f"       ★ {still_from:.1f}초부터 **한 자리도 안"
                      f" 움직입니다** ★")
                print("         (몸통 높이만으로는 서 있는지 앉은 건지"
                      " 모릅니다. --feet 로 발 높이를 보십시오.)")
                print("         ※ 학습 쪽에서는 이런 멎음이 안 나옵니다"
                      " (한 판 1000/1000 걸음). 시험대를 의심하십시오 —")
                print("           특히 이 판에 **문턱 상자가 있기만 해도**"
                      " 궤적이 갈립니다 (README 42).")
        else:
            took = over_at - reach_at
            print(f"     앞면에 닿은 때 {reach_at:.1f}초 · "
                  f"몸통이 뒷면을 지난 때 {over_at:.1f}초")
            print("     뒷발까지 다 지난 때 "
                  + (f"{clear_at:.1f}초" if clear_at else "✖ 못 지났습니다"))
            print(f"     넘는 데 걸린 시간  {took:.1f}초", end="")
            if flat:
                print(f"   (평지였다면 {flat:.1f}초쯤)")
                if took > flat * 1.8:
                    print("     ※ 넘긴 넘었는데 **붙들렸습니다.**"
                          " 멈칫한 것입니다.")
                elif took <= flat * 1.3:
                    print("     ★ 거의 안 늦었습니다 — 멈추지 않고 넘었습니다 ★")
            else:
                print()
            if z_low is not None:
                print(f"     턱 언저리 몸 높이 {z_low:.3f} ~ {z_high:.3f} m"
                      f"  (오른 폭 {z_high - z_low:.3f} m)")
            if frozen:
                print(f"     ★ 넘고 나서 {still_from:.1f}초부터 **멎었습니다**"
                      f" — 자리 {float(p1[0]):.3f} m ★")
                _rear = float(p1[0]) - REAR_PAW
                _gap = _rear - sill_far
                print(f"       뒷발 자리 {_rear:.3f} m · 턱 뒷면 {sill_far:.2f} m"
                      f"  (차이 {_gap:+.3f} m)")
                if abs(_gap) <= 0.06:
                    print("       → 뒷발이 뒷면 모서리 위입니다. 여기가 범인일 가능성이 큽니다.")
                else:
                    print("       → 뒷발은 모서리에서 떨어져 있습니다. 다른 이유입니다.")
                if args.sill_deep <= 0.10:
                    print("       ※ 지금 턱은 깊이 %.2f m 짜리 **띠** 입니다. 뒤가 낭떠러지라"
                          % args.sill_deep)
                    print("         걸릴 모서리가 있습니다. 실제 낮은 계단처럼 **올라서는 단**")
                    print("         (--sill-deep 1.5) 으로 두면 이 모서리 자체가 없습니다.")
            if z_low is not None:
                if z_high - z_low < args.sill * 0.6:
                    print("     ※ 오른 폭이 턱 높이에 못 미칩니다 —"
                          " 올라탄 게 아니라 밀고 지나갔을 수 있습니다.")
        # ★ 쓸어볼 때 이 한 줄만 모으면 됩니다 ★
        #
        #   2026-09-16 — 처음에는 '몸통이 선을 지났는가' 만 봤습니다.
        #   그랬더니 4·6 cm 는 넘어지고 8·10·12 cm 는 넘는 표가 나왔습니다.
        #   말이 안 됩니다. 턱이 높으면 **앞으로 고꾸라지면서** 선을
        #   지나거든요. 넘어지는 중에 선을 밟은 것을 '넘었다' 로 찍고
        #   있었습니다.
        #
        #   그래서 **끝 자세**를 같이 봅니다. 넘었다고 하려면 선을 지나고
        #   **그러고도 서 있어야** 합니다.
        end_high = float(p1[2])
        crossed = over_at is not None
        fell = (z_ever is not None and z_ever < 0.20) or end_high < 0.22
        if crossed and fell:
            verdict = "넘다가 넘어짐"
        elif crossed and frozen:
            verdict = "넘고 나서 멈춤"
        elif crossed:
            verdict = "넘음"
        elif reach_at is None:
            verdict = "닿지도 못함"
        elif fell:
            verdict = "앞에서 넘어짐"
        elif frozen:
            verdict = "앞에서 멈춤"
        else:
            verdict = "못 넘음"
        # 표시를 아스키로 답니다 — 글자표가 어긋나도 이 줄은 걸립니다
        # 숫자도 같이 답니다 — 표만 보고도 이상한 줄을 알아채게
        low = f" · 최저 {z_ever:.3f}" if z_ever is not None else ""
        print(f"     >>> SILL {args.sill:.2f} m : {verdict}"
              f"  (끝 x {float(p1[0]):.2f} · 끝높이 {end_high:.3f}{low})")
    print()
    if abs(ahead) <= 0.15:
        print(" ✖ 앞으로 안 갔습니다.")
        if float(p1[2]) < 0.2:
            print("   주저앉았습니다 — 걸음 이전에 서는 것부터입니다.")
        print("   --gui 를 붙이면 눈으로 볼 수 있습니다.")
        print("   --robot spot 으로 바꿔보면 뼈대 탓인지 자산 탓인지 갈립니다.")
    else:
        print(" 실기체 (2026-09-14, 13판 · 공장 컨트롤러)")
        print("   → 1 m 갈 때  옆으로 +5.0 cm · +4.1 도  (왼쪽으로)")
        print("     그중 되먹임으로 못 잡는 미끄러짐  약 4.5 cm/m")
        print(f" 시뮬레이터   → 1 m 갈 때  옆으로 "
              f"{side / abs(ahead) * 100:+.1f} cm · "
              f"{turned / abs(ahead):+.1f} 도")
        if slip_part is not None:
            print(f"     그중 미끄러짐  {slip_part / abs(ahead) * 100:+.1f} cm/m")
        print()
        if args.yaw:
            print()
            print(" ※ 돌려세우고 잰 값입니다. 위 숫자는 **몸 기준**입니다.")
            print("   0 도에서 잰 것과 부호를 견주세요 —")
            print("     같은 부호  → 로봇·정책의 버릇 (돌려도 따라옵니다)")
            print("     뒤집힘     → 시험대·바닥의 좌우 비대칭")
            print()
        print(" ※ 이 둘을 빼서 실기체 보정에 쓰지 마십시오.")
        print("   서로 다른 두 보행기입니다 (자세한 것은 파일 맨 위).")
        print("   여기서 볼 것은 **미끄러짐이 학습으로 줄어드는가** 입니다.")

print()
print(" 닫습니다…")
sys.stdout.flush()
simulation_app.close()
