# -*- coding: utf-8 -*-
"""
1단계 — 연결 확인.

로봇을 움직이지 않습니다. 안전하게 몇 번이고 돌려도 됩니다.
가장 먼저 이 스크립트를 성공시키세요. 여기서 막히면 나머지는 의미가 없습니다.

    python 01_connect_test.py
"""

import asyncio
import json
import sys

from unitree_webrtc_connect.constants import RTC_TOPIC

import common
import config


async def main():
    print("=" * 60)
    print(" Go2 연결 확인")
    print("=" * 60)
    print(f" 연결 방식 : {config.CONNECTION_MODE}")
    print(f" IP        : {config.ROBOT_IP or '(미설정)'}")
    print(f" AES 키    : {'설정됨 (' + config.AES_128_KEY[:6] + '...)' if config.AES_128_KEY else '없음'}")
    print("=" * 60)
    print("\n※ 폰의 유니트리 앱이 완전히 종료되어 있어야 합니다.\n")

    conn = await common.connect()

    # 모션 모드 확인 — 어떤 명령 체계를 쓸지 여기서 갈립니다.
    mode = await common.get_motion_mode(conn)
    print(f"\n[정보] 모션 모드: {mode}")
    if mode == "normal":
        print("       → SPORT_CMD 를 그대로 쓰면 됩니다.")
    elif mode:
        print("       → 'normal' 이 아닙니다. 02번 스크립트가 자동으로 전환합니다.")
        print("       → 만약 곡예 동작이 안 먹으면 SPORT_CMD_MCF 쪽을 봐야 합니다.")

    # 로봇 상태를 몇 초간 받아봅니다. 통신이 살아 있다는 확실한 증거입니다.
    received = {"count": 0}

    def on_state(message):
        received["count"] += 1
        if received["count"] == 1:
            data = message.get("data", {})
            print("\n[상태] 첫 수신 성공")
            if "body_height" in data:
                print(f"       몸높이: {data.get('body_height')}")
            if "mode" in data:
                print(f"       모드코드: {data.get('mode')}")

    conn.datachannel.pub_sub.subscribe(RTC_TOPIC["LF_SPORT_MOD_STATE"], on_state)

    print("\n[상태] 5초간 수신 대기...")
    await asyncio.sleep(5)

    print(f"\n[상태] {received['count']}건 수신")

    print("\n" + "=" * 60)
    if received["count"] > 0:
        print(" 성공. 연결과 양방향 통신이 모두 확인되었습니다.")
        print(" 다음: python 02_move_test.py")
    else:
        print(" 연결은 됐지만 상태 데이터가 오지 않았습니다.")
        print(" 로봇이 켜져 있고 배터리가 충분한지 확인하세요.")
    print("=" * 60)

    await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
        sys.exit(0)
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)