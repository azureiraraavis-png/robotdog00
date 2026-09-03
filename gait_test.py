# -*- coding: utf-8 -*-
"""
걸음새 찾기.  ★ 로봇이 움직입니다 ★

증상: 이동 명령을 보내면 로봇이 걷지 않고 **몸통만 기울입니다.**

원인: `BalanceStand` 는 제자리에서 균형만 잡는 자세 모드입니다.
그 상태에서 이동 명령을 받으면 걸음을 떼는 대신 무게중심을 옮겨 응답합니다.
실제로 걸으려면 보행 걸음새(gait)로 먼저 들어가야 합니다.

문제는 **어느 명령이 그 역할인지 문서에 없다는 것**입니다.
MCF 명령표에 후보가 여럿이고, 명령을 보내는 통로도 두 가지입니다.
그래서 하나씩 짧게 시험해보고 눈으로 확인합니다.

각 시험은 1.5초 전진이 전부입니다. 매번 확인을 받고 진행합니다.

    .\\run gait_test.py

  실행 전 체크리스트
    □ 사방 2~3m 이상 트인 평평한 바닥
    □ 조종 장치 손에 (힘 빼기: 게임패드 L2+B, 동반 리모컨 P 두 번)
    □ 배터리 확인
"""

import asyncio
import sys
import time

from unitree_webrtc_connect.constants import RTC_TOPIC

import common
import safety

conn = None

# 시험 목록 — 가능성이 높은 순서로 배치했습니다.
#   (표시 이름, 걸음새 명령, 파라미터, 조이스틱 통로를 쓸지)
#
# 왜 이 순서인가
#   1. 앱의 조종 화면은 조이스틱 통로를 씁니다. 그것만으로 걸을 수도 있습니다.
#   2. ClassicWalk 는 앱 모드 목록의 'Classic' 에 해당할 가능성이 큽니다.
#   3. 나머지는 MCF 명령표에 있는 보행 관련 명령들입니다.
#
# 명령표에 없는 것은 자동으로 건너뜁니다.
TRIALS = [
    ("기준선 — 지금 코드 그대로",  None,             None,             False),
    ("기준선 + 조이스틱 통로",     None,             None,             True),
    ("ClassicWalk",               "ClassicWalk",    None,             False),
    ("ClassicWalk + 조이스틱",     "ClassicWalk",    None,             True),
    ("ContinuousGait 켜기",       "ContinuousGait", {"data": True},   False),
    ("ContinuousGait + 조이스틱",  "ContinuousGait", {"data": True},   True),
    ("StaticWalk",                "StaticWalk",     None,             False),
    ("TrotRun",                   "TrotRun",        None,             False),
    ("EconomicGait",              "EconomicGait",   None,             False),
]


def joystick(conn, ly=0.0, lx=0.0, rx=0.0):
    """조이스틱 신호를 흉내 냅니다. (앱의 조종 화면이 쓰는 통로)

    ly: 전진(+)/후진(-)   lx: 좌우 게걸음   rx: 회전
    """
    conn.datachannel.pub_sub.publish_without_callback(
        RTC_TOPIC["WIRELESS_CONTROLLER"],
        {"lx": lx, "ly": ly, "rx": rx, "ry": 0.0, "keys": 0},
    )


async def move_by_joystick(conn, ly=0.3, seconds=1.5):
    """조이스틱 통로로 전진해봅니다. 50Hz 로 보냅니다."""
    print(f"     조이스틱 통로로 전진 (ly={ly}, {seconds}초)")
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            joystick(conn, ly=ly)
            await asyncio.sleep(0.02)
    finally:
        for _ in range(5):
            joystick(conn, ly=0.0)
            await asyncio.sleep(0.02)


async def try_gait(conn, label, cmd, param, use_joystick):
    print("\n" + "─" * 64)
    print(f" {label}   /   {'조이스틱 통로' if use_joystick else 'sport Move 통로'}")
    print("─" * 64)

    if cmd:
        try:
            await common.sport(conn, cmd, param)
            print(f"     걸음새 명령 전송: {cmd}")
            await asyncio.sleep(2.0)
        except KeyError:
            print(f"     ({cmd} 은 이 모드의 명령표에 없습니다 — 건너뜁니다)")
            return None
        except Exception as e:
            print(f"     걸음새 명령 실패: {e}")
            return None

    if use_joystick:
        await move_by_joystick(conn)
    else:
        await common.move(conn, x=0.25, duration=1.5)

    await asyncio.sleep(1.0)

    answer = await asyncio.to_thread(
        input, "     → 걸음을 뗐습니까? (y = 걸었다 / Enter = 아니다 / q = 중단): ")
    answer = answer.strip().lower()
    if answer == "q":
        raise KeyboardInterrupt
    return answer == "y"


async def main():
    global conn

    print("=" * 64)
    print(" 걸음새 찾기  ★ 로봇이 움직입니다 ★")
    print("=" * 64)
    print(" 이동 명령에 로봇이 걷지 않고 몸통만 기울이는 문제를 좁힙니다.")
    print(" 후보를 하나씩 시험하고, 매번 걸었는지 여쭤봅니다.")
    print(" 각 시험은 1.5초 전진이 전부입니다.")
    print("=" * 64)

    if not await common.confirm(
        "사방 2~3m 가 비어 있고, 리모컨을 든 사람이 대기 중입니까?\n"
        "(로봇이 예상보다 크게 움직일 수 있습니다)"
    ):
        print("취소했습니다.")
        return

    conn = await common.connect()
    await common.prepare_motion(conn)
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    print("\n[준비] 일어서기")
    await common.stand_and_wait(conn)

    results = []
    try:
        for n, (label, cmd, param, use_joystick) in enumerate(TRIALS, 1):
            print(f"\n[{n}/{len(TRIALS)}]", end="")
            walked = await try_gait(conn, label, cmd, param, use_joystick)
            if walked is None:
                continue
            results.append((label, "조이스틱" if use_joystick else "sport", walked))
            if walked:
                print("\n" + "=" * 64)
                print(" ★ 찾았습니다 ★")
                print("=" * 64)
                print(f"   걸음새 : {cmd or '(없음)'}")
                print(f"   통로   : {'조이스틱' if use_joystick else 'sport Move'}")
                print("=" * 64)
                print("\n 이 결과를 알려주시면 코드에 반영하겠습니다.")
                return
            # 다음 시험 전에 자세를 다시 정돈합니다
            await common.stop(conn)
            await asyncio.sleep(0.5)
    finally:
        print("\n" + "=" * 64)
        print(" 시험 결과")
        print("=" * 64)
        for label, channel, walked in results:
            mark = "걸었음" if walked else "  —   "
            print(f"   {mark}  {channel:8s}  {label}")
        if not any(w for _, _, w in results):
            print("\n 전부 걷지 않았습니다. 이 표를 그대로 알려주세요.")
            print(" 다른 방향으로 원인을 좁혀보겠습니다.")
        print()
        print(" 로봇을 정리합니다...")
        try:
            await common.settle(conn)
        except Exception:
            pass
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
