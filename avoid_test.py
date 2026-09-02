# -*- coding: utf-8 -*-
"""
장애물 회피가 코드로 켜지는가, 그리고 실제로 멈추는가.  ★ 로봇이 움직입니다 ★

  왜 이걸 확인하나
    지금 안내 데모의 이동은 **열린 루프**입니다. 앞을 보지 않고 정해진
    시간만큼 걷습니다. 좁은 복도에서는 그게 벽으로 걸어가는 것과 같아서,
    04 는 아예 공간을 계산해 안 들어가면 실행을 거부하도록 해두었습니다.

    그런데 이 기체에는 라이다가 있고, 명령표에 회피 관련 명령이 있습니다.

        SwitchAvoidMode   2058     (리모컨 옆면 2 버튼이 켜고 끄는 그것)

    이게 코드로 켜지고 실제로 벽 앞에서 서 준다면, 복도에서 안내를 할 수
    있게 됩니다. 열린 루프에서 벗어나는 첫걸음입니다.

  실험 설계
    A. 회피를 켠다               → 응답 코드가 0 인가
    B. 앞이 트인 채로 전진       → 그냥 잘 걷는가 (회피가 보행을 막지 않는가)
    C. 앞에 장애물을 두고 전진   → **스스로 멈추는가**

    B 가 대조군입니다. 같은 명령을 주고 장애물만 바꿉니다.
    회피가 없어도 안 걷는 상태라면 C 의 '멈춤'은 의미가 없으니까요.

    ※ '회피를 끄면 부딪히는가'는 시험하지 않습니다. 그건 이미 아는 사실이고,
      확인하겠다고 로봇을 벽에 박을 이유가 없습니다.

  ★ 장애물은 부드럽고 가벼운 것으로 ★
    빈 종이상자, 쿠션, 스티로폼. 벽이나 유리, 사람은 안 됩니다.
    로봇이 안 멈출 수도 있다는 전제로 준비하세요.

    .\\run avoid_test.py

  실행 전 체크리스트
    □ 앞으로 3m 이상 트인 평평한 바닥
    □ 부드러운 장애물 하나 (종이상자 등)
    □ 리모컨 손에 (P 두 번 = 힘 빼기)  ★ 이번엔 특히 ★
    □ 배터리 50% 이상
"""

import asyncio
import sys
import time

import common
import safety

conn = None

STICK = 0.25        # 느리게. 회피가 반응할 시간을 줍니다
PUSH = 4.0          # 최대 이 시간만큼 전진 (약 1.6 m)
STOPPED = 0.05      # 이 속도 아래면 멈춘 것으로 봅니다 (m/s)
STOP_HOLD = 0.5     # 이만큼 계속 느려야 '스스로 멈췄다'로 인정


async def walk(probe, seconds=PUSH):
    """전진하면서 이동 거리를 적분합니다. 스스로 멈추면 거기서 끝냅니다.

    돌려주는 값: (스스로 멈췄는가, 간 거리 m, 걸린 시간 초)
    """
    dist = 0.0
    slow_since = None
    start = last = time.time()
    deadline = start + seconds
    self_stopped = False

    while time.time() < deadline:
        common.joystick(conn, **common.stick_from_intent(x=STICK))
        await asyncio.sleep(0.02)

        now = time.time()
        dt, last = now - last, now

        v = probe.velocity
        speed = abs(v[0]) if v else 0.0
        dist += speed * dt

        # 출발 직후에는 원래 느리므로 0.8초는 봐줍니다
        if now - start > 0.8:
            if speed < STOPPED:
                slow_since = slow_since or now
                if now - slow_since > STOP_HOLD:
                    self_stopped = True
                    break
            else:
                slow_since = None

    elapsed = time.time() - start
    for _ in range(5):
        common.joystick(conn, 0.0, 0.0, 0.0)
        await asyncio.sleep(0.02)
    await common.stop(conn)
    return self_stopped, dist, elapsed


async def enable_avoid(on=True):
    """회피 모드를 켜거나 끕니다. 파라미터 형식이 문서화돼 있지 않아 몇 가지 시도합니다.

    돌려주는 값: (성공한 파라미터 형식, 응답 코드)
    """
    for label, param in (("{'data': bool}", {"data": bool(on)}),
                         ("{'data': int}", {"data": 1 if on else 0}),
                         ("(파라미터 없음)", None)):
        try:
            reply = await common.sport(conn, "SwitchAvoidMode", param)
        except KeyError:
            return None, "명령표에 없음"
        code = common.status_code(reply)
        print(f"    {label:18} → 코드 {code}")
        if code == 0:
            return label, code
    return None, code


async def run(conn_):
    await common.prepare_motion(conn_)
    await safety.set_auto_recovery(conn_, False)
    watchdog = safety.Watchdog(conn_)
    watchdog.arm()

    probe = common.StateProbe(conn_)
    await probe.read()

    print("\n[준비] 일어섭니다")
    await common.stand_and_wait(conn_, probe=probe)

    # ── A. 회피 켜기 ─────────────────────────────────────────
    print("\n" + "=" * 66)
    print(" A. 회피 모드를 코드로 켤 수 있는가")
    print("=" * 66)
    form, code = await enable_avoid(True)
    if form is None:
        print("\n  ✘ 어떤 형식으로도 받아들여지지 않았습니다.")
        print("    이 펌웨어에서는 코드로 회피를 켤 수 없는 것으로 보입니다.")
        print("    리모컨 옆면 2 버튼(두 번 = 켜기)으로만 쓸 수 있습니다.")
        print("\n    그렇다면 복도 안내는 다음 중 하나로 갑니다.")
        print("      · 리모컨으로 회피를 켜 두고 프로그램을 돌린다")
        print("      · 04 를 --stay 로만 쓴다")
        return
    print(f"\n  ✔ '{form}' 형식으로 켜졌습니다 (코드 {code})")
    await asyncio.sleep(2.0)

    # ── B. 대조군 ────────────────────────────────────────────
    print("\n" + "=" * 66)
    print(" B. 대조군 — 앞이 트인 상태")
    print("=" * 66)
    print(" 회피를 켠 채로 그냥 걷습니다. 끝까지 걸어야 정상입니다.")
    if not await common.confirm("로봇 앞 3m 가 **완전히 비어** 있습니까?"):
        return
    stopped, dist, secs = await walk(probe)
    print(f"    간 거리 {dist:.2f} m / {secs:.1f}초  →  "
          f"{'중간에 멈췄습니다' if stopped else '끝까지 걸었습니다'}")
    if stopped:
        print("\n  ※ 아무것도 없는데 멈췄습니다. 회피가 과민하거나 바닥·조명을")
        print("    장애물로 본 것일 수 있습니다. C 의 결과를 해석할 수 없으니")
        print("    여기서 멈춥니다.")
        return
    baseline = dist
    await asyncio.sleep(2.0)

    # ── C. 장애물 ────────────────────────────────────────────
    print("\n" + "=" * 66)
    print(" C. 장애물을 두고 — 스스로 멈추는가")
    print("=" * 66)
    print(" 로봇 앞 약 1.5m 에 **부드럽고 가벼운** 장애물을 놓으세요.")
    print(" (빈 종이상자, 쿠션 / 벽·유리·사람은 안 됩니다)")
    print(" 안 멈출 수도 있습니다. 리모컨을 손에 들고 계세요.")
    if not await common.confirm("장애물을 놓았고, 리모컨을 들고 계십니까?"):
        return
    stopped, dist, secs = await walk(probe)
    print(f"    간 거리 {dist:.2f} m / {secs:.1f}초  →  "
          f"{'★ 스스로 멈췄습니다 ★' if stopped else '멈추지 않았습니다'}")

    # ── 정리 ─────────────────────────────────────────────────
    print("\n" + "=" * 66)
    print(" 정리")
    print("=" * 66)
    print(f"   대조군(빈 공간)  {baseline:.2f} m — 끝까지 걸음")
    print(f"   장애물 앞        {dist:.2f} m — "
          f"{'스스로 멈춤' if stopped else '멈추지 않음'}")
    print()
    if stopped and dist < baseline - 0.2:
        print(" ★ 회피가 동작합니다 ★")
        print(" 복도에서 안내를 할 수 있게 됩니다. 다음으로 할 일:")
        print("   · common 에 '회피 켜기' 를 넣고 04 가 시작할 때 켜도록")
        print("   · 그래도 공간 확인은 남겨둡니다 — 회피는 보조 장치입니다")
    elif stopped:
        print(" 멈추긴 했는데 대조군과 거리 차이가 작습니다.")
        print(" 우연히 멈춘 것일 수 있으니 두어 번 더 돌려보세요.")
    else:
        print(" 회피 명령은 받아들여졌지만 실제로 멈추지는 않았습니다.")
        print(" 라이다가 이 장애물을 못 봤을 수 있습니다 — 더 크고 높은 것으로")
        print(" 바꿔 다시 해보시고, 그래도 안 되면 복도 안내는 보류하세요.")
        print(" 04 는 --stay 로 시연할 수 있습니다.")


async def main():
    global conn

    print("=" * 66)
    print(" 장애물 회피 확인  ★ 로봇이 움직입니다 ★")
    print("=" * 66)
    print(__doc__.split("실행 전 체크리스트")[0])

    if not await common.confirm(
        "앞으로 3m 가 비어 있고, 부드러운 장애물과 리모컨을 준비했습니까?"
    ):
        print("취소했습니다.")
        return

    conn = await common.connect()
    try:
        await run(conn)
    finally:
        print("\n정리합니다...")
        try:
            await common.settle(conn)
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
