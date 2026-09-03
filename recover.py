# -*- coding: utf-8 -*-
"""
넘어진 로봇 일으키기 / 자동 복구 끄기.

    .\\run recover.py           현재 상태를 보고, 필요하면 일으킵니다
    .\\run recover.py off       자동 복구를 끄기만 합니다
    .\\run recover.py on        자동 복구를 다시 켭니다

★ 로봇이 지금 발버둥치고 있다면 ★
  먼저 손으로 힘을 빼세요 — 게임패드 L2+B, 동반 리모컨 P 두 번. 그게 가장 빠릅니다.
  조종 장치가 없으면 이 스크립트가 붙는 데 2~3초 걸립니다.
  그동안 로봇에 손을 대지 마세요 — 다리가 빠르게 움직입니다.
"""

import asyncio
import sys

import common
import safety

conn = None


async def main():
    global conn

    mode = (sys.argv[1].lower() if len(sys.argv) > 1 else "").strip()

    print("=" * 64)
    print(" 넘어짐 복구")
    print("=" * 64)

    conn = await common.connect()
    await common.prepare_motion(conn)

    # 발버둥치고 있었다면 여기서 멈춥니다.
    # 서 있는 상태라면 곧바로 힘을 빼지 않고 먼저 눕힙니다 — 떨어지지 않도록.
    print("\n[1] 움직임을 멈추고 안전한 자세로")
    await common.settle(conn)

    # 자동 복구 끄기 — 다시 발버둥치지 않도록
    print("\n[2] 자동 복구를 끕니다")
    print("    (이게 켜져 있으면 로봇이 스스로 일어나려다 계속 발버둥칩니다)")
    await safety.set_auto_recovery(conn, False)
    await asyncio.sleep(0.5)

    if mode == "off":
        print("\n자동 복구를 끈 상태로 두고 종료합니다.")
        await common.disconnect(conn)
        return

    if mode == "on":
        await safety.set_auto_recovery(conn, True)
        print("\n자동 복구를 다시 켰습니다.")
        await common.disconnect(conn)
        return

    # 현재 기울기 확인
    print("\n[3] 자세 확인 중...")
    wd = safety.Watchdog(conn, verbose=False)
    wd.arm()
    await asyncio.sleep(2.5)
    wd.disarm()

    if wd.last_rpy:
        roll, pitch = wd.last_rpy
        print(f"    기울기: roll={roll:.0f}도  pitch={pitch:.0f}도")
        if abs(roll) > safety.FLIP_ANGLE:
            print("\n    ★ 완전히 뒤집혀 있습니다 ★")
            print("    이 상태에서는 스스로 일어나기 어렵고, 시도하면 다칩니다.")
            print("    전원이 꺼진 것처럼 힘이 빠져 있으니, 손으로 배가 바닥을")
            print("    향하도록 돌려 눕힌 다음 다시 실행해 주세요.")
            await common.disconnect(conn)
            return
    else:
        print("    기울기를 읽지 못했습니다. 눈으로 확인해 주세요.")

    print("\n" + "=" * 64)
    if not await common.confirm(
        "로봇이 배를 바닥에 대고 있고, 주변 2m 가 비어 있습니까?\n"
        "(뒤집혀 있다면 먼저 손으로 돌려 눕히세요)"
    ):
        print("취소했습니다. 힘이 빠진 상태로 두고 종료합니다.")
        await common.disconnect(conn)
        return

    print("\n[4] 일으킵니다")
    await common.sport(conn, "RecoveryStand")
    await asyncio.sleep(4)

    print("[5] 균형 자세")
    await common.sport(conn, "BalanceStand")
    await asyncio.sleep(2)

    print("\n" + "=" * 64)
    print(" 완료.")
    print()
    print(" 자동 복구는 꺼진 상태로 두었습니다.")
    print(" 다시 켜려면:  .\\run recover.py on")
    print("=" * 64)

    await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        common.explain_error(e)
        print("\n연결이 안 되면 조종 장치로 하세요:")
        print("   P 두 번 (힘 빼기)  →  손으로 바로 눕히기  →  P 길게 1초 (일으키기)")
        sys.exit(1)
