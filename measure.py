# -*- coding: utf-8 -*-
"""
안내 코스 실측 — 정차 지점 사이의 거리와, 각 지점의 복도 폭.

  ★ 이 스크립트는 로봇을 움직이지 않습니다 ★
    이동 명령을 **한 줄도** 보내지 않습니다. 로봇은 사람이 리모컨으로
    몹니다. 우리는 옆에서 듣고 적기만 합니다.
    (일으켜 세우는 것만 물어보고 합니다 — 엎드린 채로는 라이다가 낮은
     데만 봐서 복도 폭이 안 나옵니다)

  ★ 왜 이게 필요한가 ★
    안내 코스의 이동을 '몇 초' 가 아니라 '몇 미터' 로 적어야 합니다.
    시간 기반은 실측에서 25% 까지 어긋났고, 21 m 복도에서 그건 방 하나를
    통째로 지나칠 거리입니다.

    그런데 도면으로는 못 채웁니다. 받은 도면이 계획도라서 방 구획이
    현재와 다릅니다 (302호가 도면에 아예 없습니다).
    그래서 현장에서 잽니다.

  ★ 한 번에 두 가지를 얻습니다 ★
    1. 정차 지점 사이 거리   ← robot_pose (라이다 주행거리계)
    2. 각 지점의 복도 실폭   ← 라이다, 로봇 높이에서
       ※ 2번은 줄자보다 낫습니다. 도면의 2.20 m 가 아니라 **가구 사이로
         로봇이 실제로 지나갈 수 있는 폭**을 재기 때문입니다.

    그리고 덤으로 세 번째: 줄자 값과 비교하면 **21 m 를 갔을 때
    주행거리계가 얼마나 흐르는지** 알게 됩니다. 다음 단계('거리로 걷기')가
    믿을 만한지를 그 숫자가 결정합니다.

  쓰는 법

      .\\run measure.py

    1. 로봇을 대기 위치(엘리베이터 앞)에 세웁니다
    2. Enter → 지점 이름을 적습니다 (예: 대기위치)
    3. 리모컨으로 다음 정차 지점까지 몹니다
    4. Enter → 이름을 적습니다 (예: 301호앞)
    5. 반복. 끝나면 q

    끝나면 표가 나오고 measure_log.txt 에 남습니다.

  같이 챙기면 좋은 것
    □ 줄자 (주행거리계 검산용 — 최소 한 구간만이라도)
    □ 바닥에 붙일 마스킹 테이프 (정차 지점 표시. 다음에 또 옵니다)
    □ 배터리, 리모컨
"""

import asyncio
import math
import sys
import time
from pathlib import Path

import common
import perception

LOG = Path(__file__).parent / "measure_log.txt"

# 로봇이 제자리에서 돌려면 이만큼은 비어야 합니다 (m).
#   몸통 0.70 × 0.31 → 대각선 0.77. 여유를 두어 0.90.
TURN_NEED = 0.90


class Point:
    def __init__(self, name, pose, clear):
        self.name = name
        self.pose = pose            # (x, y, z, yaw)
        self.clear = clear
        self.stamp = time.time()

    def yaw_deg(self):
        return math.degrees(self.pose[3])


def gap(a, b):
    """두 지점 사이 직선 거리 (m)."""
    return math.hypot(b.pose[0] - a.pose[0], b.pose[1] - a.pose[1])


def turn(a, b):
    """a 에서 b 로 갈 때 방향이 얼마나 바뀌었는가 (도, -180~180)."""
    d = b.yaw_deg() - a.yaw_deg()
    return (d + 180) % 360 - 180


def show(points):
    if not points:
        print("\n기록된 지점이 없습니다.")
        return ""

    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    out()
    out("=" * 72)
    out(" 실측 결과")
    out("=" * 72)
    out(f"{'지점':16}{'구간거리':>10}{'누적':>9}{'방향변화':>10}"
        f"{'복도폭':>9}{'왼':>7}{'오른':>7}")
    out("-" * 72)

    total = 0.0
    for i, p in enumerate(points):
        if i == 0:
            seg = turned = 0.0
            seg_s = seg_t = "—"
        else:
            seg = gap(points[i - 1], p)
            turned = turn(points[i - 1], p)
            total += seg
            seg_s = f"{seg:.2f} m"
            seg_t = f"{turned:+.0f}°"
        c = p.clear
        w = c.width()
        out(f"{common_pad(p.name, 16)}{seg_s:>10}{f'{total:.2f} m':>9}{seg_t:>10}"
            f"{(f'{w:.2f} m' if w else '—'):>9}"
            f"{(f'{c.left:.2f}' if c.left else '—'):>7}"
            f"{(f'{c.right:.2f}' if c.right else '—'):>7}")

    out("-" * 72)
    out(f" 총 이동 거리 {total:.2f} m")

    # ── 경고 ──
    out()
    tight = [p for p in points
             if p.clear.width() is not None and p.clear.width() < TURN_NEED]
    if tight:
        out(f" ★ 제자리 회전이 어려운 지점 (폭 {TURN_NEED:.2f} m 미만) ★")
        for p in tight:
            out(f"     {p.name} — {p.clear.width():.2f} m")
        out("   여기서는 문 쪽으로 몸을 돌리는 동작을 넣지 마세요.")
    blind = [p for p in points if p.clear.width() is None]
    if blind:
        out(" ※ 폭을 못 잰 지점: " + ", ".join(p.name for p in blind))
        out("   한쪽이 트여 있거나(문이 열림), 유리라 안 보인 것입니다.")

    out()
    out(" scenario.py 에 옮길 값")
    for i in range(1, len(points)):
        out(f"   {points[i-1].name} → {points[i].name}"
            f"   meters={gap(points[i-1], points[i]):.2f}")

    out()
    out(" ※ 이 거리는 라이다 주행거리계 값입니다. 줄자와 비교해 보세요.")
    out("   한 구간만 재도 됩니다 — 어긋난 비율이 나머지에도 그대로 적용됩니다.")
    return "\n".join(lines)


def common_pad(text, width):
    """한글 폭을 세어 자리를 맞춥니다."""
    import unicodedata
    w = sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in text)
    return text + " " * max(0, width - w)


async def run(conn):
    probe = common.StateProbe(conn)
    await probe.read()

    print("\n[준비] 자세 확인")
    await common.ensure_standing(conn, probe=probe, ask=True)

    eyes = perception.Eyes(conn)
    if not await eyes.start():
        print("\n라이다가 없으면 거리도 폭도 못 잽니다. 중단합니다.")
        return
    print("[눈] 지도가 자리를 잡도록 3초 기다립니다...")
    await asyncio.sleep(3.0)

    print()
    print("=" * 72)
    print(" 기록 시작")
    print("=" * 72)
    print(" 로봇은 ★ 리모컨으로 ★ 모세요. 이 프로그램은 이동 명령을 보내지 않습니다.")
    print(" 정차 지점에 도착할 때마다 Enter 를 누르고 이름을 적으세요.")
    print(" 끝내려면 이름 자리에 q 를 넣으세요.")
    print()

    points = []
    while True:
        label = await common.ask(
            f"[{len(points) + 1}번째] 지점 이름 (q = 끝): ")
        label = label.strip()
        if label.lower() in ("q", "quit", "종료"):
            break
        if not label:
            print("   이름을 적어주세요. (예: 대기위치, 301호앞)")
            continue

        c = eyes.clearance()
        if eyes.pose is None:
            print("   ★ 자세를 못 받았습니다. 잠시 뒤 다시 시도하세요.")
            continue
        if not c.fresh(3.0):
            print("   ★ 라이다가 오래된 값입니다. 몇 초 기다렸다 다시 누르세요.")
            continue

        p = Point(label, eyes.pose, c)
        points.append(p)

        w = c.width()
        seg = f"   이전 지점에서 {gap(points[-2], p):.2f} m" if len(points) > 1 else ""
        print(f"   기록됨 — 폭 {f'{w:.2f} m' if w else '못 잼'}"
              f"  (앞 {f'{c.front:.2f} m' if c.front else '트임'}){seg}")
        if w is not None and w < TURN_NEED:
            print(f"   ★ 좁습니다 ({w:.2f} m) — 여기서 제자리 회전은 어렵습니다.")

    text = show(points)
    if text:
        LOG.write_text(text + "\n", encoding="utf-8")
        print(f"\n{LOG.name} 에 저장했습니다.")


async def main():
    print("=" * 72)
    print(" 안내 코스 실측  ★ 로봇을 움직이지 않습니다 — 리모컨으로 모세요 ★")
    print("=" * 72)
    conn = await common.connect()
    try:
        await run(conn)
    finally:
        print("\n정리합니다...")
        try:
            await common.settle(conn)
        except Exception:
            pass
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 연결을 닫았습니다.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
