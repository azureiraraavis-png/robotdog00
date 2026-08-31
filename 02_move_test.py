# -*- coding: utf-8 -*-
"""
2단계 — 동작 확인.

★ 로봇이 실제로 움직입니다. ★

  실행 전 체크리스트
    □ 사방 2m 이상 트인 평평한 바닥
    □ 발끝의 비닐 포장 제거
    □ 배터리 50% 이상
    □ 리모컨을 든 사람이 옆에 대기 (L2+B = 비상 정지)
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
    await common.prepare_motion(conn)

    # 넘어지면 즉시 힘을 빼는 감시. 자동 복구는 꺼둡니다.
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    print("\n[1/5] 일어서기")
    await common.sport(conn, "StandUp")
    await asyncio.sleep(3)

    print("\n[2/5] 균형 자세")
    await common.sport(conn, "BalanceStand")
    await asyncio.sleep(2)

    print("\n[3/5] 인사 (Hello)")
    await common.sport(conn, "Hello")
    await asyncio.sleep(4)

    if await common.confirm("이제 앞으로 천천히 걷습니다. 진행할까요?"):
        print("\n[4/5] 전진")
        await common.move(conn, x=0.2, duration=2.0)
        await asyncio.sleep(1)

        print("\n[4/5] 제자리 좌회전")
        await common.move(conn, z=0.4, duration=2.0)
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

    await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 비상 정지를 시도합니다.")
        if conn:
            try:
                asyncio.run(common.emergency_damp(conn))
            except Exception:
                pass
        print("로봇이 멈추지 않으면 리모컨의 L2+B 를 누르세요.")
        sys.exit(0)
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
