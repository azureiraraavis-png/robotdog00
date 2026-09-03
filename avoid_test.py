# -*- coding: utf-8 -*-
"""
장애물 회피 확인 — 이 건물의 복도에서.  ★ 로봇이 조금 움직입니다 ★

  어제와 달라진 점
    처음 이 실험을 짤 때는 "넓은 곳에서 하세요" 라고 썼습니다.
    그런데 이 건물에는 넓은 곳이 없습니다. 복도가 전부입니다.
    그래서 **복도에서 안전하게 할 수 있도록** 다시 짰습니다.

  이 건물의 실측 조건
    · 통로 폭이 로봇 높이에서 **1.15 m** (벽 높이에서는 3.13 m)
      → 로봇 몸통 0.31 m 를 빼면 양옆 여유가 각 0.42 m 뿐입니다
    · 바닥이 거울처럼 반사 — 라이다 점의 53% 가 유령 (높이로 걸러집니다)
    · 유리문이 있습니다 — ★ 라이다에 안 보입니다 ★

  ★ 가장 중요한 설계 ★
    시험 대상(로봇의 회피)이 안전장치를 겸하면 안 됩니다. 그건 시험이 아닙니다.
    그래서 **우리가 라이다로 따로 지켜보다가 먼저 멈춥니다.**

        로봇이 우리보다 먼저 멈추면  →  회피가 동작하는 것
        우리가 먼저 멈추면          →  회피가 없거나 늦은 것

    어느 쪽이든 로봇은 장애물에 닿지 않습니다.

  그리고 좁은 복도라 하나 더 중요합니다.
    폭 1.15 m 에서는 **옆으로 비켜갈 수 없습니다.** 회피가 '멈추기' 가 아니라
    '돌아가기' 로 동작한다면 로봇은 의자나 사물함으로 들어갑니다.
    그래서 회전과 옆미끄러짐도 같이 재서, **어떻게** 피하는지 봅니다.

    .\\run avoid_test.py

  ★ 실행 순서 ★
    1. 장애물을 **치운 채로** 시작합니다 (대조군 B 가 빈 복도를 걷습니다)
    2. B 가 끝나면 스크립트가 "상자를 놓으세요" 라고 안내합니다
    3. 그때 로봇 앞 약 2 m 에 놓습니다

    상자를 미리 놓아두면 출발 자리 확인에서 걸립니다. 그때는 치우고
    다시 재면 됩니다 — 스크립트가 기다려 줍니다.

  준비물
    □ 복도에서 앞으로 **4m 이상** 트인 구간
      (어제 사진 찍은 그 자리 — 지도 범위 밖으로 나올 만큼 트인 곳)
    □ 부드럽고 가벼운 장애물 — 빈 종이상자, 쿠션
      ★ 유리문·벽·사람 앞에서 하지 마세요 ★
    □ 리모컨 손에 (P 두 번 = 힘 빼기)
    □ 배터리 50% 이상

  먼저 .\\run look.py 로 그 자리가 어떻게 보이는지 확인하고 오세요.
"""

import asyncio
import math
import sys
import time

import common
import perception
import safety

conn = None

# ── 이 건물 기준으로 잡은 값들 ───────────────────────────────
STICK = 0.22          # 느리게. 약 0.36 m/s — 회피가 반응할 시간을 줍니다

# ★ 4.0 초로는 부족했습니다 ★
# 1차: 상자 1.80 m 앞에서 출발 → 4초 동안 0.83 m 만 가고 시간 만료.
#      상자까지 0.91 m 남은 채로 끝나서, '로봇이 멈추는가' 를 못 봤습니다.
#      대조군도 똑같이 시간 만료라 비교 자체가 성립하지 않았습니다.
# 8초면 예상 2.3 m — 상자 1.8 m 기준으로 우리 안전장치(0.9 m)에
# 4초쯤에 닿습니다. 그 전에 로봇이 서는지가 이 실험의 답입니다.
PUSH = 8.0

# ★ 출발이 느립니다 ★
# 1차 실측 (스틱 0.22, 4초):
#     0.0~0.5초  0.04 m      2.7~3.2초  0.13 m
#     0.5~1.1초  0.10 m      3.2~3.7초  0.11 m
# 처음 1.5초쯤은 자세를 잡느라 거의 안 갑니다. 그래서
#     거리 = 스틱 × STICK_TO_MPS × (시간 − RAMP)
# 로 보면 4초에 0.87 m 예상, 실측 0.82~0.83 m 로 맞습니다.
# (STICK_TO_MPS 자체는 틀리지 않았습니다 — 최고 속도 0.36 m/s 가
#  0.22 × 1.65 = 0.363 과 정확히 일치합니다. 빠진 건 출발 지연이었습니다)
RAMP_SECONDS = 1.6

# ★ 자기 몸 걸러내는 범위(앞뒤 0.55m)보다 커야 합니다 ★
# 처음에 0.70 으로 잡았더니, 걷는 중에 뻗은 앞발을 장애물로 보고
# 멈춘 것으로 의심되는 결과가 나왔습니다. 여유를 두어 올립니다.
GUARD_FRONT = 0.90    # 앞이 이보다 가까워지면 ★ 우리가 ★ 멈춥니다
GUARD_SIDE = 0.35     # 옆이 이보다 가까워지면 멈춥니다
GUARD_DRIFT = 10.0    # 방향이 이만큼 틀어지면 멈춥니다 (도)

STOPPED = 0.05        # 이 속도 아래면 멈춘 것으로 봅니다 (m/s)
STOP_HOLD = 0.5       # 이만큼 계속 느려야 '스스로 멈췄다' 로 인정

def predict_travel(seconds=PUSH):
    """이 설정으로 몇 m 나 갈지. 출발 지연을 뺀 값입니다."""
    return common.stick_to_speed(STICK) * max(0.0, seconds - RAMP_SECONDS)


# 출발 전에 앞이 이만큼은 트여 있어야 시작합니다 (m).
#
# ★ 값의 근거 ★
#   최대 이동 거리   predict_travel(8초) = 2.32 m
#   안전장치 정지    앞 0.90 m
#   합계             3.22 m  ← 이만큼은 '있어야 겨우 되는' 값입니다
#   여유를 더해 3.6 m 를 요구합니다.
NEED_FRONT = 3.6

# 지도 범위 밖이라 '앞에 아무것도 없음' 으로 나올 때 보여줄 값 (m)
MAP_RANGE_HINT = 4.0

# 마지막 이 시간 동안의 속도를 봅니다 — 로봇이 '느려졌는가' 판단용 (초)
TAIL_SECONDS = 1.5


class Result:
    def __init__(self):
        self.reason = "시간 만료"
        self.distance = 0.0
        self.seconds = 0.0
        self.peak_speed = 0.0
        self.peak_yaw = 0.0
        self.peak_side = 0.0
        self.front_at_stop = None
        self.trace = []          # (시각, 앞여유, 간거리, 속도) — 나중에 맞춰봅니다

    def self_stopped(self):
        return self.reason == "로봇이 스스로 멈춤"

    def guarded(self):
        return self.reason.startswith("우리가")

    def timed_out(self):
        return self.reason == "시간 만료"

    def tail_speed(self, window=TAIL_SECONDS):
        """마지막 window 초 동안의 평균 속도 (m/s). 자료가 모자라면 None.

        ★ 왜 필요한가 ★
        회피는 '완전히 멈추기' 말고 '느려지기' 로 나타날 수도 있습니다.
        완전히 서야만 인정하면 그 절반을 놓칩니다.
        """
        if len(self.trace) < 2:
            return None
        end = self.trace[-1]
        for t, _f, d, _v in self.trace:
            if end[0] - t <= window:
                span = end[0] - t
                return (end[2] - d) / span if span > 0.3 else None
        return None


async def approach(probe, eyes, seconds=PUSH):
    """앞으로 걸으면서, 로봇과 우리 중 누가 먼저 멈추는지 봅니다."""
    r = Result()
    drift = 0.0
    slow_since = None
    start = last = time.time()
    deadline = start + seconds

    while time.time() < deadline:
        common.joystick(conn, **common.stick_from_intent(x=STICK))
        await asyncio.sleep(0.02)

        now = time.time()
        dt, last = now - last, now
        r.seconds = now - start

        # ── 로봇이 실제로 어떻게 움직이는가 ──
        v = probe.velocity
        if v:
            r.distance += abs(v[0]) * dt
            r.peak_speed = max(r.peak_speed, abs(v[0]))
            r.peak_side = max(r.peak_side, abs(v[1]))
        if probe.yaw_speed is not None:
            drift += probe.yaw_speed * dt
            r.peak_yaw = max(r.peak_yaw, abs(probe.yaw_speed))

        # ── 우리 눈으로 본 안전 판단 (독립적) ──
        c = eyes.clearance()
        r.front_at_stop = c.front

        # ★ 기록해 둡니다 ★
        # '앞 여유가 줄어든 양' 과 '실제로 간 거리' 가 맞아야 정상입니다.
        # 안 맞으면 우리가 보는 것이 장애물이 아니거나(자기 발),
        # 자세가 늦게 따라오는 것입니다. 둘 다 실제로 의심됐습니다.
        if not r.trace or r.seconds - r.trace[-1][0] >= 0.25:
            r.trace.append((r.seconds, c.front, r.distance,
                            abs(v[0]) if v else 0.0))
        if c.fresh():
            if c.front is not None and c.front < GUARD_FRONT:
                r.reason = f"우리가 멈춤 — 앞 {c.front:.2f} m"
                break
            near = [d for d in (c.left, c.right) if d is not None]
            if near and min(near) < GUARD_SIDE:
                r.reason = f"우리가 멈춤 — 옆 {min(near):.2f} m"
                break

        if abs(math.degrees(drift)) > GUARD_DRIFT:
            r.reason = f"우리가 멈춤 — 방향 {math.degrees(drift):+.0f}도 틀어짐"
            break

        # ── 로봇이 스스로 섰는가 ──
        if now - start > 0.8:
            speed = abs(v[0]) if v else 0.0
            if speed < STOPPED:
                slow_since = slow_since or now
                if now - slow_since > STOP_HOLD:
                    r.reason = "로봇이 스스로 멈춤"
                    break
            else:
                slow_since = None

    for _ in range(5):
        common.joystick(conn, 0.0, 0.0, 0.0)
        await asyncio.sleep(0.02)
    await common.stop(conn)
    return r


def show(label, r):
    print(f"    {label}")
    print(f"      간 거리 {r.distance:.2f} m / {r.seconds:.1f}초   "
          f"최고 속도 {r.peak_speed:.2f} m/s")
    print(f"      옆미끄러짐 최대 {r.peak_side:.2f} m/s   "
          f"회전 최대 {r.peak_yaw:.2f} rad/s")
    if r.front_at_stop is not None:
        print(f"      멈출 때 앞 여유 {r.front_at_stop:.2f} m")
    print(f"      → {r.reason}")

    tail = r.tail_speed()
    if tail is not None:
        print(f"      마지막 {TAIL_SECONDS:.1f}초 평균 속도 {tail:.2f} m/s")

    # ★ 앞 여유가 줄어든 만큼 실제로 갔는가 ★
    seen = [t for t in r.trace if t[1] is not None]
    if len(seen) >= 2:
        d_front = seen[0][1] - seen[-1][1]
        d_move = seen[-1][2] - seen[0][2]
        print()
        print(f"      {'초':>5} {'앞여유':>8} {'간거리':>8} {'속도':>8}")
        for t, f, d, v in seen[::max(1, len(seen) // 8)]:
            print(f"      {t:5.1f} {f:8.2f} {d:8.2f} {v:8.2f}")
        print(f"      앞 여유 감소 {d_front:+.2f} m  vs  실제 이동 {d_move:+.2f} m")
        if d_move > 0.05 and d_front > d_move * 1.6:
            print("      ★ 앞 여유가 간 거리보다 훨씬 빨리 줄었습니다 ★")
            print("        장애물에 다가간 게 아니라 다른 것을 보고 있습니다.")
            print("        (뻗은 발이거나, 자세가 늦게 따라오는 것)")


async def enable_avoid(on=True):
    """회피 모드를 켜거나 끕니다. 파라미터 형식이 문서화돼 있지 않아 몇 가지 시도합니다."""
    last = None
    for label, param in (("{'data': bool}", {"data": bool(on)}),
                         ("{'data': int}", {"data": 1 if on else 0}),
                         ("(파라미터 없음)", None)):
        try:
            reply = await common.sport(conn, "SwitchAvoidMode", param)
        except KeyError:
            return None, "명령표에 없음"
        last = common.status_code(reply)
        print(f"      {label:18} → 코드 {last}")
        if last == 0:
            return label, last
    return None, last


async def run(conn_):
    await common.prepare_motion(conn_)
    await safety.set_auto_recovery(conn_, False)
    watchdog = safety.Watchdog(conn_)
    watchdog.arm()

    probe = common.StateProbe(conn_)
    await probe.read()

    # ★ 자세를 먼저 ★
    # 엎드린 채로 라이다를 읽으면 낮은 데만 보고, 그 값으로 자리를
    # 판정하게 됩니다. 세우고 나서 재야 합니다.
    print("\n[준비] 자세 확인")
    if not await common.ensure_standing(conn_, probe=probe, ask=False):
        print("일으켜 세우지 못했습니다. 중단합니다.")
        return

    eyes = perception.Eyes(conn_)
    if not await eyes.start():
        print("\n라이다 없이는 이 실험을 안전하게 할 수 없습니다. 중단합니다.")
        print("  .\\run look.py 로 먼저 라이다 상태를 확인하세요.")
        return

    print("[눈] 지도가 선 자세로 갱신되도록 3초 기다립니다...")
    await asyncio.sleep(3.0)

    c = eyes.clearance()
    print(f"[눈] 지금 자리: {c}")
    w = c.width()
    if w:
        print(f"     로봇 높이 통로 폭 {w:.2f} m")

    # ── 출발 자리 확인 ───────────────────────────────────────
    # ★ 순서가 중요합니다 ★
    # 대조군(B)은 **빈 복도**를 걷는 것입니다. 그러니 지금은 장애물이
    # 치워져 있어야 합니다. 상자는 C 단계에서 놓습니다.
    #
    # 처음에는 이 확인을 그냥 통과/중단으로만 만들어서, 상자를 미리
    # 놓아둔 분을 그 자리에서 막아버렸습니다. 순서를 먼저 알려주고,
    # 치운 뒤 다시 잴 수 있게 합니다.
    print("\n" + "=" * 66)
    print(" 출발 자리 확인")
    print("=" * 66)
    print(" ★ 지금은 장애물을 치워 두세요 ★")
    print("   먼저 빈 복도를 걷는 대조군(B)을 하고, 상자는 그다음 단계에서 놓습니다.")
    print()

    for attempt in range(1, 4):
        c = eyes.clearance()
        front = c.front
        shown = f"{front:.2f} m" if front is not None else f"{MAP_RANGE_HINT}+ m (범위 밖)"
        print(f" 지금 정면: {shown}")

        if front is None or front >= NEED_FRONT:
            print(" → 충분합니다.\n")
            break

        travel = predict_travel()
        print(f"\n 앞이 모자랍니다. 이 실험은 최대 {travel:.2f} m 를 걷고"
              f" 앞 {GUARD_FRONT} m 에서 멈추므로,")
        print(f" 최소 {travel + GUARD_FRONT:.2f} m, 여유를 더해"
              f" {NEED_FRONT:.1f} m 를 요구합니다.")
        print()
        print("  · 장애물을 아직 안 치우셨다면 지금 치워 주세요")
        print("  · 로봇을 돌려 복도의 긴 쪽을 보게 하거나, 더 트인 구간으로 옮기세요")
        print()
        print(" ※ 라이다 지도는 쌓인 것이라, 치운 물체가 바로 사라지지 않을 수 있습니다.")
        print("   치우고 5초쯤 두었다가 다시 재면 대개 갱신됩니다.")

        if attempt == 3:
            print("\n 세 번 다 모자랍니다. 중단합니다.")
            return
        if not await common.confirm("치웠습니다 / 옮겼습니다 — 다시 잴까요?"):
            print("\n 눈으로 보기에 앞이 충분히 트여 있습니까?")
            print(" (지도가 갱신이 늦은 것뿐이라면 계속해도 됩니다.")
            print("  어차피 우리 안전장치가 앞 %.2f m 에서 멈춥니다)" % GUARD_FRONT)
            if await common.confirm("눈으로 확인했습니다 — 그대로 진행할까요?"):
                print(" → 사람 눈을 믿고 진행합니다.\n")
                break
            print("\n 중단합니다.")
            return
        await asyncio.sleep(5.0)

    # ── A. 회피를 코드로 켤 수 있는가 ────────────────────────
    print("\n" + "=" * 66)
    print(" A. 회피 모드를 코드로 켤 수 있는가")
    print("=" * 66)
    form, code = await enable_avoid(True)
    if form is None:
        print("\n  ✘ 어떤 형식으로도 받아들여지지 않았습니다.")
        print("    코드로는 못 켭니다. 리모컨 옆면 2 버튼(두 번=켜기)으로만 가능합니다.")
        print("\n    그래도 B·C 는 의미가 있습니다 — 리모컨으로 켜고 진행하시겠습니까?")
        if not await common.confirm("리모컨으로 회피를 켰습니까?"):
            return
    else:
        print(f"\n  ✔ '{form}' 형식으로 켜졌습니다 (코드 {code})")
    await asyncio.sleep(2.0)

    # ── B. 대조군 — 앞이 트인 상태 ───────────────────────────
    print("\n" + "=" * 66)
    print(" B. 대조군 — 앞이 트인 복도")
    print("=" * 66)
    print(" 회피를 켠 채 그냥 걷습니다. 끝까지 걸어야 정상입니다.")
    print(" (여기서 멈춘다면 회피가 과민하거나 바닥 반사를 장애물로 본 것입니다)")
    print("\n ★ 사람 확인 ★  이 복도에는 사람이 앉아 있거나 지나갑니다.")
    print("   로봇이 향하는 쪽에 사람이 없는지 눈으로 확인하세요.")
    print("   라이다는 사람을 '장애물' 로 볼 뿐, 사람인지는 모릅니다.")
    if not await common.confirm(
            "로봇 앞이 비어 있고, **사람이 없으며**, 리모컨을 들고 계십니까?"):
        return
    base = await approach(probe, eyes)
    show("대조군", base)

    if base.self_stopped():
        print("\n  ※ 아무것도 없는데 로봇이 멈췄습니다.")
        print("    회피가 과민합니다. 이대로는 복도 안내에 쓸 수 없습니다.")
        print("    (거울 바닥이나 유리문을 잘못 본 것일 수 있습니다)")
        return
    if base.guarded():
        print("\n  ※ 우리 안전장치가 먼저 걸렸습니다. 자리가 좁습니다.")
        print("    더 트인 구간으로 옮겨 다시 하세요.")
        return
    await asyncio.sleep(2.0)

    # ── C. 장애물 ────────────────────────────────────────────
    print("\n" + "=" * 66)
    print(" C. 장애물을 두고 — 스스로 멈추는가")
    print("=" * 66)
    print(" 로봇 앞 약 1.5~2 m 에 부드럽고 가벼운 장애물을 놓으세요.")
    print(" 빈 종이상자나 쿠션. ★ 유리문·벽·사람은 절대 안 됩니다 ★")
    print(f" 우리 쪽 안전장치가 앞 {GUARD_FRONT} m 에서 먼저 멈춥니다.")
    if not await common.confirm("장애물을 놓았고, 리모컨을 들고 계십니까?"):
        return

    c = eyes.clearance()
    print(f"    출발 전 앞 여유: "
          f"{c.front:.2f} m" if c.front is not None else "    앞이 안 보입니다")
    if c.front is not None and c.front < 1.0:
        print("    ★ 장애물이 너무 가깝습니다. 조금 더 멀리 놓아주세요.")
        return

    test = await approach(probe, eyes)
    show("장애물 앞", test)

    # ── 정리 ─────────────────────────────────────────────────
    print("\n" + "=" * 66)
    print(" 정리")
    print("=" * 66)
    print(f"   대조군    {base.distance:.2f} m  — {base.reason}")
    print(f"   장애물    {test.distance:.2f} m  — {test.reason}")

    # ★ 완전히 멈추지 않아도 '느려졌으면' 회피입니다 ★
    bt, tt = base.tail_speed(), test.tail_speed()
    slowed = False
    if bt is not None and tt is not None:
        print(f"   마지막 {TAIL_SECONDS:.1f}초 속도   "
              f"대조군 {bt:.2f} → 장애물 {tt:.2f} m/s")
        if bt > 0.05:
            slowed = tt < bt * 0.6
    print()

    # 1차에서 실제로 걸린 함정: 둘 다 시간 만료라 비교가 성립하지 않는데
    # '애매하다' 고만 적어서, 무엇을 고쳐야 하는지 알 수 없었습니다.
    if base.timed_out() and test.timed_out() and not slowed:
        print(" 판정할 수 없습니다 — 실험이 짧았습니다.")
        print(f" 장애물까지 {test.front_at_stop:.2f} m 를 남기고 시간이 끝났습니다."
              if test.front_at_stop is not None else " 장애물에 닿기 전에 끝났습니다.")
        print(f" PUSH 를 {PUSH:.0f}초보다 늘리거나, 장애물을 더 가깝게 놓으세요.")
        print(" (로봇이 회피할 기회조차 없었으므로, '회피가 없다' 는 결론이 아닙니다)")
    elif test.self_stopped() and test.distance < base.distance - 0.15:
        print(" ★ 회피가 동작합니다 ★")
        print(" 로봇이 우리 안전장치보다 먼저 스스로 멈췄습니다.")
        if test.peak_side > 0.10 or test.peak_yaw > 0.30:
            print()
            print(" ⚠ 다만 '멈추기' 가 아니라 '비켜가기' 로 보입니다.")
            print(f"   옆미끄러짐 {test.peak_side:.2f} m/s, 회전 {test.peak_yaw:.2f} rad/s")
            print(" 폭 1.15 m 복도에서는 비켜갈 자리가 없습니다.")
            print(" 이 복도에서 쓰려면 회피에만 맡기면 안 됩니다.")
        else:
            print(" 옆으로 비켜가지 않고 제자리에 섰습니다 — 좁은 복도에 맞는 동작입니다.")
    elif slowed and not test.guarded():
        print(" ★ 회피가 '느려지기' 로 동작합니다 ★")
        print(" 완전히 서지는 않았지만, 장애물 앞에서 속도가 눈에 띄게 줄었습니다.")
        print(" 안내에 쓸 수는 있지만, 멈춰 주리라 기대하면 안 됩니다.")
    elif test.guarded():
        print(" 회피가 동작하지 않았습니다.")
        print(f" 앞 {GUARD_FRONT} m 까지 속도를 줄이지 않고 그대로 들어왔고,")
        print(" 우리 안전장치가 먼저 멈춰서 부딪히지는 않았습니다.")
        print()
        print(f" ※ 한 가지 단서: 로봇의 회피 문턱이 {GUARD_FRONT} m 보다 가깝다면")
        print("   이 실험으로는 영영 볼 수 없습니다. 하지만 폭 1.15 m 복도에서는")
        print(f"   {GUARD_FRONT} m 부터 줄이지 않는 회피는 어차피 늦습니다.")
        print()
        print(" 이 경우 복도 안내는 이렇게 갑니다.")
        print("   · 로봇의 회피에 기대지 않는다")
        print("   · 대신 우리가 라이다로 보고 멈춘다 (이 실험에서 실제로 동작했습니다)")
        print("   · 또는 리모컨 자동 추종으로 사람이 앞서 걷는다")
    else:
        print(" 판정이 애매합니다. 두어 번 더 돌려보세요.")
        print(" 장애물을 더 크고 높은 것으로 바꾸면 더 확실합니다.")

    print()
    print(" ※ 유리문은 라이다에 보이지 않습니다. 이 실험 결과와 무관하게,")
    print("   유리문 근처에서는 회피를 믿지 마세요.")


async def main():
    global conn
    print("=" * 66)
    print(" 장애물 회피 확인 (복도용)  ★ 로봇이 조금 움직입니다 ★")
    print("=" * 66)
    print(__doc__.split("준비물")[0])

    if not await common.confirm(
        "앞으로 4m 가 트여 있고, 부드러운 장애물과 리모컨을 준비했습니까?"
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
