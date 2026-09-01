# -*- coding: utf-8 -*-
"""
왜 몸통만 기울고 걷지 않는가 — 걷기 모드 찾기 실험.  ★ 로봇이 움직입니다 ★

  지금까지 알아낸 것
    · 조이스틱 신호는 분명히 로봇에 닿습니다 (몸통이 반응합니다)
    · 그런데 걸음을 떼지 않고 **몸통만 기울입니다**
    · `mode` 항목은 이 기체에서 항상 0 이라 쓸모가 없습니다
      (몸높이·회전속도는 정상 갱신되는데 이 항목만 죽어 있습니다)

  세운 가설
    `BalanceStand` 는 '서서 자세를 잡는' 모드입니다. 이 상태에서 스틱을 밀면
    로봇은 **걷는 대신 몸통을 기울입니다.** 우리가 본 그대로입니다.
    걸으려면 걷기 모드로 먼저 들어가야 합니다.

    앞서 gait_test.py 에서 조이스틱이 걸었던 것도, 바로 앞 시도에서 `Move` 를
    보냈기 때문일 수 있습니다. `Move` 가 걷기 모드로 들어가는 열쇠였고,
    그 뒤의 조이스틱이 그걸 이어받은 것이죠.

  그래서 무엇을 하나
    걷기 모드로 들어가는 후보를 하나씩 시도한 뒤 조이스틱을 주고,
    **로봇이 보고하는 실제 속도로 채점합니다.**
    몸통만 기울면 속도가 0 으로 나오고, 진짜 걸으면 값이 잡힙니다.

    한 번에 앞으로 1.5초, 뒤로 1.5초씩 줍니다. 제자리로 돌아오게 하기 위함입니다.

    .\\run mode_test.py

  실행 전 체크리스트
    □ 앞뒤로 2m 이상 트인 평평한 바닥
    □ 리모컨 손에 (P 두 번 = 힘 빼기)
    □ 배터리 50% 이상
"""

import asyncio
import sys
import time

import common
import safety

conn = None

STICK = 0.6        # 앞으로 기울이는 정도
PUSH = 1.5         # 한 방향으로 신호를 주는 시간 (초)
WALKED = 0.08      # 이 속도(m/s)를 넘으면 "걸었다"로 봅니다


async def send(name, parameter=None):
    """명령을 보내고 상태 코드를 돌려줍니다. 없는 명령이면 None."""
    try:
        reply = await common.sport(conn, name, parameter)
    except KeyError:
        return "없는명령"
    code = common.status_code(reply)
    return code


async def push(probe, seconds, ly):
    """조이스틱을 주면서 실제 속도를 지켜봅니다."""
    peak = 0.0
    deadline = time.time() + seconds
    while time.time() < deadline:
        common.joystick(conn, ly=ly)
        s = probe.speed()
        if s is not None:
            peak = max(peak, s)
        await asyncio.sleep(0.02)
    return peak


async def stop_joystick():
    for _ in range(5):
        common.joystick(conn, 0.0, 0.0, 0.0)
        await asyncio.sleep(0.02)


async def trial(probe, label, prep):
    """준비를 한 뒤 앞뒤로 밀어보고, 걸었는지 채점합니다."""
    print(f"\n─ {label}")
    codes = await prep()
    if codes:
        print(f"    응답 코드: {codes}")
    await asyncio.sleep(1.2)
    print(f"    준비 후: {probe.describe()}")

    fwd = await push(probe, PUSH, +STICK)
    back = await push(probe, PUSH, -STICK)
    await stop_joystick()
    await common.stop(conn)

    peak = max(fwd, back)
    walked = peak > WALKED
    print(f"    최고 속도 {peak:.3f} m/s  (앞 {fwd:.3f} / 뒤 {back:.3f})  →  "
          f"{'★ 걸었습니다 ★' if walked else '몸통만 움직였습니다'}")
    await asyncio.sleep(1.0)
    return (label, peak, walked)


async def find_walk_mode(conn, probe):
    print("\n" + "=" * 66)
    print(" 걷기 모드 찾기")
    print("=" * 66)
    print(f" 각 시도: 앞으로 {PUSH}초, 뒤로 {PUSH}초 (스틱 {STICK})")
    print(f" 실제 속도가 {WALKED} m/s 를 넘으면 '걸었다'로 봅니다.\n")

    async def p_balance():
        return {"BalanceStand": await send("BalanceStand")}

    async def p_move_once():
        # ★ 가장 유력한 후보 ★
        # Move 로 걷기 모드에 들어간 뒤, 조이스틱이 이어받는지 봅니다.
        c = await send("Move", {"x": 0.2, "y": 0.0, "z": 0.0})
        return {"Move": c}

    async def p_move_burst():
        # Move 를 여러 번 연속으로 (한 번으로는 모드가 안 바뀔 수도 있어서)
        codes = []
        for _ in range(5):
            codes.append(await send("Move", {"x": 0.2, "y": 0.0, "z": 0.0}))
            await asyncio.sleep(0.15)
        return {"Move x5": codes[0]}

    async def p_stopmove():
        return {"StopMove": await send("StopMove")}

    async def p_continuous():
        return {"ContinuousGait": await send("ContinuousGait", {"data": True})}

    async def p_classic():
        return {"ClassicWalk": await send("ClassicWalk", {"data": True})}

    async def p_static():
        return {"StaticWalk": await send("StaticWalk", {"data": True})}

    async def p_economic():
        return {"EconomicGait": await send("EconomicGait", {"data": True})}

    async def p_speedlevel():
        return {"SpeedLevel": await send("SpeedLevel", {"data": 0})}

    trials = [
        ("1. BalanceStand 만 (지금까지의 방식)", p_balance),
        ("2. Move 를 한 번 보낸 뒤 조이스틱  ← 유력", p_move_once),
        ("3. Move 를 다섯 번 연속으로 보낸 뒤", p_move_burst),
        ("4. StopMove 뒤에", p_stopmove),
        ("5. ContinuousGait 켜고", p_continuous),
        ("6. ClassicWalk 켜고", p_classic),
        ("7. StaticWalk 켜고", p_static),
        ("8. EconomicGait 켜고", p_economic),
        ("9. SpeedLevel 지정 뒤", p_speedlevel),
    ]

    results = []
    for label, prep in trials:
        results.append(await trial(probe, label, prep))

    print("\n" + "=" * 66)
    print(" 정리")
    print("=" * 66)
    for label, peak, walked in results:
        mark = "★ 걸음" if walked else "  기울기만"
        print(f" {mark}  {peak:>7.3f} m/s   {label}")

    good = [r for r in results if r[2]]
    print()
    if good:
        best = max(good, key=lambda r: r[1])
        print(f" → '{best[0]}' 이 통했습니다 ({best[1]:.3f} m/s).")
        print("   이 준비를 common.ensure_locomotion() 에 넣으면 됩니다.")
    else:
        print(" → 어떤 방법으로도 걷지 않았습니다.")
        print("   조이스틱은 닿는데(몸통이 반응) 걷기 모드로 못 들어간 것입니다.")
        print("   위의 응답 코드에서 0 이 아닌 값이 있으면 알려주세요.")
    return results


async def look_at_state(conn, probe):
    """상태 메시지에 무엇이 들어 있는지 통째로 봅니다."""
    print("\n" + "=" * 66)
    print(" 상태 메시지에 뭐가 들어 있나")
    print("=" * 66)
    await probe.read()
    if probe.fields is None:
        print(" 상태 메시지를 받지 못했습니다.")
        return
    print(f" 항목: {probe.fields}\n")
    for key in probe.fields:
        value = probe.raw.get(key)
        text = repr(value)
        if len(text) > 70:
            text = text[:70] + " ..."
        print(f"   {key:22} {text}")
    print("\n ※ mode 가 자세를 바꿔도 계속 0 이면, 그 항목은 쓰지 않습니다.")


async def main():
    global conn

    print("=" * 66)
    print(" 걷기 모드 찾기 실험  ★ 로봇이 움직입니다 ★")
    print("=" * 66)
    print(__doc__.split("실행 전 체크리스트")[0])

    if not await common.confirm(
        "앞뒤로 2m 가 비어 있고, 리모컨을 든 사람이 대기 중입니까?"
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


async def run(conn):
    # 조이스틱 입력은 켜 둡니다 (이건 이미 확인된 사항)
    await common.prepare_motion(conn)
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    probe = common.StateProbe(conn)
    await probe.read()

    await look_at_state(conn, probe)

    print("\n[준비] 일어섭니다")
    await common.stand_and_wait(conn, probe=probe)
    print(f"[준비] {probe.describe()}")

    await find_walk_mode(conn, probe)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
        print("로봇이 멈추지 않으면 리모컨의 P 버튼을 두 번 누르세요.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
