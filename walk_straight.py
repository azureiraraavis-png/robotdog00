# -*- coding: utf-8 -*-
"""제 방향을 보면서 고쳐가며 곧게 걷습니다.  ★ 로봇이 걷습니다 ★

  ★ 왜 고정값으로는 안 되는가 ★

    2026-09-14, drift_test 로 여덟 판을 쟀습니다.

        되잡기 없음   도는 각 +1.9 ~ +5.4 도/m   (가운데 +3.7)
        -0.012 고정   도는 각 +3.1 · +0.1 · -1.2 (가운데 +0.7)

    평균은 잘 맞췄습니다. 그런데 **낱판이 흔들리는 폭이 버릇만큼 큽니다** —
    +3.1 에서 -1.2 까지 4.3도/m 범위입니다. 고정값은 평균만 맞출 수 있고,
    계단에서 중요한 것은 평균이 아니라 **지금 이 판**입니다.

    그리고 회전을 0 으로 만들어도 옆으로 미끄러지는 몫(+1.5~+5.6 cm/m)은
    그대로 남았습니다. 돌아서 밀리는 게 아니라는 뜻입니다.

    그래서 더 좋은 상수를 찾는 대신, **보면서 고치기**로 갑니다.

  ★ 어떻게 고치는가 ★

    두 겹입니다.

      1. 출발선에서 옆으로 벗어난 만큼, **되돌아올 방향을 겨눕니다**
         (10cm 왼쪽으로 밀렸으면 조금 오른쪽을 봅니다)
      2. 겨눈 방향과 실제 방향의 차이만큼 **회전을 줍니다**

    첫째가 미끄러짐을, 둘째가 도는 버릇을 잡습니다. 회전만 잡으면
    미끄러진 채로 나란히 갑니다 — 벗어난 자리가 안 돌아옵니다.

  ★ 안전 ★

    · config.MAX_FORWARD_STICK · MAX_MOVE_DURATION 한도를 그대로 씁니다
    · 되잡는 회전은 ±0.12 로 묶습니다 (조금씩만 고칩니다)
    · 끝나면 반드시 멈춥니다

  ★ 1 m 로는 크게 안 좋아집니다 ★

    흉내로 셈해보면, 0.93 m 를 걸을 때 —

        되잡기 없음   끝 옆으로 +5.0 cm · 끝 각 +3.4도
        kp 0.4        끝 옆으로 +3.9 cm · 끝 각 -0.7도

    **각도는 확 좋아지고 옆으로는 조금**입니다. 되돌아올 거리가 짧으니
    당연합니다. 이 되잡기의 값어치는 긴 거리에서 나옵니다 — 계단 한 층
    3 m 를 갈 때 각이 안 쌓이는 것이 핵심이고, 그게 없으면 위에서
    12도 틀어진 채 다음 계단을 밟습니다.

    지금은 config.MAX_MOVE_DURATION 이 3초라 1 m 밖에 못 갑니다. 더 긴
    시험은 그 한도와 **트인 자리**가 함께 있어야 합니다.

  쓰는 법

      .\\run walk_straight.py                 3초 곧게
      .\\run walk_straight.py --seconds 3 --stick 0.3
      .\\run walk_straight.py --kp 1.5        더 세게 되잡기
      .\\run walk_straight.py --plain         되잡기 없이 (견주기용)

  ★ 실행 전 체크리스트 ★
      □ 앞으로 **3 m 이상** 트인 평평한 바닥
      □ 리모컨 손에 (P 두 번 = 힘 빼기)
      □ 사람이 옆에 (공용 기체입니다)
"""

import argparse
import asyncio
import math
import time

import common
import config
import drift_test          # measure · report · log_run 을 그대로 씁니다

# 되잡는 회전의 한도. 0.15 는 초당 14도라 너무 급합니다 — 10cm 벗어난
# 것만으로 한도에 붙고, 그러면 홱 꺾였다가 반대로 넘어가며 갈지자가 됩니다.
MAX_TURN_STICK = 0.12
MAX_AIM_DEG = 20.0        # 되돌아올 때 겨누는 각의 한도


def wrap(rad):
    return (rad + math.pi) % (2 * math.pi) - math.pi


def steer(cross, heading_err, kp, k_ct):
    """되잡을 회전 스틱을 셈합니다.

    cross        출발선에서 옆으로 벗어난 거리 (m, 왼쪽이 +)
    heading_err  겨눈 방향과 실제 방향의 차이 (rad, 왼쪽이 +)

    돌려주는 것: (회전 스틱, 겨눈 각도 rad)
    """
    aim = -k_ct * cross                                   # 벗어난 반대쪽을 겨눔
    cap = math.radians(MAX_AIM_DEG)
    aim = max(-cap, min(cap, aim))
    err = wrap(heading_err - aim)
    z = -kp * err                                         # 왼쪽으로 틀었으면 오른쪽으로
    return max(-MAX_TURN_STICK, min(MAX_TURN_STICK, z)), aim


async def main():
    ap = argparse.ArgumentParser(description="보면서 고쳐가며 곧게 걷습니다")
    ap.add_argument("--seconds", type=float, default=3.0)
    ap.add_argument("--stick", type=float, default=0.3)
    # kp 0.4 의 근거: 10도쯤 틀어진 것을 0.5 m 가는 동안(약 1.6초) 되잡으려면
    #   초당 6도 = 0.1 rad/s 가 필요하고, 스틱으로는 0.1/1.63 ≈ 0.065 입니다.
    #   0.17 rad 오차에 0.065 를 내려면 kp ≈ 0.4.
    #   ※ 이 값은 아직 **로봇에서 안 맞춰봤습니다.** 갈지자를 그리면 낮추고,
    #     굼뜨면 올리세요.
    ap.add_argument("--kp", type=float, default=0.4,
                    help="방향 차이를 회전으로 바꾸는 세기 (갈지자면 낮추세요)")
    ap.add_argument("--ct", type=float, default=1.7,
                    help="옆으로 벗어난 것을 겨눔으로 바꾸는 세기 (rad/m)")
    ap.add_argument("--plain", action="store_true",
                    help="되잡지 않습니다 (견주기용)")
    args = ap.parse_args()

    print("=" * 70)
    print(" 보면서 고쳐가며 곧게 걷기")
    print("=" * 70)
    print(" ★ 로봇이 걷습니다 ★")
    print(f"   {args.seconds:.0f}초 · 스틱 {args.stick:.1f}"
          f"{'  (되잡기 끔)' if args.plain else f'  kp={args.kp} ct={args.ct}'}")
    print("   □ 3 m 이상 트여 있습니까   □ 리모컨 손에 있습니까")
    print()
    if not await common.confirm("시작할까요?"):
        print(" 그만둡니다.")
        return 0

    conn = await common.connect()
    if conn is None:
        print(" ✖ 못 붙었습니다.")
        return 1

    try:
        await common.prepare_motion(conn)
        probe = common.StateProbe(conn)
        await asyncio.sleep(0.6)
        if not await common.ensure_standing(conn, probe):
            print(" ✖ 세우지 못했습니다.")
            return 1

        track = drift_test.Track(conn)
        await asyncio.sleep(0.8)
        if not track.rows:
            print(" ✖ robot_pose 가 안 옵니다. 잴 수 없습니다.")
            return 1

        start = len(track.rows)
        _t, x0, y0, yaw0 = track.rows[-1]
        c0, s0 = math.cos(yaw0), math.sin(yaw0)

        x = max(-config.MAX_FORWARD_STICK,
                min(config.MAX_FORWARD_STICK, args.stick))
        seconds = min(args.seconds, config.MAX_MOVE_DURATION)
        if seconds < args.seconds:
            print(f" ※ {args.seconds:.1f}초를 {seconds:.1f}초로 자릅니다 "
                  "(config.MAX_MOVE_DURATION)")

        print(" 걷습니다…")
        worst_cross = 0.0
        worst_err = 0.0
        used = []
        deadline = time.time() + seconds
        try:
            while time.time() < deadline:
                _t, px, py, yaw = track.rows[-1]
                # 출발선 기준으로 얼마나 벗어났나
                dx, dy = px - x0, py - y0
                cross = -dx * s0 + dy * c0
                if args.plain:
                    z, aim = 0.0, 0.0
                else:
                    z, aim = steer(cross, wrap(yaw - yaw0), args.kp, args.ct)
                used.append(z)
                worst_cross = max(worst_cross, abs(cross))
                worst_err = max(worst_err, abs(math.degrees(wrap(yaw - yaw0))))
                common.joystick(conn, **common.stick_from_intent(x, 0.0, z))
                await asyncio.sleep(0.02)          # 50Hz
        finally:
            for _ in range(5):
                common.joystick(conn, 0.0, 0.0, 0.0)
                await asyncio.sleep(0.02)
            await common.stop(conn)

        await asyncio.sleep(0.8)
        print()
        got = drift_test.measure(track.rows[start:])
        drift_test.report(got, "되잡기 끔" if args.plain else "보면서 고침")
        if got:
            n = drift_test.log_run(got, args.stick, False,
                                   0.0 if args.plain else "스스로")
            print(f"   ({drift_test.LOG} 에 적었습니다 — 모두 {n}판)")
        print()
        if used:
            print(" 걷는 동안")
            print(f"   회전을 준 범위   {min(used):+.3f} ~ {max(used):+.3f}"
                  f"  (한도 ±{MAX_TURN_STICK})")
            print(f"   가장 벗어난 거리 {worst_cross*100:.1f} cm")
            print(f"   가장 틀어진 각   {worst_err:.1f} 도")
            if max(abs(min(used)), abs(max(used))) >= MAX_TURN_STICK - 1e-6:
                print("   ※ 한도에 붙었습니다 — 되잡기가 모자랍니다.")
                print("     --kp 를 올리거나 MAX_TURN_STICK 을 키워야 합니다.")
        print()
        print(" 견주는 법: .\\run walk_straight.py --plain 을 몇 판 돌려")
        print("   같은 자리·같은 조건에서 '돌아감' 과 '옆으로' 를 나란히 보세요.")
        return 0
    finally:
        try:
            await common.stop(conn)
        except Exception:
            pass
        await common.disconnect(conn)


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
