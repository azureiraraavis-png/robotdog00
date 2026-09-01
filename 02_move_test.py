# -*- coding: utf-8 -*-
"""
2단계 — 동작 확인.

★ 로봇이 실제로 움직입니다. ★

  실행 전 체크리스트
    □ 사방 2m 이상 트인 평평한 바닥
    □ 발끝의 비닐 포장 제거
    □ 배터리 50% 이상
    □ 리모컨을 든 사람이 옆에 대기 (P 버튼 두 번 = 힘 빼기)
    □ 사람·전선·유리·계단 없음

    python 02_move_test.py
"""

import asyncio
import sys

import common
import config
import safety

conn = None


async def main():
    global conn

    print("=" * 60)
    print(" Go2 동작 확인  ★ 로봇이 움직입니다 ★")
    print("=" * 60)

    if not await common.confirm(
        "로봇 주변 2m 가 비어 있고, 발의 비닐을 제거했으며,\n"
        "비상 정지를 할 사람이 대기 중입니까?"
    ):
        print("취소했습니다.")
        return

    conn = await common.connect()
    try:
        await sequence(conn)
    finally:
        # ★ 정리는 반드시 살아 있는 이벤트 루프 안에서 ★
        # 루프가 끝난 뒤 asyncio.run() 으로 닫으려 하면 실패하고,
        # 로봇에 유령 세션이 남아 다음 실행이 연결조차 못 합니다.
        await shutdown(conn)


async def sequence(conn):
    await common.prepare_motion(conn)

    # 넘어지면 즉시 힘을 빼는 감시. 자동 복구는 꺼둡니다.
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    print("\n[1-2/5] 일어서기 — 실제로 설 때까지 기다립니다")
    await common.stand_and_wait(conn)

    print("\n[3/5] 인사 (Hello)")
    await common.sport(conn, "Hello")
    await asyncio.sleep(4)

    if await common.confirm("이제 앞으로 천천히 걷습니다. 진행할까요?"):
        print("\n[4/5] 전진")
        await common.move(conn, x=0.5, duration=2.0)
        await asyncio.sleep(1)

        print("\n[4/5] 제자리 좌회전")
        await common.move(conn, z=0.6, duration=2.0)
        await asyncio.sleep(1)
    else:
        print("\n[4/5] 이동은 건너뜁니다.")

    print("\n[5/5] 앉기")
    await common.sport(conn, "StandDown")
    await asyncio.sleep(3)

    print("\n" + "=" * 60)
    print(" 완료. 제어권이 확인되었습니다.")
    print(" 다음: python 03_speak_korean.py")
    print("=" * 60)


async def shutdown(conn):
    """어떤 식으로 끝나든 로봇을 멈추고 연결을 닫습니다."""
    if conn is None:
        return
    try:
        await common.stop(conn)
    except Exception:
        pass
    await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
        print("로봇이 멈추지 않으면 리모컨의 P 버튼을 두 번 누르세요.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
