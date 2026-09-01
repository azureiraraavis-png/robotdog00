# -*- coding: utf-8 -*-
"""
앉았다 일어나면 왜 못 걷는가 — 회복 조건 가려내기.  ★ 로봇이 움직입니다 ★

  ★ 앞선 실험이 왜 우리를 속였나 ★

  지난 실험에서 'BalanceStand 세 번'이 통했습니다. 그래서 그걸 일어서기
  절차에 넣었는데, **넣고 나니 안 통했습니다.** 그리고 실험을 다시 돌리면
  또 통합니다. 같은 명령인데 결과가 다릅니다.

  이유는 실험 설계에 있었습니다. 후보를 적용하기 **직전에** 측정을 하는데,
  그 측정이 끝나면서 조이스틱 신호와 StopMove 를 흘려보냅니다.
  즉 후보마다 앞 단계의 흔적이 묻어 있었습니다. 무엇이 효과를 냈는지
  가려낼 수 없는 구조였던 겁니다.

  ★ 이번 설계 ★

  후보마다 **처음부터 다시 고장냅니다.**

      앉히기 → 일으키기 → (고장 확인) → 후보 적용 → 측정

  고장 확인 측정은 StopMove 를 보내지 않습니다. 그것 자체가 회복 요인일
  수 있기 때문입니다.

  가려낼 변수
    · 시간      — 그냥 기다리기만 해도 낫는가
    · 명령      — BalanceStand 가 필요한가
    · StopMove  — 이게 열쇠인가
    · 연결      — 재접속만이 답인가

  ※ '조이스틱을 흘려보내면 낫는가'는 확인할 필요가 없습니다.
    고장 확인 측정 자체가 3초짜리 조이스틱 신호인데도 여전히 고장이므로,
    이미 아니라는 답이 나와 있습니다.

    .\\run sit_test.py

  한 후보에 30초쯤 걸립니다. 앞뒤로 조금씩 왕복합니다.

  실행 전 체크리스트
    □ 앞뒤로 2m 이상 트인 평평한 바닥
    □ 리모컨 손에 (P 두 번 = 힘 빼기)
    □ 배터리 50% 이상
"""

import asyncio
import sys
import time

import common
import safety

conn = None

STICK = 0.4
PUSH = 1.5
WALKED = 0.10      # 전진 속도가 이 값을 넘으면 걷는 것으로 봅니다

_broke_at = 0.0    # 마지막으로 RiseSit 을 보낸 시각


async def measure(probe, label, settle=True):
    """앞뒤로 밀어 최고 전진 속도를 잽니다.

    settle=False 면 StopMove 를 보내지 않습니다.
    '고장 확인' 측정에서 쓰는데, StopMove 자체가 회복 요인일 수 있어서
    그것을 실험 대상 밖으로 빼두기 위함입니다.
    """
    peak = 0.0
    for direction in (+1, -1):
        deadline = time.time() + PUSH
        while time.time() < deadline:
            common.joystick(conn, **common.stick_from_intent(x=STICK * direction))
            v = probe.velocity
            if v:
                peak = max(peak, abs(v[0]))
            await asyncio.sleep(0.02)
    for _ in range(5):
        common.joystick(conn, 0.0, 0.0, 0.0)
        await asyncio.sleep(0.02)
    if settle:
        await common.stop(conn)

    ok = peak > WALKED
    since = time.time() - _broke_at
    print(f"    {label}: 전진 {peak:.3f} m/s  "
          f"(일으킨 지 {since:.0f}초)  →  "
          f"{'★ 걷습니다 ★' if ok else '못 걷습니다'}")
    return peak, ok


async def break_it(probe):
    """앉혔다 일으켜 고장 상태를 만들고, 정말 고장인지 확인합니다.

    돌려주는 값: 고장 재현에 성공했는지
    """
    global _broke_at
    await common.sport(conn, "Sit")
    await asyncio.sleep(4.0)
    await common.sport(conn, "RiseSit")
    await asyncio.sleep(4.0)
    _broke_at = time.time()
    await common.stand_and_wait(conn, probe=probe, verbose=False)

    peak, ok = await measure(probe, "  고장 확인", settle=False)
    if ok:
        print("      ※ 이번엔 재현되지 않았습니다 — 이 후보는 건너뜁니다")
        return False
    return True


# ─────────────────────────────────────────────────────────────
# 후보들 — 변수를 하나씩만 바꿉니다
# ─────────────────────────────────────────────────────────────

async def c_wait(probe):
    """시간만. 아무 명령도 보내지 않습니다."""
    await asyncio.sleep(6.0)


async def c_balance(probe):
    """BalanceStand 세 번만. StopMove 없이."""
    for _ in range(3):
        await common.sport(conn, "BalanceStand")
        await asyncio.sleep(0.8)


async def c_stopmove(probe):
    """StopMove 한 번만. BalanceStand 없이."""
    await common.sport(conn, "StopMove")
    await asyncio.sleep(2.0)


async def c_stop_balance(probe):
    """StopMove 뒤에 BalanceStand 세 번 — 지난번에 통했던 조합."""
    await common.sport(conn, "StopMove")
    await asyncio.sleep(1.0)
    for _ in range(3):
        await common.sport(conn, "BalanceStand")
        await asyncio.sleep(0.8)


async def c_reconnect(probe):
    """연결을 다시 맺습니다 — 확실히 통한다고 확인된 방법."""
    global conn
    await common.stop(conn)
    conn = await common.reconnect(conn)
    await common.prepare_motion(conn, verbose=False)
    await safety.set_auto_recovery(conn, False, verbose=False)
    probe.__init__(conn)            # 새 연결에는 새 구독이 필요합니다
    await probe.read()
    await common.stand_and_wait(conn, probe=probe, verbose=False)


CANDIDATES = [
    ("아무것도 안 하고 6초 기다리기", c_wait),
    ("BalanceStand 세 번만", c_balance),
    ("StopMove 한 번만", c_stopmove),
    ("StopMove → BalanceStand 세 번", c_stop_balance),
    ("연결 다시 맺기", c_reconnect),
]


async def run_trials(probe):
    results = []
    for i, (label, candidate) in enumerate(CANDIDATES, 1):
        print(f"\n{'─' * 66}")
        print(f" 후보 {i}/{len(CANDIDATES)} — {label}")
        print("─" * 66)

        print("  [준비] 앉혔다 일으켜 고장 상태를 다시 만듭니다")
        if not await break_it(probe):
            results.append((label, None, None))
            continue

        print(f"  [적용] {label}")
        await candidate(probe)
        peak, ok = await measure(probe, "  결과")
        results.append((label, peak, ok))
        await asyncio.sleep(1.0)

    return results


def report(results):
    print("\n" + "=" * 66)
    print(" 정리")
    print("=" * 66)
    for label, peak, ok in results:
        if peak is None:
            print(f"   (재현 안 됨)      {label}")
        else:
            mark = "★ 걸음   " if ok else "  안 걸림 "
            print(f"   {mark} {peak:>6.3f} m/s   {label}")

    good = [r for r in results if r[2]]
    bad = [r for r in results if r[2] is False]
    print()

    if not good:
        print(" 어떤 방법으로도 회복되지 않았습니다.")
        print(" 연결 다시 맺기까지 실패했다면 로봇 재부팅 말고는 없습니다.")
        return

    names = [r[0] for r in good]
    print(f" 통한 것: {', '.join(names)}")
    if bad:
        print(f" 안 통한 것: {', '.join(r[0] for r in bad)}")

    # 변수별 해석
    print()
    lookup = {label: ok for label, peak, ok in results if ok is not None}
    if lookup.get("아무것도 안 하고 6초 기다리기"):
        print(" → 시간만 지나면 낫습니다. 명령이 아니라 **기다림**이 답입니다.")
        print("   일어서기 절차 마지막에 그만큼의 여유를 두면 됩니다.")
    elif lookup.get("StopMove 한 번만"):
        print(" → StopMove 하나가 열쇠입니다. 일어선 뒤 StopMove 를 보내세요.")
    elif lookup.get("BalanceStand 세 번만"):
        print(" → BalanceStand 는 맞는데, 일어서기 직후에 보내면 안 먹습니다.")
        print("   충분히 뒤에 보내야 합니다 — 타이밍 문제입니다.")
    elif lookup.get("StopMove → BalanceStand 세 번"):
        print(" → StopMove 와 BalanceStand 를 **함께** 보내야 합니다.")
        print("   둘 중 하나만으로는 안 됩니다.")
    elif lookup.get("연결 다시 맺기"):
        print(" → 재접속만 통합니다. 로봇의 자세가 아니라 연결에 매인 문제입니다.")
        print("   다음은 재접속이 하는 일 중 무엇이 필요한지 가리는 실험입니다.")


async def main():
    global conn

    print("=" * 66)
    print(" 앉기 문제 — 회복 조건 가려내기  ★ 로봇이 움직입니다 ★")
    print("=" * 66)
    print(__doc__.split("실행 전 체크리스트")[0])

    if not await common.confirm(
        "앞뒤로 2m 가 비어 있고, 리모컨을 든 사람이 대기 중입니까?"
    ):
        print("취소했습니다.")
        return

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


async def run(conn_):
    await common.prepare_motion(conn_)
    await safety.set_auto_recovery(conn_, False)
    watchdog = safety.Watchdog(conn_)
    watchdog.arm()

    probe = common.StateProbe(conn_)
    await probe.read()

    print("\n[기준] 먼저 정상 상태에서 재둡니다")
    await common.stand_and_wait(conn_, probe=probe, verbose=False)
    peak, ok = await measure(probe, "  정상 상태")
    if not ok:
        print("\n※ 정상 상태에서도 안 걷습니다. 그것부터 봐야 합니다.")
        print("  바닥이 미끄럽지 않은지, 배터리가 충분한지 확인하세요.")
        return

    report(await run_trials(probe))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
        print("로봇이 멈추지 않으면 리모컨의 P 버튼을 두 번 누르세요.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
