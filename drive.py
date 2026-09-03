# -*- coding: utf-8 -*-
"""
키보드 조종.  ★ 로봇이 움직입니다 ★

키를 누르고 있는 동안 로봇이 움직입니다. 손을 떼면 멈춥니다.
적당한 이동 값을 감으로 찾거나, 안내 코스를 짜볼 때 쓰세요.

    .\\run drive.py

  조작
    W / S      앞으로 / 뒤로
    A / D      왼쪽 / 오른쪽 회전
    Q / E      왼쪽 / 오른쪽 게걸음
    Space      즉시 정지
    + / -      이동 크기 조절 (0.1 단위)
    1          일어서기
    2          앉기
    3          엎드리기
    X          힘 빼기 (비상)
    ESC        종료 (로봇을 눕히고 정리합니다)

  ★ 안전장치 ★
  키를 계속 누르고 있어야 움직이고, 손을 떼면 자동으로 멈춥니다.
  프로그램이 멈추거나 창이 닫혀도 로봇이 계속 가지 않습니다.

  ★ 이동 키는 꾹 누르고 계세요 ★
  톡톡 두드리면 로봇은 걸음을 떼지 않고 몸통만 기울입니다.
  걷기 시작하려면 신호가 끊기지 않고 이어져야 합니다.

  실행 전 체크리스트
    □ 사방 3m 이상 트인 평평한 바닥
    □ 조종 장치 손에 (힘 빼기: 게임패드 L2+B, 동반 리모컨 P 두 번)
    □ 배터리 확인
"""

import asyncio
import sys
import threading
import time

import common
import config
import safety

conn = None

# ★ 데드맨 스위치 — 왜 두 단계인가 ★
#
# 이 스크립트는 윈도우의 '키 반복' 입력으로 '지금 눌려 있음'을 판단합니다.
# 그런데 키를 누르면 반복이 **곧바로 시작되지 않습니다.** 첫 입력 뒤
# 0.5초쯤(윈도우 기본 '반복 지연') 조용하다가 그때부터 촘촘히 들어옵니다.
#
# 여기에 0.4초 데드맨을 걸었더니 이런 일이 벌어졌습니다.
#
#   0.0초  첫 입력 — 스틱 0.6 나감
#   0.4초  데드맨 만료 — 아직 반복이 안 왔으므로 스틱 0
#   0.5초  반복 시작 — 다시 스틱 0.6
#
# 로봇 입장에서는 0.4초 밀렸다가 끊기는 신호입니다. 걸음을 떼기에는
# 너무 짧아서 **무게중심만 옮기고 맙니다.** 그게 '몸통만 기우뚱'의 정체였습니다.
# (mode_test.py 에서 1.5초를 끊김 없이 주면 1.0 m/s 로 잘 걷습니다)
#
# 그래서 두 단계로 나눕니다.
#   · 반복이 아직 안 온 동안  → GRACE (길게 기다림)
#   · 반복이 들어오기 시작하면 → DEADMAN (짧게, 손 떼면 바로 정지)
GRACE = 0.7        # 첫 입력 뒤, 반복을 기다려 주는 시간
DEADMAN = 0.25     # 반복이 흐르는 중에 손을 뗐을 때 멈추기까지

# 자세 키는 눌러 봤자 이 시간 안에는 한 번만 처리합니다.
# 자세 키를 잠깐 누르고 있어도 윈도우 자동 반복이 초당 30번쯤 들어옵니다.
# 그걸 그대로 받으면 도움말이 스무 번 찍히고, 앉기 명령이 스무 번 쌓입니다.
TAP_REPEAT = 0.6


# 누르고 있는 동안 움직이는 키
HOLD_KEYS = ("w", "a", "s", "d", "q", "e")

# 한 번만 처리하는 키
TAP_KEYS = ("1", "2", "3", "x", "h", "r", "0", " ", "+", "=", "-", "_")


class Keyboard:
    """윈도우에서 키 입력을 계속 읽습니다.

    ★ 두 종류의 키를 따로 다룹니다 ★
      · 이동 키 — '지금 눌려 있는가'가 중요합니다. 손을 떼면 멈춥니다.
      · 자세 키 — '눌렸는가'가 중요합니다. 큐에 쌓아 두고 순서대로 처리합니다.

    처음에는 둘을 같은 변수에 담았는데, 앉기처럼 3초 걸리는 동작 중에
    누른 키가 데드맨 규칙에 걸려 **조용히 버려졌습니다.**
    (앉기 → 엎드리기가 이어지지 않던 원인이 이것이었습니다)
    """

    def __init__(self):
        self.pressed = None
        self.last_time = 0.0
        self.repeats = 0            # 같은 키가 연달아 들어온 횟수
        self.held_since = 0.0       # 이 키를 누르기 시작한 시각
        self.taps = []
        self._last_tap = None
        self._last_tap_time = 0.0
        self.quit = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self):
        self._thread.start()

    def _loop(self):
        try:
            import msvcrt
        except ImportError:
            print("[조종] 이 스크립트는 윈도우에서만 동작합니다.")
            self.quit = True
            return
        # 시작 전에 눌린 키는 버립니다.
        # 연결과 일어서기에 15초쯤 걸리는데, 그 사이에 누른 키가 콘솔 버퍼에
        # 쌓여 있다가 조종이 시작되는 순간 한꺼번에 실행됩니다.
        # 자세 명령이 의도치 않게 나가면 위험합니다.
        while msvcrt.kbhit():
            msvcrt.getch()

        while not self.quit:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b"\x1b", b"\x03"):        # ESC, Ctrl+C
                    self.quit = True
                    return
                try:
                    key = ch.decode("ascii").lower()
                except UnicodeDecodeError:
                    continue
                if key in TAP_KEYS:
                    # ★ 자동 반복 걸러내기 ★
                    # 큐 안에서만 중복을 지우면 소용없습니다. 본체가 하나
                    # 꺼내는 순간 다음 반복이 새 입력으로 들어가기 때문입니다.
                    # 시각으로 걸러야 합니다.
                    now = time.time()
                    if key == self._last_tap and now - self._last_tap_time < TAP_REPEAT:
                        self._last_tap_time = now      # 계속 누르고 있는 중
                        continue
                    self._last_tap = key
                    self._last_tap_time = now
                    with self._lock:
                        self.taps.append(key)
                elif key in HOLD_KEYS:
                    now = time.time()
                    if key == self.pressed and now - self.last_time < GRACE:
                        self.repeats += 1
                    else:
                        self.repeats = 0
                        self.held_since = now
                    self.pressed = key
                    self.last_time = now
            else:
                time.sleep(0.01)

    def current(self):
        """지금 눌려 있다고 볼 이동 키. 손을 뗐다고 판단되면 None.

        반복이 아직 시작되지 않았으면 넉넉히(GRACE) 기다립니다.
        반복이 흐르기 시작하면 짧게(DEADMAN) 봅니다 — 손을 떼면 바로 멈춥니다.
        """
        if not self.pressed:
            return None
        window = DEADMAN if self.repeats >= 1 else GRACE
        if time.time() - self.last_time < window:
            return self.pressed
        return None

    def held_for(self):
        """지금 키를 몇 초째 잡고 있는지. 안 눌려 있으면 0."""
        if self.current() is None:
            return 0.0
        return time.time() - self.held_since

    def take_tap(self):
        """처리할 자세 키를 하나 꺼냅니다. 없으면 None."""
        with self._lock:
            return self.taps.pop(0) if self.taps else None


def show_help():
    print("""
  이동  — 누르고 있는 동안 움직입니다
    W / S      앞으로 / 뒤로
    A / D      좌회전 / 우회전
    Q / E      왼쪽 / 오른쪽 게걸음

  자세
    1          일어서기      ← 이동하려면 이 상태여야 합니다
    2          앉기
    3          엎드리기
    X          힘 빼기 (비상)

  기타
    + / -      이동 크기 조절 (0.1 단위)
    Space      즉시 정지
    0          지금 로봇 상태 보기 (안 움직일 때 이걸 먼저 확인하세요)
    R          연결 다시 맺기 (비상용)
    H          이 도움말 다시 보기
    ESC        종료 — 로봇을 눕히고 정리합니다

  ★ 이동 키는 톡톡 두드리지 말고 꾹 누르고 계세요.
     짧게 끊어 주면 로봇은 걸음을 떼지 않고 몸통만 기울입니다.
  ★ 손을 떼면 자동으로 멈춥니다 (반복 입력이 흐르는 중에는 0.25초 안에).
  ★ 앉기·엎드리기·힘빼기 뒤에는 먼저 1 을 눌러 일으키세요.
  ★ 그래도 안 걸으면 R (연결 다시 맺기). 비상용입니다.
""")


async def main():
    global conn

    print("=" * 64)
    print(" 키보드 조종  ★ 로봇이 움직입니다 ★")
    print("=" * 64)
    show_help()

    if not await common.confirm(
        "사방 3m 가 비어 있고, 조종 장치를 든 사람이 대기 중입니까?"
    ):
        print("취소했습니다.")
        return

    conn = await common.connect()
    speed = config.MAX_FORWARD_STICK
    turn = config.MAX_YAW_STICK
    try:
        while True:
            outcome, speed, turn = await session(conn, speed, turn)
            if outcome != "reconnect":
                break
            # ★ R — 연결을 다시 맺습니다 ★
            # 자세를 바꾼 뒤 걷지 못하게 되는 문제가 남아 있는데, 지금까지
            # 확실히 통하는 방법은 '프로그램 재실행' 뿐이었습니다.
            # 그 중에서 실제로 효과가 있는 부분만 여기서 합니다.
            # (로봇은 선 채로 잠시 조종을 받지 않습니다)
            print("\n[재연결] 연결을 끊고 다시 맺습니다. 로봇은 선 채로 기다립니다...")
            try:
                await common.stop(conn)
            except Exception:
                pass
            conn = await common.reconnect(conn)
    finally:
        print("\n정리합니다...")
        try:
            await common.settle(conn)
        except Exception:
            pass
        await common.disconnect(conn)


async def session(conn, speed=None, turn=None):
    """조종 한 판. ("quit"|"reconnect", 이동크기, 회전크기) 를 돌려줍니다."""
    await common.prepare_motion(conn)
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()

    probe = common.StateProbe(conn)
    posture = common.Posture(conn, probe=probe)

    await probe.read()
    print(f"[상태] 시작 — {probe.describe()}")
    if probe.mode is None:
        print(f"       (동작 상태를 못 읽었습니다. 메시지 항목: {probe.fields})")

    print("\n[준비] 일어서기")
    await posture.stand()

    # 조이스틱 입력이 꺼져 있으면 신호를 통째로 무시합니다.
    await common.enable_joystick(conn, True)

    print(f"[상태] 조종 직전 — {probe.describe()}")

    kb = Keyboard()
    kb.start()

    if speed is None:
        speed = config.MAX_FORWARD_STICK
    if turn is None:
        turn = config.MAX_YAW_STICK

    print("\n" + "=" * 64)
    print(f" 준비됐습니다. 이동 크기 {speed:.1f}   (+ / - 로 조절)")
    print(" W A S D 로 움직이고, 키를 떼면 멈춥니다. ESC 로 종료.")
    print("=" * 64 + "\n")

    last_shown = None
    warned = None
    stalled = False
    outcome = "quit"
    next_report = 0.0
    while not kb.quit:
        # ── 자세 키 (큐에 쌓인 순서대로) ──────────────────────────
        tap = kb.take_tap()
        if tap is not None:
            if tap == "1":
                print("  일어서기")
                await posture.stand()
                await common.enable_joystick(conn, True, verbose=False)
                print(f"     → {probe.describe()}")
            elif tap == "2":
                print("  앉기")
                await posture.sit()
            elif tap == "3":
                print("  엎드리기")
                await posture.lie()
            elif tap == "x":
                print("  ★ 힘 빼기 ★")
                await posture.damp()
                print("     이동하려면 1 을 눌러 일으켜 세우세요.")
            elif tap == " ":
                await common.stop(conn)
                print("  정지")
            elif tap == "0":
                print(f"  [상태] {probe.describe()}")
                if probe.velocity:
                    vx, vy = probe.velocity[0], probe.velocity[1]
                    print(f"         앞뒤 {vx:+.2f}  좌우 {vy:+.2f} m/s"
                          f"   (부호가 반대면 config 의 YAW_SIGN 쪽을 보세요)")
                print(f"         기억된 자세: {posture.state}"
                      f"   mode 신뢰 가능: {'예' if probe.mode_is_useful() else '아니오 (항상 0)'}")
                if probe.fields:
                    print(f"         상태 항목: {probe.fields}")
            elif tap == "r":
                print("  ★ 연결 다시 맺기 ★")
                outcome = "reconnect"
                kb.quit = True
                continue
            elif tap == "h":
                show_help()
            elif tap in ("+", "="):
                speed = min(1.0, round(speed + 0.1, 1))
                turn = min(1.0, round(turn + 0.1, 1))
                print(f"  이동 크기 {speed:.1f}  회전 {turn:.1f}")
            elif tap in ("-", "_"):
                speed = max(0.1, round(speed - 0.1, 1))
                turn = max(0.1, round(turn - 0.1, 1))
                print(f"  이동 크기 {speed:.1f}  회전 {turn:.1f}")
            last_shown = None
            warned = None
            stalled = False
            continue

        key = kb.current()

        # ── 이동 키 ──────────────────────────────────────────────
        ly = lx = rx = 0.0
        if key == "w":
            ly = speed
        elif key == "s":
            ly = -speed
        elif key == "a":
            rx = turn
        elif key == "d":
            rx = -turn
        elif key == "q":
            lx = -speed
        elif key == "e":
            lx = speed

        moving = bool(ly or lx or rx)

        # 자세가 안 맞으면 알려주되, 신호는 그대로 보냅니다.
        # (막아버리면 상태 판단이 틀렸을 때 조종이 통째로 죽습니다)
        if moving and not posture.can_move() and warned != posture.state:
            print(f"  ※ 지금 {probe.mode_name()} 상태입니다 — 이동이 먹지 않을 수 있습니다."
                  f" 1 을 눌러 일으키세요.")
            warned = posture.state

        # 부호 변환은 common 이 한 군데에서 맡습니다 (A/D 가 반대로 돌던 문제)
        common.joystick(conn, **common.stick_from_intent(ly, lx, rx))

        label = key if moving else None
        if label != last_shown:
            if label:
                print(f"  {label.upper()}  전진={ly:+.1f} 게걸음={lx:+.1f} 회전={rx:+.1f}")
            last_shown = label
            stalled = False
            next_report = time.time() + 0.5

        # ★ 명령이 실제로 먹었는지는 측정 속도로만 알 수 있습니다 ★
        # 걸음을 떼려면 스틱이 **끊기지 않고** 이어져야 합니다.
        # '유지' 가 0.5초를 못 넘고 계속 끊긴다면, 키를 꾹 누르고 계신 게
        # 맞는지 확인하세요. 톡톡 두드리면 로봇은 몸만 기울입니다.
        if moving and time.time() >= next_report:
            s = probe.speed()
            held = kb.held_for()
            shown = f"{s:.2f} m/s" if s is not None else "?"
            yaw = f"{probe.yaw_speed:+.2f}" if probe.yaw_speed is not None else "?"
            print(f"      실제: 속도 {shown}  회전 {yaw} rad/s   유지 {held:.1f}초")

            # ★ 조용한 실패를 눈에 보이게 만듭니다 ★
            # 스틱을 1초 넘게 끊김 없이 주고 있는데 실제로는 거의 안 움직인다면,
            # 걷기 준비가 풀린 것입니다. 로그만 정상으로 보이는 그 상태입니다.
            if held >= 1.2 and not stalled:
                slow = (s is not None and s < 0.05)
                still = (probe.yaw_speed is None or abs(probe.yaw_speed) < 0.15)
                if slow and still:
                    stalled = True
                    print("      ※ 신호는 이어지는데 로봇이 거의 안 움직입니다.")
                    print("        1 을 눌러 다시 세워 보고, 그래도 안 되면 R (연결 다시 맺기).")
            next_report = time.time() + 0.5

        await asyncio.sleep(0.02)          # 50Hz

    # 확실히 정지
    for _ in range(5):
        common.joystick(conn, 0.0, 0.0, 0.0)
        await asyncio.sleep(0.02)
    await common.stop(conn)

    if outcome == "reconnect":
        return outcome, speed, turn

    print("\n" + "=" * 64)
    print(f" 마지막으로 쓰던 이동 크기: 전진 {speed:.1f}  회전 {turn:.1f}")
    print("=" * 64)
    print(" 마음에 드는 값을 찾으셨으면 config.py 에 적어두세요:")
    print(f"   MAX_FORWARD_STICK = {speed}")
    print(f"   MAX_YAW_STICK = {turn}")
    print(" 그리고 COMMANDS 의 move 값도 그에 맞게 조정하세요.")
    print("=" * 64)
    return outcome, speed, turn


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
