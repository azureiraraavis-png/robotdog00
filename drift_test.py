# -*- coding: utf-8 -*-
"""곧게 걸으라고 시키고, 얼마나 휘는지 로봇에게 물어봅니다.
   ★ 로봇이 걷습니다 ★

  ★ 왜 이걸 재는가 ★

    사이안 님이 눈으로 보셨습니다 — "직진할 때 살짝 옆으로 휩니다."
    복도에서는 조종이 조금 불편한 정도입니다. 그런데 계단에서는
    **옆으로 휘면 난간 너머**입니다. 8층 정찰견 이야기가 나온 순간
    이 값은 취미에서 선결 과제가 됐습니다.

  ★ 줄자가 없어도 됩니다 ★

    로봇이 rt/utlidar/robot_pose 로 제 자리를 초당 18.8번 말해줍니다.
    앞으로만 가라고 시킨 뒤, **처음 바라보던 방향을 기준으로** 옆으로
    얼마나 밀렸는지 읽으면 그게 휜 양입니다. 벽도 복도도 필요 없습니다.

    ※ 주행 거리계도 완벽하지는 않습니다. 다만 몇 미터 안에서는 우리가
      쫓는 크기(수십 cm)보다 훨씬 작습니다. 그리고 **양쪽 방향으로 재면**
      바닥이 기운 것과 로봇이 휘는 것이 갈립니다 —
        · 로봇이 휘는 것: 어느 방향으로 가도 **같은 쪽**으로 휩니다
        · 바닥이 기운 것: 방향을 바꾸면 **반대쪽**으로 휩니다

  ★ 두 가지가 따로 나옵니다 ★

      옆으로 밀림   1 m 갈 때 몇 cm 옆으로 갔나
      몸이 돌아감   1 m 갈 때 몇 도 돌아갔나

    이 둘은 다릅니다. 게처럼 옆으로 밀리는 것과, 몸이 조금씩 돌아가며
    호를 그리는 것은 고치는 방법도 다릅니다.

  쓰는 법

      .\\run drift_test.py                 3초 앞으로 (약 1.2 m)
      .\\run drift_test.py --seconds 5     더 멀리
      .\\run drift_test.py --stick 0.2     더 천천히
      .\\run drift_test.py --back          뒤로 걸어서 (바닥 기울기 가리기)

  ★ 실행 전 체크리스트 ★
      □ 앞으로 **3 m 이상** 트인 평평한 바닥
      □ 리모컨 손에 (P 두 번 = 힘 빼기)
      □ 사람이 옆에 (공용 기체입니다)
      □ 로봇이 서 있고, 가고 싶은 쪽을 보고 있을 것
"""

import argparse
import asyncio
import math
import time

import common


class Track:
    """걷는 동안 자리를 계속 적어둡니다."""

    def __init__(self, conn):
        self.rows = []            # (시각, x, y, yaw)
        from unitree_webrtc_connect.constants import RTC_TOPIC
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC["ROBOTODOM"], self._on)

    def _on(self, message):
        try:
            p = message["data"]["pose"]
            q = p["orientation"]
            yaw = math.atan2(2 * (q["w"] * q["z"] + q["x"] * q["y"]),
                             1 - 2 * (q["y"] ** 2 + q["z"] ** 2))
            self.rows.append((time.monotonic(),
                              float(p["position"]["x"]),
                              float(p["position"]["y"]),
                              yaw))
        except Exception:
            pass


def measure(rows):
    """걸은 자취에서 '앞으로 간 거리' 와 '옆으로 밀린 거리' 를 뽑습니다.

    ★ 기준은 **출발할 때 바라보던 방향**입니다 ★
      도착했을 때의 방향으로 재면, 몸이 돌아간 만큼 옆으로 밀린 것이
      가려집니다. 휘어짐을 재려는데 휘어진 자로 재는 꼴입니다.
    """
    if len(rows) < 5:
        return None
    t0, x0, y0, yaw0 = rows[0]
    t1, x1, y1, yaw1 = rows[-1]
    facing = math.degrees(yaw0)
    dx, dy = x1 - x0, y1 - y0
    c, s = math.cos(yaw0), math.sin(yaw0)
    ahead = dx * c + dy * s
    side = -dx * s + dy * c
    turned = math.degrees((yaw1 - yaw0 + math.pi) % (2 * math.pi) - math.pi)
    return {
        "간 거리": ahead,
        "옆으로": side,
        "돌아감": turned,
        "걸린 시간": t1 - t0,
        "표본": len(rows),
        "출발 방향": facing,
    }


def report(got, label):
    print(f" [{label}]")
    if got is None:
        print("   ✖ 자리 정보가 너무 적습니다 (robot_pose 가 안 왔습니다)")
        return None
    d = got["간 거리"]
    # ★ 어느 쪽을 보고 걸었는지 반드시 적습니다 ★
    #
    #   2026-09-14 에 일곱 판을 모아놓고도 "로봇을 돌려놓고 한 것인지" 를
    #   알 수 없었습니다. 출력에는 '앞으로' 라고만 찍혔는데, 그건 명령이
    #   전진이라는 뜻이지 **로봇이 어느 쪽을 봤는지가 아닙니다.**
    #
    #   실험은 조건을 적어야 실험입니다. 자세를 안 적어서 라이다에서
    #   헤맨 것과 같은 실수를 하루에 두 번 했습니다.
    #
    #   odom 의 방향은 로봇 전원을 껐다 켜면 다시 0 이 됩니다. 그러니
    #   **같은 전원 주기 안에서만** 판끼리 견줄 수 있습니다.
    print(f"   출발할 때 본 방향  {got['출발 방향']:+.0f} 도 (odom 기준)")
    print(f"   앞으로 간 거리   {d:+.3f} m   ({got['걸린 시간']:.1f}초 · "
          f"표본 {got['표본']}개)")
    print(f"   옆으로 밀린 양   {got['옆으로']*100:+.1f} cm")
    print(f"   몸이 돌아간 각   {got['돌아감']:+.1f} 도")
    if abs(d) < 0.15:
        print("   ※ 거의 안 움직였습니다. 아래 비율은 뜻이 없습니다.")
        return None
    per_side = got["옆으로"] / abs(d) * 100
    per_turn = got["돌아감"] / abs(d)
    print(f"   → 1 m 갈 때  옆으로 {per_side:+.1f} cm · {per_turn:+.1f} 도")
    where = "왼" if per_side > 0 else "오른"
    print(f"   → {abs(per_side):.0f} cm/m 씩 {where}쪽으로 휩니다")

    # ── 휘어짐을 두 겹으로 가릅니다 ──────────────────────────
    #
    #   ★ 이 둘은 고치는 방법이 다릅니다 ★
    #
    #     몸이 돌아가면 경로가 호를 그리니 저절로 옆으로 밀립니다.
    #     같은 방향으로 도는 것만큼은 '게걸음' 이 아닙니다. 그 몫을 빼야
    #     **진짜 옆으로 미끄러지는 양**이 보입니다.
    #
    #     일정한 속도로 도는 경우, 호로 밀리는 거리는 대략
    #         거리 × 라디안 ÷ 2
    #     입니다 (작은 각도에서).
    #
    #   2026-09-14 실제로 세 번 재보니, 도는 각은 1.1~5.4도로 널뛰는데
    #   빼고 남는 것은 2.1~2.4 cm 로 붙박였습니다. 두 겹이 맞습니다.
    from_turn = abs(d) * math.radians(got["돌아감"]) / 2 * 100
    crab = got["옆으로"] * 100 - from_turn
    print()
    print(f"   두 겹으로 가르면 (1 m 기준)")
    print(f"     · 돌아서 밀린 몫   {from_turn / abs(d):+.1f} cm  "
          f"(몸이 {per_turn:+.1f}도/m 로 돌기 때문)")
    print(f"     · 미끄러진 몫     {crab / abs(d):+.1f} cm  "
          f"(방향과 무관하게 옆으로)")
    return per_side, per_turn


LOG = "drift_log.json"

# 두 무리가 이만큼은 떨어져야 '반대 방향' 으로 칩니다.
#   ★ 안내문과 코드가 다르면 안 됩니다 ★
#     여기 120 을 쓰면서 안내문에는 "150도쯤" 이라고 적어뒀었습니다.
#     148도가 조용히 통과했고, 읽는 사람은 150을 넘은 줄 알았습니다.
#     숫자는 한 군데만 적고 그 이름을 씁니다.
APART_LEAST = 120


def log_run(got, stick, back, yaw=0.0):
    """한 판을 파일에 적어둡니다. 눈으로 세지 않으려고.

    battery_log.json 과 같은 생각입니다 — 값이 흩어질 때는 판을 모아야
    하고, 모으려면 적어야 합니다. 화면에 스쳐 지나간 숫자는 못 모읍니다.
    """
    import json
    from pathlib import Path
    path = Path(__file__).parent / LOG
    rows = []
    if path.exists():
        try:
            rows = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            rows = []
    d = abs(got["간 거리"])
    if d < 0.15:
        return len(rows)
    rows.append({
        "언제": time.strftime("%Y-%m-%d %H:%M:%S"),
        "출발 방향": round(got["출발 방향"], 1),
        "간 거리": round(got["간 거리"], 3),
        "옆으로 cm/m": round(got["옆으로"] / d * 100, 2),
        "돌아감 도/m": round(got["돌아감"] / d, 2),
        "스틱": stick,
        "되잡기": yaw,
        "뒤로": bool(back),
    })
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return len(rows)


def summary():
    """쌓인 판들을 **바라본 방향끼리 묶어서** 봅니다.

    ★ 이것 하나를 보려고 적습니다 ★
      로봇이 휘는 것인지 바닥이 기운 것인지는, 서로 반대쪽을 보고 걸은
      두 무리를 견줘야만 갈립니다.
        · 두 무리가 **같은 쪽**으로 휜다 → 로봇입니다
        · **반대쪽**이면            → 바닥입니다
    """
    import json
    from pathlib import Path
    path = Path(__file__).parent / LOG
    if not path.exists():
        print(f" {LOG} 가 없습니다. 먼저 몇 판 돌리세요.")
        return 1
    everything = json.loads(path.read_text(encoding="utf-8"))
    if not everything:
        print(" 적힌 판이 없습니다.")
        return 1

    # ★ 되잡은 판은 판정에서 뺍니다 ★
    #   --yaw 로 밀어준 판은 '로봇이 안 휜다' 가 아니라 '우리가 밀었다'
    #   입니다. 섞어놓고 "안 휩니다" 라고 하면 그건 거짓말입니다.
    rows = [r for r in everything if not r.get("되잡기")]
    fixed = [r for r in everything if r.get("되잡기")]
    if not rows:
        print(f" 되잡지 않은 판이 없습니다 (되잡은 판만 {len(fixed)}개).")
        print(" 판정하려면 --yaw 없이 몇 판 필요합니다.")
        return 1

    # 바라본 방향을 45도 안쪽끼리 한 무리로 묶습니다
    groups = []
    for r in rows:
        f = r["출발 방향"]
        for g in groups:
            gap = abs((f - g["방향"] + 180) % 360 - 180)
            if gap <= 45:
                g["판"].append(r)
                break
        else:
            groups.append({"방향": f, "판": [r]})

    print("=" * 70)
    print(f" 쌓인 판 {len(rows)}개 · 방향 {len(groups)}무리"
          + (f"   (되잡은 판 {len(fixed)}개는 뺐습니다)" if fixed else ""))
    print("=" * 70)
    for g in sorted(groups, key=lambda g: g["방향"]):
        turns = [r["돌아감 도/m"] for r in g["판"]]
        sides = [r["옆으로 cm/m"] for r in g["판"]]
        mid_t = sorted(turns)[len(turns) // 2]
        mid_s = sorted(sides)[len(sides) // 2]
        print(f" {g['방향']:+7.0f}도 쪽  판 {len(g['판'])}개   "
              f"돌아감 {mid_t:+.1f} 도/m · 옆으로 {mid_s:+.1f} cm/m")
        print(f"           (돌아감 낱값: {', '.join(f'{t:+.1f}' for t in turns)})")
    print()

    if len(groups) < 2:
        print(" ✖ 아직 한 방향으로만 걸었습니다.")
        print("   로봇이 휘는 것인지 바닥이 기운 것인지 **가릴 수 없습니다.**")
        print("   로봇을 180도 돌려놓고 몇 판 더 돌리세요.")
        return 0

    if fixed:
        print(" [되잡아본 판들 — 밀어준 결과입니다]")
        for r in fixed[-6:]:
            how = r["되잡기"]
            how = f"{how:+.3f}" if isinstance(how, (int, float)) else str(how)
            print(f"   되잡기 {how:>7} → 돌아감 {r['돌아감 도/m']:+.1f} 도/m"
                  f" · 옆으로 {r['옆으로 cm/m']:+.1f} cm/m")
        print("   ※ 0 에 가장 가까운 값이 지금 로봇에 맞는 되잡기입니다.")
        print()

    # ★ '가장 큰 둘' 이 아니라 '가장 마주보는 둘' 을 고릅니다 ★
    #
    #   처음에는 판이 많은 두 무리를 골랐습니다. 그런데 2026-09-14 에
    #   무리가 셋(-44° · +104° · +154°)이 되자, 판 수가 같은 뒤의 둘을
    #   골라서 **50도 떨어진 짝**을 보고 "아직 반대쪽이 아닙니다" 라고
    #   했습니다. -44° 와 +154° 는 162도로 딱 좋은 짝인데요.
    #
    #   이 판정이 알고 싶은 것은 '많이 걸은 방향' 이 아니라 **'서로
    #   반대쪽을 본 두 무리'** 입니다. 그러니 그걸로 골라야 합니다.
    pairs = []
    for i, g1 in enumerate(groups):
        for g2 in groups[i + 1:]:
            apart = abs((g1["방향"] - g2["방향"] + 180) % 360 - 180)
            pairs.append((apart, len(g1["판"]) + len(g2["판"]), g1, g2))
    pairs.sort(key=lambda pr: (-pr[0], -pr[1]))
    gap, _n, a, b = pairs[0]
    if len(groups) > 2:
        print(f" (무리가 {len(groups)}개라, 가장 마주보는 둘을 골랐습니다 — "
              f"{a['방향']:+.0f}도 쪽과 {b['방향']:+.0f}도 쪽)")
    ta = sorted(r["돌아감 도/m"] for r in a["판"])[len(a["판"]) // 2]
    tb = sorted(r["돌아감 도/m"] for r in b["판"])[len(b["판"]) // 2]
    print(f" 두 무리가 {gap:.0f}도 떨어져 있습니다.")
    if gap < APART_LEAST:
        print(f" ※ 아직 서로 반대쪽이 아닙니다 ({APART_LEAST}도는 되어야 합니다).")
        print("   더 돌려놓고 몇 판 더 하세요.")
        return 0
    if gap < 165:
        print(f" ※ 180도가 아니라 {gap:.0f}도입니다. 바닥 기울기가 완전히")
        print("   뒤집히지 않아서, 아래 판정이 조금 무뎌집니다.")
    if (ta > 0) == (tb > 0):
        print(f" → 어느 쪽을 보고 걸어도 **같은 쪽**으로 돕니다 "
              f"({ta:+.1f} · {tb:+.1f})")
        print("   **로봇이 휩니다.** 걸음에 든 버릇이고, 고칠 대상입니다.")
        print()
        bias = (ta + tb) / 2
        print(f" 되잡아 볼 값 (도는 버릇 {bias:+.1f} 도/m 를 없애려면)")
        for stick in (0.2, 0.3, 0.4):
            speed = stick * 1.05                       # common.stick_to_speed
            need = math.radians(bias) * speed / 1.63   # common.stick_to_yaw_rate
            print(f"   전진 스틱 {stick:.1f} 일 때  →  회전 스틱 {-need:+.3f}")
        print(f"   .\\run drift_test.py --yaw {-math.radians(bias)*0.3*1.05/1.63:+.3f}")
        print("   ※ 아주 작은 값이라 로봇이 무시할 수도 있습니다.")
        print("     그러면 조금씩 키우면서 '돌아감' 이 0 에 가까워지는 값을 찾으세요.")
    else:
        print(f" → 방향을 바꾸니 **반대쪽**으로 돕니다 ({ta:+.1f} · {tb:+.1f})")
        print("   **바닥이 기울어 있습니다.** 로봇은 멀쩡합니다.")
        print("   다른 층·다른 복도에서도 재보면 확실해집니다.")
    return 0


async def main():
    ap = argparse.ArgumentParser(description="곧게 걷는지 잽니다")
    ap.add_argument("--seconds", type=float, default=3.0, help="몇 초 걸을지")
    ap.add_argument("--stick", type=float, default=0.3, help="스틱 세기 (0~1)")
    ap.add_argument("--back", action="store_true", help="뒤로 걷습니다")
    ap.add_argument("--yaw", type=float, default=0.0,
                    help="걸으면서 이만큼 돌립니다 (- 가 오른쪽). 휘는 버릇을 되잡을 때")
    ap.add_argument("--summary", action="store_true",
                    help="쌓인 판들을 방향끼리 묶어서 봅니다 (로봇은 안 움직입니다)")
    args = ap.parse_args()

    if args.summary:
        return summary()

    print("=" * 70)
    print(" 곧게 걷는가 — 로봇에게 물어봅니다")
    print("=" * 70)
    print(" ★ 로봇이 걷습니다 ★")
    print(f"   앞으로 {args.seconds:.0f}초 · 스틱 {args.stick:.1f}"
          f"{' (뒤로)' if args.back else ''}")
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

        track = Track(conn)
        await asyncio.sleep(0.8)          # 자리 정보가 몇 개 쌓이게
        if not track.rows:
            print(" ✖ robot_pose 가 안 옵니다. 잴 수 없습니다.")
            return 1

        start = len(track.rows)
        print(" 걷습니다…")
        x = -args.stick if args.back else args.stick
        # ★ 옆도 회전도 0 입니다 ★ 곧게 가라는 것만 시키고, 나머지는 봅니다.
        # ★ --yaw 는 '고쳐진 척' 이 아니라 '고쳐봄' 입니다 ★
        #   여기에 값을 넣으면 로봇이 덜 휩니다. 그런데 그건 **걸음이
        #   고쳐진 것이 아니라 우리가 밀어준 것**입니다. 로그에 같이
        #   적어두지 않으면, 나중에 이 판들을 보고 "어? 안 휘는데?" 가
        #   됩니다.
        await common.move(conn, x=x, y=0.0, z=args.yaw, duration=args.seconds)
        await common.stop(conn)
        await asyncio.sleep(0.8)          # 멈춘 뒤 자리가 잡히게
        print()

        got = measure(track.rows[start:])
        report(got, "뒤로" if args.back else "앞으로")
        if got:
            n = log_run(got, args.stick, args.back, args.yaw)
            print(f"   ({LOG} 에 적었습니다 — 모두 {n}판)")
        print()
        print(" 다음에 할 것")
        print("   1. 로봇을 **반대 방향으로 돌려놓고** 한 번 더 돌리세요.")
        print("      · 같은 쪽으로 휘면  → **로봇이** 휩니다 (고칠 대상)")
        print("      · 반대쪽으로 휘면  → **바닥이** 기울어 있습니다")
        print("   2. 몇 번 돌려서 값이 비슷한지 보세요. 한 번은 우연입니다.")
        print("   3. .\\run drift_test.py --summary  로 모아서 보세요.")
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
