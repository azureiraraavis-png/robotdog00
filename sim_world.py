# -*- coding: utf-8 -*-
"""우리 건물을 시뮬레이터 안에 세웁니다 — 잰 값 그대로.

  ★ 왜 이것부터인가 ★

    Go2 모델은 남이 만든 것을 받아 쓰면 됩니다. 그런데 **우리 복도는
    아무도 안 만들어 줍니다.**

    그리고 이게 없으면 시뮬레이터는 장식입니다. 남의 복도에서 잘 걷는
    정책을 만들어봐야 우리 3층에서는 벽을 긁습니다. 이 건물이 특이한
    점이 한둘이 아닙니다 —

      · 로봇 높이에서 복도가 1.15 m 밖에 안 됩니다 (눈높이는 3.13 m)
      · 방 출입구마다 10 cm 단차 + 5 cm 금속 몰딩
      · 바닥이 거울 같아 라이다 반사가 절반 넘게 섞입니다
      · 계단 2층·7층 문은 닫혀 있습니다

    앞의 셋은 시뮬레이터에 넣을 수 있습니다. 넷째는 못 넣습니다 (거울
    반사는 실물 라이다의 성질입니다) — **그것도 적어둡니다.** 시뮬레이터가
    무엇을 흉내 못 내는지 모르면, 시뮬레이터에서 잘 되는데 복도에서
    안 되는 이유를 영영 못 찾습니다.

  ★ USD 를 글자로 씁니다 ★

    Isaac Sim 없이도 돌아갑니다. .usda 는 사람이 읽는 글자 형식이라
    라이브러리가 필요 없습니다. 그래서 이 파일은 **아무 데서나** 돌고,
    만들어진 파일은 Isaac Sim 에서 열면 됩니다.

    (pxr 를 쓰면 더 그럴듯하지만, 그러면 Isaac Sim 안에서만 돌아가고
     제가 시험해 볼 수가 없습니다. 시험 못 하는 코드는 안 짭니다.)

  쓰는 법

      .\\run sim_world.py                 sim/world_3f.usda 를 만듭니다
      .\\run sim_world.py --check         치수만 찍어봅니다 (파일 안 만듦)

    만들어진 파일을 Isaac Sim 에서 File > Open 으로 엽니다.
"""

import argparse
from pathlib import Path

HERE = Path(__file__).parent

# ═════════════════════════════════════════════════════════════
# 잰 값들 — 하나하나 어디서 나왔는지 적어둡니다
#
#   ★ 안 잰 것은 '안 쟀다' 고 적습니다 ★
#     그럴듯한 값을 넣어두면 나중에 잰 값과 구별이 안 됩니다.
# ═════════════════════════════════════════════════════════════

# 3층 복도 (삽질 기록: 로봇 높이 1.15 m · 눈높이 3.13 m)
CORRIDOR_LONG = 8.0          # 안 잼 — 시험용 길이입니다
CORRIDOR_WIDE = 1.50         # 2026-09-14 lidar_look 로 잰 트인 구간
PINCH_WIDE = 1.15            # 벤치·사물함 밑동이 죄는 자리 (먼저 잰 값)
PINCH_LONG = 2.0             # 안 잼 — 죄는 구간의 길이
PINCH_HIGH = 0.60            # 안 잼 — 밑동의 높이 (눈높이는 트였으니)
CEILING = 2.40               # 안 잼

# 방 출입구 단차 (2026-09-14, 양쪽에서 재서 맞춘 값)
SILL_HIGH = 0.10             # 높은 쪽에서 -0.12, 낮은 쪽 -0.02 → 약 10 cm
NOSING_HIGH = 0.05           # 가장자리 금속 몰딩 (양쪽에서 다 5 cm 로 보임)
NOSING_DEEP = 0.06           # 안 잼 — 사진으로 보아 몰딩 폭
DOOR_WIDE = 0.90             # 안 잼 — 흔한 문 폭

# 계단 (2026-09-14, 올라가는 쪽에서 잰 기울기)
STAIR_ANGLE = 32.0           # 앞 0.7m 에서 +0.3, 앞 1.9m 에서 +1.0
STAIR_RISE = 0.17            # 안 잼 — 흔한 챌판 높이. 각도와 맞춰 디딤을 냄
STAIR_COUNT = 10             # 안 잼
STAIR_WIDE = 1.20            # 안 잼

# 시뮬레이터가 **흉내 못 내는 것** (넣지 않습니다 — 적기만 합니다)
CANNOT_SIMULATE = [
    "거울 같은 바닥 — 라이다 반사가 절반 넘게 섞입니다. 실물 라이다의 "
    "성질이라 USD 로는 안 들어갑니다.",
    "라이다가 보는 상자가 6.4×6.4×1.9 m 뿐이라는 것 — 시뮬레이터의 "
    "라이다는 설정하기 나름입니다. 똑같이 맞춰두지 않으면 "
    "'시뮬레이터에서는 계단이 다 보였는데' 가 됩니다.",
    "로봇이 왼쪽으로 4도/m 휘는 버릇 — 실기체의 걸음에 든 것입니다.",
    "계단실 2층·7층 문이 닫혀 있다는 것 — 사람이 여닫습니다.",
]


def box(name, centre, half, kind="static"):
    """네모 하나. centre 는 가운데, half 는 반지름 셋 (x, y, z).

    ★ Cube 의 size 는 2 입니다 ★
      USD 의 Cube 는 -1~+1 짜리라 한 변이 2 입니다. 그러니 scale 에
      **반지름**을 넣으면 실제 크기가 됩니다. size 를 그대로 크기로
      알고 넣으면 모든 것이 두 배가 됩니다.
    """
    cx, cy, cz = centre
    hx, hy, hz = half
    api = '["PhysicsCollisionAPI"]'
    return f'''
    def Cube "{name}" (prepend apiSchemas = {api})
    {{
        double size = 2
        double3 xformOp:translate = ({cx}, {cy}, {cz})
        float3 xformOp:scale = ({hx}, {hy}, {hz})
        uniform token[] xformOpOrder = ["xformOp:translate", "xformOp:scale"]
    }}'''


def build():
    """복도 + 문턱 + 계단. 로봇은 원점에서 +x 를 보고 섭니다."""
    parts = []
    L = CORRIDOR_LONG
    W = CORRIDOR_WIDE

    # 바닥 — 원점이 바닥면이 되도록 살짝 내려 깝니다
    parts.append(box("floor", (L / 2, 0, -0.05), (L / 2 + 1, W / 2 + 1, 0.05)))

    # 양쪽 벽
    for side, y in (("left", +W / 2), ("right", -W / 2)):
        parts.append(box(f"wall_{side}",
                         (L / 2, y + (0.1 if y > 0 else -0.1), CEILING / 2),
                         (L / 2, 0.1, CEILING / 2)))

    # ★ 죄는 자리 ★ — 벤치·사물함 밑동. 낮아서 눈높이는 트여 있습니다.
    #   이것 때문에 로봇 높이 통로가 1.15 m 로 줄어듭니다.
    squeeze = (W - PINCH_WIDE) / 2
    for side, y in (("left", +1), ("right", -1)):
        parts.append(box(
            f"pinch_{side}",
            (L * 0.35, y * (W / 2 - squeeze / 2), PINCH_HIGH / 2),
            (PINCH_LONG / 2, squeeze / 2, PINCH_HIGH / 2)))

    # ★ 방 출입구 단차 ★ — 단 + 가장자리 몰딩
    sill_x = L * 0.65
    parts.append(box("sill_platform",
                     (sill_x + 1.0, 0, SILL_HIGH / 2),
                     (1.0, DOOR_WIDE / 2, SILL_HIGH / 2)))
    parts.append(box("sill_nosing",
                     (sill_x, 0, (SILL_HIGH + NOSING_HIGH) / 2),
                     (NOSING_DEEP / 2, DOOR_WIDE / 2,
                      (SILL_HIGH + NOSING_HIGH) / 2)))

    # ★ 계단 ★ — 각도에 맞춰 디딤 깊이를 냅니다
    import math
    tread = STAIR_RISE / math.tan(math.radians(STAIR_ANGLE))
    start = L + 0.5
    for i in range(STAIR_COUNT):
        z = (i + 1) * STAIR_RISE
        parts.append(box(
            f"stair_{i:02d}",
            (start + i * tread + tread / 2, 0, z / 2),
            (tread / 2, STAIR_WIDE / 2, z / 2)))

    head = f'''#usda 1.0
(
    defaultPrim = "World"
    metersPerUnit = 1
    upAxis = "Z"
    doc = """3층 복도 — 2026-09-14 에 로봇이 직접 잰 값으로 세웠습니다.

    복도 폭 {CORRIDOR_WIDE} m · 죄는 자리 {PINCH_WIDE} m (높이 {PINCH_HIGH} m)
    문턱 {SILL_HIGH} m + 몰딩 {NOSING_HIGH} m
    계단 {STAIR_ANGLE} 도 · 챌판 {STAIR_RISE} m · 디딤 {tread:.3f} m

    ※ 안 잰 값은 sim_world.py 에 '안 잼' 이라고 적혀 있습니다."""
)

def Xform "World"
{{
    def DistantLight "sun"
    {{
        float inputs:intensity = 1500
        double3 xformOp:rotateXYZ = (-45, 0, 45)
        uniform token[] xformOpOrder = ["xformOp:rotateXYZ"]
    }}
'''
    return head + "\n".join(parts) + "\n}\n", tread


def main():
    ap = argparse.ArgumentParser(description="우리 건물을 USD 로 세웁니다")
    ap.add_argument("--check", action="store_true", help="치수만 찍습니다")
    ap.add_argument("--out", default="sim/world_3f.usda")
    args = ap.parse_args()

    text, tread = build()

    print("=" * 70)
    print(" 3층 복도 — 잰 값으로 세웁니다")
    print("=" * 70)
    print(f"  복도 폭        {CORRIDOR_WIDE:.2f} m    (잼)")
    print(f"  죄는 자리      {PINCH_WIDE:.2f} m    (잼) · 높이 {PINCH_HIGH} m (안 잼)")
    print(f"  문턱           {SILL_HIGH:.2f} m    (잼) + 몰딩 {NOSING_HIGH:.2f} m (잼)")
    print(f"  계단           {STAIR_ANGLE:.0f} 도    (잼) · 챌판 {STAIR_RISE} m (안 잼)")
    print(f"                 → 디딤 {tread:.3f} m")
    print()
    # ── 로봇이 지날 틈 ──────────────────────────────────────
    #
    #   ★ 셈해놓고 눈으로 안 보면 이렇게 됩니다 ★
    #     처음에 "14 cm 밀리는데 여유가 42 cm 입니다. 닿습니다." 라고
    #     찍었습니다. 14 는 42 보다 작습니다. 숫자를 내놓고 그 숫자를
    #     안 읽은 것입니다 — 재게 만들어놓고 판단은 손으로 했습니다.
    #     견주는 것까지 코드가 해야 합니다.
    print(" 로봇이 지날 틈 (몸 폭 0.31 m · 오늘 잰 휘어짐 5 cm/m)")
    body = 0.31
    drift = 0.05                               # m/m, 2026-09-14 측정
    for where, width, run in (("죄는 자리", PINCH_WIDE, PINCH_LONG),
                              ("복도 전체", CORRIDOR_WIDE, CORRIDOR_LONG)):
        side = (width - body) / 2
        off = drift * run
        mark = "★ 닿습니다" if off >= side else "지납니다"
        print(f"   {where:8} 여유 {side*100:4.0f} cm · "
              f"{run:.0f} m 가면 {off*100:4.0f} cm 밀림   → {mark}")
    print("   ※ 되잡지 않고 곧게만 시켰을 때입니다. walk_straight 로 "
          "되잡으면 줄어듭니다.")
    print()
    print(" ★ 시뮬레이터가 흉내 못 내는 것 ★")
    for line in CANNOT_SIMULATE:
        print(f"   · {line}")
    print()

    if args.check:
        print(" (--check 라 파일은 안 만들었습니다)")
        return 0

    out = HERE / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f" {out.relative_to(HERE)} 를 만들었습니다 ({len(text):,} 글자)")
    print(" Isaac Sim 에서 File > Open 으로 여세요.")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
