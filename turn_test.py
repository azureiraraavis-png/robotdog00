# -*- coding: utf-8 -*-
"""
회전 하나를 통째로 들여다봅니다 — 각속도가 시간에 따라 어떻게 변하는가.

  ★ 왜 만들었나 ★

    안내를 돌릴 때마다 이런 표가 나왔습니다.

        시킨 값   밀림
        -167      -5
        +130      +5
        -130      -2
        +129      +5
        -129      -6
         -72     -20     ★ 짧은 회전 하나만 서너 배
        +166      +7

    '밀림' 은 멈추라고 한 뒤에 더 도는 각도입니다. 여섯 개는 2~7도로
    모여 있고, **가장 짧은 회전 하나만 다릅니다.** 처음엔 재는 방법이
    나쁜 줄 알고 적분을 표본 기준으로 고쳤는데, 오히려 -16 이 -20 으로
    **커졌습니다.** 방법 문제가 아니라 진짜입니다.

    여기서 추측을 늘어놓을 수도 있습니다 — 제어기가 목표 속도를
    넘겼다가 잦아드는 것 아니냐, 보고가 늦는 것 아니냐. 그런데 그럴
    필요가 없습니다. **속도를 시간에 따라 그대로 찍어보면 됩니다.**

  ★ 안내와 같은 코드로 잽니다 ★

    이 스크립트는 회전 코드를 따로 갖고 있지 않습니다. 안내가 쓰는
    common.turn_by 를 그대로 부르고, 거기에 표본을 받아 적을 목록만
    건넵니다. 베껴 쓰면 '베낀 쪽' 을 재게 되고, 그건 답이 아닙니다.

  쓰는 법

      .\\run turn_test.py              45 / 90 / 180도를 좌우로
      .\\run turn_test.py 30 60 120    각도를 직접 고르기

    ★ 로봇이 제자리에서 돕니다. 사방 0.6 m 이상 비워두세요 ★
    방향은 번갈아 갑니다 (+45, -45, +90, -90 …). 한쪽으로 감기지
    않으므로 제자리에서 끝납니다.

  ★ 12번 돌려보고 알아낸 것 (2026-09-04) ★

    1. 각속도가 **일정하지 않습니다.** 걸음마다 0.8~1.2 rad/s 사이를
       오갑니다 (안정값의 35%쯤). 네 다리로 도는 것이라 그렇습니다.
       "속도 x 시간" 으로 각도를 맞추는 계산은 여기서 무너집니다.

    2. 명령을 끊은 뒤 **되돌아오기도 합니다.** 발을 다시 놓느라
       반대로 0.2 rad/s 까지 갔다 오는 판이 여럿 있었습니다.
       그래서 '밀림' 이 아니라 부호를 살린 '끊은 뒤' 로 부릅니다.

    3. 좌우가 다릅니다.
           왼쪽  6번:  +4 +6 +4 +5 +6 +6   평균 +5.2도 (폭 2도)
           오른쪽 6번:  -2 +2 -1 -4 +3 -1   평균 -0.5도 (폭 7도)
       왼쪽은 꾸준히 5도쯤 더 돌고, 오른쪽은 제자리입니다.

    4. **각도의 최소 눈금이 3도쯤입니다.** 표본 20개/초 x 1 rad/s.
       표본이 늦게 오면 한 번에 11도가 들어옵니다 — +180도를 시켰는데
       +193도로 잰 판이 그것입니다.

    ⇒ 문을 가리키는 데는 충분합니다.
      0.70 m 문틀에 들어가는 데는 부족합니다. 방향은 각도를 빼서가
      아니라 **문틀을 보고** 잡아야 합니다.

    ※ 안내에서 S4 의 -72도가 세 판 내리 -16, -16, -20 이던 것은
      여기서 재현되지 않았습니다 (-60 은 +3, -90 은 +2).
      그 자리 특유의 무언가입니다. 확인하려면:  .\\run turn_test.py 72
"""

import asyncio
import sys

import common
import config

DEFAULT_ANGLES = [45, 90, 180]
SETTLE = 1.5          # 명령을 끊고 이만큼 더 지켜봅니다 (안내는 0.6초)
REST = 2.0            # 회전 사이 쉼 — 앞 회전의 여운이 섞이지 않게


def draw(trace, t0, label):
    """각속도를 시간 순으로 그립니다. 세로가 시간, 가로가 속도."""
    if not trace:
        print("     (표본이 없습니다)")
        return
    peak = max(abs(v) for _t, v, _c in trace) or 1.0
    width = 44
    print(f"     {label}")
    print(f"     {'시각':>6} {'rad/s':>7}  0{'':^{width}}{peak:.2f}")
    for stamp, speed, cut in trace:
        n = int(round(abs(speed) / peak * width))
        bar = ("─" * n) if not cut else ("·" * n)
        mark = "◀ 명령 끊음" if cut else ""
        print(f"     {stamp - t0:6.2f} {speed:7.2f}  |{bar:<{width}}| {mark}")


def summarise(trace, t0, cut_time):
    """그림만으로는 못 읽는 숫자들.

    ★ '밀림' 이라고 부르지 않습니다 ★
      명령을 끊은 뒤 로봇은 더 돌기도 하고 **되돌아오기도** 합니다.
      네 다리로 서려면 발을 다시 놓아야 하니까요. 한 방향으로만
      새는 것이 아니라서, 부호를 살려 '끊은 뒤' 라고만 적습니다.
    """
    import math
    run = [(t - t0, v) for t, v, c in trace if not c]
    tail = [(t - t0, v) for t, v, c in trace if c]
    if not run:
        return {}

    peak = max(abs(v) for _t, v in run)
    at_cut = run[-1][1]
    half = run[len(run) // 2:]
    steady = sum(abs(v) for _t, v in half) / len(half)
    dip = min(abs(v) for _t, v in half)      # 걸음마다 흔들리는 폭

    reach = next((t for t, v in run if abs(v) >= 0.9 * steady), None)
    quiet = next((t - (cut_time - t0) for t, v in tail
                  if abs(v) <= 0.1 * steady), None)

    def integrate(pts):
        out, prev = 0.0, None
        for t, v in pts:
            if prev is not None:
                out += v * min(t - prev, 0.20)
            prev = t
        return math.degrees(out)

    return {
        "최고": peak,
        "안정": steady,
        "걸음 흔들림": (peak - dip) / steady if steady else 0.0,
        "끊는 순간": abs(at_cut),
        "90%까지": reach,
        "멎기까지": quiet,
        "끊은 뒤": integrate(tail),
        "_돈 각도": integrate(run),
    }


async def one(conn, probe, degrees):
    print()
    print("=" * 70)
    print(f" {degrees:+.0f}도")
    print("=" * 70)
    trace = []
    got = await common.turn_by(conn, degrees, probe=probe,
                               settle=SETTLE, trace=trace)
    if not trace:
        print("     ※ 상태 메시지를 하나도 못 받았습니다. 이 판은 버립니다.")
        return None

    t0 = trace[0][0]
    cut_time = next((t for t, _v, c in trace if c), trace[-1][0])
    draw(trace, t0, f"{degrees:+.0f}도 — 표본 {len(trace)}개")

    s = summarise(trace, t0, cut_time)
    print()
    for k, v in s.items():
        if k.startswith("_"):
            continue
        if v is None:
            print(f"     {k:<12} — (닿지 못했습니다)")
        elif k in ("90%까지", "멎기까지"):
            print(f"     {k:<12} {v:.2f}초")
        elif k == "끊은 뒤":
            more = "더 돎" if abs(v) > 0.5 else "제자리"
            print(f"     {k:<12} {v:+.0f}도  ({more})")
        elif k == "걸음 흔들림":
            print(f"     {k:<12} 안정 속도의 {v * 100:.0f}%")
        else:
            print(f"     {k:<12} {v:.2f} rad/s")
    s["시킨 값"] = degrees
    s["받은 값"] = got
    s["표본"] = len(trace)
    s["표본속도"] = len(trace) / max(1e-6, trace[-1][0] - t0)
    return s


def verdict(rows):
    print()
    print("=" * 70)
    print(" 그래서 무엇을 알아냈나")
    print("=" * 70)
    if not rows:
        print(" 쓸 수 있는 판이 없습니다.")
        return

    print(f" {'시킨':>6}{'안정':>8}{'최고':>8}{'흔들림':>9}"
          f"{'끊을때':>8}{'끊은 뒤':>9}{'표본/초':>9}")
    print(" " + "-" * 66)
    for r in rows:
        print(f" {r['시킨 값']:+6.0f}{r['안정']:8.2f}{r['최고']:8.2f}"
              f"{r['걸음 흔들림'] * 100:8.0f}%{r['끊는 순간']:8.2f}"
              f"{r['끊은 뒤']:+8.0f}도{r['표본속도']:9.0f}")

    # ── 1. 왼쪽과 오른쪽이 다른가 ──
    #   여기가 실제로 신호가 나온 자리입니다. 각도별로 가르면 표본이
    #   한둘씩이라 잡음을 신호로 읽게 됩니다 (제가 그랬습니다).
    left = [r["끊은 뒤"] for r in rows if r["시킨 값"] > 0]
    right = [r["끊은 뒤"] for r in rows if r["시킨 값"] < 0]
    print()
    if left and right:
        lm = sum(left) / len(left)
        rm = sum(right) / len(right)
        lw = max(left) - min(left)
        rw = max(right) - min(right)
        print(f" 왼쪽 {len(left)}번  끊은 뒤 평균 {lm:+.1f}도 (폭 {lw:.0f}도)")
        print(f" 오른쪽 {len(right)}번 끊은 뒤 평균 {rm:+.1f}도 (폭 {rw:.0f}도)")
        if abs(lm - rm) > 3 and min(lw, rw) < abs(lm - rm):
            print(" ★ 좌우가 다릅니다 ★  한쪽은 더 돌고 한쪽은 제자리입니다.")
            print("   네 다리로 서는 로봇이라 발을 다시 놓는 방식이 좌우로")
            print("   다른 것입니다. 뺄 값도 좌우로 달라야 합니다.")
        else:
            print(" 좌우 차이는 뚜렷하지 않습니다.")

    # ── 2. 한 값으로 뺄 수 있는가 ──
    after = [r["끊은 뒤"] for r in rows]
    print()
    print(f" 끊은 뒤 전체: {min(after):+.0f} ~ {max(after):+.0f}도")

    # ── 3. 애초에 얼마나 곱게 잴 수 있는가 ──
    #   ★ 이걸 안 보고 있었습니다 ★
    #   표본 하나가 덮는 시간 x 그때 속도 = 각도의 최소 눈금입니다.
    #   +180 을 시켰는데 +193 이 나온 것이 이것으로 설명됩니다
    #   (표본 하나가 늦게 와서 0.20초 x 1.18 rad/s = 13도가 한 번에).
    rate = sum(r["표본속도"] for r in rows) / len(rows)
    speed = sum(r["안정"] for r in rows) / len(rows)
    import math
    grain = math.degrees(speed / rate) if rate else 0.0
    worst = math.degrees(speed * 0.20)
    print()
    print(f" 잴 수 있는 최소 눈금  {grain:.0f}도"
          f"   (표본 {rate:.0f}개/초 x {speed:.2f} rad/s)")
    print(f" 표본이 늦게 오면 한 번에  {worst:.0f}도"
          f"   (0.20초까지 인정하므로)")
    print(" → 이보다 곱게 맞추려는 것은 의미가 없습니다.")
    if rate < 20:
        print(" ★ 표본이 20개/초 미만입니다 — 위 값들을 덜 믿으세요 ★")

    # ── 4. 그래서 지금 할 수 있는 말 ──
    print()
    print(" 문을 가리키는 데는 이 정도면 충분합니다.")
    print(" 0.70 m 문틀에 들어가는 데는 부족합니다 —"
          f" 여유가 한쪽에 0.19 m 인데")
    print("   몸통 0.70 m 가 5도 틀어지면 0.06 m 를 먹습니다.")
    print(" ⇒ 문 통과의 방향은 각도를 빼서가 아니라"
          " **문틀을 보고** 잡아야 합니다.")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    try:
        angles = [float(a) for a in args] or DEFAULT_ANGLES
    except ValueError:
        print("각도는 숫자로 적어주세요.  예:  .\\run turn_test.py 30 60 120")
        return

    print("=" * 70)
    print(" 회전 들여다보기")
    print("=" * 70)
    print(" ★ 로봇이 제자리에서 돕니다. 사방 0.6 m 이상 비워두세요 ★")
    print(f" 각도 {', '.join(f'{a:.0f}' for a in angles)} 를 좌우 번갈아 돕니다.")
    print(f" (끊고 나서 {SETTLE:.1f}초씩 더 지켜봅니다 — 안내는 0.6초)")
    print()
    input(" 준비되면 Enter (Ctrl+C 로 취소) ")

    conn = await common.connect()
    try:
        await common.prepare_motion(conn)
        probe = common.StateProbe(conn)
        await probe.read()
        if probe.yaw_speed is None:
            print("\n★ 회전 속도를 못 받고 있습니다 ★")
            print("  이 실험은 그 값으로 하는 것이라, 여기서 멈춥니다.")
            return
        if not await common.ensure_standing(conn, probe=probe, ask=False):
            print("일으켜 세우지 못했습니다.")
            return

        rows = []
        for i, a in enumerate(angles):
            for sign in (+1, -1):        # 좌우 번갈아 — 제자리로 돌아옵니다
                r = await one(conn, probe, sign * a)
                if r:
                    rows.append(r)
                await asyncio.sleep(REST)
        verdict(rows)
    finally:
        print("\n정리합니다...")
        try:
            await common.Posture(conn).damp()
        except Exception:
            pass
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
