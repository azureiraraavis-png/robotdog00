@echo off
REM Runs a script with this folder's venv python.
REM
REM WARNING for editors: keep this file PURE ASCII, and never put
REM parentheses inside an echo line within an if-block. cmd treats an
REM unescaped ) as the end of the block, so the script exits early.
REM Korean text breaks it too - cmd reads batch files by byte offset,
REM and multi-byte characters shift it into an infinite re-read loop.

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
    echo   SETUP
    echo     run get_aes_key.py       fetch and save the AES key
    echo     run find_robot.py        find robot IP / diagnose network
    echo     run stt.py               list microphones
    echo.
    echo   SAFE - robot does not move
    echo     run 01_connect_test.py   connection test
    echo     run test_listen.py       practice speech recognition, no robot
    echo     run 03_speak_korean.py   korean speech through the speaker
    echo     run speak.py             interactive korean speech console
    echo.
    echo   ROBOT MOVES - clear space, remote in hand
    echo     run 02_move_test.py      walking and turning
    echo     run drive.py             keyboard teleop, tune movement
    echo     run gait_test.py         find the walking gait
    echo     run 04_guide_demo.py     guide demo
    echo     run 05_voice_control.py  korean voice control
    echo.
    echo   SAFETY
    echo     run park.py              safe posture before power off
    echo     run carry.py             make safe to pick up
    echo     run recover.py           after a fall, disable auto-recovery
    exit /b 1
)

"%PY%" %*
