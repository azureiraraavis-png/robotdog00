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


def side_view(ahead, left, height, band=0.45, front=3.5, back=1.0,
              low=-0.7, high=1.5, cols=46):
    """옆에서 본 모습. **계단은 이 그림에서만 보입니다.**

    ★ 왜 위에서 본 지도로는 안 되는가 ★

      위에서 보면 계단도 벽도 '앞에 뭔가 있음' 으로 똑같이 찍힙니다.
      계단의 생김새는 **앞으로 갈수록 바닥이 올라가는 것**이고, 그건
      높이를 세로로 놓아야 나타납니다.

      가로 = 앞으로 얼마나  ·  세로 = 바닥에서 몇 m
      로봇 폭만큼(±band)의 띠만 봅니다 — 옆벽이 끼어들면 다 찹니다.

    읽는 법
      바닥      아래쪽에 가로로 쭉 이어진 줄
      벽        어느 자리에서 세로로 솟은 줄
      ★계단★   비스듬히 올라가는 층계 모양
      내려가는 계단  앞쪽 바닥이 뚝 끊기고 그 아래로 이어짐
    """
    keep = np.abs(left) <= band
    a, h = ahead[keep], height[keep]
    rows = int((high - low) / 0.1)
    step_x = (front + back) / cols
    grid = [[" "] * cols for _ in range(rows)]
    for x, z in zip(a, h):
        cx = int((x + back) / step_x)
        cy = int((high - z) / 0.1)
        if 0 <= cx < cols and 0 <= cy < rows:
            grid[cy][cx] = "█"
    out = []
    for i, row in enumerate(grid):
        z = high - i * 0.1
        mark = f"{z:+5.1f} "
        out.append(mark + "".join(row))
    # 로봇 자리 표시
    zero = int(back / step_x)
    floor_row = int((high - 0.0) / 0.1)
    if 0 <= floor_row < rows:
        line = list(out[floor_row])
        if 6 + zero < len(line):
            line[6 + zero] = "▲"
        out[floor_row] = "".join(line)
    ruler = "      " + "".join(
        "|" if abs((i * step_x - back) % 1.0) < step_x / 2 else "·"
        for i in range(cols))
    return out + [ruler, f"      ← {back:.1f}m 뒤        0        "
                        f"앞 {front:.1f}m →"]


def ground_ahead(ahead, left, height, band=0.45, step=0.10,
                 front=3.0, jump=0.35, floor_gap=-0.80):
    """앞쪽 **지면**을 로봇 쪽에서부터 이어가며 따라갑니다.

    ★ '그 칸의 가장 낮은 점' 으로는 안 됩니다 — 여기서 크게 틀렸습니다 ★

      2026-09-14, **내려가는 계단 위에 세워놓고 "올라갑니다" 라고
      했습니다.** 이 말을 믿고 앞으로 가면 떨어집니다. 이 저장소에서
      가장 위험한 오답이었습니다.

      까닭: 내려가는 계단은 상자 밖으로 나갑니다 (상자 바닥이 바닥에서
      0.58 m 아래인데 계단은 그보다 더 내려갑니다). 지면이 안 보이는
      칸에서 '가장 낮은 점' 을 찾으면 **건너편 벽이나 난간**이 잡히고,
      그건 0.8 m 쯤 위에 있습니다. 그러니 프로필이 위로 튀고 직선
      맞춤이 '올라감' 이 됩니다.

      ★ 지면은 이어져 있습니다 ★
        계단 한 칸은 0.17 m 쯤입니다. 앞 칸의 지면에서 jump(0.35 m)
        보다 더 튀면 그건 지면이 아니라 딴 것입니다. 그래서 로봇
        발밑에서 시작해 **이어지는 동안만** 따라가고, 끊기면 멈춥니다.

        멈춘 자리가 곧 **"여기까지만 보입니다"** 이고, 내려가는 계단에서는
        그 숫자가 계단 각도보다 중요합니다.

    돌려주는 것: (프로필 [(거리, 높이)…], 지면이 끊긴 거리 or None)
    """
    keep = (np.abs(left) <= band) & (height > floor_gap)
    a, h = ahead[keep], height[keep]

    # 발밑의 지면부터 시작합니다. 없으면 0 으로 봅니다 (바닥에 서 있으니).
    under = (a > -0.3) & (a < 0.3)
    prev = float(np.percentile(h[under], 5)) if under.sum() >= 3 else 0.0

    out = []
    lost = None
    k = 0
    while True:
        x = k * step                      # ★ 더해 나가면 라벨이 겹칩니다 ★
        if x >= front:                    #   0.2·0.2·0.8·0.8 처럼 같은 거리가
            break                         #   두 번 찍혔습니다. 곱셈으로 바꿉니다.
        here = (a >= x) & (a < x + step)
        near = here & (np.abs(h - prev) <= jump)
        if near.sum() >= 3:
            prev = float(np.percentile(h[near], 5))
            out.append((x + step / 2, prev))
        elif here.sum() >= 3:
            # 뭔가 있긴 한데 지면으로 이어지지 않습니다 — 거기서 끊깁니다
            lost = x
            break
        else:
            lost = x
            break
        k += 1
    return out, lost


def steps_in(profile, least=0.04, look=3):
    """지면에서 **턱**을 찾습니다. 계단이 아니라 문턱 같은 단차용.

    ★ 기울기로는 단차를 못 봅니다 ★

      10 cm 턱 하나를 0.5~2.5 m 에 걸쳐 직선으로 맞추면 3도쯤 됩니다.
      '평평함' 문턱이 5도니 그냥 평지로 읽힙니다. 그런데 로봇에게
      10 cm 턱은 평지가 아닙니다 — 내려설 때 헛디딥니다.

      계단은 **기울기**로 보고 단차는 **턱**으로 봐야 합니다. 같은
      지면 프로필을 두 가지 눈으로 봅니다.

    ★ 한 칸만 보고 판단하지 않습니다 ★

      한 칸은 5 cm 격자라 ±5 cm 씩 흔들립니다. 그러니 앞뒤 look 칸의
      **가운데값**을 견줍니다. 진짜 턱은 그 뒤로도 계속 높거나 낮고,
      튄 점 하나는 가운데값에 안 끌려갑니다.

    돌려주는 것: [(거리 m, 높이차 m)…]  + 는 올라섬, - 는 내려섬
    """
    if len(profile) < 3:
        return []
    zs = [z for _, z in profile]
    xs = [x for x, _ in profile]
    found = []
    # ★ 끝자락을 안 보면 안 됩니다 ★
    #   앞뒤 세 칸씩 견주느라 **마지막 세 칸을 아예 안 봤습니다.**
    #   2026-09-14 문턱 앞에서 잰 값이 하필 거기 있었습니다 (1.4 m 에서
    #   +5 cm, 프로필은 1.4 m 에서 끝) — 문턱을 낮춰도 못 찾았을 것입니다.
    #
    #   게다가 **턱 바로 뒤는 그림자라 지면이 끊깁니다.** 라이다가 머리
    #   밑에서 앞을 보니 턱의 앞면은 보여도 그 뒤 바닥은 가려집니다.
    #   그러니 '프로필의 끝' 이야말로 턱이 있을 자리입니다. 끝에서는
    #   있는 칸만으로 견줍니다.
    for i in range(1, len(zs)):
        b0 = max(0, i - look)
        a1 = min(len(zs), i + look)
        pre = sorted(zs[b0:i])
        post = sorted(zs[i:a1])
        if not pre or not post:
            continue
        before = pre[len(pre) // 2]
        after = post[len(post) // 2]
        rise = after - before
        if abs(rise) < least:
            continue
        # ★ 작은 턱은 지면이 고르던 자리에서만 믿습니다 ★
        #   문턱을 5 cm 까지 낮추니 **거친 평지에서 없는 턱 셋을
        #   만들어냈습니다** (흔들림 ±2.5cm 를 넣어봤습니다).
        #   헛울리는 검사기는 없느니만 못합니다 — 이 저장소에 이미
        #   네 번 적은 말입니다.
        #
        #   격자가 5 cm 라 그 언저리 값은 지면이 미동도 없을 때만
        #   뜻이 있습니다. 큰 턱(7 cm 이상)은 흔들려도 턱입니다.
        #   그리고 **견줄 칸이 모자라면 작은 턱은 안 봅니다.** 첫 칸에서는
        #   앞쪽 표본이 하나뿐이라 '흔들림 0' 으로 보이고, 그러면 흔들림
        #   검사를 그냥 통과합니다 — 검사가 있는 척만 하는 자리입니다.
        wobble = (max(pre) - min(pre)) if len(pre) >= 2 else 999.0
        if abs(rise) < 0.10 and (len(pre) < look or wobble > 0.02):
            continue
        found.append((xs[i], rise))
    # 붙어 있는 것들은 한 턱으로 봅니다 (계단이면 여러 개가 줄지어 옵니다)
    merged = []
    for x, rise in found:
        if merged and abs(x - merged[-1][0]) < 0.25 and \
                (rise > 0) == (merged[-1][1] > 0):
            if abs(rise) > abs(merged[-1][1]):
                merged[-1] = (merged[-1][0], rise)
        else:
            merged.append((x, rise))
    return merged


def read_steps(steps):
    """턱을 사람 말로."""
    if not steps:
        return "   턱은 없습니다 (4 cm 이상 되는 단차가 안 보입니다)"
    lines = []
    for x, rise in steps:
        way = "올라섭니다" if rise > 0 else "내려섭니다"
        lines.append(f"   앞 {x:.2f} m 에서 {abs(rise)*100:.0f} cm {way}")
    # ★ '여럿이면 계단' 이 아닙니다 ★
    #   턱이 셋 이상이면 계단이라고 했더니, 부호가 오르내리락하는 잡음
    #   셋에도 "계단일 수 있습니다" 를 붙였습니다 (2026-09-14 문턱에서).
    #   계단은 **같은 쪽으로** 연달아 갑니다. 오르락내리락은 계단이 아니라
    #   울퉁불퉁한 바닥입니다.
    ups = [r for _, r in steps if r > 0]
    downs = [r for _, r in steps if r < 0]
    if len(ups) >= 3 or len(downs) >= 3:
        lines.append("   ※ 같은 쪽 턱이 여럿 줄지어 있습니다 — 계단일 수 있습니다.")
    elif len(steps) >= 3:
        lines.append("   ※ 오르내림이 섞여 있습니다 — 계단이 아니라 "
                     "울퉁불퉁하거나, 작은 것은 잡음일 수 있습니다.")
    lines.append("   ※ 5 cm 안팎은 격자 한 칸이라 아슬아슬합니다 — 지면이")
    lines.append("     흔들림 없이 고르던 자리에서만 믿으세요.")
    lines.append("   ※ 거리는 ±0.1 m 쯤 어림입니다 — 앞뒤 세 칸의 가운데값을")
    lines.append("     견주느라 가장자리가 조금 앞당겨 잡힙니다. 높이는 정확합니다.")
    return "\n".join(lines)


def slope_of(profile, near=0.5, far=2.5):
    """지면이 얼마나 기울어 있는지. (각도°, 쓴 구간 수, 높이차 m)

    계단 한 칸씩을 보지 않고 **여러 칸에 걸친 기울기**를 봅니다 — 칸
    하나는 수직이라 각도가 90도로 나옵니다. 우리가 알고 싶은 것은
    '이 앞이 올라가는가 내려가는가' 입니다.

    ※ ground_ahead 가 **이어지는 지면만** 돌려주므로, 여기 들어오는
      것은 전부 진짜 지면입니다. 끊긴 뒤의 벽은 애초에 안 옵니다.
    """
    use = [(x, z) for x, z in profile if near <= x <= far]
    if len(use) < 4:
        return None, len(use), None
    xs = np.array([x for x, _ in use])
    zs = np.array([z for _, z in use])
    a, _b = np.polyfit(xs, zs, 1)
    return math.degrees(math.atan(a)), len(use), float(zs[-1] - zs[0])


def read_ground(profile, lost=None):
    """사람 말로 옮깁니다."""
    deg, n, rise = slope_of(profile)
    if deg is None:
        return f"   앞쪽 지면을 못 읽었습니다 (쓸 구간 {n}개)"
    if abs(deg) < 5:
        what = "평평합니다"
    elif deg > 0:
        what = f"**올라갑니다** — 계단이라면 {deg:.0f}도 (보통 30~35도)"
    else:
        what = f"**내려갑니다** — {abs(deg):.0f}도"
    lines = [f"   앞 0.5~2.5 m 의 지면이 {what}",
             f"   (그 사이 높이차 {rise:+.2f} m · 구간 {n}개)"]
    deep = [x for x, z in profile if z < -0.15]
    if deep:
        lines.append(f"   ※ 앞 {min(deep):.1f} m 부터 **바닥 아래로 이어집니다.**")
        lines.append("     내려가는 계단이거나 거울 반사입니다 — 둘은 이 숫자로")
        lines.append("     못 가립니다. 옆에서 본 그림을 보세요: 계단은 이어진")
        lines.append("     면이고, 반사는 흩어져 있습니다.")
    if lost is not None:
        lines.append(f"   ★ 지면이 앞 {lost:.1f} m 에서 **끊깁니다** — "
                     "그 너머는 못 봅니다.")
        if deep:
            lines.append("     내려가는 계단이 상자 밖으로 나간 것으로 보입니다.")
            lines.append("     상자 바닥이 바닥에서 0.58 m 아래이니, 계단 서너 칸이")
            lines.append("     한계입니다. **그 아래는 눈이 없습니다.**")
    return "\n".join(lines)


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

        # ★ 옆모습은 높이를 안 거릅니다 ★
        #   계단은 '바닥이 올라가는 것' 이라, 바닥을 걸러내면 계단도
        #   같이 사라집니다. 위에서 본 지도는 걸러야 읽히고, 옆에서 본
        #   그림은 안 걸러야 읽힙니다.
        ahead_all, left_all = robot_frame(pts, eyes.pose)
        rel_all = pts[:, 2] - floor

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
        prof, lost = ground_ahead(ahead_all, left_all, rel_all)
        print(" 앞쪽 지면")
        print(read_ground(prof, lost))
        print()
        print(" 턱 (문턱 같은 단차)")
        print(read_steps(steps_in(prof)))
        if prof:
            shown = [f"{x:.1f}m:{z:+.2f}" for x, z in prof[:14]]
            print("   " + "  ".join(shown))
        print()

        print(f" 옆에서 본 모습 (앞뒤 띠 ±0.45 m · 세로는 바닥에서 m)")
        print("   바닥=가로줄 · 벽=세로줄 · ★계단=비스듬한 층계★")
        for line in side_view(ahead_all, left_all, rel_all):
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
