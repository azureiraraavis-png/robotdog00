# -*- coding: utf-8 -*-
"""
안전하게 들어 올리기.  ★ 옮기기 전에 실행하세요 ★

왜 필요한가
───────────
전원이 켜진 로봇의 등 손잡이를 잡고 들어 올리면, 발이 땅에서 떨어집니다.
로봇은 그것을 **넘어진 것**으로 해석하고 스스로 일어나려 발버둥칩니다.
다리가 빠르게 꺾이며 움직이므로, 손이 그 사이에 있으면 다칩니다.

이 스크립트가 하는 일

  1. 자동 복구 끄기 — 넘어졌다고 판단해도 일어나려 하지 않습니다
  2. **천천히 엎드리기** — 제어된 동작으로 내려앉습니다
  3. 힘 빼기        — 이미 바닥에 닿아 있으니 떨어질 높이가 없습니다
  4. 몸높이로 확인   — 정말 힘이 빠졌는지 재서 알려줍니다

  ★ 2번이 빠지면 안 됩니다 ★
  서 있는 상태에서 곧바로 힘을 빼면 그대로 무너지며 '쿵' 떨어집니다.

그리고 **연결을 열어둔 채 대기**합니다. 옮기는 동안 설정이 유지되도록요.
다 옮기신 뒤 Enter 를 누르면 종료합니다.

    .\\run carry.py

들어 올릴 때
  · 등의 손잡이만 잡으세요. 다리나 관절을 잡지 마세요
  · 무게가 15kg 정도 됩니다. 허리를 조심하세요
  · 내려놓을 때는 배가 바닥에 먼저 닿게, 다리는 접힌 상태로
"""

import asyncio
import sys

import common

conn = None


async def main():
    global conn

    print("=" * 64)
    print(" 안전하게 들어 올리기")
    print("=" * 64)
    print(" 로봇을 천천히 눕히고 힘을 뺀 뒤, 확인해서 알려드립니다.")
    print(" 주변에 사람이 없는지, 엎드릴 자리가 평평한지 확인하세요.")
    print("=" * 64)

    conn = await common.connect()          # 연결하면서 자동 복구가 꺼집니다
    await common.prepare_motion(conn, verbose=False)
    await common.set_volume(conn)
    speaker = common.Speaker(conn)

    print("\n[1/2] 자동 복구 끄기")
    await common.set_auto_recovery(conn, False)
    await asyncio.sleep(0.5)

    print("\n[2/2] 눕히고 힘 빼기")
    before, after = await common.settle(conn, speaker=speaker)

    # 정말 힘이 빠졌는지 확인합니다
    limp = False
    if before is not None and after is not None:
        print(f"      몸높이: {before:.3f} → {after:.3f} m  ({after - before:+.3f})")
        limp = after < common.StateProbe.STANDING
    elif after is not None:
        print(f"      몸높이: {after:.3f} m")
        limp = after < common.StateProbe.STANDING
    else:
        print("      몸높이를 읽지 못했습니다.")

    print("\n" + "=" * 64)
    if limp:
        print(" 힘이 빠졌습니다 — 들어 올려도 됩니다")
        print("=" * 64)
        await common.announce(speaker, "lift_ready")
    else:
        print(" ⚠ 힘이 빠졌는지 확인되지 않았습니다")
        print("=" * 64)
        print()
        print("   로봇이 아직 서 있거나 버티고 있을 수 있습니다.")
        print("   눈으로 확인하세요 — 다리가 접혀 배가 바닥에 닿아 있어야 합니다.")
        print("   서 있다면 리모컨의 P 버튼을 두 번 눌러 힘을 빼세요.")
        print("   확실하지 않으면 들어 올리지 마세요.")

    print()
    print("   · 등의 손잡이만 잡으세요. 다리나 관절은 잡지 마세요")
    print("   · 무게가 15kg 정도 됩니다")
    print("   · 내려놓을 때는 배가 먼저 닿게, 다리는 접힌 상태로")
    print()
    print("   이 창은 열어두세요. 연결이 유지되어야 설정이 풀리지 않습니다.")
    print()
    print("=" * 64)

    try:
        await asyncio.to_thread(input, "\n다 옮기셨으면 Enter 를 누르세요... ")
    except EOFError:
        pass

    print("\n종료합니다. 로봇은 힘이 빠진 상태로 남습니다.")
    print("  다시 쓰시려면:  .\\run recover.py   (일으키기)")
    print("  전원을 끄시려면: 이미 엎드려 있으니 지금 그대로 끄셔도 됩니다")

    await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        common.explain_error(e)
        print("\n연결이 안 되면 리모컨으로 하세요:")
        print("   P 버튼 두 번 눌러 힘을 뺀 뒤  →  들어 올리기")
        sys.exit(1)
