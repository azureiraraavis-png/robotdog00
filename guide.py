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

      .\\run guide.py --manual --no-ears  음성 인식을 아예 잠급니다
                                       (기본은 열려 있고, 메뉴에서 켭니다)
      .\\run guide.py --manual     ★ 사람이 몰고 로봇이 안내합니다 ★
                                  휴대폰 주소가 뜹니다. 조종판으로 몰고,
                                  "도착했습니다" 도 휴대폰으로.

                                  ※ 켜자마자 시작하지 않습니다. '준비됐습니다'
                                    화면에서 기다리고, 로봇을 시작 위치까지
                                    몰고 나서 '안내 시작' 을 누르면 그때
                                    첫 인사가 나갑니다.

  준비물 (제자리 모드)
    □ 로봇 사방 1 m
    □ 조종 장치 손에 (힘 빼기: 게임패드 L2+B, 동반 리모컨 P 두 번)
    □ 배터리 — 화면이 "됩니다" 라고 하는가 (머리줄 밑 한 줄)

      여태 '40% 이상' 이라고 적어뒀는데, 그건 아무도 재지 않은
      숫자였습니다. 이제 프로그램이 잰 값으로 직접 답합니다:
      한 바퀴가 3%, 바퀴 사이 기다림까지 치면 3.7% 입니다.
      40% 면 다섯 바퀴가 남은 셈이라 지나치게 넉넉했습니다.
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
    """토막에 붙은 동작 하나. 돌려주는 값: 실제로 했는지.

    ※ 회전과 같은 표시를 씁니다 — 다리를 쓰는 동안에는 메뉴에서 누른
      자세가 끼어들지 않습니다. 인사하다 말고 앉으면 둘 다 망칩니다.
    """
    import common
    if not name:
        return False
    print(f"   ⟨{name}⟩")
    robot["turning"] = True
    try:
        return await _gesture(robot, name, timer)
    finally:
        robot["turning"] = False


async def _gesture(robot, name, timer):
    import common
    if name == "hello":
        await timer.run(name, common.sport(robot["conn"], "Hello"))
        await asyncio.sleep(1.0)
        # 인사는 로봇을 '서 있지 않은' 자세로 남깁니다. 그 사실을 여기서
        # 알려주지 않으면, 다음 엎드리기가 그 자세에서 그대로 떨어집니다
        # (0.5초 철푸덕). 자세한 내력은 common.Posture.disturbed 에.
        robot["posture"].disturbed("인사")
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


# 이 아래로 내려가면 낮다고 봅니다 (%).
#
# ★ 숫자는 그대로지만 근거가 생겼습니다 (2026-09-11) ★
#   처음에는 그냥 정한 값이었습니다. 세 바퀴를 재고 보니:
#
#       한 바퀴          3%   (세 번 다 정확히 3%)
#       바퀴 사이 기다림 1%
#       그래서 실제로는  3.7% / 바퀴
#
#   한계선 20% 위로 30% 면 **세 바퀴**가 남았다는 뜻입니다. 두 바퀴쯤
#   남았을 때 알려주는 것이 손 쓸 여유로 알맞습니다 — 26% 가 그
#   자리인데, 30 이면 한 바퀴 더 일찍 말합니다. 그 정도가 낫습니다.
#
#   더 내리지 않는 이유: 경고는 **늦는 쪽이 위험**합니다. 일찍 울려서
#   잃는 것은 한 바퀴뿐이고, 늦게 울려서 잃는 것은 복도에 선 로봇입니다.
LOW_BATTERY = 30

def _battery_note(bat, hand):
    """"이 코스를 돌 만큼 남았는가" 를 한 줄로.

    ★ 퍼센트만 띄우면 더 고운 경고등입니다 ★
      사람은 "37%" 를 보고도 그게 이 코스에 되는 양인지 모릅니다.
      그런데 코스가 몇 분인지는 이미 압니다 (Course.summary). 그러니
      물음에 바로 답합니다 — 그게 경고등과 계기판의 차이입니다.

    ※ 근거가 되는 common.PER_MINUTE 는 아직 **짐작**입니다. 그래서
      화면에도 '짐작' 이라고 적습니다. 몇 바퀴 돌면 진짜 값이 나옵니다.
    """
    try:
        import courses as _courses
        want = (hand.state.get("course") or {}).get("id")
        c = _courses.get(want) if want else None
        if c is None:
            return ""
        secs = c.summary()["seconds"]
        ok = bat.enough_for(secs)
        if ok is None:
            return ""
        mins = secs / 60.0
        if ok:
            return f"이 코스 {mins:.0f}분 — 지금 남은 것으로 됩니다 (짐작)"
        return f"이 코스 {mins:.0f}분 — 모자랄 수 있습니다 (짐작)"
    except Exception:
        # 화면에 한 줄 덜 뜨는 것이지, 안내가 멎을 일은 아닙니다.
        return ""


async def battery_loop(robot, hand):
    """배터리 잔량을 화면에 흘려보냅니다. 5초마다.

    ★ 왜 따로 고리를 두는가 ★
      조종 고리(drive_loop)는 50Hz 로 돕니다. 배터리는 그렇게 자주 볼
      값이 아니고, 무엇보다 **조종이 멈춰도 배터리는 계속 보여야**
      합니다. 한 고리에 묶으면 한쪽이 멎을 때 다른 쪽도 같이 멎습니다.

    ★ 모르는 것과 끊긴 것을 갈라 보냅니다 ★
      아직 첫 메시지가 안 온 것과, 오다가 끊긴 것은 다른 상황입니다.
      화면에는 둘 다 숫자가 없지만, 뒤엣것은 **마지막 값이 있는데도
      못 믿는 것**이라 사람이 알아야 합니다.
    """
    bat = robot.get("battery")
    if bat is None:
        return
    said_low = False
    try:
        while True:
            if bat.fresh():
                hand.flag(battery=bat.percent, battery_stale=False,
                          battery_note=_battery_note(bat, hand))
                # ★ 낮으면 한 번은 소리내어 말합니다 ★
                #   alert_low_battery.mp3 는 여태 만들어만 놓고 아무도
                #   틀지 않았습니다. 화면은 조종하는 사람만 보지만,
                #   소리는 곁에 선 사람도 듣습니다.
                if bat.percent <= LOW_BATTERY and not said_low:
                    said_low = True
                    print(f"\n   ★ 배터리 {bat.percent}% — 낮습니다 ★")
                    # ★ 로봇이 말하는 중이면 안 끼어듭니다 ★
                    #   안내 멘트 위에 경고를 덮어씌우면 둘 다 못
                    #   알아듣습니다. 화면에는 이미 떠 있으니, 소리는
                    #   기다렸다 다음 기회에 냅니다.
                    hub, uuids = robot.get("hub"), robot.get("uuids") or {}
                    key = "alert_low_battery"
                    if hub and key in uuids and not robot.get("busy"):
                        try:
                            await hub.play_by_uuid(uuids[key])
                        except Exception as e:
                            print(f"      (경고음을 못 냈습니다: {e})")
                    else:
                        said_low = False      # 다음 바퀴에 다시 해봅니다
                elif bat.percent > LOW_BATTERY + 5:
                    said_low = False        # 충전했으면 다시 말할 수 있게
            elif bat.percent is not None:
                hand.flag(battery=bat.percent, battery_stale=True)
            else:
                hand.flag(battery=None, battery_stale=False)
            await asyncio.sleep(5.0)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"   ※ 배터리 표시가 멎었습니다: {type(e).__name__}: {e}")


async def drive_loop(robot, hand):
    """휴대폰 조종판을 로봇 움직임으로 옮깁니다. 50Hz 로 돕니다.

    ★ 왜 이렇게 만드는가 ★

      게임패드 버튼은 우리에게 안 옵니다 (keys_test 로 확인 — 실제로
      로봇을 움직이는데도 우리 쪽 값은 0 뿐이었습니다). 그래서 조종을
      휴대폰으로 옮깁니다.

      그런데 버튼은 '누른 순간' 만 알려주고, 걷기는 '누르고 있는 동안'
      갑니다. 손 뗀 신호 하나를 놓치면 로봇이 계속 갑니다 — 복도에서요.

      그래서 반대로 만듭니다. 휴대폰이 **누르고 있다는 말을 계속**
      보내고, 그 말이 끊기면 멈춥니다 (remote.DEADMAN).
      화면이 가려져도, 네트워크가 끊겨도, 배터리가 나가도 멈춥니다.
      **놓쳐서 멈추는 것은 안전하고, 놓쳐서 계속 가는 것은 아닙니다.**

    ※ 조종판은 '다음' 버튼과 같은 규칙으로 켜집니다 (기다리는 중에만).
      설명·회전 중에 몰면 로봇이 자기 회전과 우리 조종을 동시에 받습니다.
    """
    import common
    import config
    lim = config.MAX_FORWARD_STICK
    yaw = config.MAX_YAW_STICK
    moving = False
    warned = False
    since = 0.0
    which = None
    beats = 0            # 이번 누름 동안 휴대폰이 보낸 신호 수
    last_beat = 0.0
    last_end = 0.0       # 앞 누름이 끝난 시각
    last_keys = ""
    while True:
        want = hand.stick()
        if want is not None and robot.get("busy"):
            want = None                    # 로봇이 스스로 움직이는 중
        if want is not None:
            fx, fy, fz = want
            common.joystick(robot["conn"],
                            **common.stick_from_intent(fx * lim, fy * lim,
                                                       fz * yaw))
            if not moving:
                moving = True
                since = time.time()
                which = set()
                beats = 0
                last_beat = 0.0
                if not robot["posture"].can_move() and not warned:
                    warned = True
                    print("     ※ 지금 자세로는 안 걷습니다 — 메뉴에서 '일어서기'")
            # 한 번 누르는 동안 조합이 바뀔 수 있습니다 (앞으로 → 앞으로+좌회전).
            # 무엇을 눌렀는지는 모아서 한 줄로 적습니다.
            which.update(hand.holding())
            # 휴대폰이 "아직 누르고 있다" 를 몇 번 보냈는지 셉니다.
            # 시각이 바뀌면 새 신호가 온 것입니다.
            newest = max(hand.held.values(), default=0.0)
            if newest > last_beat:
                last_beat = newest
                beats += 1
        elif moving:
            # 손을 뗐거나 소식이 끊겼습니다. 확실히 멈춥니다.
            for _ in range(3):
                common.joystick(robot["conn"], 0.0, 0.0, 0.0)
                await asyncio.sleep(0.02)
            await common.stop(robot["conn"])
            robot["facing"] = None         # 사람이 몰았으니 방향을 모릅니다
            # ★ 무엇을 재야 하는가 ★
            #
            #   처음에는 "0.6초보다 짧으면 끊긴 것" 으로 봤습니다. 그런데
            #   실제 로그를 보니 짧은 누름이 수십 번 나왔고, 그건 고장이
            #   아니라 **방향을 살짝 트는 정상적인 조작**이었습니다.
            #   0.3초짜리 톡톡 치기가 원래 그렇게 생겼습니다.
            #
            #   진짜 물어야 할 것은 **한 번 누른 것이 둘로 쪼개졌는가**
            #   입니다. 그건 길이가 아니라 **앞의 것과의 간격**에 나타납니다.
            #   손으로 두 번 치면 사이가 뜨고, 신호가 끊겨서 쪼개진 것이면
            #   거의 붙어 있습니다.
            #
            #   그래서 간격을 재고, 휴대폰이 몇 번 신호를 보냈는지도 같이
            #   적습니다. 0.4초 동안 신호가 3~4번이면 정상이고, 1번뿐이면
            #   심장박동이 안 온 것입니다.
            now = time.time()
            held = now - since
            keys = "+".join(sorted(which)) or "?"
            gap = since - last_end if last_end else 99.0
            note = ""
            if keys == last_keys and gap < 0.35:
                note = f"   ★ 앞의 것과 {gap * 1000:.0f}ms — 쪼개졌을 수 있습니다"
            elif held > 0.3 and beats <= 1:
                note = "   ★ 신호가 한 번뿐입니다"
            print(f"   ⟨조종⟩ {keys} {held:.1f}초 · 신호 {beats}회{note}")
            last_end, last_keys = now, keys
            moving = False
            warned = False
        await asyncio.sleep(0.02)


async def serve_jobs(robot, hand):
    """메뉴에서 누른 것들을 처리합니다 — 안내와 나란히 돌아갑니다.

    '다음' 과 성격이 다릅니다. 순서를 넘기는 것이 아니라 지금 당장
    하나 시키는 것이라, 기다리는 자리를 거치지 않습니다.
    ※ 서로 겹치지 않게 하나씩 처리합니다 (자물쇠).
    """
    import common
    lock = asyncio.Lock()
    conn = robot["conn"]
    while True:
        job = await hand.jobs.get()
        async with lock:
            # ★ 다리를 쓰는 것만 회전이 끝나기를 기다립니다 ★
            #   라이트·음성 인식은 언제 눌러도 됩니다. 자세는 다리를
            #   쓰므로, 도는 도중에 끼어들면 회전이 4초에서 8.2초가
            #   되고 우리가 재는 각도도 그동안 흐트러집니다 (실제 로그).
            #   회전은 길어야 4초라, 버리지 않고 기다립니다.
            if job in ("stand", "sit", "lie"):
                waited = 0.0
                while robot.get("turning") and waited < 12.0:
                    if waited == 0.0:
                        print(f"\n   ⟨메뉴: {job}⟩ — 회전이 끝나면 합니다")
                    await asyncio.sleep(0.1)
                    waited += 0.1
            try:
                if job in ("stand", "sit", "lie"):
                    print(f"\n   ⟨메뉴: {job}⟩")
                    await getattr(robot["posture"], job)()
                    hand.flag(posture=job)
                    robot["facing"] = None if job != "stand" else robot.get("facing")
                # ★ 메뉴에서 누른 것은 다 로그에 남겨야 합니다 ★
                #   자세는 ⟨메뉴: sit⟩ 으로 남는데 라이트는 안 남겼습니다.
                #   그래서 S5 에서 라이트가 여섯 번 오르내린 로그를 보고도
                #   **사람이 누른 것인지 안내가 켠 것인지 알 수가 없었습니다.**
                #   로그가 있는데 읽을 수 없는 것은 없는 것과 비슷합니다.
                elif job == "light_on":
                    print("\n   ⟨메뉴: 라이트 켜기⟩")
                    await common.light_on(conn)
                    hand.flag(light=True)
                elif job == "light_off":
                    print("\n   ⟨메뉴: 라이트 끄기⟩")
                    await common.light_off(conn)
                    hand.flag(light=False)
                elif job in ("vol_up", "vol_down"):
                    await set_volume(robot, hand,
                                     +1 if job == "vol_up" else -1)
                elif job == "mic":
                    await toggle_ears(robot, hand)
            except Exception as e:
                print(f"   ※ 메뉴 '{job}' 를 못 했습니다: {type(e).__name__}: {e}")


async def set_volume(robot, hand, step):
    """음량을 한 칸 올리거나 내립니다 (0~10).

    ★ 설명 도중에도 됩니다 ★
      다리를 쓰지 않습니다. 그리고 음량은 **그때 고쳐야 쓸모가
      있습니다** — 복도가 울린다는 걸 아는 순간은 로봇이 말하고 있는
      순간이고, 설명이 끝날 때까지 기다리라는 것은 고치지 말라는 말과
      같습니다.

    ★ 지금 값을 로봇에게 묻고 나서 움직입니다 ★
      우리가 마지막으로 보낸 값을 기억해 두었다가 거기서 더하면,
      다른 데서(앱이나 게임패드로) 바뀐 순간부터 화면의 숫자가
      거짓말을 시작합니다. 물어보는 값이 하나 더 오가는 것뿐입니다.
    """
    import common
    now = await common.get_volume(robot["conn"])
    if now is None:
        now = robot.get("volume")
    if now is None:
        import config
        now = getattr(config, "SPEAKER_VOLUME", 7)
        print("   ※ 지금 음량을 못 읽어서 설정값에서 시작합니다")
    want = max(0, min(10, int(now) + step))
    got = await common.set_volume(robot["conn"], want, verbose=False)
    if got is None:
        print(f"   ⟨음량⟩ 바꾸지 못했습니다 (지금 {now}/10)")
        return
    robot["volume"] = got
    hand.flag(volume=got)
    edge = ""
    if got == now and step:
        edge = " — 여기가 끝입니다"
    print(f"   ⟨음량⟩ {now} → {got} / 10{edge}")


async def read_volume(robot, hand):
    """시작할 때 한 번, 지금 음량을 읽어 화면에 띄웁니다."""
    import common
    got = await common.get_volume(robot["conn"])
    if got is None:
        print("[준비] 음량을 못 읽었습니다 — 메뉴에는 '—' 로 뜹니다")
        return
    robot["volume"] = got
    if hand:
        hand.flag(volume=got)
    print(f"[준비] 음량 {got}/10")


async def toggle_ears(robot, hand):
    """음성 인식 켜기/끄기.

    ★ 마이크는 이제 **폰** 에 있습니다 (2026-09, 삽질 기록 29) ★

      로봇에게는 귀가 없습니다 — 세 번 재서 확정했습니다. PC 마이크는
      복도에서 안 들립니다. 남은 것은 손에 든 폰이었습니다.

      폰이 누르는 동안 녹음해서 보내고, whisper 가 여기서 알아듣습니다.
      **인터넷은 안 씁니다.**

    ★ 알아채는 대신 누릅니다 ★
      PC 마이크 때는 소리 크기를 보고 말이 시작된 걸 알아챘습니다
      (`listener.start()` + `calibrate()`). 복도에서는 그게 안 됩니다 —
      방문객 소리, 발소리, 로봇 제 목소리가 다 '말이 시작됐다' 로
      걸립니다. 그래서 그 부분은 안 씁니다. 모델만 올리고, 소리
      덩어리는 화면이 보내줍니다.

      귀를 막는 문지기(ear_gate)도 필요 없어졌습니다. 안 누르면
      안 듣거든요. **켜고 끄는 판단이 사람 손가락 하나로 줄었습니다.**
    """
    ears = robot.get("ears")
    if ears is not None:                       # 켜져 있으면 끕니다
        robot["ears"] = None
        hand.ear = None                        # 화면의 단추가 먼저 막힙니다
        for key in ("task", "gate"):
            if ears.get(key):
                ears[key].cancel()
        try:
            ears["listener"].stop()
        except Exception:
            pass
        hand.flag(mic="off")
        print("   ⟨음성 인식 꺼짐⟩")
        return

    import stt
    hand.flag(mic="loading")
    print("\n   ⟨음성 인식 — 모델을 읽습니다. 처음이면 좀 걸립니다⟩")
    listener = stt.Listener(verbose=False)
    try:
        await asyncio.to_thread(listener.load_model)
    except Exception as e:
        hand.flag(mic="off")
        print(f"   ※ 음성 인식을 켜지 못했습니다: {type(e).__name__}: {e}")
        return

    async def hear(raw):
        """소리 덩어리 → (글자, 초). remote.py 가 부릅니다.

        옮기는 것과 알아듣는 것을 갈라두었습니다 — 안 들릴 때 어느
        쪽이 틀렸는지 가려야 하니까요 (29-2).
        """
        import web_mic
        audio = await asyncio.to_thread(web_mic.decode_to_16k, raw)
        text = await asyncio.to_thread(listener.transcribe, audio)
        return text, len(audio) / 16000

    hand.ear = hear
    task = asyncio.ensure_future(ear_loop(robot, hand, listener))
    robot["ears"] = {"listener": listener, "task": task, "gate": None}
    hand.flag(mic="on")
    print("   ⟨음성 인식 켜짐 — **폰** 의 마이크로 듣습니다⟩")
    print("     ※ 폰 화면의 '누르고 말하기' 를 누르고 있는 동안만 듣습니다.")
    print("     ※ https 주소로 열어야 폰이 마이크를 내줍니다.")


# ── ear_gate 는 없어졌습니다 (2026-09) ──────────────────────
#
#   로봇이 말하거나 도는 동안 마이크를 막던 문지기였습니다. PC 마이크가
#   늘 열려 있었기 때문에 필요했습니다 — 안 막으면 로봇이 제 목소리를
#   듣고 그걸 명령으로 알아들었습니다.
#
#   이제 **안 누르면 안 듣습니다.** 막을 것이 없어졌습니다. 사람이
#   손가락을 떼는 것이 문지기입니다.
#
#   지우면서 하나 확인했습니다: 화면의 'deaf'(잠깐 멈춤) 표시는
#   이제 안 뜹니다. 뜰 일이 없으니 맞습니다.

async def ear_loop(robot, hand, listener):
    """들은 말을 명령으로 옮깁니다.

    ★ 움직임은 여기서 하지 않습니다 ★
      들은 것은 '메뉴 버튼을 눌렀다' 와 같은 자리로 흘려보냅니다.
      말로 하든 손으로 하든 같은 길을 지나야, 한쪽만 고쳐지는 일이
      안 생깁니다.
    """
    import brain
    NEXT = ("다음", "안내", "안내해", "안내해줘", "시작", "계속")
    try:
        while True:
            # ★ 소리가 아니라 **글자** 를 기다립니다 ★
            #   여태 여기서 PC 마이크를 직접 들었습니다. 이제 폰이
            #   녹음을 보내고 remote.py 가 옮겨서 이 큐에 넣습니다.
            #   바뀐 것은 **글자가 어디서 오느냐** 한 곳뿐이고, 아래
            #   흘려보내는 부분은 그대로입니다 — 그래야 말로 하든
            #   손으로 하든 한 길을 지납니다.
            text = await hand.said.get()
            if not text:
                continue
            print(f"   ⟨들림⟩ {text}")
            plain = text.replace(" ", "")
            if any(w in plain for w in NEXT):
                hand._fire("go")
                continue
            name, _spec = brain.match_command(text)
            if name in ("sit", "stand", "lie"):
                hand.jobs.put_nowait(name)
            elif name in ("light_on", "light_off"):
                hand.jobs.put_nowait(name)
            elif name == "stop":
                hand._fire("stop")
            else:
                print("      (아는 명령이 아닙니다)")
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"   ※ 음성 인식이 멎었습니다: {type(e).__name__}: {e}")
        hand.flag(mic="off")
        robot["ears"] = None


async def turn(robot, degrees, why):
    """회전 한 번. **모든 회전은 여기를 지나갑니다.**

    ★ 왜 한 군데로 모으는가 ★
      로그에 이런 것이 찍혔습니다.

          [회전] -180도 …
             ⟨메뉴: lie⟩            ← 도는 도중에 엎드렸습니다
          [회전] -181도 · 8.2초     ← 4초짜리 회전이 8.2초

      메뉴는 안내와 나란히 돌아갑니다. 그 자체는 맞습니다 — 라이트나
      음성 인식은 언제 눌러도 됩니다. 그런데 **자세**는 다리를 씁니다.
      도는 중에 다리를 뺏으면 회전이 그만큼 늘어지고, 우리가 재는
      각도도 그동안 흐트러집니다.

      그래서 '지금 돌고 있다' 를 한 곳에 적어둡니다. 부르는 자리마다
      적으면 언젠가 한 곳이 빠집니다 — 이미 세 번 겪었습니다.

    ※ busy 는 덮어쓰지 않고 되돌려 놓습니다. do_stop 은 통째로
      interruptible 안에서 도는데, 여기서 False 로 내려버리면 설명
      중간에 조종판이 열립니다.
    """
    import common
    if why:
        print(f"   ⟨{why} {degrees:+.0f}도 회전⟩")
    was_busy = robot.get("busy", False)
    robot["busy"] = True
    robot["turning"] = True
    try:
        await common.turn_by(robot["conn"], degrees, probe=robot.get("probe"))
    finally:
        robot["turning"] = False
        robot["busy"] = was_busy
    robot["facing"] = None


async def interruptible(coro, robot, hand):
    """수행 하나를 돌리되, 도중에 '멈춤' 이 오면 끊습니다.

    ★ 빨간 버튼이 30초 뒤에 듣는 것은 정지가 아닙니다 ★
      멘트 하나가 30초입니다. 그 안에는 기다리는 자리가 없어서, 지금까지
      '멈춤' 은 설명이 다 끝난 뒤에야 반영됐습니다.
      수행과 '멈춤' 을 나란히 기다려서, 오는 쪽을 먼저 잡습니다.

    ※ 진짜 비상 정지는 여전히 게임패드 L2+B 입니다. 이건 네트워크를
      거치고, 네트워크는 시연장에서 가장 먼저 흔들리는 것입니다.
    """
    if hand is None:
        await coro
        return None

    hand.arm()
    robot["busy"] = True
    task = asyncio.ensure_future(coro)
    stop = asyncio.ensure_future(hand.wait_stop())
    try:
        await asyncio.wait({task, stop}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        if task.done():
            stop.cancel()
    robot["busy"] = False
    if task.done():
        return task.result()

    # 멈춤이 먼저 왔습니다 — 하던 것을 끊고 조용히 만듭니다
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    import common
    why = "안내 종료" if stop.result() == "end" else "멈춤"
    print(f"\n   ★ {why} ★")
    for label, work in (("소리", robot["hub"].pause()),
                        ("라이트", common.light_off(robot["conn"], verbose=False)),
                        ("움직임", common.stop(robot["conn"]))):
        try:
            await work
        except Exception as e:
            print(f"     ({label} 을 못 껐습니다: {type(e).__name__})")
    robot["facing"] = None
    return stop.result()


async def do_stop(robot, step, timer, allow_turns, hand=None):
    """정차 지점 하나.

    ★ '돌아야 하는가' 는 지금 어디를 보고 있느냐로 정합니다 ★

      처음에 '다시(repeat)냐 아니냐' 로 정했다가 틀렸습니다. "다시니까
      이미 문을 보고 있겠지" 라고 적어놨는데, **그게 참인 자리는 S4
      하나뿐입니다.** S2·S3 은 설명이 끝나면 복도 쪽으로 되돌리므로,
      '다시' 를 누르면 복도 벽을 향해 설명하고 라이트도 엉뚱한 데를
      비추게 됩니다.

      그래서 robot["facing"] 에 **지금 어느 문을 보고 있는지**를 적어둡니다.
      보고 있으면 안 돌고, 아니면 돕니다. 몇 번째 수행인지는 상관없습니다.
    """
    import common
    if hand is not None:
        hand.show(sid=step.sid, place=step.place, detail=step.purpose,
                  button="다음")
    print()
    print("─" * 70)
    print(f" {step.sid}  {step.place}   — {step.purpose}")
    print("─" * 70)

    # 문 쪽으로 돌아 라이트로 가리키기
    pointing = False
    if step.face == "door" and step.door_deg is not None:
        if robot.get("facing") == step.sid:
            print("   (이미 이 문을 보고 있습니다 — 돌지 않습니다)")
        elif allow_turns:
            await turn(robot, step.door_deg, "문 쪽으로")
        else:
            print(f"   (문 쪽으로 {step.door_deg:+.0f}도 — 제자리 모드라 건너뜁니다)")
        await common.light_on(robot["conn"])
        if hand is not None:
            hand.flag(light=True)
        pointing = True

    for line in step.lines:
        await do_gesture(robot, line.gesture, timer, allow_turns)
        await play_line(robot, step, line)

    if pointing:
        await common.light_off(robot["conn"])
        if hand is not None:
            hand.flag(light=False)
        if not getattr(step, "face_back", True):
            # 이 문으로 들어갈 것이므로 본 채로 둡니다 (S4 → M4)
            print("   (문을 본 채로 둡니다 — 이 문으로 들어갑니다)")
            robot["facing"] = step.sid
        else:
            if allow_turns and robot.get("facing") != step.sid:
                await turn(robot, -step.door_deg, "복도 쪽으로 되돌리기")
            robot["facing"] = None

    print(f"   … 질의응답 {scenario.QA_PAUSE:.0f}초")
    await asyncio.sleep(scenario.QA_PAUSE)


# ★ 회전은 common.turn_by 가 합니다 ★
#   여기에 스틱↔각속도 환산표(YAW_STICK / YAW_RATE)를 두고 시간으로
#   돌리고 있었는데, common.move 가 3초에서 자르는 바람에 112도가 넘는
#   회전은 전부 112도가 되고 있었습니다. 로그에는 "3.0초" 라고만
#   찍혔습니다. turn_by 는 나눠 보내고, 실제로 돈 각도를 재서 멈춥니다.


async def do_move(robot, step, allow_turns, hand=None):
    """이동 구간.

    hand 가 있으면 **로봇은 한 걸음도 걷지 않습니다.** 예고 멘트만 틀고,
    사람이 몰아서 다음 정차 지점에 도착했다는 신호를 기다립니다.
    """
    import common
    print()
    print(f" {step.sid}  {step.place}")

    cut = False                        # 멘트가 '멈춤' 으로 끊겼는가
    if step.text.strip():
        print(f"   ▶ {step.key}")
        print(f"     {step.text}")

        async def speak():
            await robot["hub"].play_by_uuid(robot["uuids"][step.key])
            await asyncio.sleep(scenario.seconds_for(step)[0] + 0.3)

        # ★ 이동 구간의 멘트만 못 끊고 있었습니다 ★
        #   정차 지점(do_stop)은 interruptible 로 감싸뒀는데 여기는
        #   맨몸이었습니다. M1 의 여는 인사가 제일 긴데, 하필 그동안
        #   '멈춤' 이 안 들었습니다. 같은 일은 같은 자리를 지나야 합니다.
        r = await interruptible(speak(), robot, hand)
        if r == "end":
            return "end"
        if r == "stop":
            cut = True

    # ── 출발 방향 잡기 ──
    #
    # ★ 여기가 비어 있었습니다 ★
    #   allow_turns 를 받아놓고 쓰지 않았습니다. 그래서 --turns 를 줘도
    #   정차점의 '문 쪽으로 돌기' 만 돌고 이동 구간은 한 번도 돌지 않았습니다.
    #   S2·S3·S4 가 도니까 도는 것처럼 보였을 뿐입니다.
    # ── 사람이 모는 구간 ──
    if hand is not None:
        # ★ 도는 것은 로봇이 합니다 ★
        #   조종하는 사람이 화면 버튼으로 180도를 돌리는 것은 고역이고,
        #   ±5도로 맞출 수도 없습니다. 각도는 이미 실측해 뒀으니
        #   로봇이 스스로 돌게 하고, 사람은 걷는 것만 맡습니다.
        #
        #   언제 도는지가 구간마다 다릅니다 (turn_when).
        #     M1  출발 전 — 방문객을 보다가 복도 쪽으로 돌고 나서 갑니다
        #     M5  도착 후 — 방 안까지 몰고 나서 방문객 쪽으로 돕니다
        #
        # ★ 한 구간에서 두 번 돌면 안 됩니다 ★
        #   '다시' 는 **설명을 한 번 더** 라는 뜻입니다. 그런데 같은
        #   구간을 다시 지나면서 180도를 또 돌면, 로봇은 왔던 쪽을
        #   보고 서 있게 됩니다. 이미 돈 회전은 robot["turned"] 에
        #   적어두고 건너뜁니다 (다음 구간으로 넘어갈 때 지웁니다).
        done = robot.setdefault("turned", set())
        turn_now = (step.turn_deg
                    and getattr(step, "turn_when", "before") == "before"
                    and f"{step.key}:before" not in done)
        turn_now_pending = bool(turn_now)   # 아래 안내 문구에 씁니다
        if cut:
            turn_now = False           # 멈추라고 했는데 돌면 안 됩니다
        if turn_now:
            await turn(robot, step.turn_deg, "출발 방향")
            done.add(f"{step.key}:before")

        bits = [f"{step.meters:.2f} m"] if step.meters else []
        if getattr(step, "narrow", False):
            bits.append("★ 문틀 — 좌우 0.19 m 씩입니다")
        where = step.place.split("→")[-1].strip()
        if cut:
            print("\n   … 멈췄습니다. 신호를 기다립니다")
            # 끊었으므로 회전도 안 했습니다. 그 사실을 숨기지 않습니다 —
            # '다시' 를 누르면 안내와 회전을 같이 다시 합니다.
            detail = ("멈췄습니다. '다시' 는 이 안내와 회전을 처음부터, "
                      "'다음' 은 회전 없이 넘어갑니다."
                      if turn_now_pending else
                      "멈췄습니다. 이어서 '다음', 한 번 더 들으려면 '다시'.")
        else:
            print(f"   ⟨사람이 몹니다 — {' · '.join(bits) if bits else '자리 고쳐 잡기'}⟩")
            print("     도착하면 신호를 주세요.")
            detail = ("문틀입니다. 양옆 0.19 m 씩 — 천천히."
                      if getattr(step, "narrow", False) else
                      (f"{step.meters:.1f} m 이동" if step.meters else "자리 고쳐 잡기"))
        hand.show(sid=step.sid, place=where, detail=detail,
                  button="도착했습니다")
        act = await hand.wait()
        # 사람이 몰았으니 어느 쪽을 보고 있는지 우리는 모릅니다
        robot["facing"] = None

        # 도착한 뒤에 도는 구간 (M5 — 방 안에서 방문객 쪽으로)
        if (act == "go" and step.turn_deg
                and getattr(step, "turn_when", "before") == "after"
                and f"{step.key}:after" not in done):
            hand.show(detail="방문객 쪽으로 돕니다…")
            await turn(robot, step.turn_deg, "방문객 쪽으로")
            done.add(f"{step.key}:after")
        return act

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
    robot["facing"] = None
    await asyncio.sleep(1.0)


async def run(conn, refresh=False, allow_turns=False, start_at=None,
              hand=None, course=None):
    import common
    import courses
    import safety

    # ★ 코스가 메뉴에 안 뜨는 이유는 여기서 말합니다 ★
    #   폴더에 course_*.py 를 두면 저절로 코스가 되는데, 못 읽었거나
    #   아직 초안이면 조용히 사라집니다. 시연 30분 전에 그걸 찾고
    #   있을 수는 없습니다.
    for note in courses.report():
        print(f"[코스] {note}")

    await common.prepare_motion(conn)
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    probe = common.StateProbe(conn)
    await probe.read()
    await common.set_volume(conn)

    print("\n[준비] 자세 확인")
    if not await common.ensure_standing(conn, probe=probe, ask=False):
        print("일으켜 세우지 못했습니다. 중단합니다.")
        return

    robot = {"conn": conn, "hub": None, "uuids": {}, "probe": probe,
             "battery": common.Battery(conn),
             "posture": common.Posture(conn, probe=probe)}
    robot["posture"].state = "stand"
    timer = Timer()
    robot["facing"] = None      # 지금 어느 문을 보고 있는가 (없으면 None)
    robot["ears"] = None
    robot["busy"] = False
    robot["turning"] = False    # 지금 스스로 도는 중인가 (메뉴가 봅니다)
    robot["turned"] = set()     # 이 구간에서 이미 끝낸 회전
    robot["volume"] = None      # 로봇에게 물어보기 전까지는 모릅니다
    jobs = asyncio.ensure_future(serve_jobs(robot, hand)) if hand else None
    wheel = asyncio.ensure_future(drive_loop(robot, hand)) if hand else None
    juice = asyncio.ensure_future(battery_loop(robot, hand)) if hand else None
    if hand:
        hand.flag(posture="stand", light=False,
                  mic="off" if hand.ears else "held")
    await read_volume(robot, hand)

    if hand:
        hand.show(courses=[c.brief() for c in courses.all_courses()])

    steps = []

    async def load_course(want):
        """코스를 갈아 끼우고, **그 코스의 멘트만** 만들어 올립니다.

        ★ 왜 여기서 올리는가 ★
          예전에는 프로그램을 켜자마자 올렸습니다. 코스가 하나일 때는
          그게 맞습니다. 둘이 되면 **고른 다음**이라야 합니다 —
          안 할 안내의 멘트를 올리느라 기다릴 이유가 없습니다.
          (21개에 10분이 걸린 적이 있습니다)

          이미 로봇에 있는 파일은 다시 안 올립니다. 그래서 코스를
          왔다 갔다 해도 느린 것은 처음 한 번뿐입니다.
        """
        nonlocal steps
        import voices
        scenario.use(want)
        print()
        print("=" * 70)
        print(f" {scenario.TITLE}")
        print(f" {scenario.ROUTE}")
        print("=" * 70)
        if hand:
            hand.show(sid="", place=want.name, button="…",
                      detail="멘트를 만들고 로봇에 올립니다…",
                      course={"id": want.id, "name": want.name},
                      can_pick=False, done=False, index=0, total=1)
        made, changed = await voices.build(refresh=refresh)
        paths = {k: p for k, (p, _s) in made.items()}
        print("\n[준비] 멘트를 로봇에 올립니다...")
        if changed and not refresh:
            print(f"       문장이 바뀐 {len(changed)}개는 로봇의 것도 "
                  f"갈아치웁니다: {', '.join(sorted(changed))}")
        robot["hub"], robot["uuids"] = await common.upload_all(
            conn, paths, replace=True if refresh else changed)
        print(f"[준비] 완료 — {len(robot['uuids'])}개")

        steps = list(scenario.SCENARIO)
        if start_at:
            idx = next((i for i, s in enumerate(steps)
                        if s.sid == start_at), None)
            if idx is None:
                print(f" ※ {start_at} 라는 구간이 없습니다. 처음부터 갑니다.")
            else:
                steps = steps[idx:]
        robot["facing"] = None
        robot["turned"] = set()

    await load_course(course or courses.default())
    if not allow_turns:
        print(" ★ 제자리 모드 — 걷지도 돌지도 않습니다 ★")
    else:
        print(" ★ 회전 포함 — 사방 0.5 m 이상 비어 있어야 합니다 ★")

    # ★ 앞으로만 갈 수 있는 for 문이었습니다 ★
    #   그래서 '다시' 를 눌러도 되돌아갈 자리가 없었습니다. 번호로 돌면
    #   같은 자리에 머무를 수도, 처음으로 갈 수도 있습니다.
    async def switch_course():
        """휴대폰에서 고른 코스로 갈아 끼웁니다. 못 하면 None."""
        want = courses.get(getattr(hand, "course_want", None))
        if want is None:
            print(f"\n ※ '{getattr(hand, 'course_want', None)}' 라는 코스가 "
                  f"없습니다. 코스를 그대로 둡니다.")
            return None
        if scenario.ACTIVE is not None and want.id == scenario.ACTIVE.id:
            return want
        print(f"\n ⟨코스 바꾸기⟩ {scenario.TITLE} → {want.name}")
        await load_course(want)
        return want

    async def ready():
        """시작 신호를 기다립니다.

        ★ 켜자마자 인사를 시작하면 안 됩니다 ★
          프로그램을 켜는 순간 로봇이 "안녕하십니까" 를 시작하고 있었습니다.
          그 사이에 로봇을 엘리베이터 앞까지 몰고, 일으켜 세우고,
          방문객이 모이기를 기다려야 하는데요.

          **시작하는 때는 사람이 정합니다.** 여기서 기다리는 동안에도
          조종판과 메뉴는 그대로 씁니다 — 오히려 그때 필요합니다.

        ★ 코스를 고를 수 있는 자리는 여기와 끝 화면뿐입니다 ★
          안내 도중에 대본을 갈아 끼우면, 로봇은 다른 안내의 3번
          구간부터 이어서 합니다. 그건 안내가 아닙니다.
        """
        if hand is None:
            return "go"
        while True:
            hand.show(sid="", place="준비됐습니다",
                      detail="로봇을 시작 위치(엘리베이터 앞)에 세우고, "
                             "방문객이 모이면 '안내 시작'.",
                      button="안내 시작", done=False, index=0,
                      total=len(steps), can_pick=True)
            print()
            print("=" * 70)
            print(f" 준비됐습니다 — {scenario.TITLE}")
            print(" 휴대폰에서 '안내 시작' 을 누르면 시작합니다.")
            print(" 그 전에 조종판으로 로봇을 시작 위치까지 몰 수 있습니다.")
            print(" (메뉴에서 코스 고르기·일어서기·라이트도 씁니다)")
            print("=" * 70)
            act = await hand.wait(allow=("go", "again", "restart",
                                         "end", "course"))
            if act != "course":
                hand.show(can_pick=False)
                return act
            picked = await switch_course()
            if picked is None:
                continue

    stop_asked = False
    restarting = False
    start_index = 0
    while not stop_asked:
        # 처음이거나 '처음부터' 로 돌아왔으면, 시작 신호를 기다립니다.
        # (마지막 인사만 다시 하는 경우는 start_index 가 0 이 아니라 건너뜁니다)
        if start_index == 0:
            act = await ready()
            if act in ("stop", "end"):
                break
        i, start_index = start_index, 0
        restarting = False
        # ★ 한 바퀴가 배터리를 얼마나 먹는지 여기서부터 잽니다 ★
        #   업로드 25분에 8% 가 든 것은 알지만 (0.32 %/분), 그동안
        #   로봇은 아무것도 안 했습니다. 걸을 때 몇 배가 되는지를
        #   아무도 모르고, 그 배수가 '한 번 더 돌아도 되는가' 를
        #   가릅니다. 짐작을 더 보태는 대신 적어둡니다.
        bat = robot.get("battery")
        lap_from = bat.percent if (bat and bat.fresh()) else None
        lap_start = time.time()
        while i < len(steps):
            step = steps[i]
            if hand is not None:
                hand.show(index=i, total=len(steps), done=False)

            if isinstance(step, scenario.Stop):
                r = await interruptible(
                    do_stop(robot, step, timer, allow_turns, hand=hand),
                    robot, hand)
                if r == "end":
                    stop_asked = True
                    break
                if hand is None:
                    i += 1
                    continue

                if r == "stop":
                    # 설명만 끊었습니다. 같은 자리에 서서 기다립니다 —
                    # 이어서 갈 수도, 다시 들려줄 수도 있습니다.
                    print("\n   … 멈췄습니다. 신호를 기다립니다")
                    hand.show(button="다음",
                              detail="멈췄습니다. 이어서 '다음', "
                                     "이 설명을 처음부터 들려주려면 '다시'.")
                elif i == len(steps) - 1:
                    break                      # 마지막 정차 — 아래에서 마무리
                else:
                    print("\n   … 다음으로 넘길 신호를 기다립니다")
                    hand.show(button="다음",
                              detail="다음 구간으로. ('다시' 는 이 설명을 한 번 더)")
                act = await hand.wait()
            else:
                act = await do_move(robot, step, allow_turns, hand=hand)
                if hand is None:
                    i += 1
                    continue

            if act == "end":
                stop_asked = True
                break
            # ★ 여기에 `if act == "stop": continue` 가 있었습니다 ★
            #   continue 는 같은 i 로 되돌아갑니다. 이동 구간이면 멘트도
            #   180도 회전도 처음부터 다시입니다 — **멈추라고 눌렀는데
            #   구간이 되살아났습니다.** 이제 '멈춤' 은 기다리는 자리까지
            #   오지 않습니다 (remote._fire 가 받지 않습니다).
            if act == "again":
                print("   ⟨다시⟩")
                continue                       # 같은 자리를 한 번 더
            if act == "restart":
                print("\n ⟨처음부터⟩ — 준비 화면으로 돌아갑니다\n")
                start_index = 0
                restarting = True
                robot["facing"] = None
                robot["turned"] = set()
                await common.ensure_standing(conn, probe=probe, ask=False)
                robot["posture"].state = "stand"
                break                          # 바깥 while 이 다시 돕니다
            i += 1
            robot["turned"] = set()            # 새 구간 — 회전은 아직입니다

        if hand is None or stop_asked:
            break
        if restarting:
            continue                 # '처음부터' — 끝 화면을 거치지 않습니다

        # ── 끝. 그런데 여기서 서버를 닫으면 안 됩니다 ──
        #   방문객 무리가 여럿이면 다음 무리가 옵니다. 여기서 끝내버리면
        #   조종하는 사람이 PC 로 걸어가서 다시 실행해야 합니다 —
        #   방금 없앤 바로 그 왕복입니다.
        # ★ 한 바퀴가 끝났습니다 — 값을 적어둡니다 ★
        #   사람이 종이에 적을 필요가 없고, 적는 것을 잊을 일도 없습니다.
        #   세 바퀴 쌓이면 common.PER_MINUTE 의 짐작이 잰 값으로 바뀝니다.
        if bat is not None and lap_from is not None and bat.fresh():
            # 코스 이름은 화면이 들고 있는 것을 씁니다 — load_course 가
            # 거기에 적어두고, 안내 중에는 안 바뀝니다.
            here = ((hand.state.get("course") or {}).get("id")
                    if hand is not None else None) or "?"
            row = common.log_lap(here, lap_from, bat.percent,
                                 time.time() - lap_start)
            if row:
                print()
                print(f" [배터리] 이번 바퀴: {row['from']}% → {row['to']}% "
                      f"({row['used']}%, {row['minutes']:.1f}분) "
                      f"= {row['per_minute']:.2f} %/분")
                # ★ 무엇을 안 세는지 말해둡니다 ★
                #   이 값은 '안내 시작' 을 누른 뒤부터입니다. 방문객을
                #   기다린 시간은 안 들어 있습니다 — 그 시간은 얼마든지
                #   길어질 수 있어서 코스의 값이 아닙니다.
                #   화면의 숫자로 직접 보면 더 많이 줄어든 것처럼
                #   보이는데, 그 차이가 기다린 몫입니다.
                print("          (기다린 시간은 빼고 잰 값입니다 — "
                      "'안내 시작' 부터 끝까지)")
                got = common.measured_per_minute()
                if got:
                    print(f"          쌓인 기록으로는 {got:.2f} %/분 입니다 "
                          "— 이제 짐작을 안 씁니다.")
                else:
                    print("          세 바퀴가 쌓이면 짐작 대신 이 값을 씁니다.")

        print()
        print("=" * 70)
        print(" 안내가 끝났습니다. 휴대폰에서 '처음부터' 를 누르면 다시 합니다.")
        print(" (끝내려면 메뉴의 '프로그램 종료' 또는 여기서 Ctrl+C)")
        print("=" * 70)
        # 끝 화면에서도 코스를 고를 수 있습니다 — 다음 무리에게 다른
        # 안내를 하는 일이 실제로 생깁니다.
        while True:
            hand.show(sid="끝", place="안내가 끝났습니다",
                      detail="다음 방문객이 오면 '처음부터' → 로봇을 데려다 놓고 "
                             "'안내 시작'. '다시' 는 마지막 인사만 한 번 더. "
                             "메뉴에서 다른 코스를 고를 수도 있습니다.",
                      button="처음부터", done=True, can_pick=True,
                      index=len(steps), total=len(steps))
            act = await hand.wait(allow=("go", "again", "restart",
                                         "end", "course"))
            if act != "course":
                hand.show(can_pick=False)
                break
            if await switch_course() is not None:
                # 코스가 바뀌었으니 마지막 인사만 다시 할 수는 없습니다
                act = "go"
                break
        if act in ("stop", "end"):
            break
        if act == "again":
            # 마지막 인사만 한 번 더 — 배웅이 겹칠 때 씁니다
            print("\n 마지막 인사를 한 번 더 합니다.\n")
            start_index = len(steps) - 1
        else:
            print("\n 처음 자리로 돌아갑니다. 로봇을 데려다 놓고 시작하세요.\n")
            start_index = 0
        robot["facing"] = None
        robot["turned"] = set()
        # S5 에서 엎드려 있습니다. 다시 세우고 시작합니다.
        await common.ensure_standing(conn, probe=probe, ask=False)
        robot["posture"].state = "stand"

    for t in (jobs, wheel, juice):
        if t:
            t.cancel()
    if robot.get("ears"):
        for _k in ("task", "gate"):
            if robot["ears"].get(_k):
                robot["ears"][_k].cancel()
        try:
            robot["ears"]["listener"].stop()
        except Exception:
            pass
    if hand is not None:
        hand.show(sid="", place="안내를 마쳤습니다", detail="",
                  done=True, index=len(steps), total=len(steps))
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
            # ★ 돌아나오는 것도 보여줍니다 ★
            #   여태 문 쪽으로 도는 것만 찍고 되돌아서는 것은 안 찍었습니다.
            #   S2·S3·S4 셋 다 되돌아서는데 계획에는 한 줄도 없었습니다.
            #   로봇이 **어느 쪽을 보고 다음 구간에 들어가는지**가 안 보이면,
            #   등을 돌린 채 인사하게 되는 것 같은 일을 복도에 가서야 압니다.
            #   실제로 ai_swe01 을 만들면서 그 자리를 코드로 파내야 했습니다.
            if step.face == "door" and step.door_deg is not None:
                if getattr(step, "face_back", True):
                    print(f"     ⟨복도 쪽 {-step.door_deg:+.0f}도 · 라이트 끄기⟩")
                else:
                    print("     ⟨★ 문을 본 채로 둡니다 — 이 문으로 들어갑니다 ★⟩")
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


def _pick_course(args):
    """--course <이름> 으로 처음 코스를 정합니다.

    휴대폰에서도 고를 수 있지만, PC 에서 바로 시작하는 경우와
    dry_run 에는 이 길이 필요합니다.
    """
    import courses
    if "--course" not in args:
        return courses.default()
    i = args.index("--course")
    cid = args[i + 1] if i + 1 < len(args) else ""
    got = courses.get(cid)
    if got is None:
        names = ", ".join(c.id for c in courses.all_courses())
        print(f" ※ '{cid}' 라는 코스가 없습니다. 있는 것: {names}")
        print("   기본 코스로 갑니다.")
        return courses.default()
    return got


async def main():
    import common
    args = sys.argv[1:]
    refresh = "--refresh" in args
    manual = "--manual" in args
    # ★ 사람이 모는 모드에서는 회전을 기본으로 켭니다 ★
    #   걷는 것은 사람이 하지만, 문 쪽으로 도는 것은 안내의 일부입니다
    #   (라이트로 문을 가리키는 그 동작). 복도가 좁으면 --no-turns 로 끄세요.
    allow_turns = ("--turns" in args) or (manual and "--no-turns" not in args)
    start_at = _start_at(args)

    print("=" * 70)
    print(" 안내 실행기  ★ 로봇이 말하고 자세를 바꿉니다 ★")
    print("=" * 70)
    hand = None
    if manual:
        print(" ★ 사람이 모는 모드 ★")
        print("   로봇은 한 걸음도 걷지 않습니다. 말하고, 돌고, 라이트를 켭니다.")
        print("   이동은 조종 장치로 하시고, 도착하면 휴대폰에서 신호를 주세요.")
        if allow_turns:
            print("   문 쪽 회전은 켜져 있습니다 (사방 0.5 m 필요, --no-turns 로 끔).")
    elif allow_turns:
        print(" --turns : 제자리 회전을 실제로 합니다. 사방 0.5 m 이상 비우세요.")
    else:
        print(" 제자리 모드 — 걷지도 돌지도 않습니다. 사방 1 m 면 충분합니다.")
    print(" 힘 빼기: 게임패드 L2+B, 동반 리모컨 P 두 번")

    if manual:
        import remote
        pin = None
        if "--pin" in args:
            i = args.index("--pin")
            pin = args[i + 1] if i + 1 < len(args) else None
        # ★ 음성 인식은 이제 기본으로 열려 있습니다 ★
        #   휴대폰 앱이 나올 때까지 잠가뒀던 것인데, 마이크가 PC 에
        #   있다는 사실은 그대로지만 **PC 옆에 사람이 있을 때는 쓸모가
        #   있습니다.** 잠가두면 그 경우까지 막습니다.
        #   켜고 끄는 것은 메뉴에서 하고, 아예 못 켜게 하려면 --no-ears.
        hand = remote.Remote(pin=pin, ears=("--no-ears" not in args))
        if not await hand.start():
            print(" 리모컨을 못 띄웠습니다. 중단합니다.")
            return
        print(" 휴대폰에서 화면이 보이면 Enter 를 누르세요.")

    print()
    if not await common.confirm("로봇 사방이 비어 있고, 조종 장치를 들고 계십니까?"):
        if hand:
            await hand.close()
        return

    conn = await common.connect()
    try:
        await run(conn, refresh=refresh, allow_turns=allow_turns,
                  start_at=start_at, hand=hand, course=_pick_course(args))
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
        if hand:
            await hand.close()


if __name__ == "__main__":
    # ★ --dry 는 로봇 라이브러리 없이 돌아갑니다 ★
    #   순서를 확인하는 일은 어디서든 되어야 합니다.
    if "--dry" in sys.argv[1:]:
        import courses as _c
        for _n in _c.report():
            print(f"[코스] {_n}")
        scenario.use(_pick_course(sys.argv[1:]))
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
