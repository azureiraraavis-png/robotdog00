# -*- coding: utf-8 -*-
"""
로봇이 계속 떠들 때 멈춥니다.  (로봇은 움직이지 않습니다)

    .\\run hush.py

  로봇의 기본 재생 모드는 **한 곡 반복**입니다. 그래서 멘트를 한 번
  재생시키면 끝없이 되풀이합니다. 프로그램을 끝내도 로봇은 계속 말합니다.

  이 스크립트가 두 가지를 합니다.
    1. 지금 나오는 소리를 멈춘다 (pause)
    2. 재생 모드를 '한 번만' 으로 바꾼다 — 다시 안 그러도록

  급할 때는 로봇 전원을 내려도 되지만, 서 있는 상태라면 쓰러집니다.
  이쪽이 낫습니다.
"""

import asyncio
import sys

import common

conn = None


async def main():
    global conn
    print("=" * 60)
    print(" 로봇 입 다물게 하기")
    print("=" * 60)

    conn = await common.connect()
    try:
        hub = common.make_audio_hub(conn)

        before = await common.get_play_mode(hub)
        print(f"\n[음성] 현재 재생 모드: {before or '읽지 못함'}")

        await common.hush(hub)
        await asyncio.sleep(0.5)
        await common.set_play_once(hub)

        print("\n조용해졌습니까?")
        print("  · 아직 말한다면 한 번 더 실행해 보세요.")
        print("  · 그래도 안 되면 리모컨으로 전원을 내리기 전에")
        print("    .\\run park.py 로 먼저 엎드리게 하세요.")
    finally:
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
