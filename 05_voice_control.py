# -*- coding: utf-8 -*-
"""
한국어 음성 제어.  ★ 로봇이 움직입니다 ★

사람이 한국어로 말하면 로봇이 알아듣고, 한국어로 답하고, 움직입니다.

  사람의 말
    → 마이크
    → whisper (한국어 인식, PC 에서 로컬 실행)
    → 판단
        ├ 등록된 명령이면  → 동작 + 응답        (항상)
        └ 그 밖의 말이면   → 자유 질의응답      (멈춰 있을 때만)
    → 한국어 음성 → 로봇 스피커

안전 설계
─────────
  · 로봇을 움직일 수 있는 것은 config.py 의 COMMANDS 에 적힌 것뿐입니다.
    LLM 은 말만 만들고 움직임에는 관여하지 않습니다.
  · 이동 중에는 자유 질의응답을 받지 않습니다.
  · 모든 이동은 config.py 의 속도·시간 상한 안에서만 나갑니다.
  · '정지'는 어떤 상태에서든 최우선으로 처리됩니다.

  실행 전 체크리스트
    □ 사방 2~3m 이상 트인 평평한 바닥
    □ 발끝의 비닐 포장 제거
    □ 배터리 50% 이상
    □ 리모컨을 든 사람이 대기 (P 버튼 두 번 = 힘 빼기)

    .\\run 05_voice_control.py
"""

import asyncio
import sys

import brain
import common
import config
import safety
import stt

conn = None


class Robot:
    """음성 명령을 실제 동작으로 옮깁니다."""

    def __init__(self, conn, speaker, listener=None):
        self.conn = conn
        self.speaker = speaker
        self.listener = listener          # 말하는 동안 귀를 막기 위해
        self.moving = False
        # 자세 전환은 공용 Posture 가 맡습니다.
        # (앉기·엎드림 사이를 직접 오갈 수 없고 서 있기를 경유해야 합니다)
        self.posture = common.Posture(conn)

    async def say_file(self, path):
        """로봇이 말합니다. 그동안 마이크는 닫아둡니다.

        ★ 이걸 안 하면 로봇이 자기 말을 듣습니다 ★
        "따라와" 에 대한 응답 "이쪽입니다. 저를 따라와 주세요" 안에
        '따라와' 가 들어 있어, 마이크가 그걸 주우면 같은 명령이 다시 걸립니다.
        로봇이 자기 말에 반응하며 끝없이 반복하게 됩니다.
        """
        if self.listener is None:
            await self.speaker.play(path)
            return
        with self.listener.deaf():
            await self.speaker.play(path)
            await asyncio.sleep(0.4)      # 방에 남은 울림이 잦아들 때까지

    async def say(self, text):
        """한국어 문장을 만들어 말합니다."""
        path = config.AUDIO_DIR / "adhoc" / (
            __import__("hashlib").md5(
                f"{text}|{config.TTS_VOICE}|{config.TTS_RATE}|{config.TTS_VOLUME}"
                .encode("utf-8")).hexdigest()[:8] + ".mp3")
        await common.make_tts(text, path)
        print(f"  🔊 \"{text}\"")
        await self.say_file(path)

    async def run(self, name, spec):
        """명령 하나를 수행합니다."""
        action = spec.get("action", "none")

        # 먼저 정해진 멘트가 있으면 말합니다
        key = spec.get("say")
        if key and key in config.PHRASES:
            await self.say(config.PHRASES[key])

        if action == "none":
            return

        # 정지는 자세와 무관하게 즉시. 어떤 상태에서든 최우선입니다.
        if action == "stop":
            await common.stop(self.conn)
            return

        if action == "sit":
            await self.posture.sit()
            return
        if action == "lie":
            await self.posture.lie()
            return
        if action == "stand":
            await self.posture.stand()
            return

        # 나머지는 전부 서 있는 상태를 거쳐야 합니다
        await self.posture.stand()

        if action == "hello":
            await common.sport(self.conn, "Hello")
            await asyncio.sleep(4)
        elif action in ("forward", "back", "left", "right"):
            x, y, z, dur = spec.get("move", (0.15, 0, 0, 1.5))
            self.moving = True
            try:
                await common.move(self.conn, x=x, y=y, z=z, duration=dur)
            finally:
                self.moving = False
        else:
            print(f"  [경고] 모르는 동작입니다: {action}")


async def handle(text, robot, ack_path):
    """들은 말 한 마디를 처리합니다."""
    name, spec = brain.match_command(text)

    if name:
        print(f"  ▶ 명령: {name}")
        # 즉시 짧게 대답해 지연을 덮습니다
        if ack_path is not None and spec.get("action") != "stop":
            await robot.say_file(ack_path)
        await robot.run(name, spec)
        return

    # 등록되지 않은 말 — 질의응답 영역
    if robot.moving:
        print("  · 이동 중에는 대화를 받지 않습니다 (무시)")
        return

    if not brain.llm_available():
        print("  · 등록된 명령이 아닙니다")
        await robot.say(config.FALLBACK_REPLY)
        return

    print("  · 질문으로 봅니다 — 답을 생각하는 중...")
    answer = await asyncio.to_thread(brain.ask, text)
    await robot.say(answer or config.FALLBACK_REPLY)


async def main():
    global conn

    print("=" * 64)
    print(" 한국어 음성 제어  ★ 로봇이 움직입니다 ★")
    print("=" * 64)

    # 1. 인식 준비 (로봇 연결 전에 — 모델 올리는 데 시간이 걸립니다)
    listener = stt.Listener()
    listener.load_model()

    # 2. 안내 멘트 준비
    print("\n[준비] 안내 멘트 확인...")
    paths = await common.make_all_phrases()
    ack_path = await common.make_tts(
        config.ACK_PHRASE, config.AUDIO_DIR / "adhoc" / "_ack.mp3")

    # 3. 질의응답 가능 여부
    if brain.llm_available():
        print("[준비] 자유 질의응답: 사용 가능 (멈춰 있을 때만)")
    else:
        print(f"[준비] 자유 질의응답: 꺼짐 — {brain.unavailable_reason()}")

    # 4. 안전 확인
    print()
    if not await common.confirm(
        "로봇 주변 2~3m 가 비어 있고, 발의 비닐을 제거했으며,\n"
        "비상 정지를 할 사람이 대기 중입니까?"
    ):
        print("취소했습니다.")
        return

    # 5. 연결
    conn = await common.connect()
    try:
        await session(conn, listener, paths, ack_path)
    finally:
        # ★ 정리는 반드시 살아 있는 이벤트 루프 안에서 ★
        # 루프가 끝난 뒤 asyncio.run() 으로 닫으려 하면 실패하고,
        # 로봇에 유령 세션이 남아 다음 실행이 연결조차 못 합니다.
        await shutdown()


async def session(conn, listener, paths, ack_path):
    await common.prepare_motion(conn)
    await common.set_volume(conn)

    # 넘어지면 즉시 힘을 빼는 감시. 자동 복구는 꺼둡니다.
    await safety.set_auto_recovery(conn, False)
    watchdog = safety.Watchdog(conn)
    watchdog.arm()
    speaker = common.Speaker(conn)
    robot = Robot(conn, speaker, listener)

    # 6. 마이크
    listener.start()
    listener.calibrate()

    print("\n" + "=" * 64)
    print(" 준비됐습니다. 로봇에게 말을 걸어보세요.")
    print("=" * 64)
    print(" 등록된 명령:")
    for name, spec in config.COMMANDS.items():
        print(f"   {name:9s} — {', '.join(spec['phrases'][:3])}")
    print()
    print(" 그만하려면 Ctrl+C")
    print("=" * 64 + "\n")

    await robot.say_file(paths["greet"])

    while True:
        text = await listener.listen()
        if not text:
            continue
        await handle(text, robot, ack_path)


async def shutdown():
    """어떤 식으로 끝나든 로봇을 안전하게 두고 연결을 닫습니다."""
    if conn is None:
        return
    try:
        await common.stop(conn)
    except Exception:
        pass
    await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨 — 로봇을 멈추고 연결을 닫았습니다.")
    except Exception as e:
        common.explain_error(e)
    print("종료. 전원을 끄기 전에  .\\run park.py  를 실행하세요.")
