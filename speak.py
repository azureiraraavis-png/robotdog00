# -*- coding: utf-8 -*-
"""
대화형 말하기 콘솔.  ★ 로봇이 움직이지 않습니다 ★

한국어를 입력하면 로봇이 그대로 말합니다.
등록된 안내 멘트도 골라서 들어볼 수 있고, 볼륨도 여기서 조절합니다.

    .\\run speak.py

명령
    아무 한국어 문장     그대로 말합니다 (즉석으로 음성을 만듭니다)
    :list               config.py 에 등록된 멘트 목록
    :greet  :bye  ...   등록된 멘트를 재생
    :all                등록된 멘트를 순서대로 전부 재생

    :vol                현재 볼륨 확인
    :vol 5              로봇 스피커 볼륨 (0~10). 눈금이 선형이 아니라
                        1 은 거의 안 들리고 7 이면 꽤 큽니다. 3~6 을 권합니다.
    :voltest            볼륨 3~8 을 차례로 들려줍니다. 듣고 고르세요.
    :voltest 2 6        구간을 지정할 수도 있습니다
    :diag               소리가 전혀 안 날 때. 03번과 똑같은 방식으로
                        한 번만 재생해 원인을 좁힙니다.

    :reconnect          연결을 닫고 다시 엽니다. 소리가 갑자기 안 날 때
                        스크립트를 껐다 켜는 것과 같은 효과입니다.

    :audio  /  :audio off
                        로봇 오디오 채널을 켜고 끕니다. 소리가 안 날 때
                        가장 먼저 확인할 항목입니다. (연결 시 자동으로 켭니다)

    :tts -20%           음성 파일 자체의 크기를 바꿉니다 (-100% ~ +100%).
                        로봇 볼륨으로는 너무 거칠 때 미세 조정용입니다.
                        다음 문장부터 적용됩니다.

    :quit               종료

이 스크립트가 다음 단계로 가는 다리입니다.
여기의 say_text() 에 음성 인식(STT) 결과를 그대로 넣으면
"사람이 한국어로 말하면 로봇이 한국어로 답하는" 구조가 완성됩니다.
"""

import asyncio
import hashlib
import sys
from pathlib import Path

import common
import config

# 즉석 문장은 여기에 쌓입니다 (audio/ 를 어지럽히지 않도록 분리)
TEMP_DIR = config.AUDIO_DIR / "adhoc"


async def say_text(speaker, text):
    """임의의 한국어 문장을 로봇이 말하게 합니다.

    같은 문장은 파일명이 같으므로, 두 번째부터는 생성 없이 바로 재생됩니다.
    (파이썬의 hash() 는 실행할 때마다 값이 달라져서 md5 를 씁니다)
    """
    # 목소리·속도·음량이 바뀌면 다른 파일이 되도록 키에 포함합니다.
    key = f"{text}|{config.TTS_VOICE}|{config.TTS_RATE}|{config.TTS_VOLUME}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]
    safe = "".join(c for c in text if c.isalnum())[:24] or "adhoc"
    path = TEMP_DIR / f"{digest}_{safe}.mp3"
    await common.make_tts(text, path)
    print(f"  🔊 \"{text}\"")
    await speaker.play(path)


async def volume_test(conn, speaker, low=3, high=8):
    """볼륨 단계를 차례로 들려줍니다."""
    print(f"\n  볼륨 {low} 부터 {high} 까지 차례로 들려드립니다.")
    print("  각 단계마다 '띠링' 확인음이 먼저 울리고, 이어서 목소리가 나옵니다.")
    print("  마음에 드는 값을 기억해 두었다가 :vol 로 설정하세요.\n")
    for level in range(low, high + 1):
        await common.set_volume(conn, level, verbose=False)
        await asyncio.sleep(1.0)          # 확인음이 끝나기를 기다립니다
        print(f"    볼륨 {level}/10")
        await say_text(speaker, f"볼륨 {level}입니다. 잘 들리시나요?")
        await asyncio.sleep(0.6)
    restored = await common.set_volume(conn, verbose=False)
    print(f"\n  원래 값({restored})으로 돌려놓았습니다.")
    print("  고른 값이 있으면  :vol 숫자  로 설정하고,")
    print("  계속 쓰시려면 config.py 의 SPEAKER_VOLUME 에 적어두세요.\n")


async def main():
    print("=" * 60)
    print(" 대화형 말하기 콘솔")
    print("=" * 60)
    print(" 한국어를 입력하면 로봇이 말합니다.")
    print(" :list  :all  :vol 8  :quit   (도움말은 :help)")
    print("=" * 60)

    state = {"conn": await common.connect()}
    try:
        await session(state)
    finally:
        # 어떤 식으로 끝나든 반드시 연결을 닫습니다.
        # 닫지 않으면 로봇에 유령 세션이 남아 다음 실행에서 소리가 안 납니다.
        # (:reconnect 로 연결이 바뀌어도 state 를 통해 최신 것을 닫습니다)
        await common.disconnect(state["conn"])


async def session(state):
    conn = state["conn"]
    await common.set_volume(conn)

    speaker = common.Speaker(conn)
    phrases = config.PHRASES

    print("\n준비됐습니다. 문장을 입력하세요.\n")

    while True:
        try:
            line = (await asyncio.to_thread(input, "> ")).strip()
        except EOFError:
            break

        if not line:
            continue

        # ── 명령 ──────────────────────────────────────────
        if line.startswith(":"):
            cmd, _, arg = line[1:].partition(" ")
            cmd = cmd.lower()
            arg = arg.strip()

            if cmd in ("quit", "exit", "q"):
                break

            if cmd == "help":
                print(__doc__)
                continue

            if cmd == "list":
                print("\n  등록된 멘트")
                for key, text in phrases.items():
                    print(f"    :{key:12s} {text}")
                print()
                continue

            if cmd == "vol":
                if arg:
                    await common.set_volume(conn, arg)
                else:
                    current = await common.get_volume(conn)
                    print(f"  현재 볼륨: {current}/10"
                          if current is not None else "  볼륨을 읽지 못했습니다")
                    print("  눈금이 선형이 아닙니다. 1~2 는 거의 안 들리고,")
                    print("  7 이상은 꽤 큽니다. :voltest 로 직접 들어보세요.")
                continue

            if cmd == "diag":
                # 예전에 "첫 문장만 들리던" 증상을 정확히 겨냥한 자가진단입니다.
                # 연속 재생이 되는지가 핵심이므로 세 번 연달아 말합니다.
                print("\n  진단 — 세 문장을 연달아 말합니다.")
                print("  예전에는 첫 번째만 들리고 나머지는 무음이었습니다.")
                print("  이제 셋 다 들려야 정상입니다.\n")
                common.enable_audio(conn, True)
                await asyncio.sleep(0.5)
                await common.set_volume(conn, 5)
                await asyncio.sleep(1.0)
                for n, text in enumerate(
                    ["첫 번째 문장입니다.",
                     "두 번째 문장입니다.",
                     "세 번째 문장입니다."], 1):
                    print(f"    {n}/3")
                    await say_text(speaker, text)
                print("\n  몇 개나 들렸나요?")
                print("    셋 다      → 해결됐습니다.")
                print("    첫 번째만  → 아직 남아 있습니다. 알려주세요.")
                print("    하나도 안  → :audio 로 채널을 켜고 다시 시도하세요.\n")
                continue

            if cmd in ("reconnect", "rc"):
                print("\n  연결을 닫고 다시 엽니다...")
                await common.disconnect(conn)
                await asyncio.sleep(2.0)
                conn = state["conn"] = await common.connect()
                await common.set_volume(conn)
                speaker = common.Speaker(conn)
                print("  새 연결 준비 완료\n")
                continue

            if cmd == "audio":
                common.enable_audio(conn, arg.lower() != "off")
                continue

            if cmd == "voltest":
                bounds = [int(v) for v in arg.split() if v.isdigit()]
                low, high = (bounds + [3, 8])[:2] if len(bounds) >= 2 else (3, 8)
                await volume_test(conn, speaker, low, high)
                continue

            if cmd == "tts":
                if not arg:
                    print(f"  현재 TTS 음량: {config.TTS_VOLUME}")
                    print("  예:  :tts -20%   (다음 문장부터 적용)")
                else:
                    if not arg.endswith("%"):
                        arg += "%"
                    if not arg.startswith(("+", "-")):
                        arg = "+" + arg
                    config.TTS_VOLUME = arg
                    print(f"  TTS 음량: {arg}  (다음 문장부터 적용)")
                continue

            if cmd == "all":
                for key, text in phrases.items():
                    print(f"\n  [{key}]")
                    await say_text(speaker, text)
                    await asyncio.sleep(0.5)
                print()
                continue

            if cmd in phrases:
                await say_text(speaker, phrases[cmd])
                continue

            print(f"  모르는 명령입니다: :{cmd}   (:help 로 목록 확인)")
            continue

        # ── 그냥 문장이면 말한다 ──────────────────────────
        await say_text(speaker, line)

    print("\n종료합니다.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)