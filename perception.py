# -*- coding: utf-8 -*-
"""
라이다로 주변을 보는 공용 코드.

look.py 와 avoid_test.py 가 같이 씁니다. 한 군데에 두는 이유는, 이 프로젝트에서
같은 지식이 파일마다 흩어졌다가 사고가 난 적이 여러 번이기 때문입니다.

★ 알아낸 것들 (전부 실측) ★

  1. 복셀 맵은 **로봇 기준이 아닙니다.**  frame_id 는 odom 이고,
     돌아다니며 쌓아온 지도 전체입니다. rt/utlidar/robot_pose 로 로봇의
     위치·방향을 받아 옮겨야 합니다. 안 옮기면 100도 넘게 틀어집니다.

  2. 높이는 **바닥 기준**입니다.  지도의 z=0 이 바닥입니다
     (서 있는 로봇의 자세 z 가 0.33m 로, 실측 기립 높이와 일치).
     로봇 몸통 기준으로 바꾸면 바닥 0.38~1.53m 를 보게 되어
     **걸려 넘어질 낮은 것들을 통째로 놓칩니다.**

  3. 이 건물 바닥은 거울처럼 반사합니다.  점의 **53%** 가 바닥 아래에
     찍힙니다. 다행히 수평 바닥의 반사는 언제나 아래로 가므로,
     바닥 기준 높이로 거르면 통째로 빠집니다.

  4. 통로 폭은 **높이에 따라 완전히 다릅니다.**
     3층 복도: 로봇 높이 1.15m, 벽 높이 3.13m.
"""

import asyncio
import time

import numpy as np

from unitree_webrtc_connect.constants import RTC_TOPIC

# ── 높이 구간 (바닥 기준, m) ─────────────────────────────────
OBSTACLE_LOW = 0.05        # 걸려 넘어질 것들
OBSTACLE_HIGH = 0.60
WALL_LOW = 0.60            # 벽·사물함 — 통로 폭 판단용
WALL_HIGH = 1.60

# ── 자기 몸 걸러내기 ────────────────────────────────────────
# ★ 서 있을 때와 걸을 때가 다릅니다 ★
# 서 있으면 네 발이 몸통 아래에 모여 반경 0.25m 안에 들어갑니다.
# 그런데 **걸으면 앞발이 앞으로 크게 뻗습니다.** 그 발이 '정면 0.4m 앞의
# 장애물' 로 잡히면, 아무것도 없는데 멈추게 됩니다.
#
# 그래서 원이 아니라 로봇이 쓸고 지나가는 **상자 모양**으로 뺍니다.
#   몸통 길이 약 0.70m → 앞뒤 반길이 0.35m,  발 뻗음까지 0.55m
#   몸통 폭   약 0.31m → 좌우 반폭   0.155m, 여유 두어 0.25m
SELF_LONG = 0.55       # 앞뒤로 이만큼은 자기 몸으로 봅니다 (m)
SELF_WIDE = 0.25       # 좌우로 이만큼 (m)

# 예전 이름 (원형 걸러내기). 지금은 상자 쪽을 씁니다.
SELF_RADIUS = 0.25

# 정면으로 볼 부채꼴의 반폭 (m). 로봇 몸통 폭 0.31m 보다 조금 넓게.
FRONT_HALF_WIDTH = 0.35

# 좌우를 볼 때, 앞뒤로 이 범위 안만 봅니다 (m)
SIDE_WINDOW = 0.5


def voxels_to_points(payload):
    """복셀 맵을 (N,3) 실좌표로. 돌려주는 값: (점들, 오류메시지)

    라이다는 공간을 작은 정육면체로 나눠 '여기 뭔가 있다' 를 표시합니다.
    positions 는 격자 번호이고, 실제 위치는
        원점(origin) + 격자번호 × 한 칸 크기(resolution)
    """
    try:
        inner = payload.get("data")
        if not isinstance(inner, dict):
            return None, "복셀 데이터 형식이 예상과 다릅니다"

        positions = inner.get("positions")
        if positions is None:
            return None, f"positions 가 없습니다 (있는 항목: {sorted(inner.keys())})"

        arr = np.asarray(positions)
        if arr.ndim != 1 or arr.size < 3:
            return None, f"positions 모양이 예상과 다릅니다: {arr.shape}"
        arr = arr[: (arr.size // 3) * 3].reshape(-1, 3).astype(np.float64)

        origin = payload.get("origin") or inner.get("origin") or [0.0, 0.0, 0.0]
        res = payload.get("resolution") or inner.get("resolution") or 0.05
        origin = np.asarray(origin, dtype=np.float64).reshape(3)
        return origin + arr * float(res), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def to_robot_frame(points, pose):
    """지도 기준 점들을 로봇 기준으로. 돌려주는 값: (점들, 옮겼는지)

    로봇 기준: x 앞, y 왼쪽.  z 는 **바닥에서의 높이 그대로** 둡니다.
    """
    if pose is None or points is None or len(points) == 0:
        return points, False
    rx, ry, _rz, yaw = pose
    rel = points[:, :2] - np.array([rx, ry])
    c, s = np.cos(-yaw), np.sin(-yaw)
    x = rel[:, 0] * c - rel[:, 1] * s
    y = rel[:, 0] * s + rel[:, 1] * c
    return np.stack([x, y, points[:, 2]], axis=1), True


def obstacle_band(points, low=OBSTACLE_LOW, high=OBSTACLE_HIGH):
    """부딪힐 높이의 점만 남기고, 자기 몸(과 뻗은 발) 반사를 뺍니다."""
    if points is None or len(points) == 0:
        return np.empty((0, 3))
    z = points[:, 2]
    band = points[(z > low) & (z < high)]
    if len(band) == 0:
        return band
    mine = (np.abs(band[:, 0]) < SELF_LONG) & (np.abs(band[:, 1]) < SELF_WIDE)
    return band[~mine]


class Clearance:
    """지금 앞·좌·우가 얼마나 비어 있는가. 없으면 None."""

    def __init__(self, front=None, left=None, right=None, points=0, age=None):
        self.front = front
        self.left = left
        self.right = right
        self.points = points
        self.age = age

    def width(self):
        if self.left is None or self.right is None:
            return None
        return self.left + self.right

    def fresh(self, limit=2.0):
        return self.age is not None and self.age < limit

    def __str__(self):
        def m(v):
            return f"{v:.2f}m" if v is not None else "—"
        return (f"앞 {m(self.front)}  왼 {m(self.left)}  오른 {m(self.right)}"
                f"  (점 {self.points}개, {self.age:.1f}초 전)"
                if self.age is not None else "아직 데이터 없음")


def clearance_from(band):
    """부딪힐 높이의 점들에서 앞·좌·우 여유를 잽니다."""
    if band is None or len(band) == 0:
        return Clearance()
    x, y = band[:, 0], band[:, 1]

    front = band[(x > 0.1) & (np.abs(y) < FRONT_HALF_WIDTH)]
    left = band[(y > 0.1) & (np.abs(x) < SIDE_WINDOW)]
    right = band[(y < -0.1) & (np.abs(x) < SIDE_WINDOW)]

    return Clearance(
        front=float(front[:, 0].min()) if len(front) else None,
        left=float(np.abs(left[:, 1]).min()) if len(left) else None,
        right=float(np.abs(right[:, 1]).min()) if len(right) else None,
        points=len(band),
    )


class Eyes:
    """라이다를 계속 받아, 지금 주변이 얼마나 비어 있는지 알려줍니다.

    ★ 무엇에 쓰는가 ★
    회피 실험에서 **로봇의 회피를 믿지 않고 우리가 따로 지켜보기** 위한 것입니다.
    시험 대상(로봇의 회피)이 안전장치를 겸하면 안 됩니다. 그건 시험이 아닙니다.
    """

    def __init__(self, conn):
        self.conn = conn
        self.payload = None
        self.pose = None
        self.stamp = None
        self.count = 0
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC["ULIDAR_ARRAY"], self._on_voxel)
        conn.datachannel.pub_sub.subscribe(RTC_TOPIC["ROBOTODOM"], self._on_pose)

    def _on_voxel(self, message):
        data = message.get("data")
        if isinstance(data, dict):
            self.payload = data
            self.stamp = time.time()
            self.count += 1

    def _on_pose(self, message):
        data = message.get("data")
        if not isinstance(data, dict):
            return
        pos = data.get("position") or data.get("pose", {}).get("position")
        ori = data.get("orientation") or data.get("pose", {}).get("orientation")
        try:
            xyz = ([pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0)]
                   if isinstance(pos, dict) else list(pos)[:3])
            q = ([ori.get("x", 0.0), ori.get("y", 0.0),
                  ori.get("z", 0.0), ori.get("w", 1.0)]
                 if isinstance(ori, dict) else list(ori)[:4])
            qx, qy, qz, qw = [float(v) for v in q]
            yaw = np.arctan2(2 * (qw * qz + qx * qy), 1 - 2 * (qy * qy + qz * qz))
            self.pose = (float(xyz[0]), float(xyz[1]), float(xyz[2]), float(yaw))
        except (TypeError, ValueError, IndexError, AttributeError):
            pass

    async def start(self, timeout=15.0, verbose=True):
        """라이다를 켜고 첫 장이 올 때까지 기다립니다."""
        try:
            await self.conn.datachannel.disableTrafficSaving(True)
        except Exception:
            pass
        self.conn.datachannel.pub_sub.publish_without_callback(
            RTC_TOPIC["ULIDAR_SWITCH"], "on")
        if verbose:
            print("[눈] 라이다를 켜고 첫 장을 기다립니다...")

        deadline = time.time() + timeout
        while (self.payload is None or self.pose is None) and time.time() < deadline:
            await asyncio.sleep(0.2)

        if self.payload is None:
            if verbose:
                print("[눈] ★ 라이다 데이터가 오지 않습니다 ★")
            return False
        if self.pose is None:
            if verbose:
                print("[눈] ★ 로봇 자세를 못 받았습니다 — 거리를 믿을 수 없습니다 ★")
            return False
        if verbose:
            print(f"[눈] 준비됨 — {self.clearance()}")
        return True

    def points(self):
        """지금 보이는 것들을 로봇 기준으로. 실패하면 빈 배열."""
        if self.payload is None or self.pose is None:
            return np.empty((0, 3))
        pts, err = voxels_to_points(self.payload)
        if err:
            return np.empty((0, 3))
        pts, _ = to_robot_frame(pts, self.pose)
        return pts

    def clearance(self):
        c = clearance_from(obstacle_band(self.points()))
        c.age = (time.time() - self.stamp) if self.stamp else None
        return c
