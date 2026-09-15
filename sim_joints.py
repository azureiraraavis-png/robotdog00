# -*- coding: utf-8 -*-
"""로봇의 **관절 차례**를 정책이 기대하는 것과 나란히 놓고 봅니다.

  ★ 왜 이것부터인가 ★

    2026-09-14, 시뮬레이터의 Go2 가 2.16 m 를 갔습니다. 그런데 몸 높이가
    0.119 m — 제대로 서면 0.30 m 안팎인데 배를 끌고 기어갔습니다.
    화면으로 보니 "몸을 낮추고 사냥하듯" 가더랍니다.

    같은 뼈대에서 Spot 은 똑바로 서서 8.8 m 를 걸었습니다. 그러니
    뼈대·물리 엔진·제어율은 아닙니다. **Go2 자산과 그 정책 사이**입니다.

  ★ 무엇을 의심하는가 ★

    Go2 자산은 Mujoco Menagerie 에서 변환해 온 것입니다
    (.../Isaac/Samples/Mujoco_Menagerie/unitree_go2/go2/go2.usda).
    그런 자산은 관절이 **다리별로** 묶이는 일이 많습니다 —

        FL_hip FL_thigh FL_calf  FR_hip FR_thigh FR_calf  RL… RR…

    그런데 강화학습으로 배운 보행 정책은 보통 **종류별로** 묶인 차례를
    기대합니다 —

        FL_hip FR_hip RL_hip RR_hip  FL_thigh FR_thigh …  FL_calf …

    이 둘이 어긋나면, 정책이 "허벅지를 굽혀라" 하고 낸 값이 종아리로
    갑니다. 로봇은 움직이긴 하는데 자세가 기괴해집니다.
    **어제 본 것이 정확히 그 모습입니다.**

  ★ 그래서 짐작하지 않고 이름을 뽑습니다 ★

    관절 이름을 차례대로 뽑아 default_pos 와 나란히 놓습니다.
    Go2 의 기본 자세는 대략 이렇습니다 —

        엉덩이(hip)   0 근처      (다리를 옆으로 벌리는 관절)
        허벅지(thigh) +0.8 근처   (앞다리는 +0.8, 뒷다리는 +1.0)
        종아리(calf)  -1.5 근처   (많이 굽어 있습니다)

    이름과 값이 이 규칙대로 짝지어지면 차례는 맞습니다.
    hip 이름 옆에 -1.5 가 붙어 있으면 **찾았습니다.**

  쓰는 법 (★ Isaac Sim 의 파이썬으로 ★)

      C:\\isaacsim\\python.bat D:\\workspace_raraavis\\robotdog00\\sim_joints.py
      C:\\isaacsim\\python.bat ...\\sim_joints.py --robot spot   (견주기용)

  ※ 걷게 하지 않습니다. 깨우고, 이름을 뽑고, 끝냅니다. 20초쯤 걸립니다.
"""

import argparse
import sys

ap = argparse.ArgumentParser(description="관절 차례를 봅니다")
ap.add_argument("--robot", choices=["go2", "spot"], default="go2")
ap.add_argument("--gui", action="store_true")
# ★ 자산을 바꿔 끼울 수 있게 ★
#   go2.py 는 Mujoco Menagerie 판을 기본으로 씁니다. NVIDIA 네이티브
#   자산(/Isaac/Robots/Unitree/Go2/go2.usd)으로 바꾸면 관절 이름 규칙이
#   다를 수 있고, 그러면 정책이 기대하는 차례와 어긋납니다. 여기서 봅니다.
ap.add_argument("--usd", default=None,
                help="로봇 자산 경로 (자산폴더 뒤부터)")
args, unknown = ap.parse_known_args()

print("=" * 70)
print(f" {args.robot} 의 관절 차례 — 정책이 기대하는 것과 맞는가")
print("=" * 70)
print(" ※ 걷게 하지 않습니다. 깨우고 이름만 뽑습니다.")
print()
sys.stdout.flush()

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
told = None                      # 깨운 뒤에 뽑아둔 것
hurt = None


def as_numbers(v):
    """warp·torch·numpy 무엇이 오든 평범한 numpy 배열로."""
    for how in (lambda x: x.numpy(),
                lambda x: x.detach().cpu().numpy(),
                lambda x: np.asarray(x)):
        try:
            return np.asarray(how(v))
        except Exception:
            continue
    return np.asarray(v)


def names_of(art):
    """관절 이름을 **차례대로**. 판마다 이름이 다르니 찾아봅니다.

    ★ 하나를 박아두지 않는 이유 ★
      dof_names · joint_names · get_dof_names() … 판마다 다릅니다.
      없으면 '못 읽었다'고 말해야지, 조용히 빈 목록을 돌려주면 안 됩니다.
    """
    for what in ("dof_names", "joint_names", "dof_paths"):
        got = getattr(art, what, None)
        if got is None:
            continue
        try:
            flat = list(np.asarray(got, dtype=object).reshape(-1))
            if flat:
                return [str(x) for x in flat], what
        except Exception:
            continue
    for what in ("get_dof_names", "get_joint_names"):
        fn = getattr(art, what, None)
        if callable(fn):
            try:
                flat = list(np.asarray(fn(), dtype=object).reshape(-1))
                if flat:
                    return [str(x) for x in flat], what + "()"
            except Exception:
                continue
    return None, None


def kind_of(name):
    """이름에서 관절 종류를 읽습니다 (hip · thigh · calf 따위)."""
    low = name.lower()
    for key, shown in (("hip", "엉덩이"), ("abduct", "엉덩이"), ("hx", "엉덩이"),
                       ("thigh", "허벅지"), ("hip_y", "허벅지"), ("hy", "허벅지"),
                       ("calf", "종아리"), ("knee", "종아리"), ("kn", "종아리")):
        if key in low:
            return shown
    return "?"


def on_physics_step(step_size, context):
    """첫 걸음에 깨우고, 거기서 다 뽑습니다. 걷게 하지는 않습니다."""
    global first_step, told, hurt
    if not first_step:
        return
    try:
        robot.initialize()
        first_step = False
        art = robot.robot
        names, how = names_of(art)
        pos = getattr(robot, "default_pos", None)
        now = None
        for what in ("get_dof_positions", "get_joint_positions"):
            fn = getattr(art, what, None)
            if callable(fn):
                try:
                    now = as_numbers(fn()).reshape(-1)
                    break
                except Exception:
                    continue
        # ★ 무게를 잽니다 ★
        #
        #   다리는 젓는데 몸이 안 올라오는 것은 **힘 대 무게**의 문제일 수
        #   있습니다. Go2 자산은 Mujoco Menagerie 에서 변환해 온 것이라
        #   변환 과정에서 질량·관성이 어긋날 수 있습니다. 실물 Go2 는 약
        #   15 kg, Spot 은 약 33 kg 입니다. 자산이 그보다 훨씬 무거우면
        #   이득 60으로는 절대 못 일어섭니다.
        mass = None
        for what in ("get_masses", "get_link_masses", "get_body_masses"):
            fn = getattr(art, what, None)
            if callable(fn):
                try:
                    mass = as_numbers(fn()).reshape(-1)
                    break
                except Exception:
                    continue

        # ★ 관절 이득과 힘 제한 ★
        #
        #   2026-09-15: Isaac Lab 이 찍어준 표에는 강성 0 · 감쇠 0 ·
        #   힘제한 1e9 가 적혀 있었습니다. 물리 엔진의 PD 제어를 안 쓰고
        #   파이썬에서 모터를 흉내 내 토크를 직접 넣는다는 뜻입니다.
        #   Go2FlatTerrainPolicy 는 반대로 엔진의 PD 에 목표각을 던집니다.
        #   **정책이 배운 몸과 우리가 씌운 몸이 다를 수 있습니다.**
        #   두 쪽 숫자를 나란히 놓으려면 우리 쪽부터 찍어야 합니다.
        drive = {}
        for what in ("get_dof_gains", "get_dof_stiffnesses", "get_dof_dampings",
                     "get_dof_max_efforts", "get_dof_max_velocities",
                     "get_dof_drive_types", "get_dof_armatures"):
            fn = getattr(art, what, None)
            if not callable(fn):
                continue
            try:
                drive[what] = fn()
            except Exception as e:
                drive[what] = f"✖ {type(e).__name__}"

        # 몸이 지금 어디 있는지 (놓은 높이와 견주려고)
        where = None
        try:
            p, _ = art.get_world_poses()
            where = as_numbers(p).reshape(-1, 3)[0]
        except Exception:
            pass

        told = {
            "names": names,
            "how": how,
            "default": None if pos is None else as_numbers(pos).reshape(-1),
            "now": now,
            "mass": mass,
            "where": where,
            "drive": drive,
        }
    except Exception:
        import traceback
        hurt = traceback.format_exc()
        first_step = False


# ── 무대 (공식 예제와 같은 차례) ─────────────────────────────
assets_root_path = get_assets_root_path()
if assets_root_path is None:
    carb.log_error("Could not find Isaac Sim assets folder")

prim = define_prim("/World/Ground", "Xform")
prim.GetReferences().AddReference(
    assets_root_path + "/Isaac/Environments/Grid/default_environment.usd")
define_prim("/World/PhysicsScene", "PhysicsScene")

RenderingManager.set_dt(8.0 / 200.0)
SimulationManager.set_physics_sim_device("cpu")
SimulationManager.set_physics_dt(1.0 / 200.0)

Kind = SpotFlatTerrainPolicy if args.robot == "spot" else Go2FlatTerrainPolicy
made = {"prim_path": "/World/" + args.robot,
        "position": [0, 0, 0.8 if args.robot == "spot" else 0.4]}
if args.usd:
    made["usd_path"] = assets_root_path + args.usd
    print(f" [자산] 기본 대신 이걸 씁니다: {args.usd}")
robot = Kind(**made)

base_command = torch.zeros(3, device="cpu")
_cb = SimulationManager.register_callback(on_physics_step,
                                          IsaacEvents.POST_PHYSICS_STEP)
omni.timeline.get_timeline_interface().play()
simulation_app.update()

# 깨워지기를 기다립니다 (몇 걸음이면 됩니다)
for _ in range(200):
    simulation_app.update()
    if told is not None or hurt is not None:
        break

# ── 보여줍니다 ──────────────────────────────────────────────
print()
print("=" * 70)
if hurt:
    print(" ✖ 깨우다가 터졌습니다:")
    print(hurt)
elif told is None:
    print(" ✖ 못 깨웠습니다 — 물리가 안 돌았습니다.")
else:
    names, how = told["names"], told["how"]
    default, now = told["default"], told["now"]

    if names is None:
        print(" ✖ 관절 **이름**을 못 읽었습니다.")
        print("   있는 것 중 name 이 들어간 것들:")
        for a in sorted(a for a in dir(robot.robot)
                        if "name" in a.lower() and not a.startswith("__")):
            print(f"     {a}")
        print("   → 이름 없이는 차례가 맞는지 판단할 수 없습니다.")
    else:
        print(f" 관절 이름 {len(names)}개 ({how} 로 읽었습니다)")
        print()
        print(f"   {'#':>2}  {'이름':24} {'종류':6} {'기본자세':>9} {'지금':>9}")
        print("   " + "-" * 62)
        for i, nm in enumerate(names):
            d = f"{float(default[i]):+9.3f}" if (
                default is not None and i < len(default)) else "        ?"
            c = f"{float(now[i]):+9.3f}" if (
                now is not None and i < len(now)) else "        ?"
            print(f"   {i:>2}  {nm[:24]:24} {kind_of(nm):6} {d} {c}")

        # ── 읽어줍니다 ──────────────────────────────────────
        #
        #   ★ 표만 내놓고 끝내지 않습니다 ★
        #     '기본자세'는 정책이 아는 차례이고, '이름'은 자산의 차례입니다.
        #     둘이 어긋나면 종류별로 값이 뒤섞입니다. 그걸 여기서 셉니다.
        print()
        print("-" * 70)
        if default is None or len(default) != len(names):
            print(" ※ 기본자세 값이 없거나 개수가 안 맞아 판단을 못 합니다.")
        else:
            # 종류별로 값이 뭉쳐 있어야 정상입니다.
            #   엉덩이는 0 근처, 허벅지는 +0.7~+1.1, 종아리는 -1.3~-1.8
            want = {"엉덩이": (-0.4, 0.4), "허벅지": (0.4, 1.3),
                    "종아리": (-2.0, -1.0)}
            bad = []
            unknown = 0
            for i, nm in enumerate(names):
                k = kind_of(nm)
                if k not in want:
                    unknown += 1
                    continue
                lo, hi = want[k]
                v = float(default[i])
                if not (lo <= v <= hi):
                    bad.append((i, nm, k, v))
            if unknown == len(names):
                print(" ※ 관절 이름에서 종류를 못 읽었습니다 (hip·thigh·calf 가")
                print("   아닌 이름 규칙입니다). 위 표를 직접 보셔야 합니다.")
            elif not bad:
                print(" ○ 이름과 기본자세가 종류대로 짝지어집니다.")
                print("   → **관절 차례는 범인이 아닙니다.** 다른 데를 봐야 합니다.")
            else:
                print(f" ✖ {len(bad)}개가 어긋납니다 — 이름과 값이 안 맞습니다:")
                for i, nm, k, v in bad[:8]:
                    print(f"     {i:>2} {nm[:22]:22} {k} 인데 {v:+.3f}")
                print()
                print("   → **관절 차례가 어긋났습니다.** 정책이 '허벅지'라고 낸")
                print("     값이 다른 관절로 갑니다. 어제 본 기는 자세의 원인입니다.")
                print("     고치는 길: 자산의 차례 ↔ 정책의 차례를 잇는 표를 만들어")
                print("     forward() 에 넣기 전에 값을 옮겨 심습니다.")

    # ── 무게와 자리 ─────────────────────────────────────────
    print()
    print("=" * 70)
    print(" 무게")
    print("-" * 70)
    mass, where = told.get("mass"), told.get("where")
    ANSWER = {"go2": (15.0, "실물 Unitree Go2 는 약 15 kg"),
              "spot": (33.0, "실물 Boston Dynamics Spot 은 약 33 kg")}
    real, said = ANSWER[args.robot]
    if mass is None:
        print(" ✖ 무게를 못 읽었습니다 — 판단 못 합니다.")
    else:
        total = float(np.sum(mass))
        print(f"   덩어리 {mass.size}개 · 합쳐서 {total:.2f} kg")
        print(f"   가장 무거운 덩어리 {float(np.max(mass)):.2f} kg"
              f" · 가장 가벼운 것 {float(np.min(mass)):.3f} kg")
        print(f"   ※ {said}")
        ratio = total / real
        if 0.6 <= ratio <= 1.7:
            print(f"   ○ 실물의 {ratio:.2f}배 — 무게는 말이 됩니다.")
            print("     → **무게는 범인이 아닙니다.**")
        else:
            print(f"   ✖ 실물의 {ratio:.1f}배입니다.")
            if ratio > 1.7:
                print("     → 너무 무겁습니다. 이득 60으로는 못 일어섭니다.")
                print("       Mujoco Menagerie 변환에서 단위가 어긋났을 수")
                print("       있습니다. **이것이 기는 자세의 원인입니다.**")
            else:
                print("     → 너무 가볍습니다. 반대로 튕겨 나갑니다.")

    print()
    print(" 놓은 자리와 실제 자리")
    print("-" * 70)
    put = 0.8 if args.robot == "spot" else 0.4
    if where is None:
        print(" ✖ 자리를 못 읽었습니다.")
    else:
        print(f"   놓으라고 한 높이   {put:.3f} m")
        print(f"   읽히는 높이        {float(where[2]):.3f} m")
        gap = float(where[2]) - put
        if abs(gap) < 0.03:
            print("   ○ 거의 같습니다 — 읽는 자리가 몸통 원점입니다.")
        else:
            print(f"   ※ {gap:+.3f} m 차이가 납니다.")
            print("     읽는 자리가 몸통 원점이 아니라는 뜻입니다. 그러면")
            print("     '몸 높이 0.119' 도 제가 말한 뜻이 아니었습니다 —")
            print(f"     실제 몸통은 그보다 {abs(gap):.3f} m 아래/위입니다.")

    # ── 관절을 무엇으로 미는가 ──────────────────────────────
    print()
    print("=" * 70)
    print(" 관절을 미는 힘")
    print("-" * 70)
    drive = told.get("drive") or {}
    if not drive:
        print(" ✖ 아무것도 못 읽었습니다.")
    for what, got in sorted(drive.items()):
        if isinstance(got, str):
            print(f"   {what:26} {got}")
            continue
        try:
            arr = as_numbers(got).reshape(-1)
            lo, hi = float(np.min(arr)), float(np.max(arr))
            same = "같음" if abs(hi - lo) < 1e-9 else f"{lo:g} ~ {hi:g}"
            print(f"   {what:26} {arr.size}개 · "
                  + (f"모두 {lo:g}" if same == "같음" else same))
        except Exception:
            print(f"   {what:26} {got}")
    print()
    print(" ※ Isaac Lab 의 Go2 는 강성 0 · 감쇠 0 · 힘제한 1e9 로 돌립니다")
    print("   (엔진 PD 를 안 쓰고 파이썬에서 모터를 흉내 냅니다).")
    print("   여기 숫자가 그와 많이 다르면, 정책이 배운 몸과 지금 몸이")
    print("   **다른 몸**이라는 뜻입니다.")

    print()
    print(" 견주기: --robot " + ("go2" if args.robot == "spot" else "spot")
          + " 로 한 번 더 돌려 나란히 놓으세요.")
    print(" (Spot 은 어제 이 뼈대에서 똑바로 걸었습니다 — 맞는 쪽의 본보기입니다)")

print()
print(" 닫습니다…")
sys.stdout.flush()
simulation_app.close()
