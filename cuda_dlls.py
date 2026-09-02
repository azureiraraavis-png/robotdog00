# -*- coding: utf-8 -*-
"""
윈도우에서 pip 로 받은 NVIDIA 라이브러리를 찾을 수 있게 만듭니다.

★ 왜 이 파일이 필요한가 ★

    pip install nvidia-cublas-cu12 nvidia-cudnn-cu12

이것만으로는 윈도우에서 대개 **안 고쳐집니다.** 설치는 되는데
`Library cublas64_12.dll is not found` 가 그대로 납니다.

이유는 파이썬 3.8 부터 윈도우에서 확장 모듈이 의존하는 DLL 을
**PATH 에서 찾지 않기 때문**입니다. 보안 때문에 바뀐 동작인데,
그 결과 pip 가 아래 경로에 DLL 을 잘 깔아놓아도 아무도 못 찾습니다.

    .venv\\Lib\\site-packages\\nvidia\\cublas\\bin\\cublas64_12.dll
    .venv\\Lib\\site-packages\\nvidia\\cudnn\\bin\\cudnn_ops64_9.dll

찾게 하려면 os.add_dll_directory() 로 그 폴더를 직접 등록해야 합니다.
그것도 **faster_whisper 를 import 하기 전에** 해야 합니다.

    import cuda_dlls
    cuda_dlls.enable()
    from faster_whisper import WhisperModel      # 이 순서여야 합니다

리눅스·맥에서는 아무 일도 하지 않습니다.
"""

import os
import sys
from pathlib import Path

# ★ 등록 핸들을 붙잡아 둡니다 ★
# os.add_dll_directory() 가 돌려주는 객체가 사라지면 등록도 풀립니다.
# 지역 변수에만 두면 함수를 나가는 순간 원래대로 돌아갑니다.
_HANDLES = []

# 이 이름들이 있으면 CUDA 로 돌 준비가 된 것으로 봅니다.
WANTED = ("cublas64_", "cublasLt64_", "cudnn")


def _site_dirs():
    """site-packages 후보들을 모읍니다. 가상환경도 포함합니다."""
    found = []
    try:
        import site
        found.extend(site.getsitepackages())
        user = site.getusersitepackages()
        if isinstance(user, str):
            found.append(user)
    except Exception:
        pass
    found.extend(p for p in sys.path if p)

    out, seen = [], set()
    for p in found:
        try:
            rp = Path(p).resolve()
        except Exception:
            continue
        if rp not in seen and rp.is_dir():
            seen.add(rp)
            out.append(rp)
    return out


def find_dirs():
    """NVIDIA DLL 이 들어 있는 폴더를 찾습니다."""
    dirs, seen = [], set()
    for site_dir in _site_dirs():
        nvidia = site_dir / "nvidia"
        if not nvidia.is_dir():
            continue
        for pkg in sorted(nvidia.iterdir()):
            if not pkg.is_dir():
                continue
            for sub in ("bin", "lib"):
                d = pkg / sub
                if d.is_dir() and d not in seen:
                    seen.add(d)
                    dirs.append(d)
    return dirs


def list_dlls(dirs=None):
    """찾은 폴더 안에 실제로 어떤 DLL 이 있는지 돌려줍니다."""
    if dirs is None:
        dirs = find_dirs()
    names = []
    for d in dirs:
        for f in d.glob("*.dll"):
            if any(w.lower() in f.name.lower() for w in WANTED):
                names.append(f.name)
    return sorted(set(names))


def enable(verbose=False):
    """DLL 폴더를 등록합니다. 등록한 폴더 목록을 돌려줍니다.

    윈도우가 아니면 빈 목록을 돌려주고 아무것도 하지 않습니다.

    ★ 이 함수는 절대 예외를 내지 않습니다 ★
    음성 인식이 시작될 때 불리는데, 여기서 터지면 GPU 를 못 쓰는 정도가
    아니라 **음성 인식 자체가 죽습니다.** 도우려던 것이 망가뜨리는 셈이라,
    무슨 일이 있어도 조용히 빈 목록을 돌려주고 넘어갑니다.
    (실패하면 CPU 로 돌 뿐입니다)
    """
    if os.name != "nt":
        return []

    added = []
    try:
        dirs = find_dirs()
    except Exception as e:
        if verbose:
            print(f"[CUDA] DLL 폴더를 찾는 중 문제: {e}")
        return []

    for d in dirs:
        try:
            _HANDLES.append(os.add_dll_directory(str(d)))
            added.append(d)
        except Exception:
            continue

    # PATH 에도 넣어 둡니다.
    # add_dll_directory 가 정석이지만, 라이브러리에 따라 PATH 만 보는
    # 경우가 있어 양쪽 다 해 둡니다. 해로울 게 없습니다.
    if added:
        extra = os.pathsep.join(str(d) for d in added)
        os.environ["PATH"] = extra + os.pathsep + os.environ.get("PATH", "")

    if verbose:
        if added:
            print(f"[CUDA] DLL 경로 {len(added)}곳 등록")
            for d in added:
                print(f"       {d}")
        else:
            print("[CUDA] 등록할 NVIDIA DLL 폴더를 찾지 못했습니다.")
    return added


def report():
    """지금 상태를 사람이 읽을 수 있게 정리합니다."""
    try:
        return _report()
    except Exception as e:
        return [f"상태를 확인하는 중 문제가 생겼습니다: {e}"]


def _report():
    lines = []
    if os.name != "nt":
        lines.append("윈도우가 아니므로 DLL 경로 조정이 필요 없습니다.")
        return lines

    dirs = find_dirs()
    if not dirs:
        lines.append("NVIDIA 라이브러리가 설치되어 있지 않습니다.")
        lines.append("  .\\.venv\\Scripts\\python.exe -m pip install "
                     "nvidia-cublas-cu12 nvidia-cudnn-cu12")
        return lines

    lines.append(f"NVIDIA 라이브러리 폴더 {len(dirs)}곳:")
    for d in dirs:
        lines.append(f"  {d}")

    dlls = list_dlls(dirs)
    if dlls:
        lines.append("찾은 DLL:")
        for name in dlls:
            lines.append(f"  {name}")
    else:
        lines.append("★ 폴더는 있는데 필요한 DLL 이 없습니다. 설치가 덜 된 상태입니다.")
    return lines


if __name__ == "__main__":
    for line in report():
        print(line)
    print()
    enable(verbose=True)
