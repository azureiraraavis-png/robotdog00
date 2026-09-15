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
"""

import argparse
import math
import sys

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
                help="놓는 높이 m (기본: go2 0.4 · spot 0.8)")
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
high = args.high if args.high is not None else (0.8 if args.robot == "spot"
                                                else 0.4)
Kind = SpotFlatTerrainPolicy if args.robot == "spot" else Go2FlatTerrainPolicy
made = {"prim_path": "/World/" + args.robot, "position": [0, 0, high]}
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
    if since >= args.warm:
        if start is None:
            start = pose()
        if since >= args.warm + args.seconds:
            end = pose()
            break

    if now - told >= 0.5:
        told = now
        p, _ = pose()
        print(f"   {now:8.2f} {float(p[0]):+8.3f} {float(p[1]):+8.3f}"
              f" {float(p[2]):7.3f}   "
              + ("걸음 잡는 중" if since < args.warm else "★ 재는 중"))
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

    print(f" 시뮬레이터의 {args.robot}")
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
        print(" ※ 이 둘을 빼서 실기체 보정에 쓰지 마십시오.")
        print("   서로 다른 두 보행기입니다 (자세한 것은 파일 맨 위).")
        print("   여기서 볼 것은 **미끄러짐이 학습으로 줄어드는가** 입니다.")

print()
print(" 닫습니다…")
sys.stdout.flush()
simulation_app.close()