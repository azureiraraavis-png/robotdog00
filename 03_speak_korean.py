# -*- coding: utf-8 -*-
"""
3단계 — 로봇이 한국어로 말하게 하기.  ★ 이 프로젝트의 핵심 증명 ★

로봇은 움직이지 않습니다. 소리만 냅니다.

두 가지 경로를 모두 시도합니다.
  A. 스트리밍  — mp3 를 WebRTC 오디오 트랙으로 실시간 전송 (변환 불필요, 즉시)
  B. 업로드    — 로봇 내부 저장소에 올려두고 UUID 로 재생 (안내용으로 적합)

안내 로봇의 최종 형태는 B 입니다. 멘트를 미리 올려두고 필요할 때 호출하면
네트워크가 흔들려도 음성이 끊기지 않습니다.

    python 03_speak_korean.py
"""

import asyncio
import sys


import common
import config


async def path_a_streaming(conn, paths):
    """A: mp3 를 오디오 트랙으로 흘려보냅니다."""
    print("\n" + "─" * 60)
    print(" 경로 A — 스트리밍 재생")
    print("─" * 60)

    speaker = common.Speaker(conn)
    for key in ("greet", "follow_me"):
        print(f"[A] 재생: {key}  \"{config.PHRASES[key]}\"")
        await speaker.play(paths[key])

    print("\n[A] 두 문장 모두 들렸다면 정상입니다.")
    print("    소리가 안 났다면 볼륨(config.py 의 SPEAKER_VOLUME)을 확인하세요.")
    return speaker


async def path_b_upload(conn, paths):
    """B: 모든 멘트를 로봇에 올리고 하나 재생합니다."""
    print("\n" + "─" * 60)
    print(" 경로 B — 로봇에 업로드 후 재생")
    print("─" * 60)
    print(" 멘트를 로봇 내부에 저장해 두면, 이후에는 즉시 재생됩니다.")
    print(" 처음 한 번만 시간이 걸립니다 (멘트당 20~30초, 총 2~3분).")
    print(" 이미 올라가 있는 것은 건너뜁니다.\n")

    hub = common.make_audio_hub(conn)
    await common.show_robot_audio(hub)

    answer = input("\n업로드를 진행할까요? (y / Enter=건너뛰기): ").strip().lower()
    if answer != "y":
        print("\n[B] 건너뜁니다. 경로 A 만으로도 음성은 확인되었습니다.")
        return None, None

    print()
    _, uuids = await common.upload_all(conn, paths)
    print(f"\n[B] 업로드 완료: {len(uuids)}개")
    for key, uid in uuids.items():
        print(f"    {key:12s} {uid}")

    print()
    await common.say(hub, uuids, "greet", wait=6)
    return hub, uuids


async def main():
    print("=" * 60)
    print(" 한국어 음성 시험")
    print("=" * 60)
    print(f" 음성: {config.TTS_VOICE}")
    print("=" * 60)

    # 1. 인터넷으로 한국어 mp3 를 만듭니다 (로봇 연결 전에 미리)
    print("\n[TTS] 안내 멘트를 음성 파일로 만듭니다...")
    paths = await common.make_all_phrases()
    print(f"[TTS] 완료. {config.AUDIO_DIR} 에 {len(paths)}개")
    print("      → 지금 PC에서 직접 재생해보고 발음이 어색하면")
    print("        config.py 의 PHRASES 문구나 TTS_VOICE 를 바꾸세요.")

    # 2. 로봇에 연결
    conn = await common.connect()

    # 3. 볼륨 설정 (config.py 의 SPEAKER_VOLUME)
    await common.set_volume(conn)

    await path_a_streaming(conn, paths)
    await path_b_upload(conn, paths)

    print("\n" + "=" * 60)
    print(" 로봇이 한국어로 말했다면 — 프로젝트의 핵심이 증명된 것입니다.")
    print(" 다음: python 04_guide_demo.py")
    print("=" * 60)

    await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
        sys.exit(0)
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)