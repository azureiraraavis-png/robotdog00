# -*- coding: utf-8 -*-
"""Isaac Sim 이 스크립트로 열리는지 봅니다.  ★ 시뮬레이터를 띄우지는 않습니다 ★

  ★ 왜 이것부터인가 ★

    Isaac Sim 은 GUI 로도 쓰고 스크립트로도 씁니다. GUI 만 쓰면 매번
    손으로 눌러야 하고, 무엇을 눌렀는지 기록이 안 남습니다. 이 저장소가
    여태 해온 방식과 안 맞습니다 — 우리는 **돌리면 같은 답이 나오는
    것**을 만들어 왔습니다.

    그러려면 C:\\isaacsim\\python.bat 로 파이썬을 돌릴 수 있어야 합니다.
    그게 되는지가 앞으로 할 수 있는 것을 통째로 가릅니다.

  ★ 띄우지 않고 봅니다 ★

    SimulationApp 을 실제로 만들면 수십 초가 걸리고, 화면이 없으면
    거기서 멈춥니다. 여기서는 **가져올 수 있는지만** 봅니다
    (importlib.util.find_spec — 불러오지 않고 있는지만 확인합니다).

    판마다 이름이 달라져 온 물건이라, **어느 이름이 살아 있는지**를
    찾아서 알려줍니다. 제가 짐작해서 하나를 박아두면 그 판에서만
    돌아갑니다.

  쓰는 법 (★ 보통 파이썬 말고 Isaac Sim 의 것으로 돌립니다 ★)

      C:\\isaacsim\\python.bat D:\\workspace_raraavis\\robotdog00\\sim_check.py

    그냥 .\\run sim_check.py 로 돌려도 돌아가긴 합니다 — 그때는
    "Isaac Sim 의 파이썬이 아닙니다" 라고 알려주고, 폴더만 살펴봅니다.
"""

import argparse
import importlib.util
import os
import sys
from pathlib import Path

# 판마다 이름이 바뀌어 온 것들. 있는 것을 찾아서 알려줍니다.
WANTED = [
    ("isaacsim", "요즘 판의 들머리"),
    ("isaacsim.simulation_app", "SimulationApp 이 여기 있을 수 있습니다"),
    ("omni.isaac.kit", "예전 판의 SimulationApp"),
    ("omni.isaac.core", "예전 판의 World·Robot (켜기 전 ✖ 정상)"),
    ("isaacsim.core.api", "요즘 판의 World·Robot (켜기 전 ✖ 정상)"),
    ("pxr", "USD — ★ 켜기 전에는 ✖ 가 정상입니다 ★"),
    ("isaaclab", "★ 강화학습 틀 (Go2 자산이 여기 있습니다)"),
]


def looks_like_isaac(py):
    """지금 돌고 있는 파이썬이 Isaac Sim 것인가."""
    p = str(py).replace("\\", "/").lower()
    return "isaacsim" in p or "isaac-sim" in p or "isaac_sim" in p


def find_root(given=None):
    """Isaac Sim 폴더를 찾습니다."""
    tries = []
    if given:
        tries.append(Path(given))
    env = os.environ.get("ISAAC_SIM_PATH") or os.environ.get("ISAACSIM_PATH")
    if env:
        tries.append(Path(env))
    # 지금 파이썬이 그 안에 있으면 거기서 거슬러 올라갑니다
    here = Path(sys.executable).resolve()
    for up in [here] + list(here.parents)[:4]:
        if up.name.lower().startswith("isaacsim"):
            tries.append(up)
    tries += [Path("C:/isaacsim"), Path.home() / "isaacsim"]
    for t in tries:
        try:
            if t.exists() and (t / "apps").exists():
                return t
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description="Isaac Sim 을 스크립트로 열 수 있는가")
    ap.add_argument("--root", help="Isaac Sim 폴더 (못 찾을 때만)")
    args = ap.parse_args()

    print("=" * 70)
    print(" Isaac Sim 이 스크립트로 열리는가")
    print("=" * 70)
    print(" ※ 시뮬레이터를 띄우지는 않습니다. 있는지만 봅니다.")
    print()

    # ── 1. 어느 파이썬으로 돌고 있는가 ──────────────────────
    #
    #   ★ 이걸 먼저 봐야 아래가 뜻을 가집니다 ★
    #     보통 파이썬으로 돌리면 Isaac 것이 하나도 안 보이는 게 당연합니다.
    #     그걸 "설치가 안 됐다" 로 읽으면 엉뚱한 데를 뒤집니다.
    mine = looks_like_isaac(sys.executable)
    print(f" 지금 돌고 있는 파이썬")
    print(f"   {sys.executable}")
    print(f"   {sys.version.split()[0]}")
    if mine:
        print("   ○ Isaac Sim 의 파이썬입니다 — 아래 결과를 믿어도 됩니다.")
    else:
        print("   ※ Isaac Sim 의 파이썬이 **아닙니다.**")
        print("     아래에서 Isaac 것이 안 보이는 건 당연합니다.")
        print("     제대로 보려면:")
        print("       C:\\isaacsim\\python.bat <이 파일의 전체 경로>")
    print()

    # ── 2. 폴더 ─────────────────────────────────────────────
    root = find_root(args.root)
    print(" Isaac Sim 폴더")
    if root is None:
        print("   ✖ 못 찾았습니다. --root 로 알려주세요.")
    else:
        print(f"   {root}")
        for name in ("python.bat", "python.sh", "isaac-sim.bat", "VERSION"):
            got = (root / name).exists()
            print(f"     {'○' if got else '·'} {name}")
        ver = root / "VERSION"
        if ver.exists():
            try:
                print(f"   판: {ver.read_text(encoding='utf-8').strip()}")
            except Exception:
                pass
        ex = root / "standalone_examples"
        if ex.exists():
            n = sum(1 for _ in ex.rglob("*.py"))
            print(f"   standalone_examples 에 파이썬 파일 {n}개 "
                  "— 스크립트로 쓰는 본보기들입니다")
    print()

    # ── 3. 가져올 수 있는 것들 ──────────────────────────────
    print(" 가져올 수 있는 것 (불러오지는 않습니다)")
    print("   ※ Kit 은 **시뮬레이터가 켜질 때** 확장을 올립니다. 그러니")
    print("     pxr · core 는 켜기 전에는 ✖ 가 나오는 게 정상입니다.")
    print("     정말 되는지는 .\\sim_open.py 로 한 번 켜봐야 압니다.")
    found = {}
    for name, why in WANTED:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ValueError, AttributeError):
            spec = None
        found[name] = spec is not None
        print(f"   {'○' if spec else '✖'} {name:28} {why}")
    print()

    # ── 4. 우리 세계 ────────────────────────────────────────
    world = Path(__file__).parent / "sim" / "world_3f.usda"
    print(" 우리가 세운 3층")
    if world.exists():
        text = world.read_text(encoding="utf-8", errors="replace")
        cubes = text.count("def Cube")
        print(f"   ○ {world.name} · 네모 {cubes}개 · {len(text):,} 글자")
    else:
        print("   ✖ 아직 없습니다 — .\\run sim_world.py 로 만드세요.")
    print()

    # ── 5. 그래서 무엇을 할 수 있는가 ───────────────────────
    print("=" * 70)
    print(" 이것이 뜻하는 것")
    print("-" * 70)
    if not mine:
        print("   먼저 Isaac Sim 의 파이썬으로 다시 돌려주세요.")
        print("   지금 결과로는 아무것도 판단할 수 없습니다.")
        return 0

    app = [n for n in ("isaacsim", "isaacsim.simulation_app", "omni.isaac.kit")
           if found.get(n)]
    if app:
        print(f"   ○ 스크립트로 열 수 있습니다 — {app[0]} 을 씁니다.")
        print("     GUI 를 안 거치고 세계를 열고 닫을 수 있다는 뜻입니다.")
        print("     → 이제 한 번 켜보세요:")
        print("       C:\\isaacsim\\python.bat <이 폴더>\\sim_open.py")
    else:
        print("   ✖ SimulationApp 을 찾는 이름 셋이 다 없습니다.")
        print("     판이 제 예상과 다릅니다. standalone_examples 안의")
        print("     아무 예제나 열어 맨 윗줄을 보면 이 판의 이름이 나옵니다.")

    if found.get("isaaclab"):
        print("   ○ Isaac Lab 이 있습니다 — Go2 자산과 보행 환경을 쓸 수 있습니다.")
    else:
        print("   ✖ Isaac Lab 이 없습니다.")
        print("     **Go2 자산이 거기 들어 있습니다.** 로봇을 세우려면")
        print("     따로 설치해야 하고, 그건 수 GB 를 받는 일입니다.")
        print("     오늘은 우리가 세운 복도를 여는 것까지가 끝입니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
