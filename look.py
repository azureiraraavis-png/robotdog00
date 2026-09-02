# -*- coding: utf-8 -*-
"""
로봇의 눈으로 보기 — 앞 카메라 사진과 라이다 지도를 파일로 저장합니다.

    .\\run look.py

  로봇은 움직이지 않습니다. 보기만 합니다.

  왜 만들었나
    "회피가 되는가" 를 시험하기 전에 물어야 할 것이 있습니다.
    **로봇이 애초에 복도를 보고 있는가.**

    라이다가 벽을 못 보고 있다면 회피가 될 리 없고, 시험한다고 로봇을
    벽으로 걸어보낼 이유도 없습니다. 먼저 보이는지부터 확인합니다.

  저장하는 것 (look/ 폴더)
    front_<시각>.jpg      앞 카메라 사진 그대로
    lidar_<시각>.png      라이다를 위에서 내려다본 지도
    report_<시각>.txt     숫자 요약 (앞·좌·우로 몇 미터가 비어 있는가)

    이 파일들을 대화창에 올려주시면 제가 직접 보고 판단할 수 있습니다.

  준비물
    pip install pillow      (이미지 저장용. 없으면 안내가 나옵니다)
"""

import asyncio
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

import common
from unitree_webrtc_connect.constants import RTC_TOPIC

conn = None
OUT = Path(__file__).parent / "look"

# '부딪힐 만한 높이' 구간 — ★ 바닥 기준 ★ (m)
#
# 실측으로 확인: 서 있는 로봇의 자세 z 가 +0.33 m 로 나왔고, 이는 앞서 잰
# 실제 기립 높이(0.31~0.33 m)와 일치합니다. 즉 지도의 z=0 이 바닥입니다.
#
# 그래서 높이를 '로봇 몸통 기준' 이 아니라 '바닥 기준' 으로 셉니다.
# 몸통 기준으로 세면 0.38~1.53 m 를 보게 되는데, 그건 벽과 사물함 높이일 뿐
# **로봇이 실제로 걸려 넘어질 낮은 것들을 통째로 놓칩니다.**
OBSTACLE_LOW = 0.05        # 바닥에서 이만큼 위부터
OBSTACLE_HIGH = 0.60       # 로봇 어깨 높이 언저리까지

# 참고용으로 같이 재는, 더 높은 구간 (벽·사물함 등 '통로 폭' 판단용)
WALL_LOW = 0.60
WALL_HIGH = 1.60

# 이 반경 안의 점은 로봇 자기 몸에서 돌아온 것으로 봅니다 (m)
SELF_RADIUS = 0.25

# 지도 범위 (로봇을 중심으로 앞뒤·좌우 몇 미터까지 그릴지)
MAP_RANGE = 4.0
MAP_PIXELS = 480


def stamp():
    return datetime.now().strftime("%m%d_%H%M%S")


# ═════════════════════════════════════════════════════════════
# 앞 카메라
# ═════════════════════════════════════════════════════════════

async def grab_photo(conn, path, frames=12, timeout=15.0):
    """영상 트랙에서 프레임 하나를 받아 저장합니다.

    첫 프레임은 대개 깨져 있어서 몇 장 버리고 받습니다.
    """
    got = {}

    async def on_track(track):
        try:
            for _ in range(frames):
                got["frame"] = await track.recv()
        except Exception as e:
            got["error"] = e

    conn.video.add_track_callback(on_track)
    conn.video.switchVideoChannel(True)

    print("[카메라] 영상 채널을 켜고 프레임을 기다립니다...")
    deadline = time.time() + timeout
    while "frame" not in got and "error" not in got and time.time() < deadline:
        await asyncio.sleep(0.2)

    conn.video.switchVideoChannel(False)

    if "error" in got:
        print(f"[카메라] 실패: {type(got['error']).__name__}: {got['error']}")
        return None
    if "frame" not in got:
        print("[카메라] 프레임이 오지 않았습니다.")
        print("         앱이 붙어 있거나, 이 기체가 영상 전송을 막고 있을 수 있습니다.")
        return None

    frame = got["frame"]
    try:
        image = frame.to_image()          # PIL Image
    except Exception as e:
        print(f"[카메라] 이미지 변환 실패: {e}")
        print("         pip install pillow 가 필요합니다.")
        return None

    image.save(str(path), quality=92)
    print(f"[카메라] 저장: {path.name}  ({image.width}×{image.height})")
    return path


# ═════════════════════════════════════════════════════════════
# 라이다
# ═════════════════════════════════════════════════════════════

class VoxelCatcher:
    """라이다 복셀 맵과 로봇의 자세를 받아둡니다.

    ★ 왜 자세가 필요한가 ★
    복셀 맵은 **로봇 기준이 아니라 지도 기준**입니다. 로봇이 돌아다니며
    쌓아온 주변 지도 전체이고, 좌표의 원점도 로봇이 아닙니다.

    그걸 모르고 '로봇이 원점, x 가 앞' 이라고 가정했더니, 사진에는 앞이
    훤히 트여 있는데 "정면 0.58m" 같은 숫자가 나왔습니다.

    로봇의 위치와 방향을 같이 받아 점들을 로봇 기준으로 옮겨야 합니다.
    """

    def __init__(self, conn):
        self.latest = None
        self.count = 0
        self.pose = None
        self.pose_raw = None
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["ULIDAR_ARRAY"], self._on_msg)
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["ROBOTODOM"], self._on_pose)

    def _on_msg(self, message):
        self.count += 1
        data = message.get("data")
        if isinstance(data, dict):
            self.latest = data

    def _on_pose(self, message):
        data = message.get("data")
        if not isinstance(data, dict):
            return
        self.pose_raw = data
        pos = data.get("position") or data.get("pose", {}).get("position")
        ori = data.get("orientation") or data.get("pose", {}).get("orientation")
        try:
            if isinstance(pos, dict):
                xyz = [pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0)]
            else:
                xyz = list(pos)[:3]
            if isinstance(ori, dict):
                q = [ori.get("x", 0.0), ori.get("y", 0.0),
                     ori.get("z", 0.0), ori.get("w", 1.0)]
            else:
                q = list(ori)[:4]
            # 쿼터니언 → yaw (평면 위 회전각)
            qx, qy, qz, qw = [float(v) for v in q]
            yaw = np.arctan2(2 * (qw * qz + qx * qy),
                             1 - 2 * (qy * qy + qz * qz))
            self.pose = (float(xyz[0]), float(xyz[1]), float(xyz[2]), float(yaw))
        except (TypeError, ValueError, IndexError, AttributeError):
            pass


def to_robot_frame(points, pose):
    """지도 기준 점들을 로봇 기준으로 옮깁니다.

    돌려주는 값: (옮긴 점들, 옮겼는지 여부)
    로봇 기준에서는 x 가 앞, y 가 왼쪽, z 가 로봇 몸높이 기준입니다.
    """
    if pose is None or points is None or len(points) == 0:
        return points, False

    rx, ry, rz, yaw = pose
    rel = points[:, :2] - np.array([rx, ry])
    c, s = np.cos(-yaw), np.sin(-yaw)
    x = rel[:, 0] * c - rel[:, 1] * s
    y = rel[:, 0] * s + rel[:, 1] * c
    # ★ z 는 빼지 않습니다 ★
    # 지도의 z=0 이 바닥이므로, 원래 값이 곧 '바닥에서의 높이' 입니다.
    # 로봇 몸통 기준으로 바꿔버리면 낮은 장애물을 놓칩니다.
    z = points[:, 2]
    return np.stack([x, y, z], axis=1), True


async def grab_voxels(conn, timeout=15.0):
    """라이다를 켜고 복셀 맵 한 장을 받습니다."""
    catcher = VoxelCatcher(conn)

    # 라이다 데이터는 양이 많아 기본적으로 절약 모드로 막혀 있습니다.
    try:
        await conn.datachannel.disableTrafficSaving(True)
    except Exception as e:
        print(f"[라이다] 절약 모드 해제 실패 (계속 시도): {type(e).__name__}")

    conn.datachannel.pub_sub.publish_without_callback(
        RTC_TOPIC["ULIDAR_SWITCH"], "on")
    print("[라이다] 켜고 복셀 맵을 기다립니다...")

    deadline = time.time() + timeout
    while catcher.latest is None and time.time() < deadline:
        await asyncio.sleep(0.3)

    if catcher.latest is None:
        print("[라이다] 데이터가 오지 않았습니다.")
        print(f"         받은 메시지 {catcher.count}개")
        print("         라이다가 꺼져 있거나(리모컨/앱에서 확인),")
        print("         연결 직후의 'Radar malfunction' 오류가 계속되는 상태일 수 있습니다.")
        return None, None

    if catcher.pose is None:
        print("[라이다] ★ 로봇 자세를 못 받았습니다 ★")
        print("         지도는 그리지만 '로봇 기준' 이 아니라 '지도 기준' 입니다.")
        print("         거리 숫자를 믿지 마세요.")
        if catcher.pose_raw:
            print(f"         받은 자세 항목: {sorted(catcher.pose_raw.keys())}")
    else:
        rx, ry, rz, yaw = catcher.pose
        print(f"[라이다] 로봇 위치 ({rx:+.2f}, {ry:+.2f}, {rz:+.2f}) m, "
              f"방향 {np.degrees(yaw):+.0f}도")
    return catcher.latest, catcher.pose


def voxels_to_points(payload):
    """복셀 맵을 (N, 3) 실좌표 배열로 바꿉니다. 실패하면 None.

    라이다는 공간을 작은 정육면체로 나눠 '여기 뭔가 있다' 를 표시합니다.
    positions 는 그 정육면체의 격자 번호이고, 실제 위치는
        원점(origin) + 격자번호 × 한 칸 크기(resolution)
    입니다.
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


def summarize(points):
    """앞·좌·우로 얼마나 비어 있는지 숫자로 냅니다.

    로봇 좌표: x 앞, y 왼쪽, z 위 (일반적인 로봇 관례)
    """
    lines = []
    if points is None or len(points) == 0:
        return ["점이 없습니다."]

    z = points[:, 2]
    band = points[(z > OBSTACLE_LOW) & (z < OBSTACLE_HIGH)]
    lines.append(f"전체 점 {len(points)}개 중, 부딪힐 높이"
                 f"({OBSTACLE_LOW}~{OBSTACLE_HIGH}m) 에 {len(band)}개")

    # 로봇 자기 몸에서 돌아온 점 제거 (몸통 반경 약 0.25m)
    if len(band):
        r = np.hypot(band[:, 0], band[:, 1])
        selfhits = int((r < SELF_RADIUS).sum())
        band = band[r >= SELF_RADIUS]
        if selfhits:
            lines.append(f"자기 몸 반사로 보이는 {selfhits}개는 뺐습니다"
                         f" (반경 {SELF_RADIUS}m)")

    if len(band) == 0:
        lines.append("그 높이에 아무것도 없습니다 — 트여 있거나, 라이다가 못 보고 있습니다.")
        return lines

    x, y = band[:, 0], band[:, 1]

    front = band[(x > 0.1) & (np.abs(y) < 0.35)]      # 몸통 폭만큼의 앞쪽
    if len(front):
        lines.append(f"정면(폭 0.7m): 가장 가까운 것 {front[:, 0].min():.2f} m")
    else:
        lines.append("정면(폭 0.7m): 범위 안에 아무것도 없음")

    for label, mask in (("왼쪽", (y > 0.1) & (np.abs(x) < 0.5)),
                        ("오른쪽", (y < -0.1) & (np.abs(x) < 0.5))):
        side = band[mask]
        if len(side):
            lines.append(f"{label}: 가장 가까운 것 {np.abs(side[:, 1]).min():.2f} m")
        else:
            lines.append(f"{label}: 가까운 것 없음")

    left = band[(y > 0.1) & (np.abs(x) < 0.5)]
    right = band[(y < -0.1) & (np.abs(x) < 0.5)]
    if len(left) and len(right):
        width = np.abs(left[:, 1]).min() + np.abs(right[:, 1]).min()
        lines.append(f"→ 로봇 높이에서의 통로 폭 약 {width:.2f} m")

    # 바닥 아래로 내려간 점 = 반들거리는 바닥의 거울 반사
    below = int((points[:, 2] < -0.05).sum())
    if below:
        lines.append(f"바닥 아래 점 {below}개 — 거울 반사로 보입니다"
                     f" (높이 걸러내기에서 이미 빠졌습니다)")

    # 벽 높이 구간도 따로 재둡니다
    zz = points[:, 2]
    wall = points[(zz > WALL_LOW) & (zz < WALL_HIGH)]
    wl = wall[(wall[:, 1] > 0.1) & (np.abs(wall[:, 0]) < 0.5)]
    wr = wall[(wall[:, 1] < -0.1) & (np.abs(wall[:, 0]) < 0.5)]
    if len(wl) and len(wr):
        w = np.abs(wl[:, 1]).min() + np.abs(wr[:, 1]).min()
        lines.append(f"→ 벽 높이({WALL_LOW}~{WALL_HIGH}m)에서의 폭 약 {w:.2f} m")
    return lines


def draw_map(points, path, robot_frame=True):
    """위에서 내려다본 지도를 그립니다. 로봇은 가운데, 위쪽이 앞."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[라이다] pillow 가 없어 지도를 못 그립니다.  pip install pillow")
        return None

    size = MAP_PIXELS
    img = Image.new("RGB", (size, size), (18, 20, 23))
    draw = ImageDraw.Draw(img)
    mid = size // 2
    scale = size / (2 * MAP_RANGE)          # 픽셀 / m

    # 1m 격자
    for m in range(1, int(MAP_RANGE) + 1):
        r = m * scale
        draw.ellipse([mid - r, mid - r, mid + r, mid + r],
                     outline=(58, 66, 74))
        draw.text((mid + 4, mid - r + 2), f"{m}m", fill=(120, 132, 142))
    draw.line([(mid, 0), (mid, size)], fill=(48, 54, 60))
    draw.line([(0, mid), (size, mid)], fill=(48, 54, 60))

    if points is not None and len(points):
        z = points[:, 2]
        band = points[(z > OBSTACLE_LOW) & (z < OBSTACLE_HIGH)]
        for px, py, pz in band:
            # 로봇 x(앞) → 화면 위,  y(왼쪽) → 화면 왼쪽
            sx = mid - py * scale
            sy = mid - px * scale
            if 1 <= sx < size - 1 and 1 <= sy < size - 1:
                # 높을수록 밝게. 1픽셀은 화면에서 잘 안 보여 2×2 로 찍습니다.
                t = (pz - OBSTACLE_LOW) / (OBSTACLE_HIGH - OBSTACLE_LOW)
                c = (int(90 + 165 * t), int(150 + 80 * t), int(210 - 60 * t))
                draw.rectangle([sx, sy, sx + 1, sy + 1], fill=c)

    # 로봇 표시 (앞쪽을 향한 삼각형)
    draw.polygon([(mid, mid - 11), (mid - 7, mid + 8), (mid + 7, mid + 8)],
                 fill=(235, 150, 60))
    # ★ 라벨은 ASCII 로 ★
    # PIL 기본 글꼴에는 한글이 없어 네모로 깨집니다. 글꼴 파일을 찾아
    # 넣을 수도 있지만, 이 그림은 판독용이라 영문으로 두는 편이 확실합니다.
    draw.text((8, 8), "FRONT is UP" if robot_frame else "MAP FRAME (not robot)",
              fill=(210, 220, 226) if robot_frame else (235, 130, 120))
    draw.text((8, 22), f"rings = 1m,  max {MAP_RANGE:.0f}m", fill=(140, 150, 158))
    draw.text((8, 36), f"height {OBSTACLE_LOW}-{OBSTACLE_HIGH}m above FLOOR",
              fill=(140, 150, 158))

    img.save(str(path))
    print(f"[라이다] 지도 저장: {path.name}")
    return path


# ═════════════════════════════════════════════════════════════

async def run(conn_):
    OUT.mkdir(exist_ok=True)
    t = stamp()
    made = []

    print("\n" + "=" * 62)
    print(" 1. 앞 카메라")
    print("=" * 62)
    photo = await grab_photo(conn_, OUT / f"front_{t}.jpg")
    if photo:
        made.append(photo)

    print("\n" + "=" * 62)
    print(" 2. 라이다")
    print("=" * 62)
    payload, pose = await grab_voxels(conn_)

    report = [f"찍은 시각: {datetime.now():%Y-%m-%d %H:%M:%S}"]
    if payload is not None:
        points, err = voxels_to_points(payload)
        if err:
            print(f"[라이다] 해석 실패: {err}")
            report.append(f"라이다 해석 실패: {err}")
            report.append(f"받은 항목: {sorted(payload.keys())}")
        else:
            report.append(f"복셀 맵 항목: {sorted(payload.keys())}")
            fid = payload.get("frame_id")
            res = payload.get("resolution")
            if fid is not None:
                report.append(f"좌표계(frame_id): {fid}   한 칸 크기: {res} m")
                print(f"         좌표계 {fid}, 한 칸 {res} m")
            points, moved = to_robot_frame(points, pose)
            if moved:
                rx, ry, rz, yaw = pose
                line = (f"로봇 자세: ({rx:+.2f}, {ry:+.2f}, {rz:+.2f}) m, "
                        f"{np.degrees(yaw):+.0f}도  → 로봇 기준으로 변환함")
            else:
                line = "★ 로봇 자세를 못 받아 지도 기준 그대로입니다 — 거리 숫자 믿지 마세요 ★"
            print(f"         {line}")
            report.append(line)

            print(f"[라이다] 점 {len(points)}개")
            lines = summarize(points)
            for l in lines:
                print(f"         {l}")
            report.extend(lines)
            m = draw_map(points, OUT / f"lidar_{t}.png", robot_frame=moved)
            if m:
                made.append(m)
    else:
        report.append("라이다 데이터를 받지 못했습니다.")

    rpath = OUT / f"report_{t}.txt"
    rpath.write_text("\n".join(report), encoding="utf-8")
    made.append(rpath)

    print("\n" + "=" * 62)
    print(" 저장된 파일")
    print("=" * 62)
    for p in made:
        print(f"   look\\{p.name}")
    print()
    print(" 이 파일들을 대화창에 올려주시면 제가 직접 보고 판단하겠습니다.")
    print(" 특히 라이다 지도에 복도 벽이 두 줄로 보이는지가 관건입니다.")


async def main():
    global conn
    print("=" * 62)
    print(" 로봇의 눈으로 보기  (움직이지 않습니다)")
    print("=" * 62)

    conn = await common.connect()
    try:
        await run(conn)
    finally:
        print("\n정리합니다...")
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
