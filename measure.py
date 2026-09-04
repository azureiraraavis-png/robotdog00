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

# ── 제자리 회전에 필요한 여유 ────────────────────────────────
#
# ★ 처음에 '좌우 합' 으로 판정했는데, 그건 틀렸습니다 ★
#   실측에서 왼 0.38 m / 오른 1.76 m 인 지점이 나왔습니다. 합은 2.14 m 라
#   널찍해 보이지만, **로봇은 자기 중심으로 돕니다.** 왼쪽 0.38 m 가
#   전부입니다. 합으로 보면 이런 한쪽으로 치우친 자리를 통과시킵니다.
#
#   그래서 합이 아니라 **가장 좁은 쪽**으로 봅니다.
#
# 몸통 0.70 × 0.31 → 중심에서 모서리까지 √(0.35² + 0.155²) = 0.383 m
# 발이 뻗는 것과 자세 흔들림을 감안해 0.10 m 를 더합니다.
TURN_RADIUS = 0.383
TURN_NEED = TURN_RADIUS + 0.10      # 사방으로 이만큼은 비어야 합니다 (m)

# 이보다 덜 움직였으면 '제자리에서 돌기만 한 것' 으로 봅니다 (m).
#
# ★ 문 각도를 재는 방법입니다 ★
#   한 자리에서 두 번 찍으면 됩니다 — 복도 방향으로 한 번, 문을 본 채로
#   한 번. 그 사이의 방향변화가 곧 '문을 보려면 몇 도 돌아야 하는가' 입니다.
#
#   왜 따로 재야 하냐면, 지점과 지점 사이의 방향변화에는 '문 쪽으로 돌기'
#   와 '다시 복도 쪽으로 돌기' 가 섞여 있어서 문 각도만 뽑을 수 없기
#   때문입니다. 섞이기 전에 재는 것이 유일한 방법입니다.
IN_PLACE = 0.30


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


def bearing(a, b):
    """a 에서 b 를 바라보는 방향 (도). 지도 기준."""
    return math.degrees(math.atan2(b.pose[1] - a.pose[1],
                                   b.pose[0] - a.pose[0]))


def off_axis(points, i):
    """i 번째 지점에서 로봇이 **가는 방향에서 몇 도 돌아서 있었는가**.

    ★ 이게 왜 중요한가 ★
    좌우 여유는 로봇 기준으로 잽니다. 로봇이 복도를 따라 서 있으면
    '왼 + 오른' 이 복도 폭입니다. 그런데 문 쪽으로 몸을 돌린 채 찍으면
    같은 숫자가 **복도를 따라 앞뒤로 잰 거리**가 됩니다. 전혀 다른 값인데
    생김새가 똑같아서 알아채기 어렵습니다.

    다행히 검산할 수 있습니다. 복도에서는 **가는 방향이 곧 복도 방향**이니,
    로봇이 그 방향을 보고 있었는지 확인하면 됩니다.

    돌려주는 값: 어긋난 각도(0~180). 못 구하면 None.
    """
    prev_p = points[i - 1] if i > 0 else None
    next_p = points[i + 1] if i + 1 < len(points) else None

    # 가는 방향: 이전 지점에서 온 방향을 우선 쓰고, 없으면 다음 지점 쪽
    if prev_p is not None and gap(prev_p, points[i]) > 0.3:
        course = bearing(prev_p, points[i])
    elif next_p is not None and gap(points[i], next_p) > 0.3:
        course = bearing(points[i], next_p)
    else:
        return None      # 앞뒤로 거의 안 움직여서 방향을 못 정합니다

    d = abs((points[i].yaw_deg() - course + 180) % 360 - 180)
    # 뒤돌아 선 것(180도)은 괜찮습니다 — 복도 축과는 여전히 나란하니
    # 좌우가 서로 바뀔 뿐 폭은 같습니다. 그래서 축에서 벗어난 각도로 봅니다.
    return min(d, 180.0 - d)


# 이 각도를 넘게 돌아서 있으면 '복도 폭' 으로 읽지 않습니다 (도)
OFF_AXIS_LIMIT = 30.0


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
        f"{'좌우합':>9}{'왼':>7}{'오른':>7}   {'자세':<6}")
    out("-" * 72)

    total = 0.0
    axis = []            # 복도 축과 나란히 서서 잰 지점만
    spins = []           # 제자리 회전 (앞지점, 뒷지점, 각도) — 문 각도입니다
    for i, p in enumerate(points):
        if i == 0:
            seg_s = seg_t = "—"
        else:
            seg = gap(points[i - 1], p)
            turned = turn(points[i - 1], p)
            if seg < IN_PLACE:
                # 거의 안 움직이고 방향만 바뀐 것 = 제자리 회전
                spins.append((points[i - 1].name, p.name, turned))
                seg_s = "제자리"
            else:
                total += seg
                seg_s = f"{seg:.2f} m"
            seg_t = f"{turned:+.0f}°"
        c = p.clear
        w = c.width()
        d = off_axis(points, i)
        if d is None:
            tag = "?"
        elif d <= OFF_AXIS_LIMIT:
            tag = "복도"
            axis.append(p)
        else:
            tag = f"{d:.0f}°돌아섬"
        out(f"{common_pad(p.name, 16)}{seg_s:>10}{f'{total:.2f} m':>9}{seg_t:>10}"
            f"{(f'{w:.2f} m' if w else '—'):>9}"
            f"{(f'{c.left:.2f}' if c.left else '—'):>7}"
            f"{(f'{c.right:.2f}' if c.right else '—'):>7}   {tag:<6}")

    out("-" * 72)
    out(f" 총 이동 거리 {total:.2f} m")

    # ── 폐합오차 — 줄자 없이 주행거리계를 검산하는 법 ──
    #
    # 출발점으로 돌아와 같은 이름으로 한 번 더 찍으면, 주행거리계가
    # 말하는 두 지점 사이 거리가 곧 누적 오차입니다.
    # ★ 절대 길이를 몰라도 오차를 알 수 있습니다 ★
    out()
    closed = False
    for i, p in enumerate(points):
        for j in range(i + 1, len(points)):
            if points[j].name == p.name:
                err = gap(p, points[j])
                walked = sum(gap(points[k - 1], points[k])
                             for k in range(i + 1, j + 1))
                out(f" ★ 폐합오차 — '{p.name}' 으로 돌아왔습니다 ★")
                out(f"     돌아온 거리 {walked:.2f} m,  어긋남 {err:.2f} m")
                if walked > 0.5:
                    out(f"     누적 오차 {err / walked * 100:.1f}%")
                    if err / walked < 0.03:
                        out("     → 믿을 만합니다. '거리로 걷기' 를 이 값으로 가도 됩니다.")
                    else:
                        out("     → 큽니다. 긴 구간을 열린 루프로 가면 안 됩니다.")
                closed = True
                break
        if closed:
            break
    if not closed:
        out(" ※ 폐합오차를 못 쟀습니다.")
        out("   출발점으로 정확히 돌아와 **같은 이름**으로 한 번 더 찍으면,")
        out("   줄자 없이도 주행거리계가 얼마나 흐르는지 알 수 있습니다.")

    # ── 경고 ──
    out()
    turned_pts = [p for i, p in enumerate(points)
                  if (off_axis(points, i) or 0) > OFF_AXIS_LIMIT]
    if turned_pts:
        out(" ★ 복도 폭으로 읽으면 안 되는 지점 ★")
        for p in turned_pts:
            out(f"     {p.name} — 가는 방향에서 돌아선 채로 쟀습니다")
        out("   이 지점의 '좌우합' 은 복도 폭이 아니라 복도를 따라 잰 거리입니다.")
        out("   폭이 필요하면 복도 방향으로 세우고 다시 찍으세요.")

    def narrowest(p):
        """사방 중 가장 좁은 쪽 (m). 못 재면 None."""
        seen = [d for d in (p.clear.left, p.clear.right, p.clear.front)
                if d is not None]
        return min(seen) if seen else None

    # ★ 세운 자리와 복도 자체를 구별합니다 ★
    #
    # 처음에는 '가장 좁은 쪽' 만 보고 "회전 불가" 라고 찍었습니다. 틀렸습니다.
    # 왼 0.38 / 오른 1.76 은 복도가 좁다는 뜻이 아니라, 로봇이 한쪽 벽에
    # 붙어 서 있었다는 뜻입니다. 가운데로 서면 양쪽 1.07 m 씩입니다.
    #
    #   왼·오른 **각각**  → 그때 어디에 세웠는지에 달림. 못 믿습니다.
    #   왼+오른 **합**    → 복도 폭. 어디에 세우든 같습니다. 믿습니다.
    #
    # 그래서 두 가지를 따로 말합니다.
    #   "지금 세운 자리에서 바로 돌 수 있는가"  (당장의 문제)
    #   "가운데로 서면 돌 수 있는가"            (복도의 문제)
    tight, cramped = [], []
    for p in points:
        d = narrowest(p)
        w = p.clear.width()
        if d is None:
            continue
        half = (w / 2) if w is not None else None
        if half is not None and half < TURN_NEED:
            cramped.append((p, half))       # 복도 자체가 좁습니다
        elif d < TURN_NEED:
            tight.append((p, d, half))      # 치우쳐 섰을 뿐입니다

    if cramped:
        out(" ★ 복도 자체가 좁아 회전이 어려운 지점 ★")
        for p, half in cramped:
            out(f"     {common_pad(p.name, 14)}가운데로 서도 {half:.2f} m "
                f"(필요 {TURN_NEED:.2f} m)")
        out("   여기서는 발을 돌리지 말고 **몸통만 기울여** 가리키세요 (Euler).")
        out("   바닥 공간이 전혀 필요 없습니다.")

    if tight:
        out(" ※ 치우쳐 세워서 지금은 못 도는 지점 (복도는 넉넉합니다)")
        for p, d, half in tight:
            half_s = f"{half:.2f}" if half is not None else "—"
            out(f"     {common_pad(p.name, 14)}지금 {d:.2f} m  →  "
                f"가운데로 서면 {half_s} m")
        out("   돌기 전에 옆걸음으로 가운데를 잡으면 됩니다.")
        out("   (왼·오른 각각은 어디에 세웠는지에 달렸고, 그 합만이 복도 폭입니다)")

    near = [p for p in points if p.clear.front is not None and p.clear.front < 1.0]
    if near:
        out(" ※ 정면이 1 m 안에 막힌 지점: "
            + ", ".join(f"{p.name}({p.clear.front:.2f}m)" for p in near))
        out("   여기서 앞으로 출발하려면 우리 안전장치(0.90 m)에 바로 걸립니다.")
        out("   문을 가리키려고 바짝 붙인 것이라면 괜찮습니다 — 다만 출발은")
        out("   뒤로 물러나거나 몸을 돌린 뒤에 해야 합니다.")

    blind = [p for p in points if p.clear.width() is None]
    if blind:
        out(" ※ 폭을 못 잰 지점: " + ", ".join(p.name for p in blind))
        out("   한쪽이 트여 있거나(문이 열림), 유리라 안 보인 것입니다.")

    out()
    out(" scenario.py 에 옮길 값")
    for i in range(1, len(points)):
        d = gap(points[i - 1], points[i])
        if d >= IN_PLACE:
            out(f"   {points[i-1].name} → {points[i].name}"
                f"   meters={d:.2f}  turn_deg={turn(points[i-1], points[i]):+.0f}")
    if spins:
        out()
        out("   ★ 문 각도 (Stop 의 door_deg) ★")
        for before, after, deg in spins:
            out(f"   {before} → {after}   door_deg={deg:+.0f}")
        out("     + 가 왼쪽입니다. 복도 방향에서 문을 보기까지 돈 각도입니다.")

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
    print(" ★ 두 가지만 지켜주세요 ★")
    print("   1. 찍을 때는 **복도를 따라** 서 있어야 합니다.")
    print("      문 쪽으로 돌린 채 찍으면 '복도 폭' 자리에 엉뚱한 값이 들어갑니다.")
    print("      (돌아선 것은 자동으로 표시되니, 표에서 확인하실 수 있습니다)")
    print("   2. 마지막에 **출발점으로 돌아와 같은 이름으로 한 번 더** 찍으세요.")
    print("      줄자 없이도 주행거리계가 얼마나 흐르는지 알 수 있습니다.")
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
