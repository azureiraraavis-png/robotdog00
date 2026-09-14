# -*- coding: utf-8 -*-
"""Isaac Sim 이 들고 있는 **원본 코드**를 꺼내 봅니다.  ★ 시뮬레이터를 안 띄웁니다 ★

  ★ 왜 이걸 만드는가 ★

    2026-09-14, sim_go2.py 로 Go2 를 세웠더니 **주저앉았습니다** —
    몸 높이 0.065 m. 물리는 돕니다(중력에 떨어졌으니까). 그런데 정책이
    다리를 안 붙들고 있습니다.

    여기서 제가 "아마 initialize 를 부르는 순서가 틀렸을 겁니다" 라고
    고쳐보는 건 **짐작**입니다. 오늘 그 짐작으로 라이다에서 다섯 번,
    계단에서 한 번 틀렸습니다.

    그런데 정답이 이미 이 컴퓨터 안에 있습니다. NVIDIA 가 go2.py 와
    그걸 쓰는 공식 예제를 같이 넣어뒀습니다. **읽으면 됩니다.**

  ★ 시뮬레이터를 안 띄웁니다 ★

    그냥 파일을 찾아서 읽을 뿐입니다. 12초짜리 부팅이 필요 없습니다.
    그래서 보통 파이썬으로도 돌아갑니다.

  쓰는 법

      .\\run sim_source.py
      C:\\isaacsim\\python.bat D:\\workspace_raraavis\\robotdog00\\sim_source.py

      옵션
        --root C:\\isaacsim   폴더를 못 찾을 때만
        --full               예제를 통째로 (기본은 요점만)
"""

import argparse
import os
import re
import sys
from pathlib import Path

# 찾을 것들 — 파일 이름과, 그 안에서 눈여겨볼 것
LOOK = [
    ("go2.py", "Go2 정책 클래스 — 무엇을 받고 initialize 가 뭘 하는지"),
    ("policy_controller.py", "그 부모 — 관절 이득(gain)을 어디서 넣는지"),
]

# 공식 예제에서 우리가 알고 싶은 것: **도는 차례**
#   world.step 이 먼저인가 forward 가 먼저인가, initialize 를 언제 부르는가.
LOOP_HINTS = ("initialize", "world.step", "my_world.step", "is_playing",
              "reset", "forward", "physics_dt", "first_step", "base_command")


def find_root(given=None):
    tries = []
    if given:
        tries.append(Path(given))
    for key in ("ISAAC_SIM_PATH", "ISAACSIM_PATH"):
        if os.environ.get(key):
            tries.append(Path(os.environ[key]))
    here = Path(sys.executable).resolve()
    for up in [here] + list(here.parents)[:5]:
        if up.name.lower().startswith("isaacsim"):
            tries.append(up)
    tries += [Path("C:/isaacsim"), Path.home() / "isaacsim"]
    for t in tries:
        try:
            if t.exists() and (t / "exts").exists():
                return t
        except Exception:
            continue
    return None


def show(path, title, full=False):
    """파일을 보여줍니다. 길면 요점만."""
    print()
    print("=" * 70)
    print(f" {path.name}   — {title}")
    print(f" {path}")
    print("=" * 70)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        print(f" ✖ 못 읽었습니다: {e}")
        return
    lines = text.splitlines()
    if full or len(lines) <= 160:
        for i, ln in enumerate(lines, 1):
            print(f"{i:4} {ln}")
        return

    # ★ 길면 통째로 찍지 않습니다 ★
    #   오늘 dir() 를 20개에서 잘라서 답을 제 손으로 가린 적이 있습니다.
    #   그래서 여기서는 **자르되, 자른 것을 말합니다.**
    print(f" ※ {len(lines)}줄입니다. def 와 그 속을 보여줍니다 (--full 로 전부).")
    keep = set()
    for i, ln in enumerate(lines):
        if re.match(r"\s*(def |class |@)", ln):
            for j in range(i, min(i + 24, len(lines))):
                keep.add(j)
    last = -2
    for i in sorted(keep):
        if i != last + 1:
            print("   ...")
        print(f"{i+1:4} {lines[i]}")
        last = i


def main():
    ap = argparse.ArgumentParser(description="Isaac Sim 원본 코드를 꺼내 봅니다")
    ap.add_argument("--root")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()

    print("=" * 70)
    print(" Isaac Sim 이 들고 있는 원본 코드")
    print("=" * 70)
    print(" ※ 시뮬레이터를 띄우지 않습니다. 파일만 읽습니다.")

    root = find_root(args.root)
    if root is None:
        print(" ✖ Isaac Sim 폴더를 못 찾았습니다. --root 로 알려주세요.")
        return 1
    print(f" 폴더: {root}")

    exts = root / "exts"

    # ── 1. 우리가 쓰는 클래스의 원본 ────────────────────────
    for name, why in LOOK:
        hits = sorted(exts.rglob(name))
        hits = [h for h in hits if "policy" in str(h).lower()]
        if not hits:
            print(f"\n ✖ {name} 을 못 찾았습니다.")
            continue
        show(hits[0], why, full=args.full)
        if len(hits) > 1:
            print(f" ※ 같은 이름이 {len(hits)}개 더 있습니다: "
                  + ", ".join(str(h) for h in hits[1:3]))

    # ── 2. 공식 예제 — ★ 도는 차례를 여기서 봅니다 ★ ────────
    #
    #   클래스만 봐서는 "언제 부르는가" 가 안 나옵니다. 예제가 그걸
    #   보여줍니다. 우리가 지금 막힌 게 정확히 그 차례입니다.
    print()
    print("=" * 70)
    print(" 공식 예제 — 이 정책을 **어떤 차례로** 부르는가")
    print("=" * 70)
    ex = root / "standalone_examples"
    found = []
    if ex.exists():
        for p in ex.rglob("*.py"):
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if "FlatTerrainPolicy" in t or "policy.examples" in t:
                found.append((p, t))
    if not found:
        print(" ✖ standalone_examples 에서 못 찾았습니다.")
        print("   exts 안의 예제도 봅니다…")
        for p in exts.rglob("*.py"):
            if "example" not in str(p).lower():
                continue
            try:
                t = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if "FlatTerrainPolicy" in t and "class " not in t.split("\n")[0]:
                found.append((p, t))

    # Go2 를 쓰는 것을 먼저
    found.sort(key=lambda pt: (0 if "go2" in str(pt[0]).lower() else 1,
                               len(pt[1])))
    if not found:
        print(" ✖ 예제를 못 찾았습니다. 그러면 클래스 원본만 보고 갑니다.")
        return 0

    for p, t in found[:2]:
        print()
        print("-" * 70)
        print(f" {p}")
        print("-" * 70)
        lines = t.splitlines()
        if args.full or len(lines) <= 140:
            for i, ln in enumerate(lines, 1):
                print(f"{i:4} {ln}")
        else:
            print(f" ※ {len(lines)}줄 — 도는 차례에 해당하는 줄만 (--full 로 전부)")
            for i, ln in enumerate(lines, 1):
                if any(h in ln for h in LOOP_HINTS):
                    print(f"{i:4} {ln}")
    if len(found) > 2:
        print(f"\n ※ 이런 예제가 {len(found)}개 있습니다. 나머지: "
              + ", ".join(p.name for p, _ in found[2:6]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
