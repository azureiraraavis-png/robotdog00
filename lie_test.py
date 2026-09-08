# -*- coding: utf-8 -*-
"""
왜 안내 끝에서만 철푸덕인가 — 조건을 바꿔가며 재봅니다.

  ★ 무엇을 알고 무엇을 모르는가 ★

    같은 명령(StandDown)이 자리에 따라 세 배 다릅니다. 이건 이제
    짐작이 아니라 잰 값입니다.

        메뉴에서 눌렀을 때      1.6초 · 초당 0.17 m
        안내 끝(S5)에서        0.5초 · 초당 0.61 m   ★ 급합니다

    한동안 못 봤던 이유는 **재는 코드가 명령이 돌아온 뒤에 재기
    시작했기 때문**입니다. 하필 그 자리에서 명령 왕복이 1.1초라,
    다 내려간 뒤부터 재고 있었습니다. 그건 고쳤습니다.

    그런데 원인은 아직 모릅니다. 단서는 하나 있습니다 —
    **급한 자리에서 명령 왕복도 같이 느립니다.** 증상 둘이 한자리에
    있으면 원인이 하나일 가능성이 큽니다.

  ★ 그래서 조건을 하나씩 바꿔봅니다 ★

    안내 끝의 엎드리기는 이런 상황에 놓여 있습니다.

        인사 동작(hello) → 멘트 6초 → 가만히 5초 → 엎드리기

    셋 다 후보입니다. 하나씩 떼어 만들어 보고, 어느 것이 재현하는지
    봅니다. 재현되는 조건이 곧 원인입니다.

        ㄱ. 그냥        서 있다가 곧장
        ㄴ. 기다린 뒤   가만히 5초 두었다가
        ㄷ. 인사 뒤     hello 하고 나서
        ㄹ. 걷고 나서   잠깐 앞뒤로 움직이고 나서

  ★ 로봇이 실제로 움직입니다 ★
    앉고 일어서고 엎드립니다. 사방 1 m 를 비워주세요.
    걷는 조건(ㄹ)에서 앞뒤로 조금 움직입니다 — 앞뒤 0.5 m 씩.

  쓰는 법

      .\\run lie_test.py              각 조건 3번씩 (약 4분)
      .\\run lie_test.py --once       각 조건 1번씩 (빠르게 보기)
"""

import asyncio
import sys
import time

import common

REPEATS = 3
# ★ 1차에서 '인사 뒤' 가 범인으로 나왔습니다 ★
#   세 번 다 0.5초, 명령 왕복도 세 번 다 1.1초. 나머지는 세 번 다 1.6~1.7초.
#   이제 **고치는 방법 두 가지**를 같은 자리에서 견줍니다.
CONDITIONS = ("그냥", "인사 뒤", "인사+균형", "인사+세우기")


async def prepare(robot, how):
    """엎드리기 직전 상황을 만듭니다."""
    conn = robot["conn"]
    if how == "그냥":
        return
    if how == "기다린 뒤":
        await asyncio.sleep(5.0)
        return
    if how.startswith("인사"):
        await common.sport(conn, "Hello")
        await asyncio.sleep(5.0)          # 인사 동작이 끝나기를 기다립니다
        # ★ 인사 뒤에 로봇은 '서 있는' 것이 아닙니다 ★
        #   그런데 우리 상태 기계는 여전히 서 있다고 믿습니다. 그래서
        #   lie() 안의 stand() 가 "이미 서 있습니다" 하고 건너뛰고,
        #   인사 자세에서 곧장 StandDown 이 나갑니다.
        #   되돌리는 방법이 둘인데, 어느 쪽이 되는지 재봅니다.
        if how == "인사+균형":
            # 싼 쪽 — 균형 자세만 다시 잡아줍니다 (1초 안팎)
            await common.sport(conn, "BalanceStand")
            await asyncio.sleep(1.0)
        elif how == "인사+세우기":
            # 비싼 쪽 — 제대로 다시 세웁니다 (StandUp 부터, 7초쯤)
            robot["posture"].walk_ready = False
            await robot["posture"].stand(verbose=False)
        return
    if how == "걷고 나서":
        import config
        lim = config.MAX_FORWARD_STICK
        for sign in (+1, -1):             # 앞으로 조금, 뒤로 조금
            for _ in range(20):           # 0.4초
                common.joystick(conn, **common.stick_from_intent(
                    sign * lim * 0.4, 0.0, 0.0))
                await asyncio.sleep(0.02)
        for _ in range(3):
            common.joystick(conn, 0.0, 0.0, 0.0)
            await asyncio.sleep(0.02)
        await common.stop(conn)
        await asyncio.sleep(1.0)


async def one(robot, how):
    """조건 하나로 한 번 엎드려 봅니다. 돌려주는 값: 잰 것 또는 None."""
    posture = robot["posture"]
    await posture.stand(verbose=False)
    await asyncio.sleep(1.0)
    await prepare(robot, how)
    await posture.lie(verbose=False)
    got = posture.last_descent
    await asyncio.sleep(0.5)
    return got


def _mid(xs):
    """가운데 값. 평균을 쓰면 튄 표본 하나에 끌려갑니다."""
    xs = sorted(xs)
    return xs[len(xs) // 2]


def show(rows):
    """조건별로 견줍니다.

    ★ 무엇으로 채점하는가 — 1차에서 여기를 틀렸습니다 ★

      처음에는 '가장 빠를 때(m/s)' 의 평균으로 채점했습니다. 그런데
      그 값은 **이웃한 표본 두 개**로 계산합니다. 높이 값 하나가 튀면
      그 한 쌍이 통째로 부풀고, 평균이 끌려갑니다.

      실제로 이렇게 나왔습니다.

          기다린 뒤   1.7초 · 1.7초 · 1.6초    ← 내려간 시간은 멀쩡한데
                      0.20 · 0.17 · 1.58 m/s  ← 하나가 튀어서 평균 0.65

      1.6초에 걸쳐 내려가는 중에 초당 1.58 m 는 물리적으로 말이 안
      됩니다. 그런데 요약은 그걸 근거로 '기다린 뒤가 범인' 이라고
      찍었습니다. **사람이 낱개 줄을 보고 바로잡아 줬습니다.**

      그래서 이제 **내려간 시간(took)** 으로 채점합니다. 그건 여러
      표본에 걸쳐 있어서 하나가 튀어도 안 흔들립니다. 그리고 평균
      대신 가운데 값을 씁니다.
      m/s 는 참고로만 보여주고, 튄 표본이 있으면 그렇다고 적습니다.
    """
    print()
    print("=" * 70)
    print(" 조건별로 어떻게 내려갔는가")
    print("=" * 70)
    print(f" {'조건':<12}{'횟수':>4}{'명령 왕복':>10}{'내려간 시간':>12}"
          f"   {'낱개 (초)':<20}")
    print(" " + "-" * 66)
    summary = {}
    for how in CONDITIONS:
        got = [r[1] for r in rows if r[0] == how and r[1]]
        if not got:
            print(f" {how:<12}{'—':>4}     못 쟀습니다")
            continue
        cmd = _mid([g["command"] for g in got])
        took = _mid([g["took"] for g in got])
        speeds = [g["fast"] for g in got]
        summary[how] = (cmd, took, _mid(speeds), speeds)
        each = " · ".join(f"{g['took']:.1f}" for g in got)
        print(f" {how:<12}{len(got):>4}{cmd:>9.1f}초{took:>11.1f}초   {each}")

    # m/s 는 따로, 튄 것을 표시해서
    print()
    print(f" {'조건':<12}{'가운데 m/s':>12}   낱개 m/s")
    for how, (_c, _t, mid, speeds) in summary.items():
        each = " · ".join(
            (f"{s:.2f}★" if mid and s > mid * 2.5 else f"{s:.2f}")
            for s in speeds)
        print(f" {how:<12}{mid:>11.2f}   {each}")
    if any(mid and s > mid * 2.5 for _h, (_c, _t, mid, sp) in summary.items()
           for s in sp):
        print("   ★ 는 이웃 표본 하나가 튄 것입니다 — 채점에 쓰지 않습니다.")

    print()
    if len(summary) < 2:
        print(" 견줄 것이 모자랍니다. 다시 돌려보세요.")
        return None

    # ★ 채점은 '내려간 시간' 으로 ★ 짧을수록 급합니다.
    slow = max(summary.items(), key=lambda kv: kv[1][1])     # 가장 느긋한
    quick = min(summary.items(), key=lambda kv: kv[1][1])    # 가장 급한
    ratio = slow[1][1] / quick[1][1] if quick[1][1] else 0

    if ratio < 1.5:
        print(" ★ 조건들이 서로 비슷합니다 ★")
        print(f"   제일 느긋한 '{slow[0]}'({slow[1][1]:.1f}초) 와"
              f" 제일 급한 '{quick[0]}'({quick[1][1]:.1f}초) 가")
        print(f"   {ratio:.1f}배밖에 차이 안 납니다. 여기 있는 것들 중에는")
        print("   원인도 해법도 없습니다.")
        return None

    print(f" ★ '{quick[0]}' 가 '{slow[0]}' 보다 {ratio:.1f}배 급합니다 ★")
    print(f"   {slow[0]:<12}{slow[1][1]:.1f}초")
    print(f"   {quick[0]:<12}{quick[1][1]:.1f}초")

    if summary[quick[0]][0] > summary[slow[0]][0] * 1.5:
        print()
        print("   ※ 그 조건에서 **명령 왕복도 같이 느립니다**"
              f" ({slow[1][0]:.1f}초 → {quick[1][0]:.1f}초).")
        print("     증상 둘이 같이 움직이면 원인은 하나입니다.")

    # 고치는 방법이 통했는지 — '인사 뒤' 를 기준으로 견줍니다
    base = summary.get("인사 뒤")
    if base:
        print()
        print(" ── 고치는 방법 ──")
        for how in ("인사+균형", "인사+세우기"):
            if how not in summary:
                continue
            t2 = summary[how][1]
            if t2 > base[1] * 1.5:
                print(f"   {how:<12}{t2:.1f}초  ★ 됩니다"
                      f" (인사 뒤 {base[1]:.1f}초 → {t2:.1f}초)")
            else:
                print(f"   {how:<12}{t2:.1f}초  — 소용없습니다")
    return quick[0]


async def main():
    once = "--once" in sys.argv[1:]
    reps = 1 if once else REPEATS

    print("=" * 70)
    print(" 왜 안내 끝에서만 철푸덕인가")
    print("=" * 70)
    print(" ★ 로봇이 앉고 일어서고 엎드립니다. 사방 1 m 를 비워주세요 ★")
    print(f" 조건 {len(CONDITIONS)}가지 × {reps}번"
          f" = 모두 {len(CONDITIONS) * reps}번 엎드립니다.")
    print()

    conn = await common.connect()
    rows = []
    try:
        import safety
        await common.prepare_motion(conn)
        await safety.set_auto_recovery(conn, False)
        probe = common.StateProbe(conn)
        await probe.read()
        robot = {"conn": conn, "probe": probe,
                 "posture": common.Posture(conn, probe=probe)}
        if not await common.ensure_standing(conn, probe=probe, ask=False):
            print("일으켜 세우지 못했습니다. 중단합니다.")
            return 1

        n = 0
        for r in range(reps):
            for how in CONDITIONS:
                n += 1
                print(f"─ [{n}/{len(CONDITIONS) * reps}] {how} " + "─" * 40)
                got = await one(robot, how)
                if got:
                    # 판정은 시간으로 합니다 — m/s 는 표본 하나에 튑니다
                    mark = "   ★ 급합니다" if got["took"] < 0.9 else ""
                    print(f"   명령 왕복 {got['command']:.1f}초 · "
                          f"내려가는 데 {got['took']:.1f}초 · "
                          f"초당 {got['fast']:.2f} m{mark}")
                else:
                    print("   못 쟀습니다")
                rows.append((how, got))

        await robot["posture"].stand(verbose=False)
        show(rows)
        return 0
    finally:
        print("\n정리합니다...")
        try:
            await common.settle(conn)
        except Exception:
            pass
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()) or 0)
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
