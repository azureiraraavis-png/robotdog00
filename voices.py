# -*- coding: utf-8 -*-
"""
안내 멘트 음성 만들기 — 그리고 **길이를 실제로 재기**.  ★ 로봇이 필요 없습니다 ★

  지금까지 시간표의 '추정' 칸은 글자 수로 어림한 값이었습니다.
      글자수 ÷ 5.5 + 쉼표·마침표 휴지
  대충은 맞지만, 문서가 "한 지점 15~25초" 를 요구하는데 어림값으로
  넘었느니 아니니를 따지는 건 우스운 일입니다. 실제로 만들어서 재면 됩니다.

  ★ 여기서 만드는 파일이 그대로 로봇에 올라갑니다 ★
    04_guide_demo 나 안내 실행기가 쓰는 것과 **같은 파일, 같은 처리**입니다.
    따로 만들어 두고 나중에 다시 만드는 게 아닙니다. 그래서 여기서 들은
    소리가 로봇에서 나올 소리입니다 (스피커 특성만 빼면).

  쓰는 법

      .\\run voices.py                 만들고 길이를 잽니다
      .\\run voices.py --play          만들고 순서대로 들려줍니다
      .\\run voices.py --play s1_welcome    하나만 들어봅니다
      .\\run voices.py --refresh       기존 파일을 지우고 다시 만듭니다
                                      (멘트나 목소리를 바꿨을 때)

  재는 값은 audio/durations.json 에 남고, scenario.py 가 그걸 읽어
  시간표의 '추정' 칸을 **실측**으로 바꿉니다.

  ※ 만들 때만 인터넷이 필요합니다 (edge-tts 가 마이크로소프트 서버를 씁니다).
    한 번 만들어두면 그다음부터는 필요 없습니다.
"""

import asyncio
import json
import sys
from pathlib import Path

import common
import config
import scenario

DURATIONS = Path(config.AUDIO_DIR) / "durations.json"

# ★ 어떤 문장으로 만든 파일인지 적어둡니다 ★
#
# make_tts 는 "파일이 있으면 건너뛴다" 입니다. 빠르지만 함정이 있습니다 —
# **멘트를 고쳐도 옛날 음성이 그대로 남습니다.** 실제로 당했습니다.
# config.PHRASES 에 같은 이름의 다른 문장이 있어서, 문서에서 가져온 새
# 문장 대신 옛날 파일이 쓰였고 로그에는 아무 이상 없이 찍혔습니다.
# (실측 길이가 추정보다 짧게 나온 한 줄이 유일한 단서였습니다)
#
# 그래서 만든 문장을 같이 적어두고, 달라졌으면 다시 만듭니다.
# 이러면 --refresh 를 잊어도 안전합니다. 사람은 잊습니다.
TEXTS = Path(config.AUDIO_DIR) / "texts.json"


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}


def wav_seconds(path):
    """wav 파일의 길이 (초). 못 읽으면 None."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        try:
            import wave
            with wave.open(str(path), "rb") as w:
                return w.getnframes() / float(w.getframerate())
        except Exception:
            pass
    try:
        from pydub import AudioSegment
        return len(AudioSegment.from_file(str(path))) / 1000.0
    except Exception:
        return None


def play(path):
    """PC 스피커로 재생합니다. 끝날 때까지 기다립니다.

    윈도우의 winsound 는 파이썬에 기본으로 들어 있고 PCM wav 를 그대로
    재생합니다. 추가 설치가 필요 없어서 이걸 먼저 씁니다.
    """
    path = Path(path)
    try:
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return True
    except Exception:
        pass

    # 윈도우가 아니거나 winsound 가 안 되면 ffplay (pydub 이 있으면 대개 같이 있습니다)
    import shutil
    import subprocess
    for player in ("ffplay", "afplay", "aplay"):
        exe = shutil.which(player)
        if not exe:
            continue
        args = [exe, "-nodisp", "-autoexit", "-loglevel", "quiet", str(path)] \
            if player == "ffplay" else [exe, str(path)]
        try:
            subprocess.run(args, check=False)
            return True
        except Exception:
            continue
    print(f"     ※ 재생기를 못 찾았습니다. 직접 열어보세요: {path}")
    return False


async def build(refresh=False):
    """멘트를 전부 만들고 길이를 잽니다.

    돌려주는 값: ({key: (wav경로, 초)}, 새로 만든 키들)

    ★ 두 번째 값이 중요합니다 ★
      바뀐 것을 지역에서 다시 만드는 것만으로는 부족합니다. 로봇에 있는
      같은 이름의 옛 파일도 갈아치워야 합니다. 그러지 않으면 화면에는
      새 문장이, 스피커에서는 옛 문장이 나옵니다.
      이 목록을 common.upload_all(replace=...) 에 그대로 넘기세요.
    """
    out_dir = Path(config.AUDIO_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    phrases = scenario.phrases()
    if refresh:
        n = 0
        for key in phrases:
            for ext in (".mp3", ".wav"):
                f = out_dir / f"{key}{ext}"
                if f.exists():
                    f.unlink()
                    n += 1
        print(f"[정리] 기존 파일 {n}개를 지웠습니다.\n")

    # 지난번에 어떤 문장으로 만들었는지 보고, 달라진 것만 지웁니다
    known = load_json(TEXTS)
    stale = [k for k, t in phrases.items()
             if k in known and known[k] != scenario.for_tts(t)]
    unknown = [k for k in phrases if k not in known
               and (out_dir / f"{k}.mp3").exists()]
    for key in stale + unknown:
        for ext in (".mp3", ".wav"):
            f = out_dir / f"{key}{ext}"
            if f.exists():
                f.unlink()
    if stale:
        print(f"[갱신] 문장이 바뀐 멘트 {len(stale)}개를 다시 만듭니다: "
              f"{', '.join(stale)}\n")
    if unknown:
        print(f"[갱신] 어떤 문장으로 만들었는지 모르는 파일 {len(unknown)}개를 "
              f"다시 만듭니다: {', '.join(unknown)}")
        print("       (다른 스크립트가 같은 이름으로 만들어 둔 것일 수 있습니다)\n")

    made = {}
    for i, (key, text) in enumerate(phrases.items(), 1):
        print(f"[{i:2d}/{len(phrases)}] {key}")
        mp3 = await common.make_tts(scenario.for_tts(text), out_dir / f"{key}.mp3")
        wav = common.prepare_wav(mp3, verbose=True)
        secs = wav_seconds(wav)
        made[key] = (wav, secs)
        if secs is not None:
            print(f"          {secs:.1f}초")

    # scenario.py 가 읽을 수 있게 남깁니다
    data = {k: round(s, 2) for k, (_p, s) in made.items() if s is not None}
    DURATIONS.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    TEXTS.write_text(json.dumps(
        {k: scenario.for_tts(t) for k, t in phrases.items()},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{DURATIONS.name} 에 길이를, {TEXTS.name} 에 문장을 저장했습니다.")
    return made, set(stale) | set(unknown)


def report(made):
    """추정과 실측을 나란히 놓고 봅니다."""
    pad = scenario._pad
    print()
    print("=" * 70)
    print(" 멘트 길이 — 추정 vs 실측")
    print("=" * 70)
    print(f"{pad('멘트', 18)}{pad('글자', 6, True)}{pad('추정', 8, True)}"
          f"{pad('실측', 8, True)}{pad('차이', 8, True)}   비고")
    print("-" * 70)

    order = scenario.ordered_keys()
    order += [k for k in made if k not in order]

    for key in order:
        if key not in made:
            continue
        wav, secs = made[key]
        text = scenario.phrases().get(key, "")
        est = scenario.estimate_seconds(text)
        n = len(text.replace(" ", ""))
        if secs is None:
            print(f"{pad(key, 18)}{pad(str(n), 6, True)}"
                  f"{pad(f'{est:.0f}초', 8, True)}{pad('—', 8, True)}")
            continue
        note = ""
        step, _line = scenario.find(key)
        if isinstance(step, scenario.Stop) and secs > scenario.MENT_MAX_SECONDS:
            note = f"★ {scenario.MENT_MAX_SECONDS:.0f}초 초과"
        print(f"{pad(key, 18)}{pad(str(n), 6, True)}"
              f"{pad(f'{est:.0f}초', 8, True)}{pad(f'{secs:.1f}초', 8, True)}"
              f"{pad(f'{secs - est:+.1f}', 8, True)}   {note}")

    # ── 어림값이 얼마나 맞았나 ──
    pairs = [(scenario.estimate_seconds(scenario.phrases()[k]), s)
             for k, (_p, s) in made.items() if s is not None]
    if pairs:
        err = sum(abs(e - a) for e, a in pairs) / len(pairs)
        ratio = sum(a for _e, a in pairs) / max(1e-9, sum(e for e, _a in pairs))
        print("-" * 70)
        print(f" 어림값 평균 오차 {err:.1f}초,  실측이 추정의 {ratio * 100:.0f}%")
        if abs(ratio - 1) > 0.12:
            hint = scenario.CHARS_PER_SECOND / ratio
            print(f" → scenario.py 의 CHARS_PER_SECOND 를 "
                  f"{scenario.CHARS_PER_SECOND} → {hint:.1f} 로 고치면 맞습니다.")
            print("   (음성을 못 만든 곳에서도 어림이 정확해집니다)")


async def main():
    args = [a for a in sys.argv[1:]]
    refresh = "--refresh" in args
    do_play = "--play" in args
    only = [a for a in args if not a.startswith("--")]

    print("=" * 70)
    print(" 안내 멘트 음성 만들기  ★ 로봇이 필요 없습니다 ★")
    print("=" * 70)
    print(f" 목소리 {config.TTS_VOICE}   속도 {config.TTS_RATE}"
          f"   음량보정 {'켜짐' if config.TTS_NORMALIZE else '꺼짐'}")
    print()

    made, _changed = await build(refresh=refresh)
    report(made)

    if not do_play:
        print()
        print(" 들어보시려면:  .\\run voices.py --play")
        return

    targets = only or scenario.ordered_keys()
    print()
    print("=" * 70)
    print(" 재생 — Ctrl+C 로 언제든 멈출 수 있습니다")
    print("=" * 70)
    for key in targets:
        if key not in made:
            print(f" ※ {key} 는 없는 멘트입니다.")
            continue
        wav, secs = made[key]
        step, line = scenario.find(key)
        where = f"  ({step.place})" if step is not None else ""
        if line is not None and line.gesture:
            where += f"  ⟨{line.gesture}⟩"
        print(f"\n▶ {key}{where}   {secs:.1f}초" if secs else f"\n▶ {key}{where}")
        print(f"  {scenario.phrases()[key][:60]}...")
        await asyncio.to_thread(play, wav)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
