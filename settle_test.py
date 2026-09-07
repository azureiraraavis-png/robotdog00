# -*- coding: utf-8 -*-
"""
어떻게 하면 덜 철푸덕 엎드리는가 — 내려앉는 방법 세 가지 비교.

  ★ 왜 ★

    안내 마지막에 엎드리는 것이 "철푸덕 엎어지는 것 같다" 는 보고를
    받았습니다. 지금은 서 있는 상태에서 StandDown 한 방입니다.

        몸높이 0.32 m  →  0.07 m     (한 번에)

    부드럽게 내리려면 몸높이를 조금씩 낮춰야 하는데, **이 기체에는
    그 명령이 없습니다.** 이 기체는 MCF 모드로 돌고, MCF 명령표에는
    BodyHeight 가 아예 들어 있지 않습니다 (일반 모드에는 있습니다).

        MCF:  Damp BalanceStand StandUp StandDown RecoveryStand
              Euler Sit RiseSit SpeedLevel Pose ...      ← BodyHeight 없음
        일반: ... BodyHeight FootRaiseHeight ...

    남은 수는 **중간에 앉기를 끼우는 것** 하나였는데, 한 번 재보고
    **닫혔습니다.**

        → Sit         2.5초 뒤 몸높이 0.229 m
        → StandDown   ★ 거부됨 (code=-1)
                      3.0초 뒤 몸높이 0.229 m    ← 그대로

    앉은 상태에서는 StandDown 이 실행되지 않습니다. 그러니 실제 선택은
    1번(지금처럼 한 번에)과 3번(앉기로 끝내기) 둘뿐입니다.

  ★ 그런데 첫 판에서 이 시험이 스스로 틀렸습니다 ★

    로그에 code=-1 과 0.229 → 0.229 가 그대로 찍혀 있는데, 판정은
    이렇게 나왔습니다.

        "앉기가 실제로 먹혔습니다 ... 0.32 → 0.23 → 바닥."

    **바닥에 닿지도 않았는데요.** 제가 확인한 것은 '중간 높이가 시작과
    다른가' 하나였고, '끝이 바닥인가' 는 묻지 않았습니다. 그래서 두
    단계를 거쳤다는 것만 보고 다 내려갔다고 적었습니다.

    ★ 중간을 보고 끝을 단정했습니다 ★  이제 세 가지를 봅니다.

      1. 명령이 거부되지 않았는가   (sport 의 응답 코드를 실제로 읽습니다)
      2. **끝난 높이가 바닥인가**   (FLOOR 아래인가)
      3. 내려가는 데 몇 초 걸렸는가 (내려가는 동안 촘촘히 재서)

    3번도 첫 판에는 없었습니다. 명령을 보내고 3초 자고 나서 높이를 한
    번 읽었으니, 잰 것은 "3초 걸렸다" 가 아니라 "내가 3초를 잤다"
    였습니다. 실제 하강이 0.8초인지 2.5초인지는 여전히 몰랐습니다 —
    그게 바로 '철푸덕' 인지 아닌지를 가르는 값인데요.

  쓰는 법

      .\\run settle_test.py

    세 가지를 차례로 보여줍니다. 사이에 다시 일으켜 세우고 쉽니다.

      1. 지금 방식        서 있다가 StandDown
      2. 앉았다 엎드리기   Sit → 잠깐 → StandDown   (거부되는 것 재확인)
      3. 앉기까지만        Sit 에서 끝

    ★ 로봇이 실제로 앉고 엎드립니다. 사방 1 m 를 비워두세요 ★
    바닥이 딱딱하면 소리가 큽니다 — 판단에 그것도 넣으세요.
"""

import asyncio
import sys
import time

import common

REST = 2.5          # 방법 사이 쉼 (다음 것과 섞이지 않게)
PEEK = 0.10         # 높이를 얼마나 촘촘히 볼 것인가
FLOOR = 0.12        # 이보다 낮으면 바닥에 닿은 것으로 봅니다


async def trace(probe, seconds):
    """내려가는 **동안** 의 몸높이를 촘촘히 적습니다. [(초, 높이), ...]

    ★ 지난 판에서 이걸 만들어놓고 안 썼습니다 ★
      명령을 보내고 3초 자고 나서 높이를 한 번만 읽었습니다. 그러면
      '3초 걸렸다' 가 아니라 '내가 3초를 잤다' 를 잰 것입니다.
      실제로 몇 초에 걸쳐 내려가는지는 여전히 몰랐습니다.
    """
    out = []
    t0 = time.time()
    while time.time() - t0 < seconds:
        h = probe.height
        if h is not None:
            out.append((time.time() - t0, h))
        await asyncio.sleep(PEEK)
    return out


def descent(pts, start):
    """내려간 구간만 골라 (시작초, 끝초, 걸린시간, 최대 초당 하강)."""
    if not pts or start is None:
        return None
    lo = min(h for _t, h in pts)
    if start - lo < 0.03:
        return None
    moving = [(t, h) for t, h in pts if start - h > 0.02 and h - lo > 0.02]
    fast = 0.0
    for (t1, h1), (t2, h2) in zip(pts, pts[1:]):
        if t2 > t1:
            fast = max(fast, (h1 - h2) / (t2 - t1))
    if not moving:
        return (0.0, 0.0, 0.0, fast)
    return (moving[0][0], moving[-1][0], moving[-1][0] - moving[0][0], fast)


async def method(conn, probe, n, name, steps, note):
    print()
    print("=" * 70)
    print(f" {n}. {name}")
    print("=" * 70)
    print(f"   {note}")
    print()
    await common.ensure_standing(conn, probe=probe, ask=False)
    await asyncio.sleep(1.0)

    start = probe.height
    print(f"   시작 몸높이 {start:.3f} m" if start else "   시작 몸높이 —")
    marks, pts, refused = [], [], []
    t0 = time.time()
    for cmd, wait in steps:
        print(f"   → {cmd}")
        reply = await common.sport(conn, cmd)
        code = common.status_code(reply) if reply is not None else None
        if code not in (0, None):
            refused.append((cmd, code))
        seg = await trace(probe, wait)
        base = time.time() - t0 - wait
        pts += [(base + t, h) for t, h in seg]
        h = probe.height
        marks.append((cmd, h, time.time() - t0))
        print(f"     {wait:.1f}초 뒤 몸높이 {h:.3f} m" if h else "     몸높이 —")
    took = time.time() - t0

    print()
    end = probe.height
    if start and end is not None:
        print(f"   {start:.3f} → {end:.3f} m   ({start - end:.3f} m 내려감)")
    d = descent(pts, start)
    if d:
        print(f"   ★ 실제로 내려가는 데 {d[2]:.1f}초 "
              f"(가장 빠를 때 초당 {d[3]:.2f} m)")
    if refused:
        for cmd, code in refused:
            print(f"   ★ '{cmd}' 이 거부됐습니다 (code={code}) — 이 방법은 안 됩니다")
    return {"이름": name, "초": took, "높이": marks, "시작": start,
            "끝": end, "하강": d, "거부": refused, "점": pts}


def verdict(rows):
    print()
    print("=" * 70)
    print(" 기계가 답할 수 있는 것")
    print("=" * 70)
    print(f" {'방법':20}{'끝난 높이':>10}{'내려간 거리':>12}"
          f"{'내려가는 시간':>14}   결과")
    print(" " + "-" * 68)
    for r in rows:
        end = f"{r['끝']:.2f} m" if r["끝"] is not None else "—"
        drop = f"{r['시작'] - r['끝']:.2f} m" if r["끝"] and r["시작"] else "—"
        secs = f"{r['하강'][2]:.1f}초" if r["하강"] else "—"
        if r["거부"]:
            got = "★ 거부됨 — 안 됨"
        elif r["끝"] is not None and r["끝"] < FLOOR:
            got = "바닥까지 내려감"
        else:
            got = "바닥에 안 닿음"
        print(f" {r['이름']:20}{end:>10}{drop:>12}{secs:>14}   {got}")

    print()
    # ★ '바닥에 닿았는가' 를 먼저 묻습니다 ★
    #   지난 판에서 저는 '중간 높이가 시작과 다른가' 만 보고 "바닥까지
    #   두 번에 나눠 내려간다" 고 찍었습니다. 로그에는 code=-1 과
    #   0.23 → 0.23 이 그대로 있었는데도요. **끝을 안 보고 중간만
    #   봤습니다.** 이제 끝부터 봅니다.
    ok = [r for r in rows if not r["거부"] and r["끝"] is not None
          and r["끝"] < FLOOR]
    dead = [r for r in rows if r["거부"]]
    for r in dead:
        cmd, code = r["거부"][0]
        print(f" ★ '{r['이름']}' 은 불가능합니다 — {cmd} 이 거부(code={code})")
    if dead:
        print("   명령을 보내도 실행되지 않습니다. 이 길은 닫혔습니다.")
        print()

    if not ok:
        print(" 바닥까지 내려가는 방법이 하나도 없었습니다.")
    else:
        best = min(ok, key=lambda r: r["하강"][3] if r["하강"] else 9)
        print(" 바닥까지 내려간 방법:")
        for r in ok:
            fast = f"초당 {r['하강'][3]:.2f} m" if r["하강"] else "—"
            print(f"   {r['이름']} — 가장 빠를 때 {fast}")
        if best["하강"]:
            print(f" 그중 가장 완만한 것: {best['이름']}")

    sit_only = [r for r in rows if not r["거부"] and r["끝"] is not None
                and r["끝"] >= FLOOR]
    if sit_only:
        print()
        print(" 바닥에 안 닿는 방법 (앉기로 끝내는 쪽):")
        for r in sit_only:
            print(f"   {r['이름']} — {r['시작']:.2f} → {r['끝']:.2f} m "
                  f"({r['시작'] - r['끝']:.2f} m 만 내려감)")
        print("   엎드리지는 않지만 훨씬 조용하고 완만합니다.")

    print()
    print(" 나머지는 사람이 봐야 합니다 — 어느 쪽이 배웅답게 보였습니까?")
    print("   (딱딱한 바닥이면 소리도 판단에 넣으세요)")


async def main():
    print("=" * 70)
    print(" 내려앉는 방법 비교")
    print("=" * 70)
    print(" ★ 로봇이 실제로 앉고 엎드립니다. 사방 1 m 를 비워두세요 ★")
    print(" 세 가지를 차례로 보여드립니다. 사이에 다시 일으켜 세웁니다.")
    print()
    if not await common.confirm("로봇 사방이 비어 있고, 조종 장치를 들고 계십니까?"):
        return

    conn = await common.connect()
    try:
        await common.prepare_motion(conn)
        probe = common.StateProbe(conn)
        await probe.read()

        rows = []
        rows.append(await method(
            conn, probe, 1, "지금 방식",
            [("StandDown", 3.0)],
            "서 있다가 바로 엎드립니다. 지금 안내가 하는 것입니다."))
        await asyncio.sleep(REST)

        rows.append(await method(
            conn, probe, 2, "앉았다 엎드리기",
            [("Sit", 2.5), ("StandDown", 3.0)],
            "앉고 나서 잠깐 두었다가 엎드립니다. "
            "앉은 채로 StandDown 이 먹히는지가 관건입니다."))
        await asyncio.sleep(REST)

        rows.append(await method(
            conn, probe, 3, "앉기까지만",
            [("Sit", 2.5)],
            "엎드리지 않고 앉은 채로 끝냅니다. 제일 조용합니다."))

        verdict(rows)
    finally:
        print("\n정리합니다...")
        try:
            await common.ensure_standing(conn, probe=probe, ask=False)
            await common.settle(conn)
        except Exception:
            pass
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
