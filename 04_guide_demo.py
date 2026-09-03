# -*- coding: utf-8 -*-
"""
4단계 — 한국어 안내 데모.  ★ 로봇이 말하면서 움직입니다 ★

    인사 → 따라오라고 안내 → 이동 → 도착 안내 → 마무리 인사

  ★ 좁은 곳에서 이걸 그냥 돌리면 안 됩니다 ★

  이 스크립트의 이동은 **열린 루프**입니다. 앞을 보지 않고 정해진 시간만큼
  걷습니다. 게다가 직진 명령만 줘도 로봇은 조금씩 돌아갑니다.
  폭이 좁은 복도에서 그 표류는 곧 벽입니다.

  그래서 두 가지를 넣었습니다.

    1. 공간 확인 — config.py 에 적어둔 실제 공간에 코스가 들어가는지
       계산하고, 안 들어가면 **실행을 거부합니다.**
    2. 표류 감시 — 직진 중 방향이 틀어지면 그 자리에서 멈춥니다.

  그래도 앞을 보는 것은 아닙니다. 사람이 지켜봐야 합니다.

  실행 방법

      .\\run 04_guide_demo.py             이동 포함 (공간을 먼저 확인합니다)
      .\\run 04_guide_demo.py --stay      ★ 이동 없이 제자리에서만 ★
      .\\run 04_guide_demo.py --refresh   로봇의 멘트를 지우고 새로 올림
                                         (음량 설정이나 문구를 바꿨을 때)

  `--stay` 는 좁은 복도·사무실에서도 안전합니다. 인사, 안내 멘트, 제스처,
  마무리까지 전부 하고 **걷기만 뺍니다.** 실제 안내의 대부분이 여기 들어
  있으므로, 공간이 확보되기 전까지는 이쪽으로 시연하세요.

  실행 전 체크리스트 (이동 모드)
    □ config.py 의 COURSE_LENGTH / COURSE_WIDTH 를 **줄자로 재서** 적었는가
    □ 발끝의 비닐 포장 제거
    □ 배터리 50% 이상
    □ 리모컨을 든 사람이 대기 (P 버튼 두 번 = 힘 빼기)
"""

import asyncio
import sys

import common
import config
import safety

conn = None

# ── 안내 코스 ────────────────────────────────────────────────
# (설명, 전진 스틱, 회전 스틱, 지속 초)
#   회전은 거리를 먹지 않으므로 공간 계산에서 빠집니다.
COURSE = [
    ("앞으로 나아갑니다", 0.3, 0.0, 2.0),
    ("방향을 바꿉니다", 0.0, 0.4, 1.5),
    ("조금 더 갑니다", 0.3, 0.0, 1.5),
]


def course_distance(steps=None, safe=True):
    """코스가 앞으로 나아가는 총 거리 (m).

    ★ 기본이 safe=True 인 이유 ★
    이 값으로 "공간에 들어가는가" 를 판정합니다. 판정에서는 **크게** 잡아야
    합니다 — 작게 잡고 틀리면 벽입니다. 실제로 얼마나 갈지 궁금할 때만
    safe=False 로 부르세요.
    """
    steps = COURSE if steps is None else steps
    return sum(common.distance_for(x, secs, safe=safe)
               for _, x, z, secs in steps if abs(z) <= 0.05)


def check_space(verbose=True):
    """코스가 공간에 들어가는지 확인합니다.

    돌려주는 값: (들어가는가, 필요 거리, 쓸 수 있는 거리)
    """
    need = course_distance()
    length = getattr(config, "COURSE_LENGTH", 3.0)
    margin = getattr(config, "COURSE_MARGIN", 0.8)
    usable = length - margin

    if verbose:
        real = course_distance(safe=False)
        print("\n[공간] 코스가 들어가는지 확인합니다")
        print(f"       코스가 나아가는 거리   최대 {need:.2f} m"
              f"  (실제로는 {real:.2f} m 쯤)")
        print(f"       쓸 수 있는 거리        {length:.2f} m − 여유 {margin:.2f} m"
              f" = {usable:.2f} m")
        width = getattr(config, "COURSE_WIDTH", 1.5)
        print(f"       좌우 폭                {width:.2f} m")

    return need <= usable, need, usable


async def guide_sequence(conn, hub, uuids, probe, stay=False):
    """안내 시나리오 본체. 여기를 고쳐서 코스를 만드세요."""

    print("\n▶ 1. 일어서서 인사")
    await common.stand_and_wait(conn, probe=probe)

    await common.say(hub, uuids, "greet", wait=6)
    await common.sport(conn, "Hello")          # 앞발 흔들기
    await asyncio.sleep(4)

    print("\n▶ 2. 따라오라고 안내")
    await common.say(hub, uuids, "follow_me", wait=4)

    if stay:
        print("\n▶ 3. 이동  — 건너뜁니다 (--stay)")
        print("     제자리에서 좌우를 둘러보는 것으로 대신합니다.")
        # 아주 짧은 좌우 회전. 제자리에서 도는 것이라 거리를 먹지 않습니다.
        await common.move_guarded(conn, probe, z=0.3, duration=1.0)
        await asyncio.sleep(1)
        await common.move_guarded(conn, probe, z=-0.3, duration=1.0)
        await asyncio.sleep(1)
    else:
        print("\n▶ 3. 이동")
        for label, x, z, secs in COURSE:
            print(f"     {label}")
            done, drift = await common.move_guarded(
                conn, probe, x=x, z=z, duration=secs)
            if not done:
                print("\n[안내] 방향이 틀어져 코스를 중단했습니다.")
                print("       남은 이동은 건너뛰고 마무리로 넘어갑니다.")
                break
            await asyncio.sleep(1)

    print("\n▶ 4. 도착 안내")
    await common.say(hub, uuids, "arrived", wait=6)

    print("\n▶ 5. 마무리")
    await common.say(hub, uuids, "bye", wait=5)
    await common.sport(conn, "StandDown")
    await asyncio.sleep(3)


async def main():
    global conn

    stay = "--stay" in sys.argv or "--제자리" in sys.argv
    refresh = "--refresh" in sys.argv

    print("=" * 62)
    print(" 한국어 안내 데모  " + ("★ 제자리 모드 (이동 없음) ★" if stay
                                   else "★ 로봇이 말하고 움직입니다 ★"))
    print("=" * 62)

    if not stay:
        fits, need, usable = check_space()
        if not fits:
            print("\n" + "=" * 62)
            print(" ★ 공간이 부족합니다 — 실행하지 않습니다 ★")
            print("=" * 62)
            print(f" 코스에는 {need:.2f} m 가 필요한데 {usable:.2f} m 밖에 없습니다.")
            print()
            print(" 셋 중 하나를 하세요.")
            print("   1. 넓은 곳으로 옮긴다")
            print("   2. config.py 의 COURSE_LENGTH 를 실제로 재서 고친다")
            print("      (지금 값이 실제보다 작게 적혀 있을 수 있습니다)")
            print("   3. 이동 없이 시연한다:")
            print("        .\\run 04_guide_demo.py --stay")
            print()
            print(" COURSE 의 지속 시간을 줄여 거리를 맞출 수도 있습니다.")
            return
        print("       → 들어갑니다.\n")
    else:
        print("\n[모드] 제자리 모드 — 걷지 않습니다. 좁은 곳에서도 안전합니다.")
        print("       제자리 회전만 아주 조금 합니다.\n")

    # 음성 파일은 미리 준비 (로봇 연결 전에)
    print("[준비] 안내 멘트 확인...")
    paths = await common.make_all_phrases()

    question = ("로봇이 제자리에서 말하고 조금 돕니다. 사방 1m 가 비어 있습니까?"
                if stay else
                "로봇 주변이 비어 있고, 발의 비닐을 제거했으며,\n"
                "비상 정지를 할 사람이 대기 중입니까?")
    if not await common.confirm(question):
        print("취소했습니다.")
        return

    conn = await common.connect()
    try:
        await run_demo(conn, paths, stay=stay, refresh=refresh)
    finally:
        # ★ 정리는 반드시 살아 있는 이벤트 루프 안에서 ★
        try:
            await common.stop(conn)
        except Exception:
            pass
        await common.disconnect(conn)


async def run_demo(conn, paths, stay=False, refresh=False):
    await common.prepare_motion(conn)

    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    probe = common.StateProbe(conn)
    await probe.read()

    await common.set_volume(conn)

    if refresh:
        print("\n[준비] 로봇의 기존 멘트를 지우고 새로 올립니다 (--refresh)...")
    else:
        print("\n[준비] 안내 멘트를 로봇에 올립니다 (처음 한 번만 오래 걸립니다)...")
    hub, uuids = await common.upload_all(conn, paths, replace=refresh)
    print(f"[준비] 완료 — {len(uuids)}개\n")

    await guide_sequence(conn, hub, uuids, probe, stay=stay)

    print("\n" + "=" * 62)
    print(" 데모 완료.")
    print()
    if stay:
        print(" 제자리 모드로 돌렸습니다. 이동까지 보려면")
        print(" config.py 의 COURSE_LENGTH 를 실제 공간에 맞게 재서 적고")
        print(" --stay 없이 다시 실행하세요.")
    else:
        print(" 다음 단계 아이디어")
        print("  · config.py 의 PHRASES 에 지점별 설명을 추가")
        print("  · COURSE 를 실제 동선에 맞게 수정")
        print("  · 장애물 회피를 붙여 열린 루프에서 벗어나기 (avoid_test.py)")
    print("=" * 62)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
        print("로봇이 멈추지 않으면 리모컨의 P 버튼을 두 번 누르세요.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
