@echo off
setlocal
set "PY=%~dp0.venv\Scripts\python.exe"

if not exist "%PY%" (
    echo [ERROR] venv not found at .venv\Scripts\python.exe
    echo Create it first:  py -V:3.12 -m venv .venv
    exit /b 1
)

if "%~1"=="" (
    echo Usage: run SCRIPT.py
    echo.
    echo   run get_aes_key.py       - fetch AES key
    echo   run 01_connect_test.py   - connection test
    echo   run 02_move_test.py      - motion test   [ROBOT MOVES]
    echo   run 03_speak_korean.py   - korean speech
    echo   run 04_guide_demo.py     - guide demo    [ROBOT MOVES]
    echo   run speak.py             - interactive korean speech
    echo   run 05_voice_control.py  - korean voice control [ROBOT MOVES]
    echo   run stt.py               - list microphones
    echo   run park.py              - safe posture before power off
    echo   run carry.py             - make safe to pick up
    echo   run recover.py           - after a fall / disable auto-recovery
    exit /b 1
)

"%PY%" %*
