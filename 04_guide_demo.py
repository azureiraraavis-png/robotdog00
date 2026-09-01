# -*- coding: utf-8 -*-
"""
4단계 — 한국어 안내 데모.  ★ 로봇이 말하면서 움직입니다 ★

방문객 앞에서 보여줄 수 있는 최소한의 완성된 흐름입니다.

    인사 → 따라오라고 안내 → 이동 → 도착 안내 → 마무리 인사

이 파일이 앞으로 확장의 출발점입니다. 여기에
  · 음성 인식(STT)으로 명령을 받는 부분
  · 지점별 설명 멘트
  · LiDAR 기반 회피
를 얹어 나가면 됩니다.

  실행 전 체크리스트
    □ 사방 3m 이상 트인 평평한 바닥
    □ 발끝의 비닐 포장 제거
    □ 배터리 50% 이상
    □ 리모컨을 든 사람이 대기 (P 버튼 두 번 = 힘 빼기)

    python 04_guide_demo.py
"""

import asyncio
import sys

import common
import config
import safety

conn = None


async def guide_sequence(conn, hub, uuids):
    """안내 시나리오 본체. 여기를 고쳐서 코스를 만드세요."""

    print("\n▶ 1. 일어서서 인사")
    await common.stand_and_wait(conn)

    await common.say(hub, uuids, "greet", wait=6)
    await common.sport(conn, "Hello")          # 앞발 흔들기
    await asyncio.sleep(4)

    print("\n▶ 2. 따라오라고 안내")
    await common.say(hub, uuids, "follow_me", wait=4)

    print("\n▶ 3. 이동")
    await common.move(conn, x=0.2, duration=3.0)
    await asyncio.sleep(1)
    await common.move(conn, z=0.4, duration=1.5)   # 방향 전환
    await asyncio.sleep(1)
    await common.move(conn, x=0.2, duration=2.0)
    await asyncio.sleep(1)

    print("\n▶ 4. 도착 안내")
    await common.say(hub, uuids, "arrived", wait=6)

    print("\n▶ 5. 마무리")
    await common.say(hub, uuids, "bye", wait=5)
    await common.sport(conn, "StandDown")
    await asyncio.sleep(3)


async def main():
    global conn

    print("=" * 60)
    print(" 한국어 안내 데모  ★ 로봇이 말하고 움직입니다 ★")
    print("=" * 60)

    # 음성 파일은 미리 준비 (로봇 연결 전에)
    print("\n[준비] 안내 멘트 확인...")
    paths = await common.make_all_phrases()

    if not await common.confirm(
        "로봇 주변 3m 가 비어 있고, 발의 비닐을 제거했으며,\n"
        "비상 정지를 할 사람이 대기 중입니까?"
    ):
        print("취소했습니다.")
        return

    conn = await common.connect()
    try:
        await run_demo(conn, paths)
    finally:
        # ★ 정리는 반드시 살아 있는 이벤트 루프 안에서 ★
        try:
            await common.stop(conn)
        except Exception:
            pass
        await common.disconnect(conn)


async def run_demo(conn, paths):
    await common.prepare_motion(conn)

    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    await common.set_volume(conn)

    print("\n[준비] 안내 멘트를 로봇에 올립니다 (처음 한 번만 오래 걸립니다)...")
    hub, uuids = await common.upload_all(conn, paths)
    print(f"[준비] 완료 — {len(uuids)}개\n")

    await guide_sequence(conn, hub, uuids)

    print("\n" + "=" * 60)
    print(" 데모 완료.")
    print()
    print(" 다음 단계 아이디어")
    print("  · config.py 의 PHRASES 에 지점별 설명을 추가")
    print("  · guide_sequence() 를 실제 동선에 맞게 수정")
    print("  · 폰/PC에서 한국어 음성 인식을 붙여 명령으로 이 함수들을 호출")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
        print("로봇이 멈추지 않으면 리모컨의 P 버튼을 두 번 누르세요.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
