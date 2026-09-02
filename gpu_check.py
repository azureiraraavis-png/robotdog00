# -*- coding: utf-8 -*-
"""
음성 인식을 GPU 로 돌릴 수 있는지 확인합니다.  (로봇 없이 실행합니다)

    .\\run gpu_check.py

  왜 따로 만들었나
    `WhisperModel(device="cuda")` 는 CUDA 라이브러리가 없어도 **객체 생성은
    성공합니다.** 실제로 계산할 때가 되어서야 죽습니다. 그래서 "GPU 사용"
    이라고 찍힌 뒤 한참 있다가 터지는 일이 생깁니다.

    이 스크립트는 순서대로 짚어가며 **어디서 막혔는지 정확히** 알려줍니다.
    막힌 지점에 맞는 해결 명령까지 같이 내놓습니다.

  확인 순서
    1. 파이썬이 가상환경의 것인가
    2. 그래픽카드와 드라이버      (nvidia-smi)
    3. 관련 패키지 버전            (faster-whisper, ctranslate2)
    4. NVIDIA DLL 이 깔려 있는가   (윈도우에서 가장 흔한 실패 지점)
    5. CUDA 장치가 보이는가        (ctranslate2)
    6. 실제로 추론이 되는가        ★ 여기까지 통과해야 진짜입니다
"""

import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import cuda_dlls

# 모델을 받을 때마다 나오는 심볼릭 링크 경고를 끕니다 (기능에는 영향 없음)
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

SAMPLE_RATE = 16000
LINE = "─" * 66


def step(n, title):
    print(f"\n{LINE}\n {n}. {title}\n{LINE}")


def ok(msg):
    print(f"  ✔ {msg}")


def bad(msg):
    print(f"  ✘ {msg}")


def info(msg):
    print(f"    {msg}")


# ── 1. 파이썬 ────────────────────────────────────────────────
def check_python():
    step(1, "파이썬")
    exe = Path(sys.executable)
    info(f"{exe}")
    info(f"버전 {sys.version.split()[0]}")

    in_venv = (hasattr(sys, "real_prefix")
               or sys.prefix != getattr(sys, "base_prefix", sys.prefix))
    if in_venv:
        ok("가상환경의 파이썬입니다")
    else:
        bad("가상환경이 아닙니다 — 시스템 파이썬으로 돌고 있습니다")
        info("  .\\run gpu_check.py  로 실행하세요")
    return in_venv


# ── 2. 그래픽카드 ────────────────────────────────────────────
def check_gpu():
    step(2, "그래픽카드와 드라이버")
    try:
        out = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=name,memory.total,memory.used,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=20)
    except FileNotFoundError:
        bad("nvidia-smi 를 찾을 수 없습니다 — NVIDIA 드라이버가 없습니다")
        return False
    except Exception as e:
        bad(f"nvidia-smi 실행 실패: {e}")
        return False

    if out.returncode != 0:
        bad(f"nvidia-smi 오류: {out.stderr.strip()[:120]}")
        return False

    line = out.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in line.split(",")]
    if len(parts) >= 4:
        name, total, used, driver = parts[:4]
        ok(f"{name}")
        info(f"VRAM {used} / {total}   드라이버 {driver}")
    else:
        ok(line)
    return True


# ── 3. 패키지 ────────────────────────────────────────────────
def check_packages():
    step(3, "패키지 버전")
    versions = {}
    for name in ("faster_whisper", "ctranslate2", "torch"):
        try:
            mod = __import__(name)
            v = getattr(mod, "__version__", "?")
            versions[name] = v
            ok(f"{name} {v}")
        except ImportError:
            versions[name] = None
            if name == "torch":
                info("torch 없음 — faster-whisper 만 쓸 거면 필요 없습니다")
            else:
                bad(f"{name} 이 설치되어 있지 않습니다")
    return versions


# ── 4. NVIDIA DLL ────────────────────────────────────────────
def check_dlls():
    step(4, "NVIDIA 라이브러리 (윈도우에서 가장 흔한 실패 지점)")
    for line in cuda_dlls.report():
        info(line)

    if os.name != "nt":
        return True

    dlls = cuda_dlls.list_dlls()
    if not dlls:
        return False

    print()
    added = cuda_dlls.enable(verbose=False)
    if added:
        ok(f"DLL 경로 {len(added)}곳을 등록했습니다")
        info("이 등록이 없으면 설치되어 있어도 못 찾습니다 (파이썬 3.8+ 동작)")
    return True


# ── 5. CUDA 장치 ─────────────────────────────────────────────
def check_cuda_device():
    step(5, "CUDA 장치 인식")
    try:
        import ctranslate2
    except ImportError:
        bad("ctranslate2 가 없습니다")
        return False
    try:
        n = ctranslate2.get_cuda_device_count()
    except Exception as e:
        bad(f"장치 조회 실패: {type(e).__name__}: {str(e)[:120]}")
        return False

    if n > 0:
        ok(f"CUDA 장치 {n}개")
        return True
    bad("CUDA 장치가 0개입니다")
    return False


# ── 6. 실제 추론 ─────────────────────────────────────────────
def check_inference(size="tiny"):
    step(6, f"실제 추론 (모델 '{size}')")
    info("1초짜리 무음을 GPU 로 한 번 돌려봅니다. 여기까지 통과해야 진짜입니다.")
    info("처음이면 모델을 내려받느라 잠시 걸립니다.")
    print()

    from faster_whisper import WhisperModel
    try:
        model = WhisperModel(size, device="cuda", compute_type="float16")
    except Exception as e:
        bad(f"모델 생성 실패: {type(e).__name__}: {str(e)[:160]}")
        return False, str(e)

    try:
        silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
        segments, _ = model.transcribe(silence, language="ko", beam_size=1)
        list(segments)          # 제너레이터라 소비해야 실제로 계산합니다
    except Exception as e:
        bad(f"추론 실패: {type(e).__name__}")
        info(str(e).split("\n")[0][:200])
        return False, str(e)

    ok("GPU 추론 성공")
    return True, ""


# ── 처방 ─────────────────────────────────────────────────────
def prescribe(error, versions):
    """오류 문구에 맞는 해결책을 내놓습니다."""
    e = (error or "").lower()
    print(f"\n{LINE}\n 무엇을 하면 되나\n{LINE}")

    ct2 = versions.get("ctranslate2") or ""

    if "cublas" in e:
        print("""
  cuBLAS 라이브러리를 못 찾고 있습니다.

    .\\.venv\\Scripts\\python.exe -m pip install nvidia-cublas-cu12

  이미 설치했는데도 같은 오류라면, DLL 경로 등록 문제입니다.
  stt.py 가 cuda_dlls.enable() 을 부르고 있는지 확인하세요.
  (이 스크립트는 이미 등록한 뒤에 시험했으므로, 그래도 안 되면
   설치 자체가 덜 된 것입니다 — 위 4번 항목의 DLL 목록을 보세요)
""")
    elif "cudnn" in e:
        print(f"""
  cuDNN 을 못 찾고 있습니다. 그런데 **버전이 맞아야 합니다.**

  ctranslate2 4.5.0 부터 cuDNN 9 를 씁니다. 그 아래는 cuDNN 8 입니다.
  지금 설치된 ctranslate2: {ct2 or '확인 안 됨'}

  · 오류에 cudnn_ops64_9.dll 이 보이면 → cuDNN 9 가 필요합니다
        pip install nvidia-cudnn-cu12
  · 오류에 cudnn_ops64_8.dll 이 보이면 → cuDNN 8 이 필요합니다
        pip install "nvidia-cudnn-cu12==8.9.7.29"

  둘을 섞어 깔면 더 헷갈립니다. 하나로 맞추세요.
""")
    elif "out of memory" in e or "cuda_error_out_of_memory" in e:
        print("""
  VRAM 이 모자랍니다.

  · 다른 GPU 프로그램을 닫으세요 (Isaac Sim, 브라우저, 게임)
  · config.py 의 STT_MODEL 을 한 단계 낮추세요
  · 또는 compute_type 을 'int8_float16' 으로 (메모리 절반)
""")
    elif "no kernel image" in e or "invalid device function" in e:
        print("""
  설치된 ctranslate2 가 이 그래픽카드용으로 빌드되지 않았습니다.

    pip install --upgrade --force-reinstall ctranslate2 faster-whisper
""")
    else:
        print("""
  아래를 순서대로 해 보세요.

    .\\.venv\\Scripts\\python.exe -m pip install --upgrade ^
        faster-whisper ctranslate2 nvidia-cublas-cu12 nvidia-cudnn-cu12

  그래도 안 되면 위의 오류 문구를 그대로 알려주세요.
  GPU 없이도 CPU 로 잘 동작하므로 급한 일은 아닙니다.
""")


def main():
    print("=" * 66)
    print(" 음성 인식 GPU 사용 가능 여부 확인")
    print("=" * 66)

    check_python()
    has_gpu = check_gpu()
    versions = check_packages()

    if not has_gpu:
        print(f"\n{LINE}\n 결론\n{LINE}")
        print("  NVIDIA 그래픽카드를 쓸 수 없습니다. CPU 로 진행하세요.")
        print("  config.py:  STT_DEVICE = \"cpu\"")
        return

    if versions.get("faster_whisper") is None:
        print(f"\n{LINE}\n 결론\n{LINE}")
        print("  faster-whisper 가 설치되어 있지 않습니다.")
        print("    .\\.venv\\Scripts\\python.exe -m pip install faster-whisper")
        return

    has_dll = check_dlls()
    check_cuda_device()
    passed, error = check_inference()

    print(f"\n{LINE}\n 결론\n{LINE}")
    if passed:
        print("  ★ GPU 로 음성 인식이 가능합니다 ★")
        print()
        print("  config.py 를 이렇게 바꾸세요:")
        print('     STT_DEVICE = "cuda"')
        print('     STT_MODEL  = "medium"      # small 보다 한국어가 훨씬 낫습니다')
        print()
        print("  그다음  .\\run stt.py  로 실제 마이크 인식을 확인하세요.")
    else:
        print("  아직 GPU 로 돌릴 수 없습니다.")
        if not has_dll:
            print("  가장 유력한 원인: NVIDIA 라이브러리 미설치 (위 4번 항목)")
        prescribe(error, versions)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        print(f"\n[오류] {type(e).__name__}: {e}")
        sys.exit(1)
