# -*- coding: utf-8 -*-
"""
안내 실행기 — scenario.py 를 실제로 돌립니다.

  ★ 기본은 '제자리 모드' 입니다. 걷지 않습니다 ★
    이동 구간에서는 "여기서 9.7 m 이동합니다" 라고 알리고 넘어갑니다.
    책상 옆에서도 돌릴 수 있고, 안내의 대부분이 그래도 들어 있습니다.

  ── 왜 걷기부터 만들지 않는가 ──
    걷기는 아직 못 정한 것들에 걸려 있습니다.
      · 문 통과를 좌우 보며 가운데 맞추기로 해야 하는데 (주행거리계 오차가
        문틀 여유의 두 배라서) 그 부품이 아직 없습니다
      · S5 마무리 자리는 방 안으로 정해졌지만, 그 자리를 아직 안 쟀습니다

    반면 **말하기와 동작은 지금 다 정해져 있습니다.** 그런데 한 번도
    돌려본 적이 없습니다. 토막(Line) 구조도, 동작 삽입도, 파일 20개
    업로드도 전부 처음입니다. 먼저 여기서 걸리는 것을 털어내는 편이
    낫습니다 — 좁은 복도에서 발견하는 것보다 훨씬 쌉니다.

  ── 덤으로 동작 시간을 잽니다 ──
    scenario.GESTURE_SECONDS 는 지금 전부 어림값입니다 (인사 3초, 앉기
    3.5초…). 돌리면서 실제로 재서, 끝날 때 고칠 값을 알려줍니다.
    voices.py 가 멘트 길이로 했던 것과 같은 방식입니다.

  쓰는 법

      .\\run guide.py              제자리 모드 (걷지 않음)
      .\\run guide.py --turns      제자리 회전도 실제로 합니다
                                  ★ 사방 0.5 m 이상 비워두세요 ★
      .\\run guide.py --refresh    음성을 다시 만들어 올립니다
      .\\run guide.py --from S3    중간부터
      .\\run guide.py --dry        로봇 없이 순서만 봅니다

  준비물 (제자리 모드)
    □ 로봇 사방 1 m
    □ 조종 장치 손에 (힘 빼기: 게임패드 L2+B, 동반 리모컨 P 두 번)
    □ 배터리 40% 이상
"""

import asyncio
import sys
import time

import scenario

# ★ 로봇 관련 모듈은 함수 안에서 불러옵니다 ★
#   --dry (순서만 보기) 는 로봇도 라이브러리도 없이 돌아가야 합니다.
#   맨 위에서 import 하면 unitree 라이브러리가 없는 PC 에서는
#   순서표조차 못 봅니다. 연습은 어디서든 되어야 합니다.


class Timer:
    """동작이 실제로 몇 초 걸렸는지 모읍니다."""

    def __init__(self):
        self.seen = {}

    async def run(self, name, coro):
        t0 = time.time()
        await coro
        took = time.time() - t0
        self.seen.setdefault(name, []).append(took)
        return took

    def report(self):
        if not self.seen:
            return
        print()
        print("=" * 70)
        print(" 동작에 걸린 시간 — 어림값 vs 실측")
        print("=" * 70)
        pad = scenario._pad
        print(f"{pad('동작', 12)}{pad('횟수', 6, True)}"
              f"{pad('어림', 9, True)}{pad('실측', 9, True)}")
        print("-" * 70)
        fixes = []
        for name, times in sorted(self.seen.items()):
            avg = sum(times) / len(times)
            guess = scenario.GESTURE_SECONDS.get(name, 0.0)
            print(f"{pad(name, 12)}{pad(str(len(times)), 6, True)}"
                  f"{pad(f'{guess:.1f}초', 9, True)}{pad(f'{avg:.1f}초', 9, True)}")
            if abs(avg - guess) > 0.5:
                fixes.append((name, avg))
        if fixes:
            print()
            print(" scenario.py 의 GESTURE_SECONDS 를 이렇게 고치면 됩니다")
            for name, avg in fixes:
                print(f'     "{name}": {avg:.1f},')
            print()
            print(" 이 값이 맞아야 시간표가 진짜가 됩니다.")


async def do_gesture(robot, name, timer, allow_turns):
    """토막에 붙은 동작 하나. 돌려주는 값: 실제로 했는지."""
    import common
    if not name:
        return False
    print(f"   ⟨{name}⟩")
    if name == "hello":
        await timer.run(name, common.sport(robot["conn"], "Hello"))
        await asyncio.sleep(1.0)
    elif name == "sit":
        await timer.run(name, robot["posture"].sit())
    elif name == "stand":
        await timer.run(name, robot["posture"].stand())
    elif name == "lie":
        await timer.run(name, robot["posture"].lie())
    elif name == "tilt":
        print("      (몸통 기울이기는 아직 안 만들었습니다 — 건너뜁니다)")
        return False
    else:
        print(f"      ※ 모르는 동작입니다: {name}")
        return False
    return True


async def play_line(robot, step, line):
    """토막 하나: 동작 → 멘트 → 쉼."""
    secs, real = scenario._line_seconds(line)
    tag = "실측" if real else "추정"
    head = line.text[:40] + ("…" if len(line.text) > 40 else "")
    if line.text.strip():
        print(f"   ▶ {line.key}  ({secs:.0f}초 {tag})")
        print(f"     {head}")
        await robot["hub"].play_by_uuid(robot["uuids"][line.key])
        await asyncio.sleep(secs + 0.3)      # 끝까지 나오도록 조금 더
    if line.pause:
        print(f"     … {line.pause:.1f}초 쉼")
        await asyncio.sleep(line.pause)


async def do_stop(robot, step, timer, allow_turns):
    import common
    print()
    print("─" * 70)
    print(f" {step.sid}  {step.place}   — {step.purpose}")
    print("─" * 70)

    # 문 쪽으로 돌아 라이트로 가리키기
    pointing = False
    if step.face == "door" and step.door_deg is not None:
        if allow_turns:
            print(f"   ⟨문 쪽으로 {step.door_deg:+.0f}도 회전⟩")
            await common.turn_by(robot["conn"], step.door_deg,
                                 probe=robot.get("probe"))
        else:
            print(f"   (문 쪽으로 {step.door_deg:+.0f}도 — 제자리 모드라 건너뜁니다)")
        await common.light_on(robot["conn"])
        pointing = True

    for line in step.lines:
        await do_gesture(robot, line.gesture, timer, allow_turns)
        await play_line(robot, step, line)

    if pointing:
        await common.light_off(robot["conn"])
        if not getattr(step, "face_back", True):
            # 이 문으로 들어갈 것이므로 본 채로 둡니다 (S4 → M4)
            print("   (문을 본 채로 둡니다 — 이 문으로 들어갑니다)")
        elif allow_turns:
            print("   ⟨복도 쪽으로 되돌리기⟩")
            await common.turn_by(robot["conn"], -step.door_deg,
                                 probe=robot.get("probe"))

    print(f"   … 질의응답 {scenario.QA_PAUSE:.0f}초")
    await asyncio.sleep(scenario.QA_PAUSE)


# ★ 회전은 common.turn_by 가 합니다 ★
#   여기에 스틱↔각속도 환산표(YAW_STICK / YAW_RATE)를 두고 시간으로
#   돌리고 있었는데, common.move 가 3초에서 자르는 바람에 112도가 넘는
#   회전은 전부 112도가 되고 있었습니다. 로그에는 "3.0초" 라고만
#   찍혔습니다. turn_by 는 나눠 보내고, 실제로 돈 각도를 재서 멈춥니다.


async def do_move(robot, step, allow_turns):
    import common
    print()
    print(f" {step.sid}  {step.place}")
    if step.text.strip():
        secs, _r = scenario._line_seconds(step.lines[0]
                                          if hasattr(step, "lines") else step)
        print(f"   ▶ {step.key}")
        print(f"     {step.text}")
        await robot["hub"].play_by_uuid(robot["uuids"][step.key])
        await asyncio.sleep(scenario.seconds_for(step)[0] + 0.3)

    # ── 출발 방향 잡기 ──
    #
    # ★ 여기가 비어 있었습니다 ★
    #   allow_turns 를 받아놓고 쓰지 않았습니다. 그래서 --turns 를 줘도
    #   정차점의 '문 쪽으로 돌기' 만 돌고 이동 구간은 한 번도 돌지 않았습니다.
    #   S2·S3·S4 가 도니까 도는 것처럼 보였을 뿐입니다.
    if step.turn_deg:
        if allow_turns:
            print(f"   ⟨출발 방향 {step.turn_deg:+.0f}도 회전⟩")
            await common.turn_by(robot["conn"], step.turn_deg,
                                 probe=robot.get("probe"))
        else:
            print(f"   (출발 방향 {step.turn_deg:+.0f}도 — 제자리 모드라 건너뜁니다)")

    if getattr(step, "align", False):
        print("   ⟨복도와 나란히 맞추기⟩  ※ 아직 안 만들었습니다 (라이다)")

    bits = []
    if step.meters:
        bits.append(f"{step.meters:.2f} m 이동")
    if getattr(step, "narrow", False):
        bits.append("★ 좁은 통로 — 좌우 보며 가운데 맞추기 ★")
    if bits:
        print(f"   ⟨{' · '.join(bits)}⟩")
        print("     (제자리 모드라 실제로 가지는 않습니다)")
    await asyncio.sleep(1.0)


async def run(conn, refresh=False, allow_turns=False, start_at=None):
    import common
    import safety
    import voices
    made, changed = await voices.build(refresh=refresh)
    paths = {k: p for k, (p, _s) in made.items()}

    await common.prepare_motion(conn)
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    probe = common.StateProbe(conn)
    await probe.read()
    await common.set_volume(conn)

    print("\n[준비] 멘트를 로봇에 올립니다...")
    if changed and not refresh:
        print(f"       문장이 바뀐 {len(changed)}개는 로봇의 것도 갈아치웁니다: "
              f"{', '.join(sorted(changed))}")
    hub, uuids = await common.upload_all(
        conn, paths, replace=True if refresh else changed)
    print(f"[준비] 완료 — {len(uuids)}개")

    print("\n[준비] 자세 확인")
    if not await common.ensure_standing(conn, probe=probe, ask=False):
        print("일으켜 세우지 못했습니다. 중단합니다.")
        return

    robot = {"conn": conn, "hub": hub, "uuids": uuids, "probe": probe,
             "posture": common.Posture(conn, probe=probe)}
    robot["posture"].state = "stand"
    timer = Timer()

    print()
    print("=" * 70)
    print(f" {scenario.TITLE}")
    print(f" {scenario.ROUTE}")
    print("=" * 70)
    if not allow_turns:
        print(" ★ 제자리 모드 — 걷지도 돌지도 않습니다 ★")
    else:
        print(" ★ 회전 포함 — 사방 0.5 m 이상 비어 있어야 합니다 ★")

    started = start_at is None
    for step in scenario.SCENARIO:
        if not started:
            if step.sid == start_at:
                started = True
            else:
                continue
        if isinstance(step, scenario.Stop):
            await do_stop(robot, step, timer, allow_turns)
        else:
            await do_move(robot, step, allow_turns)

    timer.report()


def dry_run(start_at=None):
    """로봇 없이 순서만 봅니다."""
    print("=" * 70)
    print(f" {scenario.TITLE}   (연습 — 로봇 없이 순서만)")
    print("=" * 70)
    started = start_at is None
    total = 0.0
    for step in scenario.SCENARIO:
        if not started:
            if step.sid == start_at:
                started = True
            else:
                continue
        secs, real = scenario.seconds_for(step)
        total += secs
        if isinstance(step, scenario.Stop):
            print(f"\n {step.sid}  {step.place}   {secs:.0f}초")
            if step.face == "door" and step.door_deg is not None:
                print(f"     ⟨문 쪽 {step.door_deg:+.0f}도 + 라이트⟩")
            for line in step.lines:
                g = f"⟨{line.gesture}⟩ " if line.gesture else ""
                ls, _r = scenario._line_seconds(line)
                body = line.text[:44] or "(말 없음)"
                print(f"     {g}{ls:4.0f}초  {body}")
            total += scenario.QA_PAUSE
        else:
            bits = []
            if step.turn_deg:
                bits.append(f"{step.turn_deg:+.0f}도")
            if getattr(step, "align", False):
                bits.append("벽과 나란히")
            if step.meters:
                bits.append(f"{step.meters:.2f} m")
            if getattr(step, "narrow", False):
                bits.append("★좁음★")
            print(f"\n {step.sid}  {step.place}   ⟨{' · '.join(bits)}⟩")
            if step.text.strip():
                print(f"     {step.text}")
    print()
    print("-" * 70)
    print(f" 멘트+대기 합계 약 {total:.0f}초 = {total/60:.1f}분  (걷는 시간 제외)")


def _start_at(args):
    if "--from" in args:
        i = args.index("--from")
        if i + 1 < len(args):
            return args[i + 1].upper()
    return None


async def main():
    import common
    args = sys.argv[1:]
    refresh = "--refresh" in args
    allow_turns = "--turns" in args
    start_at = _start_at(args)

    print("=" * 70)
    print(" 안내 실행기  ★ 로봇이 말하고 자세를 바꿉니다 ★")
    print("=" * 70)
    if allow_turns:
        print(" --turns : 제자리 회전을 실제로 합니다. 사방 0.5 m 이상 비우세요.")
    else:
        print(" 제자리 모드 — 걷지도 돌지도 않습니다. 사방 1 m 면 충분합니다.")
    print(" 힘 빼기: 게임패드 L2+B, 동반 리모컨 P 두 번")
    print()
    if not await common.confirm("로봇 사방이 비어 있고, 조종 장치를 들고 계십니까?"):
        return

    conn = await common.connect()
    try:
        await run(conn, refresh=refresh, allow_turns=allow_turns,
                  start_at=start_at)
    finally:
        print("\n정리합니다...")
        try:
            await common.light_off(conn, verbose=False)
        except Exception:
            pass
        try:
            await common.settle(conn)
        except Exception:
            pass
        await common.disconnect(conn)


if __name__ == "__main__":
    # ★ --dry 는 로봇 라이브러리 없이 돌아갑니다 ★
    #   순서를 확인하는 일은 어디서든 되어야 합니다.
    if "--dry" in sys.argv[1:]:
        dry_run(_start_at(sys.argv[1:]))
        sys.exit(0)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
        print("로봇이 멈추지 않으면 게임패드 L2+B, 또는 동반 리모컨 P 두 번.")
    except Exception as e:
        try:
            import common
            common.explain_error(e)
        except Exception:
            print(f"\n{type(e).__name__}: {e}")
        sys.exit(1)
