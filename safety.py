# -*- coding: utf-8 -*-
"""
안전 장치.

넘어짐·뒤집힘에 대한 대응을 모아둡니다.

★ 먼저 알아둘 것 ★
전원을 켜는 순간의 발버둥은 **소프트웨어로 막을 수 없습니다.**
그때는 아직 우리 코드가 로봇에 붙기 전이기 때문입니다.
그 구간은 아래의 물리적 절차로만 막을 수 있습니다 (README 참고).

  1. 배를 바닥에 대고, 다리를 완전히 접은 상태로 눕혀 놓기
  2. 평평하고 미끄럽지 않은 바닥
  3. 켜는 사람이 리모컨을 손에 들고 있기 — L2+B 가 가장 빠른 정지

우리 코드가 붙은 뒤부터는 아래 장치들이 일합니다.
"""

import asyncio
import json
import math
import time

from unitree_webrtc_connect.constants import RTC_TOPIC

import common

# 이 각도를 넘으면 "쓰러졌다"고 봅니다 (도)
TIP_ANGLE = 60.0

# 이 각도를 넘으면 "뒤집혔다"고 봅니다 (도)
FLIP_ANGLE = 120.0


# ═════════════════════════════════════════════════════════════
# 자동 복구 끄기 / 켜기
# ═════════════════════════════════════════════════════════════

# set_auto_recovery / get_auto_recovery 는 common.py 로 옮겼습니다.
# (연결 직후 바로 호출해야 해서 순환 import 를 피했습니다)
set_auto_recovery = common.set_auto_recovery
get_auto_recovery = common.get_auto_recovery


# ═════════════════════════════════════════════════════════════
# 자세 감시
# ═════════════════════════════════════════════════════════════

def _rpy_from(data):
    """상태 메시지에서 기울기(roll, pitch)를 도 단위로 꺼냅니다.

    로봇 펌웨어에 따라 필드 위치가 다를 수 있어 몇 군데를 찾아봅니다.
    """
    imu = data.get("imu_state") or data.get("imu") or {}

    rpy = imu.get("rpy") or data.get("rpy")
    if isinstance(rpy, (list, tuple)) and len(rpy) >= 2:
        return math.degrees(rpy[0]), math.degrees(rpy[1])

    q = imu.get("quaternion") or data.get("quaternion")
    if isinstance(q, (list, tuple)) and len(q) >= 4:
        w, x, y, z = q[0], q[1], q[2], q[3]
        roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
        sp = max(-1.0, min(1.0, 2 * (w * y - z * x)))
        pitch = math.asin(sp)
        return math.degrees(roll), math.degrees(pitch)

    return None


class Watchdog:
    """로봇의 기울기를 지켜보다가, 쓰러지면 즉시 힘을 뺍니다.

        wd = safety.Watchdog(conn)
        wd.arm()
        ...
        wd.disarm()

    쓰러진 채로 관절에 힘이 들어가 있으면 모터가 계속 버티려 하면서
    발열과 마모가 생깁니다. 감지 즉시 Damp 를 보내는 이유입니다.
    """

    def __init__(self, conn, tip_angle=TIP_ANGLE, verbose=True):
        self.conn = conn
        self.tip_angle = tip_angle
        self.verbose = verbose
        self.armed = False
        self.tripped = False
        self.last_rpy = None
        self._reported_fields = False
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = asyncio.get_event_loop()

    def arm(self):
        if self.armed:
            return
        self.conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["LF_SPORT_MOD_STATE"], self._on_state)
        self.armed = True
        if self.verbose:
            print(f"[안전] 자세 감시 켜짐 (기울기 {self.tip_angle:.0f}도 초과 시 힘 빼기)")

    def disarm(self):
        self.armed = False

    def _on_state(self, message):
        if not self.armed or self.tripped:
            return
        data = message.get("data", {})
        rpy = _rpy_from(data)

        if rpy is None:
            if not self._reported_fields:
                self._reported_fields = True
                if self.verbose:
                    print("[안전] 상태 메시지에서 기울기를 찾지 못했습니다.")
                    print(f"       사용 가능한 항목: {sorted(data.keys())}")
                    print("       자세 감시는 동작하지 않습니다. 리모컨을 반드시 준비하세요.")
            return

        self.last_rpy = rpy
        roll, pitch = rpy
        if abs(roll) > self.tip_angle or abs(pitch) > self.tip_angle:
            self.tripped = True
            state = "뒤집힘" if abs(roll) > FLIP_ANGLE else "쓰러짐"
            print(f"\n[안전] ★ {state} 감지 ★  기울기 roll={roll:.0f}도 pitch={pitch:.0f}도")
            print("[안전] 즉시 힘을 뺍니다. 로봇에서 손을 떼고 주변을 확인하세요.")
            asyncio.run_coroutine_threadsafe(self._emergency(), self._loop)

    async def _emergency(self):
        try:
            await common.emergency_damp(self.conn)
        except Exception as e:
            print(f"[안전] 비상 정지 실패: {e}")
        print("[안전] 로봇을 손으로 바로 눕힌 뒤,  .\\run recover.py  로 일으키세요.\n")

    def reset(self):
        """복구한 뒤 다시 감시를 시작할 때."""
        self.tripped = False
