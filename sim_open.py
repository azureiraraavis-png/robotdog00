# -*- coding: utf-8 -*-
"""우리 3층을 Isaac Sim 으로 실제로 열어봅니다.  ★ 화면 없이 (headless) ★

  ★ sim_check 로는 여기까지 못 봤습니다 ★

    sim_check 가 `pxr ✖` 라고 했는데, USD 가 없는 게 아닙니다.
    **Kit 은 시뮬레이터가 켜질 때 확장을 올립니다.** pxr 도 그때
    길에 올라옵니다. 켜기 전에 본 검사가 "없다" 로 읽은 것뿐입니다.

    그래서 진짜 확인은 한 번 켜보는 것입니다. 이 파일이 그것입니다.

  ★ 켜는 이름을 짐작하지 않습니다 ★

    SimulationApp 을 가져오는 길이 판마다 달라져 왔습니다. 세 가지를
    차례로 해보고 **되는 것을 알려줍니다.** 제가 하나를 박아두면 그
    판에서만 돌아가고, 안 될 때 왜 안 되는지도 안 알려줍니다.

  ★ 순서가 중요합니다 ★

    SimulationApp 을 **먼저 만들어야** pxr·omni 를 가져올 수 있습니다.
    위에 몰아서 import 하면 거기서 죽습니다. 그래서 이 파일은 import 가
    함수 안에 흩어져 있습니다 — 보기에 이상하지만 이게 맞습니다.

  쓰는 법 (★ Isaac Sim 의 파이썬으로 ★)

      C:\\isaacsim\\python.bat D:\\workspace_raraavis\\robotdog00\\sim_open.py

      옵션
        --gui        화면을 띄웁니다 (느립니다)
        --seconds 3  물리를 몇 초 돌려봅니다 (물건이 안 무너지는지)

  ※ 처음 켜면 셰이더를 굽느라 **몇 분** 걸릴 수 있습니다. 그 뒤로는 빠릅니다.
"""

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).parent
WORLD = HERE / "sim" / "world_3f.usda"


def start(headless=True):
    """SimulationApp 을 켭니다. (앱, 어느 이름으로 켰는지) 를 돌려줍니다."""
    tries = [
        ("isaacsim", "SimulationApp"),
        ("isaacsim.simulation_app", "SimulationApp"),
        ("omni.isaac.kit", "SimulationApp"),
    ]
    last = None
    for mod, attr in tries:
        try:
            ns = __import__(mod, fromlist=[attr])
            App = getattr(ns, attr)
        except (ImportError, AttributeError) as e:
            last = f"{mod}: {type(e).__name__}"
            continue
        print(f" [켜기] {mod}.{attr} 로 켭니다…")
        return App({"headless": headless}), f"{mod}.{attr}"
    raise SystemExit(
        " ✖ SimulationApp 을 어디서도 못 찾았습니다.\n"
        f"   마지막 오류: {last}\n"
        "   C:\\isaacsim\\standalone_examples 의 아무 예제나 열어\n"
        "   맨 윗줄을 보면 이 판의 이름이 나옵니다.")


def look(path):
    """연 무대를 훑어봅니다. SimulationApp 이 켜진 뒤에만 부를 수 있습니다."""
    from pxr import Usd, UsdGeom          # ★ 켠 뒤라야 가져와집니다 ★

    stage = Usd.Stage.Open(str(path))
    if stage is None:
        return None

    kinds = {}
    cubes = []
    for prim in stage.Traverse():
        t = prim.GetTypeName()
        kinds[t] = kinds.get(t, 0) + 1
        if t == "Cube":
            cubes.append(prim.GetName())

    # 무대가 실제로 얼마나 큰지 — 우리가 적어둔 치수와 견주려고
    lo = hi = None
    try:
        cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                                  [UsdGeom.Tokens.default_])
        box = cache.ComputeWorldBound(stage.GetPseudoRoot())
        rng = box.ComputeAlignedRange()
        lo, hi = rng.GetMin(), rng.GetMax()
    except Exception:
        pass
    return {"stage": stage, "kinds": kinds, "cubes": cubes, "lo": lo, "hi": hi}


def main():
    ap = argparse.ArgumentParser(description="우리 3층을 Isaac Sim 으로 엽니다")
    ap.add_argument("--gui", action="store_true", help="화면을 띄웁니다")
    ap.add_argument("--seconds", type=float, default=0.0,
                    help="물리를 몇 초 돌려봅니다")
    ap.add_argument("--world", default=str(WORLD))
    args = ap.parse_args()

    world = Path(args.world)
    print("=" * 70)
    print(" 우리 3층을 Isaac Sim 으로 열어봅니다")
    print("=" * 70)
    if not world.exists():
        print(f" ✖ {world} 가 없습니다 — 먼저 .\\run sim_world.py")
        return 1
    print(f" 세계: {world}")
    print(f" 화면: {'띄웁니다' if args.gui else '안 띄웁니다 (headless)'}")
    print(" ※ 처음 켜면 셰이더를 굽느라 몇 분 걸릴 수 있습니다.")
    print()

    app, how = start(headless=not args.gui)
    try:
        got = look(world)
        print()
        print("=" * 70)
        if got is None:
            print(" ✖ USD 를 못 열었습니다. 파일이 깨졌을 수 있습니다.")
            return 1

        print(f" ○ 열렸습니다 ({how})")
        print()
        print(" 무대 안에 있는 것")
        for kind, n in sorted(got["kinds"].items(), key=lambda kv: -kv[1]):
            print(f"   {kind or '(이름없음)':16} {n:>3}개")
        print()
        if got["lo"] is not None:
            lo, hi = got["lo"], got["hi"]
            print(" 실제로 차지하는 크기 (우리가 적어둔 치수와 견주세요)")
            print(f"   x {lo[0]:+7.2f} ~ {hi[0]:+7.2f} m   "
                  f"(길이 {hi[0]-lo[0]:.2f})")
            print(f"   y {lo[1]:+7.2f} ~ {hi[1]:+7.2f} m   "
                  f"(폭  {hi[1]-lo[1]:.2f})")
            print(f"   z {lo[2]:+7.2f} ~ {hi[2]:+7.2f} m   "
                  f"(높이 {hi[2]-lo[2]:.2f})")
            print("   ※ 벽 두께와 계단이 더해진 값입니다. 복도 폭 자체는")
            print("     sim_world.py 의 CORRIDOR_WIDE 입니다.")
        print()
        print(" 네모들: " + ", ".join(got["cubes"][:8])
              + (f" … 그 밖에 {len(got['cubes'])-8}개"
                 if len(got["cubes"]) > 8 else ""))

        # ── 물리를 돌려봅니다 ────────────────────────────────
        #   ★ 열렸다와 서 있다는 다릅니다 ★
        #     치수가 틀리면 물건이 겹친 채로 시작하고, 물리를 켜는
        #     순간 튕겨 나갑니다. 몇 초 돌려보면 그게 드러납니다.
        if args.seconds > 0:
            print()
            print(f" 물리를 {args.seconds:.0f}초 돌려봅니다…")
            from isaacsim.core.api import World
            w = World(stage_units_in_meters=1.0)
            w.scene.add_default_ground_plane()
            w.reset()
            steps = int(args.seconds * 60)
            for _ in range(steps):
                w.step(render=args.gui)
            print(f"   ○ {steps}걸음 돌았습니다. 터지지 않았습니다.")

        print("=" * 70)
        print(" 다음에 할 것")
        print("   · Isaac Lab 을 깔면 Go2 자산이 생깁니다 (수 GB)")
        print("   · 그 전까지는 이 세계에 아무 로봇이나 세워 걸려보는 정도")
        print("   · ★ 시뮬레이터 라이다를 우리 것과 같게 맞추기 ★")
        print("     6.4×6.4×1.9 m 상자. 안 맞추면 계단 밑바닥까지 다 보입니다.")
        return 0
    finally:
        print()
        print(" 닫습니다…")
        app.close()


if __name__ == "__main__":
    sys.exit(main())
