# -*- coding: utf-8 -*-
"""
공용 헬퍼.

연결 수립, 모션 모드 확인, 안전한 이동, 한국어 TTS 생성,
로봇 스피커 업로드/재생을 한 곳에 모아둡니다.

모든 스크립트가 이 파일을 씁니다.
"""

import asyncio
import contextlib
import fractions
import io
import json
import math
import random
import sys
import time
from pathlib import Path

import av
from aiortc.contrib.media import MediaPlayer
from aiortc.mediastreams import MediaStreamTrack

from unitree_webrtc_connect.webrtc_driver import (
    UnitreeWebRTCConnection,
    WebRTCConnectionMethod,
)
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD, SPORT_CMD_MCF
from unitree_webrtc_connect.webrtc_audiohub import WebRTCAudioHub

import config


# ═════════════════════════════════════════════════════════════
# 설정 저장 (환경변수를 매번 입력하지 않아도 되도록)
# ═════════════════════════════════════════════════════════════

SETTINGS_FILE = Path(__file__).parent / "settings.local.json"
SIGNALING_PORTS = (9991, 8081)


def load_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_settings(**values):
    """settings.local.json 에 값을 저장합니다. (git 에는 올라가지 않습니다)"""
    data = load_settings()
    data.update({k: v for k, v in values.items() if v})
    try:
        SETTINGS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as e:
        print(f"[설정] 저장 실패(무시): {e}")
    return data


def port_open(ip, timeout=0.5):
    """신호 포트가 열려 있으면 포트 번호, 아니면 None."""
    import socket
    for port in SIGNALING_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            if s.connect_ex((ip, port)) == 0:
                return port
        except OSError:
            pass
        finally:
            s.close()
    return None


def _local_subnets():
    subnets = []
    try:
        import ifaddr
        for adapter in ifaddr.get_adapters():
            for ip in adapter.ips:
                if not isinstance(ip.ip, str):
                    continue
                if ip.ip.startswith(("127.", "169.254.")):
                    continue
                parts = ip.ip.split(".")
                if len(parts) == 4:
                    subnets.append(".".join(parts[:3]))
    except Exception:
        pass
    return sorted(set(subnets))


def discover_robot(verbose=True):
    """로봇 IP 를 자동으로 찾습니다. 멀티캐스트 → 포트 스캔 순."""
    from concurrent.futures import ThreadPoolExecutor

    try:
        from unitree_webrtc_connect import discover_ip_sn
        found = discover_ip_sn(timeout=3, device_type="Go2",
                               sn=config.ROBOT_SN or None)
        if found:
            ip = list(found.values())[0]
            if verbose:
                print(f"[탐색] 멀티캐스트로 찾음: {ip}")
            return ip
    except Exception:
        pass

    for subnet in _local_subnets():
        targets = [f"{subnet}.{i}" for i in range(1, 255)]
        if verbose:
            print(f"[탐색] {subnet}.x 대역을 훑는 중...")
        with ThreadPoolExecutor(max_workers=128) as pool:
            for ip, port in zip(targets, pool.map(port_open, targets)):
                if port:
                    if verbose:
                        print(f"[탐색] 포트 스캔으로 찾음: {ip}")
                    return ip
    return None


def resolve_ip(verbose=True):
    """쓸 수 있는 로봇 IP 를 알아냅니다.

    순서: 환경변수/config → 저장된 값(살아 있으면) → 자동 탐색
    찾으면 저장해 두므로, 다음부터는 그냥 실행하면 됩니다.
    """
    candidate = (config.ROBOT_IP or "").strip()
    if candidate and "x" not in candidate:
        return candidate

    saved = load_settings().get("robot_ip", "")
    if saved:
        if verbose:
            print(f"[연결] 저장된 IP 확인 중: {saved}")
        if port_open(saved):
            return saved
        if verbose:
            print("[연결] 저장된 IP 가 응답하지 않습니다. 다시 찾습니다.")

    ip = discover_robot(verbose=verbose)
    if ip:
        save_settings(robot_ip=ip)
    return ip


def resolve_key():
    """AES 키: 환경변수/config → 저장된 값"""
    key = (config.AES_128_KEY or "").strip()
    return key or load_settings().get("aes_key", "")


# ═════════════════════════════════════════════════════════════
# 연결
# ═════════════════════════════════════════════════════════════

# 연결이 이 시간 안에 안 되면 실패로 봅니다 (초).
#
# ★ 왜 필요한가 ★
# WebRTC 협상이 어긋나면 라이브러리 안의 백그라운드 작업만 죽고
# `await conn.connect()` 는 **영원히 돌아오지 않습니다.** 화면에는
#     AttributeError: 'NoneType' object has no attribute 'media'
# 한 줄만 찍히고 그대로 멈춰 있습니다. 사람이 강제 종료할 때까지요.
# 실측: 로봇을 막 켠 직후나 이전 세션이 남아 있을 때 가끔 이렇게 됩니다.
CONNECT_TIMEOUT = 30.0

# 실패했을 때 다시 붙기까지 기다리는 시간 (초).
# 로봇이 이전 세션을 놓는 데 시간이 걸립니다.
RECONNECT_WAIT = 20.0


async def _open_with_timeout(method, kwargs, verbose=True, tries=2):
    """연결을 열되, 매달리지 않습니다. 실패하면 한 번 더 시도합니다."""
    last = None
    for n in range(1, tries + 1):
        conn = UnitreeWebRTCConnection(method, **kwargs)
        try:
            await asyncio.wait_for(conn.connect(), timeout=CONNECT_TIMEOUT)
            return conn
        except asyncio.TimeoutError:
            last = TimeoutError(
                f"연결이 {CONNECT_TIMEOUT:.0f}초 안에 되지 않았습니다.")
        except Exception as e:
            last = e
        finally:
            if last is not None:
                with contextlib.suppress(Exception):
                    await conn.disconnect()

        if verbose:
            print(f"\n[연결] 실패 ({type(last).__name__}) — {n}/{tries}")
        if n < tries:
            if verbose:
                print(f"[연결] 로봇이 이전 세션을 놓도록 "
                      f"{RECONNECT_WAIT:.0f}초 기다렸다 다시 시도합니다...")
            await asyncio.sleep(RECONNECT_WAIT)
            last = None

    raise last if last else RuntimeError("연결에 실패했습니다.")


async def connect(verbose=True):
    """로봇에 연결하고 UnitreeWebRTCConnection 을 돌려줍니다.

    ※ 연결 전에 폰의 유니트리 앱을 완전히 종료해야 합니다.
       로봇은 한 번에 하나의 WebRTC 클라이언트만 받습니다.
    """
    mode = (config.CONNECTION_MODE or "sta").lower()

    kwargs = {}
    key = resolve_key()
    if key:
        kwargs["aes_128_key"] = key
    elif verbose:
        print("[연결] AES 키가 없습니다. 펌웨어 1.1.15 이상이면 실패합니다.")
        print("       →  .\\run get_aes_key.py  로 발급받으세요.")

    if mode == "ap":
        if verbose:
            print("[연결] AP 모드 — 로봇 핫스팟에 직접 접속합니다...")
            print("       (PC 의 Wi-Fi 가 GO2-XXXXXX 에 붙어 있어야 합니다)")
        method = WebRTCConnectionMethod.LocalAP
    else:
        ip = resolve_ip(verbose=verbose)
        if not ip:
            raise ValueError(
                "로봇을 찾지 못했습니다.\n"
                "  → 로봇이 켜져 있고 PC 와 같은 네트워크에 있는지 확인하세요.\n"
                "  → 자세한 진단:  .\\run find_robot.py\n"
                "  → 네트워크가 막혀 있다면 config.py 의 "
                "CONNECTION_MODE 를 \"ap\" 로 바꾸세요."
            )
        if verbose:
            print(f"[연결] {ip} 에 접속 중...")
        method = WebRTCConnectionMethod.LocalSTA
        kwargs["ip"] = ip

    conn = await _open_with_timeout(method, kwargs, verbose=verbose)

    if verbose:
        print("[연결] 성공")

    # 로봇의 오디오 경로를 엽니다.
    # 이걸 켜지 않으면 오디오 트랙을 보내도 스피커에서 소리가 나지 않습니다.
    enable_audio(conn, True, verbose=verbose)

    # 자동 복구를 끕니다.
    # ★ 이 설정은 재부팅하면 초기화됩니다 (실측 확인). ★
    # 그래서 특정 스크립트가 아니라 '연결할 때마다' 끕니다.
    # 켜져 있으면 로봇이 넘어졌다고 판단할 때마다 스스로 일어나려 발버둥칩니다.
    # 특히 등의 손잡이를 잡고 들어 올리면 발이 땅에서 떨어지므로
    # 로봇은 그것을 '넘어짐'으로 해석합니다. 손이 다리 사이에 있으면 위험합니다.
    if getattr(config, "DISABLE_AUTO_RECOVERY", True):
        await _detect_mode_quietly(conn)
        await set_auto_recovery(conn, False, verbose=verbose)

    return conn


async def _detect_mode_quietly(conn):
    """모션 모드만 조용히 알아냅니다. (명령표를 고르기 위해)"""
    try:
        _ACTIVE_MODE["name"] = await get_motion_mode(conn)
    except Exception:
        pass


def enable_audio(conn, on=True, verbose=True):
    """로봇의 오디오 채널을 켜고 끕니다.

    데이터 채널로 "on"/"off" 신호를 보냅니다. 켜져 있어야 우리가 보낸
    오디오 트랙이 로봇 스피커로 나갑니다.
    """
    for target in (getattr(conn, "audio", None), getattr(conn, "datachannel", None)):
        if target is None:
            continue
        try:
            target.switchAudioChannel(on)
            if verbose:
                print(f"[음성] 오디오 채널: {'켜짐' if on else '꺼짐'}")
            return True
        except Exception:
            continue
    if verbose:
        print("[음성] 오디오 채널 전환에 실패했습니다.")
    return False


async def reconnect(conn, wait=12.0, tries=3, verbose=True):
    """연결을 끊고 다시 맺습니다. 새 연결 객체를 돌려줍니다.

    ★ 곧바로 다시 붙으면 실패합니다 ★
    끊은 직후에는 로봇 쪽에 이전 세션이 남아 있어, 2초 뒤에 붙으려 하면
    `DataChannelTimeoutError` 로 죽습니다. 충분히 기다렸다가 붙고,
    실패하면 더 기다렸다 다시 시도합니다.
    """
    await disconnect(conn, verbose=verbose)

    for n in range(1, tries + 1):
        if verbose:
            print(f"[연결] 로봇이 이전 세션을 놓을 때까지 {wait:.0f}초 기다립니다...")
        await asyncio.sleep(wait)
        try:
            return await connect()
        except Exception as e:
            if n == tries:
                raise
            if verbose:
                print(f"[연결] 다시 붙지 못했습니다 ({type(e).__name__}) — {n}/{tries}")
            wait = min(wait * 1.5, 30.0)


async def disconnect(conn, verbose=True):
    """연결을 확실히 닫습니다.

    닫지 않고 종료하면 로봇에 유령 세션이 남아, 다음 실행에서
    소리가 안 나거나 RobotBusyError 가 납니다. Ctrl+C 로 끊을 때도
    반드시 이 함수를 거치도록 각 스크립트가 finally 로 감쌉니다.
    """
    if conn is None:
        return
    try:
        enable_audio(conn, False, verbose=False)
    except Exception:
        pass
    try:
        await conn.disconnect()
        if verbose:
            print("[연결] 정상 종료")
    except Exception as e:
        if verbose:
            print(f"[연결] 종료 중 오류(무시): {e}")


def explain_error(exc):
    """자주 나오는 예외를 한국어로 풀어서 설명합니다."""
    name = type(exc).__name__
    hints = {
        "RobotBusyError":
            "다른 클라이언트가 이미 붙어 있습니다.\n"
            "  → 폰의 유니트리 앱을 완전히 종료하세요 (백그라운드 포함).\n"
            "  → 방금 껐다면 로봇이 놓아줄 때까지 10~20초 기다리세요.",
        "AesKeyRequiredError":
            "이 펌웨어는 기기별 AES 키를 요구합니다.\n"
            "  → README 의 'AES 키 받기' 절을 따라 키를 발급받아 GO2_AES_KEY 에 넣으세요.",
        "AesKeyRejectedError":
            "AES 키가 거부되었습니다. 키가 이 기체의 것이 맞는지 확인하세요.\n"
            "  → 일련번호(SN)가 맞는지, region 설정이 맞는지 확인하세요.",
        "LocalSignalingPortError":
            "해당 IP에서 로봇을 찾지 못했습니다 (포트 9991, 8081 모두 응답 없음).\n"
            "  → IP가 맞는지, 로봇이 켜져 있는지, PC와 같은 네트워크인지 확인하세요.",
        "DataChannelTimeoutError":
            "데이터 채널이 열리지 않았습니다.\n"
            "  → 앱이 아직 붙어 있을 수 있습니다. 20초 후 다시 시도하세요.",
        "NoSdpAnswerError":
            "로봇이 응답하지 않았습니다. 재부팅 후 다시 시도해 보세요.",
        "TimeoutError":
            "연결 협상이 제 시간에 끝나지 않았습니다.\n"
            "  → 로봇을 막 켠 직후라면 1분쯤 두었다가 다시 시도하세요.\n"
            "  → 폰의 유니트리 앱이 붙어 있지 않은지 확인하세요.\n"
            "  → 화면에 'NoneType' object has no attribute 'media' 가 함께\n"
            "    떴다면 WebRTC 협상이 어긋난 것입니다. 재시도로 대개 풀립니다.",
        "AttributeError":
            "라이브러리 내부에서 예상 못 한 값이 나왔습니다.\n"
            "  → 'NoneType' object has no attribute 'media' 라면 WebRTC 협상\n"
            "    실패입니다. 20초 기다렸다 다시 시도하세요.",
    }
    print(f"\n[오류] {name}: {exc}")
    if name in hints:
        print(f"\n{hints[name]}\n")
    else:
        print("\n  → README 의 '문제 해결' 절을 참고하세요.\n")


# ═════════════════════════════════════════════════════════════
# 모션 모드
# ═════════════════════════════════════════════════════════════

async def get_motion_mode(conn):
    """현재 모션 모드 이름을 돌려줍니다 ('normal', 'ai', 'mcf' 등)."""
    resp = await conn.datachannel.pub_sub.publish_request_new(
        RTC_TOPIC["MOTION_SWITCHER"], {"api_id": 1001}
    )
    if resp and resp.get("data", {}).get("header", {}).get("status", {}).get("code") == 0:
        return json.loads(resp["data"]["data"]).get("name")
    return None


# 감지된 모션 모드를 기억해 두고, 명령표를 자동으로 고릅니다.
_ACTIVE_MODE = {"name": None}


def command_table():
    """현재 모드에 맞는 명령표."""
    return SPORT_CMD_MCF if _ACTIVE_MODE["name"] == "mcf" else SPORT_CMD


def command_id(name):
    """동작 이름 → api_id. 현재 모드의 표를 먼저 보고, 없으면 기본표를 봅니다."""
    table = command_table()
    if name in table:
        return table[name]
    if name in SPORT_CMD:
        return SPORT_CMD[name]
    raise KeyError(
        f"'{name}' 은 {_ACTIVE_MODE['name'] or 'normal'} 모드의 명령표에 없습니다."
    )


async def prepare_motion(conn, verbose=True, joystick_input=True):
    """모션 모드를 감지하고, 필요할 때만 전환합니다.

    mcf 는 펌웨어 1.1.7 이후의 기본 모드입니다. 기본 동작
    (StandUp / BalanceStand / Move / Hello / StandDown / Damp) 의 번호가
    normal 과 같으므로 굳이 바꾸지 않습니다. 곡예·자율 동작만 번호가
    다른데, 그건 command_id() 가 알아서 골라줍니다.
    """
    mode = await get_motion_mode(conn)
    _ACTIVE_MODE["name"] = mode

    if verbose:
        print(f"[모드] 현재 모션 모드: {mode}")

    # 이동을 조이스틱 통로로 보내는 설정이면, 로봇이 그 신호를 받아들이도록
    # 켜 둡니다. 꺼져 있어도 아무 오류가 나지 않기 때문에 무조건 켭니다.
    if joystick_input and getattr(config, "MOVE_CHANNEL", "joystick") == "joystick":
        await enable_joystick(conn, True, verbose=verbose)

    if mode == "mcf":
        if verbose:
            print("[모드] MCF 명령표를 사용합니다. 기본 동작은 그대로 동작합니다.")
        return mode

    if mode and mode not in ("normal", "mcf"):
        if verbose:
            print(f"[모드] '{mode}' → 'normal' 로 전환합니다. 로봇이 일어섭니다...")
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["MOTION_SWITCHER"],
            {"api_id": 1002, "parameter": {"name": "normal"}},
        )
        await asyncio.sleep(5)
        _ACTIVE_MODE["name"] = await get_motion_mode(conn)

    return _ACTIVE_MODE["name"]


# 예전 이름 (하위 호환)
ensure_normal_mode = prepare_motion


# ═════════════════════════════════════════════════════════════
# 자동 복구 (넘어졌을 때 스스로 일어나려 하는 동작)
# ═════════════════════════════════════════════════════════════

async def set_auto_recovery(conn, on, verbose=True):
    """로봇이 넘어졌을 때 스스로 일어나려 하는 동작을 켜고 끕니다.

    ★ 이것이 전원을 켤 때 발버둥친 원인일 가능성이 큽니다 ★

    켜져 있으면 로봇은 넘어진 것을 감지하는 즉시 스스로 일어나려 합니다.
    바닥이 미끄럽거나 자세가 이상하면 성공하지 못하고 계속 재시도하는데,
    그게 네 발을 빠르게 휘젓는 것처럼 보입니다.

    끄면 넘어져도 가만히 있습니다. 사람이 상황을 보고
    recover() 로 일으키거나 손으로 자세를 잡아줄 수 있습니다.
    시연 환경에서는 꺼두는 쪽을 권합니다.
    """
    try:
        await sport(conn, "SetAutoRecovery", {"data": bool(on)})
        if verbose:
            print(f"[안전] 자동 복구: {'켜짐' if on else '꺼짐'}")
        return True
    except KeyError:
        if verbose:
            print("[안전] 이 모드에는 자동 복구 설정 명령이 없습니다 "
                  "(normal 모드에서는 지원되지 않습니다)")
        return False
    except Exception as e:
        if verbose:
            print(f"[안전] 자동 복구 설정 실패: {e}")
        return False


async def get_auto_recovery(conn):
    """현재 자동 복구 상태를 읽어옵니다."""
    try:
        resp = await sport(conn, "GetAutoRecovery")
        data = resp.get("data", {}).get("data")
        return json.loads(data) if isinstance(data, str) else data
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════
# 동작 명령
# ═════════════════════════════════════════════════════════════

def sport_no_reply(conn, api_id, parameter=None):
    """응답을 기다리지 않는 sport 명령 (Move 처럼 연속 발행하는 것들)."""
    generated_id = int(time.time() * 1000) % 2147483648 + random.randint(0, 1000)
    payload = {
        "header": {
            "identity": {"id": generated_id, "api_id": api_id},
            "policy": {"priority": 0, "noreply": True},
        },
        "parameter": json.dumps(parameter) if parameter is not None else "",
        "binary": [],
    }
    conn.datachannel.pub_sub.publish_without_callback(RTC_TOPIC["SPORT_MOD"], payload)


SPORT_TIMEOUT = 8.0     # 응답을 이만큼 기다립니다 (초)


# 이미 알린 거부는 다시 알리지 않습니다 (50Hz 로 도배되지 않도록)
_REPORTED_REJECT = set()


def status_code(reply):
    """로봇의 응답에서 상태 코드를 꺼냅니다. 0 이면 정상.

    ★ 지금까지 이 값을 그냥 버리고 있었습니다 ★
    명령이 거부돼도 예외가 나지 않습니다. 응답 안에 코드로만 들어옵니다.
    그래서 '보냈는데 아무 일도 안 일어나는' 상황의 원인을 못 봤습니다.

    응답 구조가 펌웨어마다 조금씩 달라 재귀로 찾습니다.
    """
    def dig(node, depth=0):
        if depth > 6 or not isinstance(node, dict):
            return None
        status = node.get("status")
        if isinstance(status, dict) and isinstance(status.get("code"), int):
            return status["code"]
        if isinstance(node.get("code"), int):
            return node["code"]
        for value in node.values():
            if isinstance(value, dict):
                found = dig(value, depth + 1)
                if found is not None:
                    return found
        return None

    return dig(reply)


async def sport(conn, name, parameter=None, timeout=SPORT_TIMEOUT):
    """이름으로 sport 명령을 보냅니다. 예: await sport(conn, "StandUp")

    현재 모션 모드(normal / mcf)에 맞는 api_id 를 자동으로 고릅니다.

    ※ 반드시 시간 제한을 둡니다.
      연결이 끊긴 뒤에 명령을 보내면 응답이 영원히 오지 않아
      화면이 멈춘 채 아무 설명 없이 대기하게 됩니다.
      그럴 때는 조용히 멈추는 대신 무슨 일인지 알려줘야 합니다.
    """
    options = {"api_id": command_id(name)}
    if parameter is not None:
        options["parameter"] = parameter
    try:
        reply = await asyncio.wait_for(
            conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], options),
            timeout=timeout,
        )
        code = status_code(reply)
        if code not in (0, None) and name not in _REPORTED_REJECT:
            _REPORTED_REJECT.add(name)
            print(f"[명령] ★ 로봇이 '{name}' 을 거부했습니다 (code={code}) ★")
            print("       명령은 보냈지만 실행되지 않았습니다.")
        return reply
    except asyncio.TimeoutError:
        print(f"\n[명령] '{name}' 응답이 {timeout:.0f}초 안에 오지 않았습니다.")
        print("       연결이 끊겼을 가능성이 큽니다. 로봇 상태를 눈으로 확인하세요.")
        print("       필요하면 리모컨의 P 버튼을 두 번 눌러 힘을 빼세요.\n")
        return None


# ★ 회전 부호 ★
#   로봇의 rx 는 **+ 가 우회전**입니다. 사람이 쓰는 좌표(좌회전 +)와 반대입니다.
#   실측: rx=+0.8 을 보냈더니 yaw_speed 가 -1.30 rad/s (시계 방향) 였습니다.
#
#   부호를 뒤집는 곳은 **여기 한 군데뿐**이어야 합니다. drive.py, move(),
#   음성 명령이 각자 뒤집으면 어디선가 반드시 어긋납니다.
YAW_SIGN = -1


def stick_from_intent(x=0.0, y=0.0, z=0.0):
    """사람 기준 방향 → 로봇 스틱 값.

    x: 전진(+)/후진(-)   y: 오른쪽(+)/왼쪽(-) 게걸음   z: 좌회전(+)/우회전(-)
    """
    return {"ly": x, "lx": y, "rx": YAW_SIGN * z}


def joystick(conn, ly=0.0, lx=0.0, rx=0.0, ry=0.0):
    """조이스틱 신호를 보냅니다. (앱의 조종 화면이 쓰는 통로)

    ly: 전진(+)/후진(-)   lx: 좌우 게걸음   rx: 회전
    값의 범위는 -1.0 ~ +1.0 입니다. 속도(m/s)가 아니라 스틱을 기울인 정도입니다.
    """
    conn.datachannel.pub_sub.publish_without_callback(
        RTC_TOPIC["WIRELESS_CONTROLLER"],
        {"lx": lx, "ly": ly, "rx": rx, "ry": ry, "keys": 0},
    )


async def move(conn, x=0.0, y=0.0, z=0.0, duration=1.0):
    """안전 한계 안에서 이동합니다. 끝나면 반드시 정지합니다.

    x: 전진(+)/후진(-)      y: 좌우 게걸음      z: 좌회전(+)/우회전(-)
    값은 **스틱을 기울인 정도(-1.0 ~ +1.0)** 입니다. m/s 가 아닙니다.

    ★ 왜 조이스틱 통로인가 ★
    sport 의 Move(1008) 명령을 보내면 MCF 모드에서는 걸음을 떼지 않고
    **몸통만 기울입니다.** 자세 조정으로 해석되는 것으로 보입니다.
    앱의 조종 화면이 쓰는 조이스틱 신호 통로로 보내야 실제로 걷습니다.
    (두 통로를 나란히 시험해 확인했습니다 — gait_test.py)
    """
    if config.MOVE_CHANNEL == "sport":
        return await _move_by_sport(conn, x, y, z, duration)

    lim = config.MAX_FORWARD_STICK
    yaw = config.MAX_YAW_STICK
    x = max(-lim, min(lim, x))
    y = max(-lim, min(lim, y))
    z = max(-yaw, min(yaw, z))
    duration = min(duration, config.MAX_MOVE_DURATION)

    print(f"[이동] 전진={x} 게걸음={y} 회전={z} / {duration}초")
    deadline = time.time() + duration
    try:
        while time.time() < deadline:
            joystick(conn, **stick_from_intent(x, y, z))
            await asyncio.sleep(0.02)         # 50Hz — 조이스틱은 촘촘히 보내야 합니다
    finally:
        # 반드시 0 을 여러 번 보내 확실히 멈춥니다
        for _ in range(5):
            joystick(conn, 0.0, 0.0, 0.0)
            await asyncio.sleep(0.02)
        await stop(conn)


def stick_to_speed(stick):
    """스틱 값 → **실제로 유지되는** 속도 (m/s). 거리 계산용."""
    return abs(stick) * getattr(config, "STICK_TO_MPS", 1.05)


def stick_to_peak_speed(stick):
    """스틱 값 → **순간 최고** 속도 (m/s). 안전 여유 계산용."""
    return abs(stick) * getattr(config, "STICK_TO_MPS_PEAK", 1.65)


def distance_for(stick, seconds, safe=False):
    """이 명령이 몇 미터를 갈지.

    ★ 어느 쪽으로 틀릴지를 골라야 합니다 ★
      safe=False (기본)  실제에 가까운 값. "얼마나 갈까" 를 물을 때.
      safe=True          넉넉히 큰 값. "이 코스가 공간에 들어갈까" 를 물을 때.
                         공간 판정에서 작게 잡으면 벽에 부딪힙니다.

    출발 지연 0.5초를 뺍니다. 짧은 명령에서는 이게 큽니다 —
    1.5초 명령이면 3분의 1이 출발하는 데 쓰입니다.
    """
    lag = 0.0 if safe else getattr(config, "START_LAG", 0.5)
    speed = stick_to_peak_speed(stick) if safe else stick_to_speed(stick)
    return speed * max(0.0, seconds - lag)


async def move_guarded(conn, probe, x=0.0, y=0.0, z=0.0, duration=1.0,
                       max_drift_deg=None, verbose=True):
    """이동하되, 방향이 틀어지면 멈춥니다.

    ★ 좁은 곳에서 열린 루프로 걷는 것의 진짜 위험 ★
    직진 명령만 줘도 로봇은 조금씩 돌아갑니다. 실측 로그에서 전진 중
    회전 속도가 ±0.2 rad/s 까지 튀었습니다. 3초면 30도 넘게 틀어질 수
    있고, 폭 1.5m 복도에서 그건 벽입니다.

    앞을 보는 것은 아직 못 하지만, **얼마나 틀어졌는지는 지금도 압니다.**
    로봇이 보고하는 회전 속도를 적분하면 됩니다. 한도를 넘으면 멈춥니다.

    돌려주는 값: (끝까지 갔는지, 누적 회전 각도)
    """
    if max_drift_deg is None:
        max_drift_deg = getattr(config, "MAX_DRIFT_DEG", 20.0)

    lim = config.MAX_FORWARD_STICK
    yaw = config.MAX_YAW_STICK
    x = max(-lim, min(lim, x))
    y = max(-lim, min(lim, y))
    z = max(-yaw, min(yaw, z))
    duration = min(duration, config.MAX_MOVE_DURATION)

    turning = abs(z) > 0.05
    if verbose:
        dist = distance_for(x, duration)
        note = "" if turning else f"  (약 {dist:.2f} m)"
        print(f"[이동] 전진={x} 게걸음={y} 회전={z} / {duration}초{note}")

    drift = 0.0                 # 누적 회전 (라디안)
    last = time.time()
    deadline = last + duration
    finished = True

    try:
        while time.time() < deadline:
            joystick(conn, **stick_from_intent(x, y, z))
            await asyncio.sleep(0.02)

            now = time.time()
            dt, last = now - last, now

            # 회전 명령을 준 구간은 당연히 도는 것이므로 재지 않습니다.
            if not turning and probe is not None and probe.yaw_speed is not None:
                drift += probe.yaw_speed * dt
                if abs(math.degrees(drift)) > max_drift_deg:
                    finished = False
                    if verbose:
                        print(f"[이동] ★ 방향이 {math.degrees(drift):+.0f}도 틀어져 멈춥니다 ★")
                        print("       좁은 곳이라면 여기서 사람이 자세를 잡아주세요.")
                    break
    finally:
        for _ in range(5):
            joystick(conn, 0.0, 0.0, 0.0)
            await asyncio.sleep(0.02)
        await stop(conn)

    return finished, math.degrees(drift)


async def _move_by_sport(conn, x, y, z, duration):
    """예전 방식 — sport Move 명령. MCF 모드에서는 걷지 않습니다.

    config.MOVE_CHANNEL 을 "sport" 로 두었을 때만 쓰입니다.
    비교나 문제 추적용으로 남겨둡니다.
    """
    lim = config.MAX_FORWARD_STICK
    yaw = config.MAX_YAW_STICK
    x = max(-lim, min(lim, x))
    y = max(-lim, min(lim, y))
    z = max(-yaw, min(yaw, z))
    duration = min(duration, config.MAX_MOVE_DURATION)

    print(f"[이동] (sport 통로) x={x} y={y} z={z} / {duration}초")
    move_id = command_id("Move")
    deadline = time.time() + duration
    try:
        while time.time() < deadline:
            sport_no_reply(conn, move_id, {"x": x, "y": y, "z": z})
            await asyncio.sleep(0.1)
    finally:
        await stop(conn)


async def stop(conn):
    """즉시 정지. 두 통로 모두에 정지 신호를 보냅니다."""
    try:
        joystick(conn, 0.0, 0.0, 0.0)
    except Exception:
        pass
    sport_no_reply(conn, command_id("StopMove"))
    await asyncio.sleep(0.2)


class StateProbe:
    """로봇 상태를 지켜봅니다.

    ★ 몸높이만 보면 안 됩니다 ★
    로봇이 "서 있다"와 "걸을 수 있다"는 다른 이야기입니다.
    StandUp 으로 세운 뒤 BalanceStand 를 받지 못하면 관절이 굳은 채로 서 있고,
    이때 조이스틱 신호는 **조용히 무시됩니다.** 화면에는 명령이 나간 것처럼
    보이는데 로봇만 가만히 있습니다.

    그래서 상태 메시지의 mode(로봇이 스스로 보고하는 동작 상태) 와
    velocity(실제 측정 속도) 를 같이 봅니다.
      · mode      — 지금 어떤 동작 상태인지. 숫자의 의미는 펌웨어마다 달라
                    MODE_NAMES 는 참고용입니다. 확정은 mode_test.py 로 합니다.
      · velocity  — 실제로 움직였는지. **명령이 먹혔는지 눈이 아니라
                    숫자로 확인할 수 있는 유일한 값입니다.**
    """

    # 이보다 높으면 서 있는 것으로 봅니다 (m)
    #   실측: 완전히 선 상태 0.31, 엎드림 0.08.
    #   0.15 로 뒀더니 아직 일어서는 중인 0.153 에서 통과해버려 올렸습니다.
    STANDING = 0.24

    # 참고용 이름표. 이 로봇에서 실제로 어떤 숫자가 나오는지는
    #   .\run mode_test.py  로 직접 확인하세요.
    MODE_NAMES = {
        0: "idle",
        1: "balanceStand",
        2: "pose",
        3: "locomotion",
        5: "lieDown",
        6: "jointLock",
        7: "damp",
        8: "recoveryStand",
        10: "sit",
    }

    # 이 상태들에서는 이동 명령이 먹습니다.
    MOVING_MODES = (1, 3)

    def __init__(self, conn):
        self.height = None
        self.mode = None
        self.gait = None
        self.velocity = None            # [vx, vy, vz] m/s
        self.yaw_speed = None
        self.fields = None              # 상태 메시지에 실제로 있던 항목 이름들
        self.raw = None                 # 마지막 상태 메시지 통째로
        self.modes_seen = set()
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["LF_SPORT_MOD_STATE"], self._on_state)

    def mode_is_useful(self):
        """이 기체가 mode 를 실제로 갱신하는지.

        ★ 02 호기(MCF 모드)는 서 있든 앉아 있든 항상 0 을 보고합니다 ★
        그런데 몸높이와 회전 속도는 정상적으로 갱신됩니다. 즉 메시지는 살아
        있는데 이 항목만 죽어 있습니다. 이걸 모르고 mode 로 판단했다가
        멀쩡한 로봇을 '이동 불가'로 몰아세웠습니다.
        → 0 말고 다른 값을 한 번이라도 본 적이 있을 때만 믿습니다.
        """
        return bool(self.modes_seen - {0})

    def _on_state(self, message):
        data = message.get("data", {}) or {}
        self.raw = data
        if self.fields is None:
            self.fields = sorted(data.keys())

        h = data.get("body_height")
        if isinstance(h, (int, float)):
            self.height = float(h)

        m = data.get("mode")
        if isinstance(m, int):
            self.mode = m
            self.modes_seen.add(m)

        g = data.get("gait_type")
        if isinstance(g, int):
            self.gait = g

        v = data.get("velocity")
        if isinstance(v, (list, tuple)) and len(v) >= 2:
            try:
                self.velocity = [float(x) for x in v[:3]]
            except (TypeError, ValueError):
                pass

        y = data.get("yaw_speed")
        if isinstance(y, (int, float)):
            self.yaw_speed = float(y)

    async def read(self, seconds=1.5):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        while self.height is None and loop.time() < deadline:
            await asyncio.sleep(0.1)
        return self.height

    def is_standing(self):
        return self.height is None or self.height > self.STANDING

    def mode_name(self):
        if self.mode is None:
            return "읽지 못함"
        return f"{self.mode}({self.MODE_NAMES.get(self.mode, '?')})"

    def speed(self):
        """지금 실제로 나아가는 속도 (m/s). 방향은 무시한 크기입니다."""
        if not self.velocity:
            return None
        vx, vy = self.velocity[0], self.velocity[1]
        return (vx * vx + vy * vy) ** 0.5

    def describe(self):
        h = f"{self.height:.3f}m" if self.height is not None else "?"
        s = self.speed()
        v = f"{s:.2f}m/s" if s is not None else "?"
        w = f"{self.yaw_speed:+.2f}rad/s" if self.yaw_speed is not None else "?"
        g = self.gait if self.gait is not None else "?"
        return f"mode={self.mode_name()} 걸음={g} 높이={h} 속도={v} 회전={w}"

    def can_move(self):
        """로봇이 스스로 보고하는 상태로 판단합니다.

        판단 근거가 없으면 막지 않습니다 — 확인 못 한다고 조종을 막아버리면
        멀쩡한 로봇이 먹통이 됩니다. (실제로 그렇게 만들어 봤습니다)
        """
        if self.mode is None or not self.mode_is_useful():
            return True
        return self.mode in self.MOVING_MODES


async def settle(conn, speaker=None, verbose=True):
    """로봇을 안전하게 눕히고 힘을 뺍니다.

    ★ 순서가 전부입니다 ★
    Damp(힘 빼기)를 먼저 하면 서 있던 자세 그대로 무너지며 '쿵' 떨어집니다.
    반드시 StandDown 으로 제어된 동작으로 내려앉힌 다음에 힘을 빼야 합니다.

    speaker 를 주면 눕기 전에 음성으로 안내합니다.

    돌려주는 값: (시작 몸높이, 끝 몸높이)
    """
    probe = StateProbe(conn)
    before = await probe.read()

    await stop(conn)
    await asyncio.sleep(0.3)

    if probe.is_standing():
        if verbose:
            h = f"{before:.3f} m" if before is not None else "확인 불가"
            print(f"[자세] 서 있습니다 (몸높이 {h}) — 천천히 엎드립니다")
        if speaker is not None:
            await announce(speaker, "settle")
        await sport(conn, "StandDown")
        await asyncio.sleep(4.0)          # 완전히 내려갈 때까지
    else:
        if verbose:
            print(f"[자세] 이미 낮은 자세입니다 (몸높이 {before:.3f} m)")

    if verbose:
        print("[자세] 힘 빼기")
    await sport(conn, "Damp")
    await asyncio.sleep(1.5)

    probe.height = None
    after = await probe.read(2.0)
    return before, after


async def stand_and_wait(conn, probe=None, timeout=10.0, verbose=True):
    """일으켜 세우고, 실제로 섰는지 확인될 때까지 기다립니다.

    ★ 고정된 초를 기다리면 안 됩니다 ★
    엎드리거나 힘이 빠진 상태에서 일어서는 데 4~5초가 걸립니다.
    아직 일어서는 중에 다음 명령이 도착하면 **조용히 버려집니다.**
    오류도 나지 않아 화면에는 명령이 나간 것처럼 보이는데 로봇만 반응이 없습니다.
    (인사 동작이 안 나가던 원인이 이것이었습니다)

    돌려주는 값: 섰는지 여부
    """
    if probe is None:
        probe = StateProbe(conn)

    await sport(conn, "StandUp")

    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    standing = False
    settled = 0
    last_h = None
    while loop.time() < deadline:
        h = probe.height
        if h is not None and h > StateProbe.STANDING:
            standing = True
            # ★ 높이가 더 안 오를 때까지 기다립니다 ★
            #   기준을 넘자마자 다음 명령을 보내면, 아직 일어서는 중이라
            #   BalanceStand 가 조용히 버려집니다. 그러면 관절이 굳은 채로
            #   서 있게 되고 조이스틱이 통째로 먹지 않습니다.
            if last_h is not None and abs(h - last_h) < 0.004:
                settled += 1
                if settled >= 3:
                    break
            else:
                settled = 0
            last_h = h
        await asyncio.sleep(0.2)

    if verbose:
        h = probe.height
        shown = f"{h:.3f} m" if h is not None else "읽지 못함"
        if standing:
            print(f"[자세] 일어섰습니다 (몸높이 {shown})")
        else:
            print(f"[자세] 일어서기 확인 실패 (몸높이 {shown}) — 그대로 진행합니다")
            print("       로봇이 실제로 서 있는지 눈으로 확인하세요.")

    await ensure_locomotion(conn, probe, verbose=verbose)
    return standing


async def ensure_standing(conn, probe=None, ask=True, verbose=True):
    """서 있지 않으면 일으켜 세웁니다. 돌려주는 값: 서 있게 되었는지

    ★ 왜 필요한가 ★
    엎드린 로봇으로 주변을 보면 **카메라는 바닥을 찍고, 라이다는 낮은 데만
    봅니다.** 복도 벽이 제대로 안 잡힙니다.

    그런데 실험이 중단되면 settle() 이 로봇을 눕히고 끝납니다(서 있는 채로
    힘을 빼면 넘어지니까요). 그래서 **다음 실행은 기본적으로 엎드린
    상태에서 시작합니다.** 사람에게 "리모컨으로 세우세요" 라고 말로 맡기면
    잊어버리기 마련이고, 그러면 바닥 사진만 남습니다.

    ask=True 면 일으키기 전에 물어봅니다. 제자리에서 일어서기만 하고
    이동하지는 않습니다.
    """
    if probe is None:
        probe = StateProbe(conn)
    h = await probe.read()

    if h is not None and h > StateProbe.STANDING:
        if verbose:
            print(f"[자세] 이미 서 있습니다 (몸높이 {h:.3f} m)")
        return True

    if verbose:
        shown = f"{h:.3f} m" if h is not None else "읽지 못함"
        print(f"[자세] 로봇이 서 있지 않습니다 (몸높이 {shown})")
        print("       이대로는 카메라가 바닥을 찍고, 라이다도 낮은 데만 봅니다.")

    if ask and not await confirm(
            "일으켜 세울까요?  (제자리에서 일어서기만 하고 이동하지 않습니다)"):
        if verbose:
            print("[자세] 엎드린 채로 진행합니다 — 결과를 그대로 믿지 마세요.")
        return False

    await stand_and_wait(conn, probe=probe, verbose=verbose)
    return True


async def ensure_locomotion(conn, probe=None, tries=3, verbose=True):
    """이동 명령을 받을 수 있는 상태로 만듭니다.

    ★ 열쇠는 StopMove 입니다 ★

    자세를 바꾼 뒤(특히 앉았다 일어난 뒤)에는 조이스틱을 아무리 보내도
    걸음이 나오지 않습니다. 서 있고 오류도 없는데 걸음만 안 나옵니다.
    `StopMove` 를 한 번 보내면 그 자리에서 풀립니다.

    변수를 하나씩만 바꿔 확인했습니다 (sit_test.py, 매번 새로 고장낸 뒤 측정):

        6초 그냥 기다리기          → 0.026 m/s   시간 문제가 아님
        BalanceStand 세 번         → 0.022 m/s   이 명령의 문제가 아님
        StopMove 한 번             → 0.498 m/s   ★ 이것 하나로 풀림 ★
        StopMove + BalanceStand    → 0.550 m/s

    짐작하자면, 특수 자세(Sit/StandDown)에서 빠져나온 직후의 로봇은
    아직 '동작 수행 중'으로 남아 있고, 그 상태에서는 조이스틱 입력이
    무시되는 것으로 보입니다. StopMove 가 그 동작을 끝내 줍니다.

    BalanceStand 는 그 자체로 회복 수단은 아니지만, 걷기 준비 자세로
    맞춰 주는 명령이므로 뒤이어 보냅니다.

    돌려주는 값: 이동 가능한 상태로 보이는지
    """
    if probe is None:
        probe = StateProbe(conn)

    # ★ 순서가 중요합니다 — StopMove 가 먼저입니다 ★
    await sport(conn, "StopMove")
    await asyncio.sleep(1.0)

    for n in range(1, tries + 1):
        await sport(conn, "BalanceStand")
        # mode 가 반영될 시간
        for _ in range(15):
            await asyncio.sleep(0.1)
            if probe.can_move() and probe.mode is not None:
                break

        if probe.mode is None or not probe.mode_is_useful():
            # mode 를 못 믿는 기체 — 확인할 수단이 없으므로 확인하지 않습니다.
            # 회복은 위의 StopMove 가 이미 했으므로 여기서 끝냅니다.
            await asyncio.sleep(1.0)
            return True

        if probe.can_move():
            if verbose:
                print(f"[자세] 이동 준비됨 ({probe.mode_name()})")
            return True

        if verbose:
            print(f"[자세] 아직 이동할 수 없는 상태 ({probe.mode_name()}) — 다시 시도 {n}/{tries}")
        await asyncio.sleep(1.0)

    if probe.mode is None or not probe.mode_is_useful():
        # 확인할 수단이 없는 기체. 보낼 건 다 보냈으니 정상으로 봅니다.
        return True

    if verbose:
        print(f"[자세] ★ 이동 준비 실패 ★  현재 {probe.mode_name()}")
        print("       조이스틱 신호를 보내도 로봇이 무시할 수 있습니다.")
        print("       리모컨으로 한 번 세운 뒤 다시 시도하거나, mode_test.py 로 확인하세요.")
    return False


async def enable_joystick(conn, on=True, verbose=True):
    """로봇이 조이스틱 신호(WIRELESS_CONTROLLER)를 받아들이도록 합니다.

    앱의 조종 화면을 열고 닫으면 이 설정이 꺼진 채로 남을 수 있습니다.
    꺼져 있으면 조이스틱 신호가 통째로 무시되는데, 보내는 쪽에는
    아무 오류도 나지 않습니다. 그래서 조종 전에 무조건 한 번 켭니다.
    """
    try:
        await sport(conn, "SwitchJoystick", {"data": bool(on)})
        if verbose:
            print(f"[조종] 조이스틱 입력 {'켬' if on else '끔'}")
        return True
    except KeyError:
        return False
    except Exception as e:
        if verbose:
            print(f"[조종] 조이스틱 입력 설정 실패 (계속 진행): {e}")
        return False


class Posture:
    """로봇의 자세를 기억하고, 안전한 순서로 전환합니다.

    ★ Go2 의 자세 상태 기계 ★

           앉기 ──RiseSit──┐
                           ├── 서 있기 ──── 다른 모든 동작
         엎드림 ──StandUp──┘

    앉기와 엎드림은 특수 자세라 그 상태에서는 다른 동작 명령이
    **조용히 무시됩니다.** 오류도 나지 않아 원인을 찾기 어렵습니다.
    자세끼리 직접 오갈 수 없고, 반드시 서 있기를 경유해야 합니다.

    힘을 뺀(damp) 뒤에도 마찬가지입니다. 이동 명령이 먹지 않으니
    먼저 일으켜 세워야 합니다.

        posture = common.Posture(conn)
        await posture.sit()
        await posture.lie()     # 알아서 일어섰다가 엎드립니다
    """

    # 특수 자세에서 빠져나오는 명령.
    #   힘을 뺀 뒤에는 StandUp 이 아니라 RecoveryStand 입니다.
    #   StandUp 은 관절을 세우기만 해서, 그 뒤에 이동이 먹지 않습니다.
    EXIT_COMMAND = {"sit": "RiseSit", "lie": "StandUp", "damp": "RecoveryStand"}

    def __init__(self, conn, probe=None):
        self.conn = conn
        self.probe = probe if probe is not None else StateProbe(conn)
        self.state = "unknown"

    def can_move(self):
        """지금 이동 명령이 먹히는 상태인지.

        기억해 둔 이름표보다 **로봇이 스스로 보고하는 상태**를 우선합니다.
        이름표만 믿으면, 기록이 어긋났을 때 멀쩡한 로봇을 통째로
        막아버리게 됩니다.
        """
        if self.probe.mode is not None:
            return self.probe.can_move()
        return self.state in ("stand", "unknown")

    async def stand(self, verbose=True):
        """일으켜 세우고, **걸을 수 있는 상태까지** 만듭니다.

        ★ 탈출 명령만으로는 부족합니다 ★
        `RiseSit` 은 앉은 자세에서 빠져나오게만 해줍니다. 그 뒤에 곧바로
        `BalanceStand` 를 보내면 로봇은 서 있긴 한데 **걷지 못합니다.**
        조이스틱을 주면 처음 한순간만 반응하고 곧 몸통만 들썩입니다.

        실측으로 확인한 차이는 `StandUp` 하나였습니다.
          · StandUp → 안정 대기 → BalanceStand  → 0.47 m/s 로 걸음
          · RiseSit → BalanceStand             → 0.01 m/s, 못 걸음
        그래서 어떤 자세에서 오든 **항상 StandUp 을 거칩니다.**
        """
        # mode 를 믿을 수 있을 때만 '이미 서 있으니 건너뛰기'를 합니다.
        # 믿을 수 없는 기체에서 건너뛰면, 걷기가 풀렸는데도 1 번 키가
        # 아무 일도 안 하는 상태가 됩니다. (실제로 그랬습니다)
        if self.state == "stand" and self.probe.mode_is_useful() and self.can_move():
            return True

        exit_cmd = self.EXIT_COMMAND.get(self.state)
        if exit_cmd and exit_cmd != "StandUp":
            if verbose:
                print(f"     ({self.state} 상태 → {exit_cmd} 로 먼저 빠져나옵니다)")
            await sport(self.conn, exit_cmd)
            await asyncio.sleep(3.0)

        # 어느 경로로 왔든 여기를 지납니다 (StandUp → 안정 → BalanceStand)
        await stand_and_wait(self.conn, probe=self.probe, verbose=verbose)
        self.state = "stand"
        return True

    async def sit(self, verbose=True):
        """앉힙니다.

        앉은 뒤에 일으켜 세우면 한동안 걷지 못하는 문제가 있었는데,
        `ensure_locomotion()` 이 BalanceStand 를 간격을 두고 여러 번
        보내면서 해결됐습니다. (sit_test.py 로 확인)
        """
        if self.state == "sit":
            if verbose:
                print("     (이미 앉아 있습니다)")
            return
        await self.stand(verbose=verbose)
        await sport(self.conn, "Sit")
        await asyncio.sleep(3)
        self.state = "sit"

    async def lie(self, verbose=True):
        if self.state == "lie":
            if verbose:
                print("     (이미 엎드려 있습니다)")
            return
        await self.stand(verbose=verbose)
        await sport(self.conn, "StandDown")
        await asyncio.sleep(3)
        self.state = "lie"

    async def damp(self, verbose=True):
        """힘 빼기. 이후에는 일으켜 세워야 이동 명령이 먹습니다."""
        await emergency_damp(self.conn)
        await asyncio.sleep(1.0)
        self.state = "damp"


async def announce(speaker, phrase_key, verbose=True):
    """등록된 멘트를 로봇 스피커로 말합니다. 실패해도 진행을 막지 않습니다."""
    text = config.PHRASES.get(phrase_key)
    if not text or speaker is None:
        return
    try:
        path = await make_tts(text, config.AUDIO_DIR / f"{phrase_key}.mp3")
        if verbose:
            print(f"  🔊 \"{text}\"")
        await speaker.play(path)
    except Exception as e:
        if verbose:
            print(f"  (음성 안내 실패, 계속 진행: {e})")


async def emergency_damp(conn):
    """비상 정지. 힘을 빼고 그 자리에 주저앉습니다. (리모컨 P 버튼 두 번과 같은 동작)"""
    print("\n[비상] 댐핑 — 로봇을 내려앉힙니다.")
    try:
        # 비상 경로에서는 표 조회 실패 위험을 없애려고 번호를 직접 씁니다.
        # StopMove=1003, Damp=1001 은 normal / mcf 양쪽에서 동일합니다.
        sport_no_reply(conn, 1003)
        await asyncio.sleep(0.1)
        sport_no_reply(conn, 1001)
    except Exception as e:
        print(f"[비상] 댐핑 명령 실패: {e}")


async def ask(prompt):
    """사람에게 한 줄 물어봅니다.

    confirm() 과 같은 이유로 반드시 to_thread 를 씁니다 — 그냥 input() 을
    쓰면 이벤트 루프가 멈춰 로봇과의 연결이 끊깁니다.
    """
    return await asyncio.to_thread(input, prompt)


async def confirm(message):
    """위험한 동작 전 사람의 확인을 받습니다.

    ★ 반드시 async 로 기다려야 합니다 ★
    그냥 input() 을 쓰면 asyncio 이벤트 루프가 통째로 멈춥니다.
    그러면 로봇에 심장박동 신호가 나가지 못해 연결이 끊기고,
    다음 명령은 오지 않을 응답을 영원히 기다리게 됩니다.
    (실제로 그렇게 멈춘 적이 있어 to_thread 로 바꿨습니다)
    """
    print("\n" + "=" * 60)
    print(message)
    print("=" * 60)
    answer = await asyncio.to_thread(
        input, "계속하려면 y 를 누르고 Enter (취소는 그냥 Enter): ")
    return answer.strip().lower() == "y"


# ═════════════════════════════════════════════════════════════
# 한국어 음성
# ═════════════════════════════════════════════════════════════

async def make_tts(text, out_path):
    """한국어 문장을 mp3 로 만듭니다. 이미 있으면 건너뜁니다."""
    out_path = Path(out_path)
    if out_path.exists():
        return out_path

    import edge_tts

    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[TTS] 생성: {out_path.name}  ← \"{text}\"")
    communicate = edge_tts.Communicate(
        text,
        config.TTS_VOICE,
        rate=config.TTS_RATE,
        pitch=config.TTS_PITCH,
        volume=getattr(config, "TTS_VOLUME", "+0%"),
    )
    await communicate.save(str(out_path))
    return out_path


# ═════════════════════════════════════════════════════════════
# 로봇 스피커로 말하기 (스트리밍)
# ═════════════════════════════════════════════════════════════

class ContinuousAudioTrack(MediaStreamTrack):
    """끝나지 않는 오디오 트랙.

    ★ 왜 이런 게 필요한가 ★
    mp3 를 MediaPlayer 로 만들어 pc.addTrack 하면 첫 파일은 잘 나갑니다.
    그런데 파일이 끝나는 순간 트랙이 MediaStreamError 를 던지고,
    그걸 받은 aiortc 의 송신 루프가 **죽습니다**. 그 뒤로는 replaceTrack 으로
    새 음원을 꽂아도 읽어가는 사람이 없어 영원히 무음이 됩니다.

    그래서 트랙 자체는 절대 끝나지 않게 만들고, 내부에서 음원만 갈아끼웁니다.
    재생할 것이 없으면 무음 프레임을 내보내 송신 루프를 살려둡니다.

    (WebRTC 루프백으로 3회 연속 재생을 녹음해 검증했습니다)
    """

    kind = "audio"
    SR = 48000
    LAYOUT = "stereo"
    SAMPLES = 960          # 20ms

    RESYNC_AFTER = 1.0     # 이만큼 밀리면 기준 시계를 다시 잡습니다

    def __init__(self):
        super().__init__()
        self._source = None
        self._player = None
        self._pts = 0
        self._start = None

    def play_file(self, path):
        """지금 재생 중인 것을 멈추고 새 파일을 재생합니다."""
        player = MediaPlayer(str(path))
        old, self._player = self._player, player
        self._source = player.audio
        if old is not None:
            try:
                old.audio.stop()
            except Exception:
                pass

    @property
    def busy(self):
        """재생 중이면 True."""
        return self._source is not None

    def _silence(self):
        frame = av.AudioFrame(format="s16", layout=self.LAYOUT, samples=self.SAMPLES)
        for plane in frame.planes:
            plane.update(bytes(plane.buffer_size))
        frame.sample_rate = self.SR
        return frame

    async def recv(self):
        frame = None
        if self._source is not None:
            try:
                frame = await self._source.recv()
            except Exception:
                # 재생이 끝났을 뿐, 트랙은 계속 살아 있습니다.
                self._source = None
                self._player = None
        if frame is None:
            frame = self._silence()

        # ★ 박자는 절대 시계로 맞춥니다 ★
        # sleep(0.02) 로 20ms 씩 세면 매번 조금씩 더 걸려서 오차가 쌓입니다.
        # 실측 결과 1.8% 씩 뒤처졌고 (1분에 약 1초), 그만큼 수신 버퍼가
        # 말라가다 소리가 끊기고 결국 멈췄습니다.
        # 시작 시각 기준으로 "이 프레임이 나가야 할 시각"을 계산해 기다리면
        # 오차가 누적되지 않습니다. (실측 0.1%)
        now = time.time()
        if self._start is None:
            self._start = now
        else:
            wait = self._start + self._pts / self.SR - now
            if wait > 0:
                await asyncio.sleep(wait)
            elif wait < -self.RESYNC_AFTER:
                # 크게 밀렸으면 (연결 지연 등) 기준을 다시 잡습니다.
                self._start = now - self._pts / self.SR

        # 타임스탬프는 우리가 끊김 없이 이어붙입니다.
        frame.pts = self._pts
        frame.sample_rate = self.SR
        frame.time_base = fractions.Fraction(1, self.SR)
        self._pts += frame.samples
        return frame


class Speaker:
    """로봇 스피커로 음성 파일을 재생합니다.

        speaker = common.Speaker(conn)
        await speaker.play("audio/greet.mp3")
    """

    TAIL = 0.8             # 재생이 끝나고 스피커까지 도달할 여유
    MAX_WAIT = 120.0       # 안전장치

    def __init__(self, conn):
        self.conn = conn
        self.track = ContinuousAudioTrack()
        self.sender = None          # 첫 재생 때 붙입니다 (아래 설명)

    async def play(self, mp3_path, tail=None):
        # ★ 순서가 중요합니다 ★
        # 트랙을 먼저 붙이고 무음부터 흘려보내면, 로봇이 그 스트림을
        # 빈 것으로 보고 스피커 경로를 열지 않는 것으로 보입니다.
        # 그래서 음원을 먼저 물린 다음에 트랙을 붙입니다.
        self.track.play_file(mp3_path)

        if self.sender is None:
            self.sender = self.conn.pc.addTrack(self.track)

        await asyncio.sleep(0.3)               # 재생 시작을 기다립니다

        deadline = time.time() + self.MAX_WAIT
        while self.track.busy and time.time() < deadline:
            await asyncio.sleep(0.1)

        await asyncio.sleep(self.TAIL if tail is None else tail)


# ═════════════════════════════════════════════════════════════
# 볼륨
# ═════════════════════════════════════════════════════════════

async def set_volume(conn, level=None, verbose=True):
    """로봇 스피커 볼륨을 맞춥니다 (0~10)."""
    if level is None:
        level = getattr(config, "SPEAKER_VOLUME", 7)
    level = max(0, min(10, int(level)))
    try:
        await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["VUI"], {"api_id": 1003, "parameter": {"volume": level}}
        )
        if verbose:
            print(f"[음성] 로봇 볼륨: {level}/10")
        return level
    except Exception as e:
        if verbose:
            print(f"[음성] 볼륨 설정 실패: {e}")
        return None


async def get_volume(conn):
    """현재 볼륨을 읽어옵니다."""
    try:
        resp = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["VUI"], {"api_id": 1004}
        )
        return json.loads(resp["data"]["data"]).get("volume")
    except Exception:
        return None


async def make_all_phrases():
    """config.PHRASES 전체를 mp3 로 만들고 {key: path} 를 돌려줍니다."""
    paths = {}
    for key, text in config.PHRASES.items():
        paths[key] = await make_tts(text, config.AUDIO_DIR / f"{key}.mp3")
    return paths


def prepare_wav(mp3_path, verbose=True):
    """업로드용 wav 를 만듭니다. 이미 있으면 그대로 씁니다.

    ★ 왜 우리가 직접 변환하나 ★
    라이브러리에 mp3 를 주면 알아서 44.1kHz wav 로 바꿔 올립니다.
    그런데 그 변환은 **소리 크기를 손보지 않습니다.**

    edge-tts 의 출력은 24kHz / 48kbps 로 고정되어 있고(라이브러리가 그렇게
    박아두어 우리가 못 올립니다), 게다가 최대 음량이 꽤 낮게 나옵니다.
    그 상태로 올리면 잘 안 들려서 로봇 볼륨을 올리게 되는데, 로봇의 볼륨
    눈금은 선형이 아니라 7 이상에서 거칠어집니다. 결국 압축 잡음과
    스피커 잡음까지 같이 커집니다.

    그래서 **여기서 최대 음량을 맞춰 올립니다.** 같은 크기로 들리면서
    로봇 볼륨은 더 낮게 쓸 수 있습니다.

    ※ 소리의 근본 품질(24kHz/48kbps)은 이걸로 나아지지 않습니다.
      나빠지지 않게 하고, 음량만 제대로 맞추는 것입니다.
    """
    mp3_path = Path(mp3_path)
    wav_path = mp3_path.with_suffix(".wav")
    if wav_path.exists():
        return wav_path

    try:
        from pydub import AudioSegment
    except ImportError:
        return mp3_path          # pydub 이 없으면 라이브러리에 맡깁니다

    try:
        audio = AudioSegment.from_mp3(str(mp3_path))
        audio = audio.set_channels(1).set_frame_rate(44100)

        if getattr(config, "TTS_NORMALIZE", True):
            target = getattr(config, "TTS_PEAK_DBFS", -1.0)
            gain = target - audio.max_dBFS
            if audio.max_dBFS > -90:      # 무음이 아니면
                audio = audio.apply_gain(gain)
                if verbose and abs(gain) > 0.5:
                    print(f"[음성] {mp3_path.stem}: 음량 {gain:+.1f} dB 보정")

        audio.export(str(wav_path), format="wav")
        return wav_path
    except Exception as e:
        if verbose:
            print(f"[음성] wav 변환 실패, mp3 그대로 올립니다: {type(e).__name__}")
        return mp3_path


# ═════════════════════════════════════════════════════════════
# 로봇 스피커 (AudioHub)
# ═════════════════════════════════════════════════════════════

def make_audio_hub(conn):
    """AudioHub 핸들. 라이브러리 버전에 따라 logger 인자를 요구하기도 합니다."""
    import logging
    logger = logging.getLogger("audiohub")
    try:
        return WebRTCAudioHub(conn, logger)
    except TypeError:
        return WebRTCAudioHub(conn)


async def _audio_list(hub):
    """로봇에 올라가 있는 오디오 목록."""
    resp = await hub.get_audio_list()
    if not resp or not isinstance(resp, dict):
        return []
    data_str = resp.get("data", {}).get("data", "{}")
    return json.loads(data_str).get("audio_list", [])


class _FilteredStdout(io.TextIOBase):
    """base64 조각 덤프만 걸러내는 stdout 프록시.

    라이브러리의 upload_audio_file 안에 디버그용 print 가 남아 있어서
    4KB 짜리 base64 조각을 수백 개 화면에 쏟아냅니다. 그 줄만 버리고
    나머지 출력은 그대로 통과시킵니다.
    """

    NOISE = '"block_content"'

    def __init__(self, target):
        self.target = target
        self._buf = ""
        self.dropped = 0

    def write(self, s):
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if self.NOISE in line:
                self.dropped += 1
            else:
                self.target.write(line + "\n")
        return len(s)

    def flush(self):
        self.target.flush()

    def close_buffer(self):
        if self._buf and self.NOISE not in self._buf:
            self.target.write(self._buf)
        self._buf = ""


@contextlib.contextmanager
def quiet_upload():
    """업로드 중의 base64 덤프를 억제합니다."""
    proxy = _FilteredStdout(sys.stdout)
    old = sys.stdout
    sys.stdout = proxy
    try:
        yield proxy
    finally:
        proxy.close_buffer()
        sys.stdout = old


async def upload_phrase(hub, mp3_path, replace=False):
    """멘트를 로봇에 올리고 UUID 를 돌려줍니다. 이미 있으면 재사용합니다.

    replace=True 면 로봇에 있는 같은 이름을 지우고 다시 올립니다.
    음량 보정처럼 **파일 내용이 바뀌었을 때** 씁니다. 그러지 않으면
    이름이 같아서 옛 파일이 계속 재생됩니다.

    ※ 라이브러리 예제에는 업로드 직후 목록을 다시 읽지 않는 버그가 있습니다.
       여기서는 새로 읽어서 우회합니다.
    """
    mp3_path = Path(mp3_path)
    name = mp3_path.stem

    existing = [i for i in await _audio_list(hub)
                if i.get("CUSTOM_NAME") == name]
    if existing and not replace:
        return existing[0]["UNIQUE_ID"]
    for item in existing:
        await hub.delete_record(item["UNIQUE_ID"])
        await asyncio.sleep(0.4)

    # 업로드용 wav 로 바꿉니다 (음량 보정 포함)
    mp3_path = prepare_wav(mp3_path)

    # 4KB 조각 단위로 올라가고 조각마다 0.1초 쉽니다.
    size = mp3_path.stat().st_size
    est = max(5, int(size * 1.4 / 4096 * 0.1))     # wav 변환 후 base64 기준 어림값
    print(f"[음성] 로봇에 업로드: {name}  (약 {est}초, 조용히 진행됩니다)")

    with quiet_upload() as proxy:
        await hub.upload_audio_file(str(mp3_path))
    if proxy.dropped:
        print(f"[음성]   조각 {proxy.dropped}개 전송 완료")
    await asyncio.sleep(1.0)

    for item in await _audio_list(hub):        # 반드시 다시 읽는다
        if item.get("CUSTOM_NAME") == name:
            return item["UNIQUE_ID"]

    raise RuntimeError(f"업로드 후에도 '{name}' 을 목록에서 찾지 못했습니다.")


async def show_robot_audio(hub):
    """로봇에 올라가 있는 오디오 목록을 보여줍니다."""
    items = await _audio_list(hub)
    print(f"[음성] 로봇에 저장된 오디오: {len(items)}개")
    for item in items:
        print(f"         {item.get('CUSTOM_NAME')}  ({item.get('UNIQUE_ID')})")
    return items


async def delete_robot_audio(hub, name):
    """이름으로 로봇의 오디오를 지웁니다. (업로드가 중간에 끊겼을 때 사용)"""
    for item in await _audio_list(hub):
        if item.get("CUSTOM_NAME") == name:
            print(f"[음성] 삭제: {name}")
            await hub.delete_record(item["UNIQUE_ID"])
            return True
    return False


# 로봇의 재생 모드.  라이브러리 문서 기준:
#   single_cycle — 한 곡 반복   ★ 이게 기본값이라 멘트가 끝없이 되풀이됐습니다 ★
#   no_cycle     — 한 번만 재생
#   list_loop    — 목록 전체 반복
PLAY_ONCE = "no_cycle"


async def get_play_mode(hub):
    """로봇의 현재 재생 모드를 읽습니다. 못 읽으면 None."""
    try:
        resp = await hub.get_play_mode()
    except Exception:
        return None
    if not isinstance(resp, dict):
        return None
    try:
        inner = resp.get("data", {}).get("data")
        if isinstance(inner, str):
            inner = json.loads(inner)
        if isinstance(inner, dict):
            return inner.get("play_mode")
    except (ValueError, AttributeError):
        pass
    return None


async def set_play_once(hub, verbose=True):
    """멘트를 한 번만 재생하도록 맞춥니다.

    ★ 이게 없으면 로봇이 같은 멘트를 끝없이 되풀이합니다 ★
    기본 재생 모드가 '한 곡 반복'이라, play_by_uuid 한 번에 재생이
    영원히 이어집니다. 04 에서 "두 번 말한다"고 느껴졌던 것도 사실은
    반복이었고, 다음 명령이 우연히 끊어준 것뿐이었습니다.

    돌려주는 값: 실제로 바뀌었는지 (읽어서 확인합니다)
    """
    before = await get_play_mode(hub)
    try:
        await hub.set_play_mode(PLAY_ONCE)
    except Exception as e:
        if verbose:
            print(f"[음성] 재생 모드를 바꾸지 못했습니다: {type(e).__name__}")
        return False
    await asyncio.sleep(0.3)
    after = await get_play_mode(hub)

    if verbose:
        if after == PLAY_ONCE:
            note = f" (이전: {before})" if before and before != after else ""
            print(f"[음성] 재생 모드: {after} — 한 번만 재생합니다{note}")
        elif after is None:
            print(f"[음성] 재생 모드를 {PLAY_ONCE} 로 설정했습니다 (확인은 못 했습니다)")
        else:
            print(f"[음성] ★ 재생 모드가 여전히 '{after}' 입니다 ★")
            print("       멘트가 반복될 수 있습니다. hush.py 로 멈출 수 있습니다.")
    return after in (PLAY_ONCE, None)


async def hush(hub, verbose=True):
    """지금 나오는 소리를 멈춥니다. (라이브러리에 stop 은 없고 pause 가 있습니다)"""
    try:
        await hub.pause()
        if verbose:
            print("[음성] 재생을 멈췄습니다.")
        return True
    except Exception as e:
        if verbose:
            print(f"[음성] 멈추지 못했습니다: {type(e).__name__}")
        return False


async def upload_all(conn, paths, replace=False):
    """모든 안내 멘트를 올리고 {key: uuid} 를 돌려줍니다.

    replace=True 면 로봇에 있는 것을 지우고 새로 올립니다.
    (음량 보정을 켰거나 멘트 문구를 바꿨을 때)
    """
    hub = make_audio_hub(conn)
    await set_play_once(hub)          # ★ 올리기 전에 반복부터 끕니다 ★
    uuids = {}
    for key, path in paths.items():
        uuids[key] = await upload_phrase(hub, path, replace=replace)
    return hub, uuids


async def say(hub, uuids, key, wait=3.0, stop_after=False):
    """올려둔 멘트를 로봇 스피커로 재생합니다.

    stop_after 를 켜면 기다린 뒤 확실히 멈춥니다. 재생 모드가 말을 듣지
    않는 기체를 위한 보험인데, wait 가 멘트 길이보다 짧으면 말을 자릅니다.
    """
    print(f"[음성] 재생: {key} — \"{config.PHRASES.get(key, '')}\"")
    await hub.play_by_uuid(uuids[key])
    await asyncio.sleep(wait)
    if stop_after:
        await hush(hub, verbose=False)
