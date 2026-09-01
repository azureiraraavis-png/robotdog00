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
import contextlib
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
        self._fails = 0
        self._paused = False

    # ── 준비 ──────────────────────────────────────────────

    @staticmethod
    def _smoke_test(model):
        """모델이 실제로 동작하는지 1초짜리 무음으로 한 번 돌려봅니다.

        ★ 이 확인이 왜 필요한가 ★
        WhisperModel(device="cuda") 는 CUDA 라이브러리가 없어도 **객체 생성은
        성공합니다.** 실제로 계산을 시도하는 순간에야
        `Library cublas64_12.dll is not found` 같은 오류로 죽습니다.
        그래서 "GPU 사용"이라고 찍어놓고 한참 뒤에 터지는 일이 생깁니다.
        만들자마자 한 번 돌려보면 그 자리에서 판별됩니다.
        """
        silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
        segments, _ = model.transcribe(silence, language="ko", beam_size=1)
        list(segments)          # 제너레이터라 소비해야 실제로 계산합니다

    def load_model(self):
        """whisper 모델을 올립니다. 첫 실행 때는 내려받느라 몇 분 걸립니다."""
        from faster_whisper import WhisperModel

        size = config.STT_MODEL
        want = (getattr(config, "STT_DEVICE", "auto") or "auto").lower()

        if self.verbose:
            print(f"[인식] 모델 '{size}' 준비 중...")
            print("       처음이면 내려받느라 몇 분 걸립니다. 이후에는 즉시 뜹니다.")

        if want in ("auto", "cuda"):
            try:
                model = WhisperModel(size, device="cuda", compute_type="float16")
                self._smoke_test(model)          # 여기서 진짜인지 판별됩니다
                self.model = model
                if self.verbose:
                    print("[인식] GPU 사용")
                return self.model
            except Exception as e:
                if want == "cuda":
                    raise
                if self.verbose:
                    reason = str(e).split("\n")[0][:100]
                    print(f"[인식] GPU 를 쓸 수 없습니다 — {reason}")
                    if "cublas" in str(e).lower() or "cudnn" in str(e).lower():
                        print("       CUDA 라이브러리가 없습니다. GPU 로 쓰고 싶다면:")
                        print("         pip install nvidia-cublas-cu12 nvidia-cudnn-cu12")
                    print("[인식] CPU 로 진행합니다.")

        self.model = WhisperModel(size, device="cpu", compute_type="int8")
        self._smoke_test(self.model)
        if self.verbose:
            print("[인식] CPU 사용")
            if size in ("medium", "large-v2", "large-v3"):
                print(f"       ※ CPU 에서 '{size}' 는 느립니다. "
                      "답답하면 config.py 의 STT_MODEL 을 'small' 로 낮추세요.")
        return self.model

    def _callback(self, indata, frames, time_info, status):
        if self._paused:
            return              # 로봇이 말하는 동안은 담지 않습니다
        self._queue.put(indata[:, 0].copy())

    # ── 로봇이 말하는 동안 귀를 막기 ──────────────────────

    def pause(self):
        """마이크 입력을 잠시 무시합니다.

        ★ 왜 필요한가 ★
        로봇이 스피커로 말하면 그 소리를 마이크가 다시 주워 담습니다.
        예를 들어 "따라와" 명령에 로봇이 "이쪽입니다. 저를 따라와 주세요"
        라고 답하면, 그 말에 '따라와' 가 들어 있어 또 같은 명령으로 인식됩니다.
        그대로 두면 로봇이 자기 말에 반응하며 끝없이 반복합니다.
        """
        self._paused = True

    def resume(self, drain=True):
        """다시 듣기 시작합니다. 그동안 남은 소리는 버립니다."""
        if drain:
            self._drain()
        self._paused = False

    def _drain(self):
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                return

    @contextlib.contextmanager
    def deaf(self):
        """로봇이 말하는 구간을 감쌉니다.

            with listener.deaf():
                await speaker.play(path)
        """
        self.pause()
        try:
            yield
        finally:
            self.resume()

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
        """말 한 마디를 듣고 한국어 문장으로 돌려줍니다. 없으면 None.

        한 마디를 옮기다 실패해도 전체를 멈추지 않습니다.
        한 번 삐끗했다고 대화가 통째로 끝나면 곤란하니까요.
        """
        audio = await asyncio.to_thread(self._next_utterance)
        if audio is None or len(audio) == 0:
            return None

        seconds = len(audio) / SAMPLE_RATE
        try:
            text = await asyncio.to_thread(self.transcribe, audio)
        except Exception as e:
            self._fails += 1
            print(f"[인식] 실패 ({seconds:.1f}초 분량): {type(e).__name__}: "
                  f"{str(e).split(chr(10))[0][:80]}")
            if self._fails == 3:
                print("[인식] 계속 실패하고 있습니다. "
                      "config.py 의 STT_DEVICE 를 \"cpu\" 로 고정해 보세요.")
            return None

        self._fails = 0
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
