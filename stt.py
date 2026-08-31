# -*- coding: utf-8 -*-
"""
한국어 음성 인식 (로컬 faster-whisper).

인터넷도 API 키도 필요 없습니다. 첫 실행 때만 모델을 내려받고,
그 뒤로는 완전히 오프라인으로 동작합니다.

동작 방식
─────────
  1. 마이크를 계속 열어두고 소리 크기를 봅니다
  2. 주변 소음보다 뚜렷하게 커지면 "말이 시작됐다"고 보고 녹음
  3. 조용해지면 끊어서 한 덩어리로 만듭니다
  4. 그 덩어리만 whisper 에 넘겨 한국어로 옮깁니다

시작할 때 주변 소음을 재서 기준선을 잡습니다. 전시장처럼 시끄러운 곳에서도
그 환경의 소음을 기준으로 삼기 때문에 그대로 쓸 수 있습니다.
"""

import asyncio
import queue
import sys
import threading
import time

import numpy as np

import config

SAMPLE_RATE = 16000        # whisper 가 쓰는 표준
BLOCK = 1600               # 0.1초 단위로 봅니다


class Listener:
    """마이크에서 발화 구간을 잘라내 한국어 문장으로 돌려줍니다."""

    def __init__(self, verbose=True):
        self.verbose = verbose
        self.model = None
        self.threshold = None
        self._queue = queue.Queue()
        self._stream = None
        self._stop = threading.Event()

    # ── 준비 ──────────────────────────────────────────────

    def load_model(self):
        """whisper 모델을 올립니다. 첫 실행 때는 내려받느라 몇 분 걸립니다."""
        from faster_whisper import WhisperModel

        size = config.STT_MODEL
        if self.verbose:
            print(f"[인식] 모델 '{size}' 준비 중...")
            print("       처음이면 내려받느라 몇 분 걸립니다. 이후에는 즉시 뜹니다.")

        # GPU 가 있으면 쓰고, 없으면 CPU 로 떨어집니다.
        try:
            self.model = WhisperModel(size, device="cuda", compute_type="float16")
            if self.verbose:
                print("[인식] GPU 사용")
        except Exception:
            self.model = WhisperModel(size, device="cpu", compute_type="int8")
            if self.verbose:
                print("[인식] CPU 사용 (GPU 를 못 찾았거나 사용할 수 없습니다)")
        return self.model

    def _callback(self, indata, frames, time_info, status):
        self._queue.put(indata[:, 0].copy())

    def start(self):
        """마이크를 엽니다."""
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK,
            channels=1,
            dtype="float32",
            device=config.MIC_DEVICE,
            callback=self._callback,
        )
        self._stream.start()
        if self.verbose:
            name = config.MIC_DEVICE if config.MIC_DEVICE is not None else "기본 장치"
            print(f"[마이크] 열림 ({name})")

    def stop(self):
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def calibrate(self, seconds=2.0):
        """주변 소음을 재서 발화 판정 기준선을 정합니다."""
        if self.verbose:
            print(f"[마이크] 주변 소음 측정 중... {seconds:.0f}초간 조용히 해주세요")

        levels = []
        deadline = time.time() + seconds
        while time.time() < deadline:
            try:
                block = self._queue.get(timeout=0.5)
                levels.append(float(np.sqrt(np.mean(block ** 2))))
            except queue.Empty:
                pass

        noise = float(np.median(levels)) if levels else 0.005
        self.threshold = max(noise * config.STT_SENSITIVITY, config.STT_MIN_LEVEL)
        if self.verbose:
            print(f"[마이크] 소음 {noise:.4f} → 발화 기준 {self.threshold:.4f}")
        return self.threshold

    # ── 듣기 ──────────────────────────────────────────────

    def _next_utterance(self):
        """말 한 덩어리를 잘라 돌려줍니다. (블로킹, 별도 스레드에서 호출)"""
        collected = []
        speaking = False
        silence_blocks = 0
        speech_blocks = 0

        need_silence = int(config.STT_END_SILENCE / (BLOCK / SAMPLE_RATE))
        need_speech = int(config.STT_MIN_SPEECH / (BLOCK / SAMPLE_RATE))
        max_blocks = int(config.STT_MAX_SECONDS / (BLOCK / SAMPLE_RATE))

        while not self._stop.is_set():
            try:
                block = self._queue.get(timeout=0.3)
            except queue.Empty:
                continue

            level = float(np.sqrt(np.mean(block ** 2)))
            loud = level > self.threshold

            if not speaking:
                if loud:
                    speaking = True
                    collected = [block]
                    speech_blocks = 1
                    silence_blocks = 0
            else:
                collected.append(block)
                if loud:
                    speech_blocks += 1
                    silence_blocks = 0
                else:
                    silence_blocks += 1

                too_long = len(collected) >= max_blocks
                done = silence_blocks >= need_silence

                if done or too_long:
                    if speech_blocks >= need_speech:
                        return np.concatenate(collected)
                    # 너무 짧으면 잡음으로 보고 버립니다
                    speaking = False
                    collected = []
        return None

    def transcribe(self, audio):
        """오디오 덩어리를 한국어 문장으로 옮깁니다."""
        segments, _ = self.model.transcribe(
            audio,
            language="ko",
            beam_size=config.STT_BEAM,
            vad_filter=True,
            condition_on_previous_text=False,   # 앞 문장에 끌려가지 않게
        )
        return "".join(s.text for s in segments).strip()

    async def listen(self):
        """말 한 마디를 듣고 한국어 문장으로 돌려줍니다. 없으면 None."""
        audio = await asyncio.to_thread(self._next_utterance)
        if audio is None or len(audio) == 0:
            return None
        seconds = len(audio) / SAMPLE_RATE
        text = await asyncio.to_thread(self.transcribe, audio)
        if self.verbose and text:
            print(f"[인식] ({seconds:.1f}초) \"{text}\"")
        return text or None


# ─────────────────────────────────────────────────────────────

def list_microphones():
    """쓸 수 있는 마이크 목록을 보여줍니다."""
    import sounddevice as sd

    print("=" * 64)
    print(" 사용 가능한 입력 장치")
    print("=" * 64)
    default = sd.default.device[0]
    for i, dev in enumerate(sd.query_devices()):
        if dev["max_input_channels"] < 1:
            continue
        mark = "  ← 기본" if i == default else ""
        print(f"  [{i:2d}] {dev['name']}{mark}")
    print()
    print(" 다른 마이크를 쓰려면 config.py 의 MIC_DEVICE 에 번호를 적으세요.")
    print("=" * 64)


if __name__ == "__main__":
    list_microphones()
