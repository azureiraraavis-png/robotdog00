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

    conn = UnitreeWebRTCConnection(method, **kwargs)
    await conn.connect()

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


async def prepare_motion(conn, verbose=True):
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
        return await asyncio.wait_for(
            conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["SPORT_MOD"], options),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        print(f"\n[명령] '{name}' 응답이 {timeout:.0f}초 안에 오지 않았습니다.")
        print("       연결이 끊겼을 가능성이 큽니다. 로봇 상태를 눈으로 확인하세요.")
        print("       필요하면 리모컨의 L2+B 로 힘을 빼세요.\n")
        return None


async def move(conn, x=0.0, y=0.0, z=0.0, duration=1.0):
    """안전 한계 안에서 이동합니다. 끝나면 반드시 정지합니다.

    x: 전진(+)/후진(-) m/s
    y: 좌우 게걸음 m/s
    z: 좌회전(+)/우회전(-) rad/s
    """
    lim = config.MAX_FORWARD_SPEED
    yaw = config.MAX_YAW_SPEED
    x = max(-lim, min(lim, x))
    y = max(-lim, min(lim, y))
    z = max(-yaw, min(yaw, z))
    duration = min(duration, config.MAX_MOVE_DURATION)

    print(f"[이동] x={x} y={y} z={z} / {duration}초")
    move_id = command_id("Move")
    deadline = time.time() + duration
    try:
        while time.time() < deadline:
            sport_no_reply(conn, move_id, {"x": x, "y": y, "z": z})
            await asyncio.sleep(0.1)          # 10Hz 로 계속 갱신
    finally:
        await stop(conn)                       # 예외가 나도 반드시 멈춤


async def stop(conn):
    """즉시 정지."""
    sport_no_reply(conn, command_id("StopMove"))
    await asyncio.sleep(0.2)


class StateProbe:
    """로봇 상태를 지켜봅니다. 몸높이로 서 있는지 엎드렸는지 알 수 있습니다."""

    STANDING = 0.15        # 이보다 높으면 서 있는 것으로 봅니다 (m)

    def __init__(self, conn):
        self.height = None
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["LF_SPORT_MOD_STATE"], self._on_state)

    def _on_state(self, message):
        h = message.get("data", {}).get("body_height")
        if isinstance(h, (int, float)):
            self.height = float(h)

    async def read(self, seconds=1.5):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + seconds
        while self.height is None and loop.time() < deadline:
            await asyncio.sleep(0.1)
        return self.height

    def is_standing(self):
        return self.height is None or self.height > self.STANDING


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
    """비상 정지. 힘을 빼고 그 자리에 주저앉습니다. (리모컨 L2+B 와 같은 동작)"""
    print("\n[비상] 댐핑 — 로봇을 내려앉힙니다.")
    try:
        # 비상 경로에서는 표 조회 실패 위험을 없애려고 번호를 직접 씁니다.
        # StopMove=1003, Damp=1001 은 normal / mcf 양쪽에서 동일합니다.
        sport_no_reply(conn, 1003)
        await asyncio.sleep(0.1)
        sport_no_reply(conn, 1001)
    except Exception as e:
        print(f"[비상] 댐핑 명령 실패: {e}")


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


async def upload_phrase(hub, mp3_path):
    """mp3 를 로봇에 올리고 UUID 를 돌려줍니다. 이미 있으면 재사용합니다.

    ※ 라이브러리 예제에는 업로드 직후 목록을 다시 읽지 않는 버그가 있습니다.
       여기서는 새로 읽어서 우회합니다.
    """
    mp3_path = Path(mp3_path)
    name = mp3_path.stem

    for item in await _audio_list(hub):
        if item.get("CUSTOM_NAME") == name:
            return item["UNIQUE_ID"]

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


async def upload_all(conn, paths):
    """모든 안내 멘트를 올리고 {key: uuid} 를 돌려줍니다."""
    hub = make_audio_hub(conn)
    uuids = {}
    for key, path in paths.items():
        uuids[key] = await upload_phrase(hub, path)
    return hub, uuids


async def say(hub, uuids, key, wait=3.0):
    """올려둔 멘트를 로봇 스피커로 재생합니다."""
    print(f"[음성] 재생: {key} — \"{config.PHRASES.get(key, '')}\"")
    await hub.play_by_uuid(uuids[key])
    await asyncio.sleep(wait)
