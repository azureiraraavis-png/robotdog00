# -*- coding: utf-8 -*-
"""
음성 인식 연습.  ★ 로봇에 연결하지 않습니다 ★

말을 알아듣는지, 그 말을 어떤 명령으로 판단하는지만 화면에 보여줍니다.
로봇은 전혀 관여하지 않으므로 꺼져 있어도 되고, 몇 번을 돌려도 안전합니다.

05_voice_control.py 로 넘어가기 전에 여기서 먼저 확인하세요.

  · whisper 모델이 제대로 받아졌는지
  · 마이크가 목소리를 잡는지
  · 한국어를 얼마나 정확히 옮기는지
  · 어떤 말투가 어떤 명령으로 잡히는지
  · 질문은 명령으로 오인되지 않는지

    .\\run test_listen.py

처음 실행하면 모델을 내려받느라 몇 분 걸립니다. 인터넷이 필요하고,
한 번 받아두면 그 뒤로는 오프라인으로 동작합니다.

그만하려면 Ctrl+C
"""

import asyncio
import sys

import brain
import config
import stt


def describe(text):
    """이 말을 05 가 어떻게 처리할지 보여줍니다."""
    name, spec, how, score = brain.match_detail(text)

    if name:
        action = spec.get("action", "none")
        say = spec.get("say")
        if how == "fuzzy":
            print(f"  ~ 정확히 일치하진 않지만 비슷해서 추정함 (유사도 {score:.2f})")
            print("     자주 이렇게 들린다면 config.py 의 phrases 에 추가하세요")
        line = f"  ▶ 명령으로 인식: {name}   (동작: {action}"
        if action in ("forward", "back", "left", "right"):
            x, y, z, dur = spec.get("move", (0, 0, 0, 0))
            line += f", x={x} y={y} z={z} {dur}초"
        line += ")"
        print(line)
        if say and say in config.PHRASES:
            print(f"     먼저 할 말: \"{config.PHRASES[say]}\"")
        if action in ("forward", "back", "left", "right"):
            print("     ※ 실제 실행하면 로봇이 움직입니다")
        return

    print("  · 등록된 명령이 아닙니다 → 질문으로 분류")
    if brain.llm_available():
        print("     (로봇이 멈춰 있으면 답변을 생성합니다)")
    else:
        print(f"     (질의응답이 꺼져 있어 \"{config.FALLBACK_REPLY}\" 라고 답합니다)")


async def main():
    print("=" * 64)
    print(" 음성 인식 연습  —  로봇에 연결하지 않습니다")
    print("=" * 64)

    listener = stt.Listener()
    listener.load_model()
    listener.start()
    listener.calibrate()

    print("\n" + "=" * 64)
    print(" 말해보세요. 알아들은 내용과 판단 결과를 보여드립니다.")
    print("=" * 64)
    print(" 등록된 명령:")
    for name, spec in config.COMMANDS.items():
        print(f"   {name:9s} — {', '.join(spec['phrases'][:4])}")
    print()
    print(" 이런 것도 해보세요:")
    print("   · \"앞으로 계획이 어떻게 되나요?\"  → 명령으로 잡히면 안 됩니다")
    print("   · \"여기 앉아서 쉬어도 되나요?\"    → 명령으로 잡히면 안 됩니다")
    print("   · 평소 말투로 자연스럽게, 그리고 조금 떨어져서도")
    print()
    print(" 그만하려면 Ctrl+C")
    print("=" * 64 + "\n")

    heard = 0
    matched = 0
    guessed = 0
    try:
        while True:
            text = await listener.listen()
            if not text:
                continue
            heard += 1
            name, _, how, _ = brain.match_detail(text)
            if name:
                matched += 1
                if how == "fuzzy":
                    guessed += 1
            describe(text)
            print()
    finally:
        listener.stop()
        print("\n" + "=" * 64)
        print(f" 들은 말 {heard}개, 그중 명령으로 인식 {matched}개"
              + (f" (추측으로 맞춘 것 {guessed}개)" if guessed else ""))
        print("=" * 64)
        print()
        print(" 인식이 잘 안 되면 config.py 에서 조정하세요")
        print("   · 말해도 반응이 없다  → STT_SENSITIVITY 를 낮추기 (예: 1.5)")
        print("   · 소음에 자꾸 반응한다 → STT_SENSITIVITY 를 올리기 (예: 3.5)")
        print("   · 자꾸 잘못 알아듣는다 → STT_MODEL 을 \"medium\" 으로")
        print("   · 너무 느리다          → STT_MODEL 을 \"base\" 로")
        print()
        print(" 알아듣는 말투가 다르다면 config.py 의 COMMANDS 에 추가하세요.")
        print(" 예: \"sit\" 의 phrases 에 실제로 자주 쓰는 표현을 넣기")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
        sys.exit(0)
    except Exception as e:
        print(f"\n[오류] {type(e).__name__}: {e}")
        if "faster_whisper" in str(e) or isinstance(e, ImportError):
            print("\n  음성 인식 패키지가 없습니다:")
            print("    .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt")
        sys.exit(1)
