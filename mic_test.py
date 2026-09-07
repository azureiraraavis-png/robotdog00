# -*- coding: utf-8 -*-
"""
로봇에게 귀가 있는가 — 로봇 마이크 소리가 우리에게 오는지 확인합니다.

  ★ 왜 확인해야 하는가 ★

    안내를 사람이 몰기로 정했습니다. 그러면 "안내해" 를 어디서 듣느냐가
    남습니다. 지금은 **PC 마이크**로 듣고 있는데, 조종하는 사람은 복도에
    있고 PC 는 방에 있을 수 있습니다. 로봇이 직접 들을 수 있다면 그
    문제가 통째로 사라집니다.

    라이브러리 소스를 보면 통로는 열려 있습니다.

        self.pc.addTransceiver("audio", direction="sendrecv")
                                                   ~~~~~~~~
        async def frame_handler(self, frame): ...   ← 받는 자리

    ★ 그런데 '통로가 있다' 와 '소리가 온다' 는 다릅니다 ★
    우리는 지금까지 보내는 쪽만 썼습니다. 받는 쪽은 한 번도 안 켜봤습니다.
    코드가 있으니 될 것이라고 적어두는 것은 확인이 아닙니다.

  ★ 이 시험이 스스로 채점합니다 ★

    소리가 오느냐만 보면 안 됩니다. **조용한 구간에도** 프레임은 올 수
    있습니다 (무음이든 잡음이든). 그래서 조용할 때와 소리 낼 때를
    번갈아 재고, **차이가 나는지**를 봅니다. 차이가 없으면 마이크가
    아니라 그냥 무음 통로입니다.

        1. 조용히    5초   ← 바닥값
        2. 말하기    5초   ← 로봇 가까이에서
        3. 조용히    5초   ← 다시 바닥값으로 돌아오는지

    2번이 1번·3번보다 뚜렷하게 커야 '듣고 있다' 입니다.

  ★ 재본 결과 (2026-09-07) ★

    프레임은 옵니다. 진짜 형식입니다.

        920개 · 초당 50개 · 48000 Hz · stereo
        1,920 표본/프레임 = 20 ms      ← 규격에 맞습니다

    그런데 소리가 안 담겨 있습니다.

        조용히          -36.7 dB
        말하기          -36.7 dB      ← 똑같습니다
        다시 조용히      -36.7 dB

    ★ 소수점까지 세 번 같은 것이 오히려 단서입니다 ★
    진짜 소리는 조용할 때도 값이 흔들립니다. 세 구간이 -36.7 로
    딱 같다는 것은 **일정한 레벨을 만들어내는 무언가**라는 뜻이지
    마이크가 조용한 것이 아닙니다. (0.0146 rms ≒ int16 으로 479)

  ★ 안 열어본 문 ★

    라이브러리 상수에 이런 것이 있습니다.

        "ASSISTANT_RECORDER": "rt/api/assistant_recorder/request"

    **라이브러리 어디서도 안 씁니다.** 앱의 음성 비서가 녹음할 때
    쓰는 것으로 보입니다. 전방 라이트를 찾았던 그 모양 그대로입니다 —
    상수표에만 있고 아무도 안 부르는 서비스. 그때도 "컨트롤러 기능인
    줄 알았는데 실은 VUI 서비스의 brightness" 였습니다.

    그러니 지금 결론은 "귀가 없다" 가 아닙니다.
    **"통로는 열렸는데 아무것도 안 흐르고, 안 열어본 문이 있다."**

    다만 음성 인식은 휴대폰 앱까지 보류하기로 했으므로, 여기까지
    적어두고 멈춥니다. 열어볼 때는 light_test.py 처럼 api_id 를
    훑는 방식이 맞습니다 (홀수=설정, 짝수=조회).

  ※ 위 판정을 한 번 더 확인하려면 --save 로 wav 를 남겨 직접
    들어보세요. 쉭 하는 잡음뿐이면 통로가 정말 빈 것이고, 말소리가
    희미하게라도 들리면 **제 재는 방법이 틀린 것**입니다.

  쓰는 법

      .\\run mic_test.py            15초 시험
      .\\run mic_test.py --save     받은 소리를 wav 로 남깁니다
                                    (직접 들어보거나 whisper 에 넣어볼 수 있게)

    ★ 로봇은 움직이지 않습니다. 이동 명령을 한 줄도 보내지 않습니다 ★
    엎드려 있어도 됩니다 — 마이크는 자세와 상관없습니다.

  ※ 시험 중에는 로봇이 말하지 않습니다. 자기 스피커 소리를 자기 마이크가
    다시 듣는 것(에코)은 따로 봐야 하는 문제라, 여기서는 섞지 않습니다.
"""

import asyncio
import math
import sys
import time
from pathlib import Path

import numpy as np

import common

PHASES = [("조용히 해주세요", 5.0), ("★ 로봇 가까이에서 말해주세요 ★", 5.0),
          ("다시 조용히", 5.0)]
BAR = 46


class Ear:
    """받은 오디오 프레임을 모읍니다."""

    def __init__(self):
        self.frames = 0
        self.samples = 0
        self.rate = None
        self.layout = None
        self.chunks = []          # (시각, rms)
        self.pcm = []             # --save 일 때만
        self.keep = False
        self.first_at = None
        self.error = None

    async def on_frame(self, frame):
        try:
            arr = frame.to_ndarray()
        except Exception as e:                      # 형식이 예상과 다르면
            if self.error is None:
                self.error = f"프레임을 못 읽었습니다: {e!r}"
            return
        now = time.time()
        if self.first_at is None:
            self.first_at = now
            self.rate = getattr(frame, "sample_rate", None)
            self.layout = getattr(getattr(frame, "layout", None), "name", None)
        self.frames += 1

        a = np.asarray(arr, dtype=np.float64)
        if a.size == 0:
            return
        # 정수 PCM 이면 -1~1 로 맞춥니다
        if np.issubdtype(np.asarray(arr).dtype, np.integer):
            a = a / 32768.0
        self.samples += a.size
        rms = float(np.sqrt(np.mean(a * a)))
        self.chunks.append((now, rms))
        if self.keep:
            self.pcm.append(np.clip(a.reshape(-1), -1.0, 1.0))


def db(rms):
    return 20 * math.log10(max(rms, 1e-9))


def meter(rms):
    """-60 dB ~ 0 dB 를 막대로."""
    x = max(0.0, min(1.0, (db(rms) + 60) / 60))
    n = int(round(x * BAR))
    return "█" * n + "·" * (BAR - n)


def window(ear, t0, t1):
    """구간 안의 rms 들. 없으면 빈 목록."""
    return [r for t, r in ear.chunks if t0 <= t < t1]


def verdict(ear, marks):
    print()
    print("=" * 70)
    print(" 그래서 로봇에게 귀가 있는가")
    print("=" * 70)

    if ear.error:
        print(f" ※ {ear.error}")

    if ear.frames == 0:
        print(" ★ 오디오 프레임이 하나도 오지 않았습니다 ★")
        print("   통로는 열려 있는데(sendrecv) 로봇이 아무것도 안 보냅니다.")
        print("   → 마이크는 이 길로는 못 씁니다. PC 마이크나 무선 마이크를")
        print("     써야 합니다. 이것도 답입니다 — 이제 추측하지 않아도 됩니다.")
        return False

    took = (ear.chunks[-1][0] - ear.first_at) or 1e-9
    print(f" 프레임 {ear.frames}개 · 초당 {ear.frames / took:.0f}개")
    print(f" 표본 {ear.samples:,}개"
          + (f" · {ear.rate} Hz" if ear.rate else "")
          + (f" · {ear.layout}" if ear.layout else ""))
    print()

    levels = []
    for (name, _sec), (a, b) in zip(PHASES, marks):
        w = window(ear, a, b)
        if not w:
            print(f" {name:26} — 프레임 없음")
            levels.append(None)
            continue
        avg = sum(w) / len(w)
        levels.append(avg)
        print(f" {name:26} {db(avg):6.1f} dB  |{meter(avg)}|")

    quiet = [v for v in (levels[0], levels[2]) if v is not None]
    loud = levels[1]
    print()
    if loud is None or not quiet:
        print(" 구간을 다 못 재서 판정할 수 없습니다. 다시 돌려보세요.")
        return None

    base = sum(quiet) / len(quiet)
    gap = db(loud) - db(base)
    print(f" 말할 때가 조용할 때보다 {gap:+.1f} dB")

    if gap >= 6.0:
        print()
        print(" ★ 듣고 있습니다 ★")
        print("   로봇 마이크 소리가 우리에게 옵니다. 조종하는 사람이 복도에서")
        print("   말해도 로봇이 받을 수 있습니다.")
        print("   다음: 이 소리를 whisper 에 넣어 '안내해' 가 잡히는지 봅니다.")
        return True
    if gap >= 2.0:
        print()
        print(" 애매합니다. 차이는 있는데 작습니다.")
        print("   더 크게, 더 가까이에서 한 번 더 해보세요. 그래도 이 정도면")
        print("   음성 인식에는 모자랄 가능성이 큽니다.")
        return None
    print()
    print(" ★ 프레임은 오는데 소리가 안 담겨 있습니다 ★")
    print("   말해도 조용할 때와 같습니다. 무음 통로이거나, 마이크가")
    print("   이 경로로는 안 실리는 것입니다.")
    print("   → PC 마이크나 무선 마이크 쪽으로 갑니다.")
    return False


def save_wav(ear, path):
    if not ear.pcm:
        print(" ※ 남길 소리가 없습니다.")
        return
    import wave
    data = np.concatenate(ear.pcm)
    pcm16 = (np.clip(data, -1, 1) * 32767).astype("<i2")
    rate = int(ear.rate or 48000)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm16.tobytes())
    print(f" {path} 에 남겼습니다 ({len(data) / rate:.1f}초, {rate} Hz).")
    print(" 직접 들어보시고, 말이 알아들을 만하면 whisper 에 넣어볼 수 있습니다.")


async def main():
    keep = "--save" in sys.argv[1:]

    print("=" * 70)
    print(" 로봇에게 귀가 있는가")
    print("=" * 70)
    print(" 로봇은 움직이지 않습니다. 이동 명령을 한 줄도 보내지 않습니다.")
    print(" 15초 동안 조용히 → 말하기 → 조용히 를 시킵니다.")
    print()

    conn = await common.connect()
    ear = Ear()
    ear.keep = keep
    try:
        # 받는 쪽을 켭니다 — 여기가 이 시험의 전부입니다
        conn.audio.add_track_callback(ear.on_frame)
        try:
            conn.audio.switchAudioChannel(True)
        except Exception as e:
            print(f" ※ 오디오 채널을 켜는 데 문제가 있었습니다: {e!r}")

        print(" 3초 뒤에 시작합니다...")
        await asyncio.sleep(3.0)

        marks = []
        for name, sec in PHASES:
            print()
            print("─" * 70)
            print(f" {name}   ({sec:.0f}초)")
            print("─" * 70)
            a = time.time()
            end = a + sec
            last = 0.0
            while time.time() < end:
                await asyncio.sleep(0.25)
                w = window(ear, time.time() - 0.35, time.time() + 1)
                cur = (sum(w) / len(w)) if w else last
                last = cur
                left = end - time.time()
                print(f"   |{meter(cur)}| {db(cur):6.1f} dB   {left:3.1f}초",
                      end="\r", flush=True)
            print(" " * 78, end="\r")
            marks.append((a, time.time()))

        ok = verdict(ear, marks)
        if keep:
            print()
            save_wav(ear, Path("robot_mic.wav"))
        return ok
    finally:
        print("\n정리합니다...")
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
