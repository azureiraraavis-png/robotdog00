# -*- coding: utf-8 -*-
"""
안전 종료 자세.  ★ 전원을 끄기 전에 실행하세요 ★

로봇은 전원을 끄는 순간 관절의 힘이 한꺼번에 풀립니다.
서 있는 상태에서 끄면 그대로 주저앉으며 '쿵' 하고 떨어집니다.
관절과 감속기에 좋을 리가 없고, 바닥과 로봇 모두에 부담입니다.

이 스크립트는 끄기 전에 안전한 자세를 만듭니다.

    1. StopMove    — 움직이는 중이면 먼저 멈춥니다
    2. StandDown   — 제어된 동작으로 천천히 엎드립니다
    3. Damp        — 힘을 뺍니다 (이미 바닥에 닿아 있으니 떨어질 높이가 없습니다)

순서가 중요합니다. Damp 를 먼저 하면 서 있던 자세 그대로 무너집니다.
반드시 엎드린 다음에 힘을 빼야 합니다.

    .\\run park.py

끝나면 화면 안내에 따라 전원 버튼을 누르세요.
"""

import asyncio
import sys

import common

conn = None


async def main():
    global conn

    print("=" * 60)
    print(" 안전 종료 자세")
    print("=" * 60)
    print(" 전원을 끄기 전에 로봇을 눕히고 힘을 뺍니다.")
    print()
    print(" ※ 로봇 주변이 비어 있는지, 엎드릴 자리가 평평한지 확인하세요.")
    print("=" * 60)

    conn = await common.connect()
    await common.prepare_motion(conn, verbose=False)
    await common.set_volume(conn)
    speaker = common.Speaker(conn)

    print("\n[진행] 눕히고 힘 빼기")
    before, after = await common.settle(conn, speaker=speaker)

    if before is not None and after is not None:
        print(f"      몸높이: {before:.3f} → {after:.3f} m")
    elif after is not None:
        print(f"      몸높이: {after:.3f} m")

    down = after is not None and after < common.StateProbe.STANDING

    print("\n" + "=" * 60)
    if down:
        print(" 완료 — 이제 전원을 꺼도 됩니다")
    else:
        print(" ⚠ 완전히 엎드렸는지 확인되지 않았습니다")
    print("=" * 60)
    print()
    if down:
        await common.announce(speaker, "power_ready")
        print("   배터리의 전원 버튼을 길게 눌러 끄세요.")
        print("   이미 엎드려 있으므로 떨어지지 않습니다.")
    else:
        print("   눈으로 확인하세요 — 배가 바닥에 닿아 있어야 합니다.")
        print("   서 있는 상태로 전원을 끄면 그대로 떨어집니다.")
        print("   확실하지 않으면 리모컨의 P 버튼을 두 번 누르세요.")
    print()
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
        print("\n연결이 안 되면 리모컨으로도 같은 순서를 할 수 있습니다:")
        print("   P 버튼 두 번  (엎드림/힘 빼기)  →  전원 끄기")
        sys.exit(1)
