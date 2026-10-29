# switch_terrain.py — robotdog00 · 꺾인 계단 (참에서 180도 도는 계단) 학습 지형 (2026-10-29, README 83-1)
#
#  flat_env_cfg.py 의 SWITCH_STAIRS = True 일 때 지형 조각 "switch_up" · "switch_down" 으로 씁니다
#  (cfg 에는 "모듈:함수" 글자로만 적음 — 이 파일은 지형을 만들 때 (시뮬레이터가 뜬 뒤) 불러옵니다 · 77-2 와 같은 까닭).
#  numpy · trimesh 만 씁니다 (pxr 를 안 부름).
#
#  모양 (한 조각 8 × 8 m · rig 의 v2 무대를 본뜸 · 79-2):
#      x →   [바닥참 floor_depth] [단 num_steps × step_width] [가운데 참 landing_depth]
#      y ↑   A 쪽 단 (폭 flight_width) · 칸막이 (gap) · B 쪽 단 (폭 flight_width)
#      A 쪽: 바닥참 높이 0 → 단을 +x 로 오름 → 가운데 참 (높이 N·r · A · B 를 다 덮음)
#      B 쪽: 가운데 참에서 −x 로 오름 → 위 바닥참 (높이 2N·r)
#      둘레와 칸막이는 벽 (가장 높은 바닥 + wall_height) · 계단실 밖은 벽 높이까지 막힌 덩어리.
#      위아래 층이 겹치지 않습니다 (한 조각 = 한 층 높이) — 위에서 쏘는 높이 스캔이 머리 위 층에 맞지 않게.
#  start = "bottom" (switch_up): A 쪽 바닥참 가운데에 놓임 → 오르기
#  start = "top"    (switch_down): B 쪽 위 바닥참 가운데에 놓임 → 내려가기
#  rig 와 다른 점 (적어 둠): 가운데 참의 깎은 모서리 없음 · 문 · 사람 없음 · 1층 들머리 없음 · 한 조각에 한 층.
import numpy as np
import trimesh


def switch_layout(cfg):
    """조각 안의 치수 (조각 왼쪽 아래 모서리 = (0, 0))."""
    W, G, N, t = cfg.flight_width, cfg.gap, int(cfg.num_steps), cfg.step_width
    L = cfg.floor_depth + N * t + cfg.landing_depth
    x0 = 0.5 * (cfg.size[0] - L)
    y0 = 0.5 * (cfg.size[1] - (2 * W + G))
    xa = x0 + cfg.floor_depth           # 단 시작
    xm = xa + N * t                     # 가운데 참 시작
    x1 = xm + cfg.landing_depth         # 가운데 참 끝 (뒤 벽)
    yA0, yA1 = y0, y0 + W
    yB0, yB1 = yA1 + G, yA1 + G + W
    return dict(x0=x0, xa=xa, xm=xm, x1=x1, yA0=yA0, yA1=yA1, yB0=yB0, yB1=yB1, N=N, t=t, W=W, G=G)


def _box(x0, x1, y0, y1, z0, z1):
    return trimesh.creation.box(
        (x1 - x0, y1 - y0, z1 - z0),
        trimesh.transformations.translation_matrix((0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1))))


def switch_stairs_terrain(difficulty: float, cfg):
    r = cfg.step_height_range[0] + difficulty * (cfg.step_height_range[1] - cfg.step_height_range[0])
    g = switch_layout(cfg)
    N, t = g["N"], g["t"]
    top = 2 * N * r
    wall = top + cfg.wall_height
    zb = -0.5                                                     # 덩어리의 밑 (바닥 아래로 묻음)
    sx, sy = cfg.size
    m = []
    # A 쪽: 바닥참 (0) · 단 (오름)
    m.append(_box(g["x0"], g["xa"], g["yA0"], g["yA1"], zb, 0.0))
    for k in range(1, N + 1):
        m.append(_box(g["xa"] + (k - 1) * t, g["xa"] + k * t, g["yA0"], g["yA1"], zb, k * r))
    # 가운데 참 (A · 칸막이 · B 를 다 덮음)
    m.append(_box(g["xm"], g["x1"], g["yA0"], g["yB1"], zb, N * r))
    # B 쪽: 가운데 참에서 −x 로 오르는 단 · 위 바닥참
    for k in range(1, N + 1):
        m.append(_box(g["xm"] - k * t, g["xm"] - (k - 1) * t, g["yB0"], g["yB1"], zb, N * r + k * r))
    m.append(_box(g["x0"], g["xa"], g["yB0"], g["yB1"], zb, top))
    # 칸막이 (단 사이 · 바닥참에서 가운데 참 앞까지)
    m.append(_box(g["x0"], g["xm"], g["yA1"], g["yB0"], zb, wall))
    # 계단실 밖은 벽 높이까지 막음 (네 덩어리)
    m.append(_box(0.0, sx, 0.0, g["yA0"], zb, wall))
    m.append(_box(0.0, sx, g["yB1"], sy, zb, wall))
    m.append(_box(0.0, g["x0"], g["yA0"], g["yB1"], zb, wall))
    m.append(_box(g["x1"], sx, g["yA0"], g["yB1"], zb, wall))
    xc = 0.5 * (g["x0"] + g["xa"])
    if cfg.start == "top":
        origin = np.array([xc, 0.5 * (g["yB0"] + g["yB1"]), top])
    else:
        origin = np.array([xc, 0.5 * (g["yA0"] + g["yA1"]), 0.0])
    return m, origin


def switch_offsets(cfg):
    """놓인 자리 (origin) 에서 본 길의 치수 — 명령 클래스 · 커리큘럼이 씁니다 (guide_mix_command.py).
    u = x − 놓인 x · 가운데 참의 가운데 u_mid · 단 끝 (참 시작) u_land · 건너편 단의 줄은 놓인 y + dy."""
    g = switch_layout(cfg)
    xc = 0.5 * (g["x0"] + g["xa"])
    u_land = g["xm"] - xc
    u_mid = 0.5 * (g["xm"] + g["x1"]) - xc
    dy = (0.5 * (g["yB0"] + g["yB1"]) - 0.5 * (g["yA0"] + g["yA1"]))
    return dict(u_land=u_land, u_mid=u_mid, dy=(dy if cfg.start != "top" else -dy), lane_half=0.5 * g["W"])
