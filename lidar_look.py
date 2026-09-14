# -*- coding: utf-8 -*-
"""라이다가 보는 것을 사람이 읽을 수 있게 바꿉니다.
   ★ 로봇은 움직이지 않습니다 — 다만 **서 있어야 합니다** ★

  ★ 로봇을 세워두세요 ★

    Go2 는 **서 있을 때만** 점구름을 내보냅니다. 엎드려 있으면 한 개도
    안 옵니다 (2026-09-14 확인). 라이다는 눕든 서든 돌고 있는데
    (cloud_frequency 13.9Hz) 내보내기만 안 합니다.

    이걸 모르고 엎드린 채로 다섯 번 짐작했습니다 — 스위치에 뭘 보낼지
    넷, 통신량 절약 모드 탓이라고 하나. 다 틀렸습니다. 사이안 님이
    "혹시 눕혀 놓은 것과 관련이 있을까요" 하고 물어보신 것이 답이었습니다.

  ★ 무엇을 받는가 ★

    rt/utlidar/voxel_map_compressed 가 초당 7번쯤 옵니다. 라이브러리가
    풀어주므로 우리는 이런 것을 받습니다 —

        resolution   0.05          한 칸 5cm
        origin       [x, y, z]     상자의 한 귀퉁이 (odom 좌표)
        width        [128,128,38]  6.4m × 6.4m × 1.9m
        positions    칸 번호들      0~127 짜리 정수 셋씩

    미터로 바꾸는 법:  **origin + 칸번호 × resolution**

    ★ 좌표계가 위치와 같습니다 ★
      둘 다 frame_id 가 "odom" 입니다. rt/utlidar/robot_pose 의 자리와
      같은 자로 재므로, 맞출 필요 없이 그냥 겹칩니다.

  ★ 무엇을 내놓는가 ★

    · 바닥이 어디쯤인지 (점들의 높이 분포로 짐작)
    · 앞·왼쪽·오른쪽으로 가장 가까운 것이 몇 미터인지
    · 위에서 본 글자 지도

    이 셋이 되면 다음이 열립니다 — 휘어짐 재기, 계단 알아보기, 지도 쌓기.

  쓰는 법

      .\\run lidar_look.py               한 장 받아서 봅니다
      .\\run lidar_look.py --frames 5    다섯 장을 겹쳐서 (빈틈이 줍니다)
      .\\run lidar_look.py --band 0.1 0.8   볼 높이 (바닥에서 몇 m 위)

  실행 전 체크리스트
      □ ★ 로봇이 **서 있을 것** ★ — 엎드려 있으면 아무것도 안 옵니다
      □ 주변이 트여 있을 것 (벽이 너무 가까우면 다 벽만 보입니다)
"""

import argparse
import asyncio
import math

import numpy as np

import common

try:
    from unitree_webrtc_connect.constants import RTC_TOPIC
except ImportError as e:                       # pragma: no cover
    raise SystemExit(f"unitree_webrtc_connect 를 못 읽었습니다: {e}")


class Eyes:
    """점구름과 자기 위치를 같이 모읍니다."""

    def __init__(self, conn):
        self.frames = []          # 최근 점구름들 (odom 미터 좌표)
        self.pose = None          # (x, y, yaw)
        self.pose_z = None        # 로봇 몸통의 높이 — 천장을 바닥으로 잡지 않으려고
        self.box = None           # (origin, width, resolution) — 라이다가 보는 상자
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["ULIDAR_ARRAY"], self._on_cloud)
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["ROBOTODOM"], self._on_pose)

    def _on_cloud(self, message):
        pts = to_metres(message)
        if pts is not None and len(pts):
            self.frames.append(pts)
            try:
                d = message["data"]
                # ★ 상자의 크기를 적어둡니다 ★
                #   라이다가 보는 것은 로봇 둘레의 **상자 하나**지 세상
                #   전체가 아닙니다. 그걸 모르면 "천장이 안 잡힌다" 처럼
                #   상자 끝을 세상 끝으로 읽게 됩니다.
                self.box = (np.asarray(d["origin"], float),
                            np.asarray(d["width"], int),
                            float(d["resolution"]))
            except Exception:
                pass

    def _on_pose(self, message):
        try:
            p = message["data"]["pose"]
            x = p["position"]["x"]
            y = p["position"]["y"]
            q = p["orientation"]
            # 쿼터니언에서 yaw 만
            yaw = math.atan2(2 * (q["w"] * q["z"] + q["x"] * q["y"]),
                             1 - 2 * (q["y"] ** 2 + q["z"] ** 2))
            self.pose = (x, y, yaw)
            self.pose_z = float(p["position"]["z"])
        except Exception:
            pass


def to_metres(message):
    """받은 한 장을 미터 좌표 점들로. 못 읽으면 None.

    ★ 칸 번호지 미터가 아닙니다 ★
      positions 는 0~127 짜리 정수입니다. 그대로 쓰면 로봇이 100미터
      밖의 벽을 본다고 하게 됩니다. origin 과 resolution 을 반드시
      거쳐야 합니다.
    """
    try:
        data = message["data"]
        res = float(data["resolution"])
        origin = np.asarray(data["origin"], dtype=float)
        raw = data["data"]["positions"]
        idx = np.asarray(raw)
        if idx.ndim == 1:
            if idx.size % 3:
                return None
            idx = idx.reshape(-1, 3)
        if idx.shape[1] != 3:
            return None
        return origin + idx.astype(float) * res
    except Exception:
        return None


def floor_of(pts, below=None, step=0.05):
    """바닥 높이를 찾습니다. **가장 빽빽한 층**이 바닥입니다.

    ★ '가장 낮은 곳' 으로 찾으면 안 됩니다 ★

      처음에 아래쪽 5% 자리를 썼습니다. 이 건물 바닥은 거울 같아서
      **반사가 바닥 아래로 찍히고**, 그 반사가 전체의 절반이 넘습니다
      (이 저장소에 이미 적어둔 사실인데 제가 안 보고 짰습니다).

      그러면 반사층을 바닥으로 잡고, 그 위 0.1m 부터 본다고 하니
      **진짜 바닥이 통째로 장애물**이 됩니다. 시험용 복도를 넣었더니
      지도가 새까맣게 찼고, 앞이 0.02m 라고 했습니다.

    ★ 그래서 '빽빽함' 으로 찾습니다 ★

      바닥은 얇고 빽빽한 평면입니다. 벽은 높이로 퍼져 있고, 반사는
      흩어집니다. 그러니 높이를 5cm 칸으로 나눠 **점이 가장 많은 칸**을
      고르면 바닥이 잡힙니다.

      천장도 빽빽하므로, 로봇보다 위는 안 봅니다 (below).
    """
    z = pts[:, 2]
    if below is not None:
        z = z[z < below]
        if z.size == 0:
            z = pts[:, 2]
    lo, hi = float(z.min()), float(z.max())
    if hi - lo < step:
        return lo
    edges = np.arange(lo, hi + step, step)
    counts, _ = np.histogram(z, bins=edges)
    k = int(counts.argmax())
    return float((edges[k] + edges[k + 1]) / 2)


def robot_frame(pts, pose):
    """odom 좌표를 로봇이 보는 좌표로. (앞, 왼쪽) 을 돌려줍니다."""
    x, y, yaw = pose
    dx = pts[:, 0] - x
    dy = pts[:, 1] - y
    c, s = math.cos(yaw), math.sin(yaw)
    ahead = dx * c + dy * s
    left = -dx * s + dy * c
    return ahead, left


# 로봇 제 몸이 차지하는 자리. 이 안의 점은 장애물이 아닙니다.
#
#   ★ 반경으로 빼면 안 됩니다 ★
#     처음에는 "20cm 안쪽은 빼자" 로 원을 그렸습니다. 그런데 Go2 는
#     길이 0.70 m · 폭 0.31 m 로 **길쭉합니다.** pose 원점이 몸
#     가운데라면 앞다리 끝이 35cm 앞에 있습니다. 원으로는 옆은 너무
#     많이 빼고 앞은 못 뺍니다.
#
#     실제로 2026-09-14 첫 측정에서 "앞 0.22 m" 가 나왔는데, 지도에는
#     로봇 바로 앞이 비어 있었습니다. 벽이 아니라 제 다리였을 것입니다.
#     넉넉히 잡습니다 — 덜 빼서 제 다리를 벽으로 부르는 쪽이 더 나쁩니다.
BODY_AHEAD = 0.45        # 앞뒤로 이만큼 (몸 길이 절반 0.35 + 여유)
BODY_SIDE = 0.25         # 좌우로 이만큼 (몸 폭 절반 0.16 + 여유)


def not_me(ahead, left):
    """제 몸이 아닌 점들만 골라내는 표."""
    return ~((np.abs(ahead) <= BODY_AHEAD) & (np.abs(left) <= BODY_SIDE))


def nearest(ahead, left, half_width=0.4, half_angle=0.5):
    """앞·왼쪽·오른쪽으로 가장 가까운 것. 제 몸은 빼고 봅니다.

    앞은 **띠**로 봅니다 — 로봇 폭만큼의 통로에 무엇이 있는가.
    옆은 부채꼴로 봅니다 — 벽까지 얼마나 떨어져 있는가.
    """
    ok = not_me(ahead, left)
    out = {}
    band = ok & (np.abs(left) <= half_width) & (ahead > 0)
    out["앞"] = float(ahead[band].min()) if band.any() else None

    side = ok & (np.abs(ahead) <= half_angle)
    l = side & (left > 0)
    r = side & (left < 0)
    out["왼쪽"] = float(left[l].min()) if l.any() else None
    out["오른쪽"] = float(-left[r].max()) if r.any() else None
    out["제몸"] = int((~ok).sum())
    return out


def corridor_fit(ahead, left, span=2.0):
    """복도가 어느 쪽으로 뻗어 있는지 점들에게 물어보고, 그 기준으로 폭을 잽니다.

    ★ 왜 '앞뒤 ±0.5m 의 왼쪽·오른쪽' 으로는 안 되는가 ★

      그 방식은 **로봇이 복도와 나란히 서 있다고 가정**합니다. 비스듬히
      서 있으면 옆벽까지의 거리가 1/cos(각도) 배로 부풀고, 폭이 통째로
      틀립니다. 54도 틀어지면 1.15 m 짜리 복도가 1.98 m 로 보입니다.

      2026-09-14 에 같은 복도에서 1.98 과 1.62 가 나왔습니다. 어디에
      서 있든 단면의 폭은 같아야 하는데 달랐습니다 — 가정이 깨진 것입니다.

    ★ 그래서 벽에게 묻습니다 ★

      주변 점들이 가장 길게 늘어선 방향이 복도 방향입니다 (주성분).
      그 방향에 직각으로 재면 로봇이 어떻게 서 있든 같은 폭이 나옵니다.

      덤으로 **로봇이 복도와 몇 도 틀어져 있는지**가 같이 나옵니다.
      이 각도가 곧 나중에 '곧게 걷는가' 를 재는 자입니다.

    돌려주는 것: (틀어진 각도°, 왼쪽 m, 오른쪽 m, 폭 m, 쓴 점 수)
                 못 재면 전부 None.
    """
    return _fit(ahead, left, span)


def _old_pca_fit(ahead, left, span=2.0):
    """(안 씁니다 — 왜 버렸는지 남겨둡니다)

    주성분으로 복도 방향을 찾던 방식입니다. 평행한 두 벽만 있으면 잘
    맞습니다. 그런데 2026-09-14 실제 복도에서 **왼쪽 벽이 0.03 m** 라는
    답을 내놨습니다. 양쪽에 사물함·문틀 같은 덩어리가 있으면 주성분이
    엉뚱한 데를 가리키고, 그 위에 얹힌 계산이 그럴듯한 숫자를 만듭니다.

    틀린 것보다 나쁜 것은 **틀렸는데 측정처럼 생긴 것**입니다.
    """
    # ★ 고르는 모양은 원이어야 합니다 ★
    #   처음에 |앞| ≤ span 인 **띠**로 골랐습니다. 로봇이 비스듬하면 그
    #   띠가 비스듬히 잘려서 양쪽 벽이 서로 다른 길이로 뽑힙니다. 그러면
    #   주성분 방향이 몇 도 기울고, 긴 복도에서는 그 몇 도가 치명적입니다
    #   (4m 지점에서 6도면 0.42m 가 밀립니다). 원은 어느 쪽으로 돌려도
    #   같은 만큼 뽑으니 그런 편향이 없습니다.
    near = (ahead ** 2 + left ** 2) <= span ** 2
    if near.sum() < 20:
        return (None,) * 4 + (int(near.sum()),)
    pts = np.column_stack([ahead[near], left[near]])
    centred = pts - pts.mean(axis=0)
    vals, vecs = np.linalg.eigh(np.cov(centred.T))
    axis = vecs[:, int(vals.argmax())]
    if axis[0] < 0:                     # 늘 앞쪽을 향하게
        axis = -axis
    angle = math.degrees(math.atan2(axis[1], axis[0]))
    normal = np.array([-axis[1], axis[0]])       # 왼쪽이 +
    d = pts @ normal                              # 로봇은 원점입니다

    # ★ 최솟값이 아니라 '가장 빽빽한 자리' 가 벽입니다 ★
    #   최솟값은 튄 점 하나, 축의 작은 오차 하나에 그대로 끌려갑니다.
    #   벽은 줄지어 선 점 무더기라 histogram 에서 봉우리로 섭니다.
    def wall_at(side):
        v = d[side]
        if v.size < 10:
            return None
        lo, hi = float(np.abs(v).min()), float(np.abs(v).max())
        if hi - lo < 0.05:
            return float(np.abs(v).mean())
        edges = np.arange(lo, hi + 0.05, 0.05)
        counts, _ = np.histogram(np.abs(v), bins=edges)
        k = int(counts.argmax())
        return float((edges[k] + edges[k + 1]) / 2)

    left_m = wall_at(d > 0)
    right_m = wall_at(d < 0)
    width = (left_m + right_m) if (left_m is not None and right_m is not None) else None
    return angle, left_m, right_m, width, int(near.sum())


def _fit(ahead, left, span=2.5, bin_m=0.05, least=2.0):
    """복도를 **찾아서** 잽니다. 없으면 없다고 합니다.

    ★ 어떻게 찾는가 ★

      복도란 '어떤 방향으로 보면 점들이 **두 개의 빽빽한 평면**으로
      갈라지는 곳' 입니다. 그러니 방향을 1도씩 다 돌려보면서, 그
      방향에 직각으로 점을 늘어놨을 때 양쪽에 봉우리가 가장 또렷하게
      서는 각도를 고릅니다. 작은 허프 변환입니다.

      주성분과 다른 점은 **양쪽을 동시에 요구한다**는 것입니다. 점수를
      min(왼쪽 봉우리, 오른쪽 봉우리) 로 매기니, 한쪽 벽만 크게 보이는
      방향은 이길 수 없습니다. 덩어리 하나에 끌려가지 않습니다.

    ★ 그리고 아니면 아니라고 합니다 ★

      봉우리가 약하면 (전체의 least 미만) None 을 돌려줍니다. 여기가
      복도가 아니면 복도 폭이라는 것이 없습니다. 없는 값을 지어내는
      것보다 "못 재겠습니다" 가 낫습니다.

    돌려주는 것: (복도방향°, 왼쪽 m, 오른쪽 m, 폭 m, 쓴 점, 또렷함 — 1.0 이면 아무 방향이나 똑같음, 클수록 복도다움)
    """
    near = (ahead ** 2 + left ** 2) <= span ** 2
    n = int(near.sum())
    if n < 200:
        return (None,) * 4 + (n, 0.0)
    a, l = ahead[near], left[near]
    if a.size > 20000:                      # 너무 많으면 솎습니다 (결과는 같습니다)
        pick = np.linspace(0, a.size - 1, 20000).astype(int)
        a, l = a[pick], l[pick]

    edges = np.arange(-span, span + bin_m, bin_m)
    centres = (edges[:-1] + edges[1:]) / 2
    is_left = centres > 0.15                # 로봇 몸통 바로 옆은 벽이 아닙니다
    is_right = centres < -0.15

    def face(counts, xs, share=0.4):
        """벽까지의 거리 = **덩어리의 앞면**.

        ★ 가장 점이 많은 칸을 고르면 안 됩니다 ★
          사물함·문틀 같은 두꺼운 것은 속이 겉보다 점이 많습니다. 그러면
          벽이 실제보다 멀리 잡힙니다 — 2026-09-14 에 왼쪽 벽이 0.80 m
          인데 1.28 m 라고 했습니다. 로봇이 벽에 부딪히는 곳은 앞면이지
          속이 아닙니다.

          그래서 로봇 쪽에서부터 훑어나가며, 봉우리의 share 만큼 높아진
          **첫 칸**을 앞면으로 봅니다.
        """
        order = np.argsort(np.abs(xs))
        c = counts[order]
        x = np.abs(xs)[order]
        if c.max() <= 0:
            return None, 0
        hit = np.flatnonzero(c >= share * c.max())
        if not hit.size:
            return None, 0
        k = int(hit[0])
        return float(x[k]), int(c[k])

    scores = []
    best = (-1, None, None, None)
    for deg in range(-90, 90):
        th = math.radians(deg)
        d = -a * math.sin(th) + l * math.cos(th)
        counts, _ = np.histogram(d, bins=edges)
        lc = counts[is_left]
        rc = counts[is_right]
        if not lc.size or not rc.size:
            continue
        lx, ln = face(lc, centres[is_left])
        rx, rn = face(rc, centres[is_right])
        if lx is None or rx is None:
            continue
        score = min(ln, rn)
        scores.append(score)
        if score > best[0]:
            best = (score, deg, lx, rx)

    score, deg, lm, rm = best

    # ★ 또렷함은 '각도끼리 견줘서' 잽니다 ★
    #
    #   처음에는 '전체 점 대비 몇 %' 로 쟀습니다. 그러면 벽이 두꺼울수록
    #   점이 여러 칸에 퍼져서 저절로 작아지고, 주변이 어수선할수록 또
    #   작아집니다. 복도가 있느냐와 상관없는 것들에 흔들리는 자입니다.
    #
    #   복도가 있으면 **한 각도만 유난히 좋습니다.** 없으면 어느 각도나
    #   고만고만하고요. 그러니 가장 좋은 점수를 보통 점수로 나눕니다.
    #   1.0 이면 아무 방향이나 똑같다는 뜻이고, 크면 한 방향이 특별합니다.
    typical = float(np.median(scores)) if scores else 0.0
    sharp = (score / typical) if typical > 0 else 0.0
    if deg is None or sharp < least:
        return None, None, None, None, n, sharp
    return float(deg), lm, rm, lm + rm, n, sharp


def picture(ahead, left, reach=3.0, cols=45):
    """위에서 본 글자 지도. 로봇은 한가운데, 위쪽이 앞입니다."""
    rows = cols // 2
    step = (2 * reach) / cols
    grid = [[" "] * cols for _ in range(rows)]
    for a, l in zip(ahead, left):
        # 화면: 가로 = 왼쪽(왼쪽이 왼쪽), 세로 = 앞(위가 앞)
        cx = int((reach - l) / step)
        cy = int((reach - a) / (2 * reach / rows))
        if 0 <= cx < cols and 0 <= cy < rows:
            grid[cy][cx] = "█"
    mid_y, mid_x = rows // 2, cols // 2
    grid[mid_y][mid_x] = "▲"
    lines = ["".join(row) for row in grid]
    edge = "·" * cols
    return [edge] + lines + [edge]


async def main():
    ap = argparse.ArgumentParser(description="라이다가 보는 것을 읽습니다")
    ap.add_argument("--frames", type=int, default=3, help="몇 장을 겹칠지")
    ap.add_argument("--band", type=float, nargs=2, default=(0.10, 0.80),
                    metavar=("아래", "위"), help="볼 높이 (바닥에서 m)")
    ap.add_argument("--reach", type=float, default=3.0, help="지도 반경 (m)")
    ap.add_argument("--wait", type=float, default=8.0, help="몇 초까지 기다릴지")
    args = ap.parse_args()

    print("=" * 70)
    print(" 라이다가 보는 것")
    print("=" * 70)
    print(" ★ 로봇이 서 있어야 합니다 — 엎드려 있으면 점이 안 옵니다 ★")
    print()

    conn = await common.connect()
    if conn is None:
        print(" ✖ 못 붙었습니다.")
        return 1

    try:
        eyes = Eyes(conn)
        waited = 0.0
        while len(eyes.frames) < args.frames and waited < args.wait:
            await asyncio.sleep(0.3)
            waited += 0.3

        if not eyes.frames:
            print(" ✖ 점이 한 장도 안 왔습니다.")
            print()
            print("   로봇이 서 있습니까? 엎드려 있으면 안 옵니다.")
            print("   .\\run topics_seen.py 로 자세와 함께 확인해 보세요.")
            return 1
        if eyes.pose is None:
            print(" ✖ 자기 위치가 안 왔습니다 (robot_pose). 견줄 기준이 없습니다.")
            return 1

        pts = np.vstack(eyes.frames[-args.frames:])
        ceiling_guard = None if eyes.pose_z is None else eyes.pose_z + 0.05
        floor = floor_of(pts, below=ceiling_guard)
        print(f" 점 {len(pts):,}개 · {len(eyes.frames[-args.frames:])}장을 겹쳤습니다")
        print(f" 바닥으로 본 높이: {floor:+.2f} m (점이 가장 빽빽한 층)")
        print()

        # ★ 라이다가 보는 것은 상자 하나입니다 ★
        top = None
        if eyes.box is not None:
            origin, width, res = eyes.box
            span = width * res
            top = float(origin[2] + span[2]) - floor
            print(f" 라이다가 보는 상자: {span[0]:.1f} × {span[1]:.1f} × {span[2]:.1f} m")
            print(f"   바닥에서 위로 {top:.2f} m 까지만 봅니다 — "
                  "그 위는 '없는' 게 아니라 **안 보이는** 것입니다.")
            print()

        # 높이 분포 — 바닥·벽이 어디 있는지 사람이 보게
        print(" 높이 분포 (바닥 기준)")
        rel = pts[:, 2] - floor
        edges = [-0.5, -0.1, 0.1, 0.3, 0.5, 0.8, 1.2, 2.0, 9.0]
        for lo, hi in zip(edges, edges[1:]):
            n = int(((rel >= lo) & (rel < hi)).sum())
            bar = "▇" * min(40, n * 40 // max(1, len(pts)))
            edge = ""
            if top is not None and lo >= top:
                edge = "  ← 상자 밖 (안 보이는 높이)"
            print(f"   {lo:+5.1f} ~ {hi:+5.1f} m  {n:>7,}  {bar}{edge}")
        print()

        low, high = args.band
        keep = (rel >= low) & (rel <= high)
        if not keep.any():
            print(f" ✖ {low}~{high} m 사이에 점이 없습니다. --band 를 바꿔보세요.")
            return 1

        ahead, left = robot_frame(pts[keep], eyes.pose)
        near = nearest(ahead, left)

        print(f" 가장 가까운 것 ({low}~{high} m 높이만 봤습니다)")
        for name in ("앞", "왼쪽", "오른쪽"):
            d = near[name]
            print(f"   {name:4} {f'{d:.2f} m' if d is not None else '아무것도 없음'}")
        print(f"   ※ 제 몸으로 보고 뺀 점 {near['제몸']:,}개 "
              f"(앞뒤 {BODY_AHEAD} m · 좌우 {BODY_SIDE} m 안쪽)")
        print()

        # ── 복도를 벽에게 물어서 잽니다 ───────────────────────
        angle, cl, cr, cw, used, sharp = corridor_fit(ahead, left)
        print(" 복도 (벽이 뻗은 방향을 찾아서 직각으로 쟀습니다)")
        if cw is None:
            print(f"   ✖ 복도로 안 보입니다 (또렷함 {sharp:.2f}, 점 {used:,}개 · 2.0 이상이어야 믿습니다)")
            print("     평행한 두 벽이 안 잡힙니다. 트인 곳이거나,")
            print("     양쪽이 덩어리(사물함·문틀)라서 벽 평면이 안 섭니다.")
            print("     ※ 여기서 폭을 지어내지 않습니다 — 없는 값입니다.")
        else:
            # angle 은 **복도가 뻗은 방향**입니다 (로봇 정면 기준).
            #   복도가 왼쪽으로 뻗어 보이면(+) 로봇이 오른쪽으로 튼 것입니다.
            lean = ("복도와 나란합니다" if abs(angle) < 5 else
                    f"복도에서 {abs(angle):.0f}도 "
                    f"{'오른쪽' if angle > 0 else '왼쪽'}으로 틀어져 있습니다")
            print(f"   폭      {cw:.2f} m   (왼쪽 {cl:.2f} · 오른쪽 {cr:.2f})")
            print(f"   로봇은  {lean}    [또렷함 {sharp:.2f}]")
            off = (cl - cr) / 2
            print(f"   가운데에서 {abs(off):.2f} m "
                  f"{'오른쪽' if off > 0 else '왼쪽'}으로 치우쳐 있습니다")
            if near["왼쪽"] is not None and near["오른쪽"] is not None:
                naive = near["왼쪽"] + near["오른쪽"]
                if abs(naive - cw) > 0.15:
                    print(f"   ※ 로봇 방향 그대로 재면 {naive:.2f} m 입니다 — "
                          f"{abs(naive - cw):.2f} m 차이는 틀어진 탓입니다")
        print()

        behind = int((ahead < -0.5).sum())
        print(f" 뒤쪽(-0.5 m 뒤)의 점: {behind:,}개")
        print("   ※ 라이다가 머리 밑에 있어 뒤는 잘 안 봅니다.")
        print("     지도의 빈 곳은 '없다' 가 아니라 **'안 봤다'** 일 수 있습니다.")
        print()

        print(f" 위에서 본 모습 (반경 {args.reach:.1f} m · ▲ 가 로봇, 위가 앞)")
        print(f"   가로 한 칸 ≈ {2 * args.reach / 45:.2f} m · 제 몸은 뺐습니다")
        keep_body = not_me(ahead, left)
        for line in picture(ahead[keep_body], left[keep_body], reach=args.reach):
            print("   " + line)
        print()
        print(" ※ 이 건물 바닥은 거울 같아서 반사가 바닥 아래로 찍힙니다.")
        print("   높이로 걸러낸 덕에 위 지도에는 안 들어왔습니다.")
        return 0
    finally:
        await common.disconnect(conn)


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
