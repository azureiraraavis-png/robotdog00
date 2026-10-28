# -*- coding: utf-8 -*-
"""라이다로 본 바닥이 몸 둘레 어디까지인가 — 특히 **뒤 사각** 을 잽니다 (README 2부 79-12 · docs/2_training.md).
   ★ 로봇은 움직이지 않습니다 — 다만 **서 있어야 합니다** ★

  왜:
    계단 위에서 서서 기다리는 대신 "가장 가까운 참까지 뒤로" 가려면 (사이안 님 10/28),
    개가 뒤를 얼마나 보는지 알아야 합니다. 라이다 (L1) 는 사양상 360° × 90° 이지만
    머리 앞에 달려 있어서, 몸 뒤 낮은 곳은 제 몸이 가릴 수 있습니다.

  무엇을 하는가 (읽기만):
    · 점구름 (voxel_map_compressed · 5 cm 칸) 과 자기 위치 (robot_pose) 를 받습니다 — 명령은 하나도 안 보냅니다.
      (연결할 때 common.connect 가 늘 하는 두 가지 — 오디오 길 열기 · 자동 복구 끄기 — 만 합니다. 다른 스크립트와 같습니다.)
    · 바닥 (점이 가장 빽빽한 층 · lidar_look.py 와 같은 방법) 에서 ±6 cm 안의 점을 "보인 바닥" 으로 셉니다.
      거울 반사는 바닥 아래로 찍히므로 빠집니다.
    · 몸 둘레를 10 cm 칸으로 나눠 위에서 본 글자 지도를 찍고,
      앞 · 뒤 · 왼쪽 · 오른쪽으로 "몸 끝에서 처음 바닥이 보이는 거리" 와
      "몸 끝에서 1 m 안의 칸 중 바닥이 보인 비율" 을 셉니다.
    · 받은 점을 seen\\rear_시각.npz 로 남깁니다 (seen\\ 은 git 밖).

  ★ 지도는 쌓인 것입니다 ★
    로봇이 켜진 뒤 움직였다면 지나온 바닥도 지도에 남아 "보인다" 고 나옵니다.
    **켜고 일어선 자리에서 움직이지 않은 채** 재야 그 자리에서 보는 사각이 나옵니다.

  쓰는 법
      .\\run rear_look.py               10장 겹쳐서 (15초까지 기다림)
      .\\run rear_look.py --frames 20   더 많이 겹쳐서

  실행 전 체크리스트
      □ ★ 로봇이 서 있을 것 ★ (엎드려 있으면 점이 안 옵니다)
      □ 켜고 일어선 뒤 움직이지 않았을 것 (위 ★)
      □ 둘레 1.5 m 안에 사람이 없을 것 (사람 다리가 바닥을 가립니다)
      □ 폰의 유니트리 앱을 닫을 것 (한 번에 한 손님만 받습니다)
"""

import argparse
import asyncio
import math
import os
import sys
import time

import numpy as np

import common
from lidar_look import Eyes, robot_frame

HALF_L, HALF_W = 0.35, 0.155      # Go2 몸 반길이 · 반폭 (m) — 몸 끝은 몸 가운데에서 이만큼
CELL = 0.10                       # 지도 칸 (m)
FLOOR_TOL = 0.06                  # 바닥 ±이만큼을 "보인 바닥" 으로


def floor_est(pts, below=None, step=0.05):
    """바닥 = 점이 가장 빽빽한 높이 층 (lidar_look.floor_of 와 같은 생각).
       다만 칸 경계를 점 높이 사이 (반 칸 밀어서) 에 둡니다 — 점 높이가 5 cm 격자 위에 있어서,
       경계가 점 높이와 겹치면 맨 위 층이 히스토그램 밖으로 빠질 수 있습니다 (시험 자료에서 겪음)."""
    z = pts[:, 2]
    if below is not None and (z < below).any():
        z = z[z < below]
    lo, hi = float(z.min()), float(z.max())
    edges = np.arange(lo - step / 2.0, hi + step, step)
    if len(edges) < 2:
        return lo
    counts, _ = np.histogram(z, bins=edges)
    k = int(counts.argmax())
    return float((edges[k] + edges[k + 1]) / 2.0)


def floor_cells(ahead, left, rel, reach=2.0):
    """바닥 점이 있는 칸 (i: 앞 방향 · j: 왼쪽 방향) 집합 · 장애물 칸 집합."""
    fl, ob = set(), set()
    for a, l, r in zip(ahead, left, rel):
        if abs(a) > reach + HALF_L or abs(l) > reach + HALF_W:
            continue
        key = (int(math.floor(a / CELL)), int(math.floor(l / CELL)))
        if abs(r) <= FLOOR_TOL:
            fl.add(key)
        elif 0.10 <= r <= 0.80:
            ob.add(key)
    return fl, ob


def first_seen(ahead, left, rel, direction, band):
    """몸 끝에서 그 방향으로 처음 바닥이 보이는 거리 (m) · 몸 끝에서 1 m 안 (몸 옆으로 ±band) 을 10 cm 칸으로 나눴을 때 바닥이 보인 칸의 비율.
       칸은 몸 끝에서부터 잽니다 (몸 가운데가 아니라)."""
    m = np.abs(rel) <= FLOOR_TOL
    a, l = ahead[m], left[m]
    if direction == "앞":
        d, o = a - HALF_L, l
    elif direction == "뒤":
        d, o = -a - HALF_L, l
    elif direction == "왼쪽":
        d, o = l - HALF_W, a
    else:
        d, o = -l - HALF_W, a
    k = (d > 0.0) & (d <= 1.0) & (np.abs(o) <= band)
    if not k.any():
        return None, 0.0
    cells = {(int(dd // CELL), int(math.floor(oo / CELL))) for dd, oo in zip(d[k], o[k])}
    total = int(round(1.0 / CELL)) * int(round(2 * band / CELL))
    return float(d[k].min()), min(1.0, len(cells) / total)


def draw(fl, ob, reach=1.6):
    """위에서 본 글자 지도 — 위쪽이 개의 앞. '#' 몸 · '.' 보인 바닥 · 'o' 바닥 위 0.1~0.8 m 의 것 · ' ' 안 보임."""
    rows = []
    n = int(round(reach / CELL))
    for i in range(n, -n - 1, -1):                # 앞 → 뒤
        row = []
        for j in range(n, -n - 1, -1):            # 왼쪽 → 오른쪽
            a, l = (i + 0.5) * CELL, (j + 0.5) * CELL
            if abs(a) <= HALF_L and abs(l) <= HALF_W:
                row.append("#")
            elif (i, j) in ob:
                row.append("o")
            elif (i, j) in fl:
                row.append(".")
            else:
                row.append(" ")
        mark = ""
        if i == int(math.floor(HALF_L / CELL)):
            mark = "   ← 몸 앞끝"
        if i == int(math.floor(-HALF_L / CELL)):
            mark = "   ← 몸 뒤끝"
        if i == int(math.floor(-(HALF_L + 0.30) / CELL)):
            mark = "   ← 뒤끝에서 0.3 m"
        if i == int(math.floor(-(HALF_L + 1.0) / CELL)):
            mark = "   ← 뒤끝에서 1.0 m"
        rows.append("   |" + "".join(row) + "|" + mark)
    return "\n".join(rows)


async def main():
    ap = argparse.ArgumentParser(description="라이다로 본 바닥 — 뒤 사각 재기 (읽기만)")
    ap.add_argument("--frames", type=int, default=10, help="몇 장을 겹칠지")
    ap.add_argument("--wait", type=float, default=15.0, help="몇 초까지 기다릴지")
    args = ap.parse_args()

    print("=" * 70)
    print(" 뒤 사각 재기 — 라이다로 본 바닥 (로봇은 움직이지 않습니다)")
    print("=" * 70)
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
            print(" ✖ 점이 한 장도 안 왔습니다 — 로봇이 서 있습니까? (엎드려 있으면 안 옵니다)")
            return 1
        if eyes.pose is None:
            print(" ✖ 자기 위치 (robot_pose) 가 안 왔습니다.")
            return 1
        pts = np.vstack(eyes.frames[-args.frames:])
        guard = None if eyes.pose_z is None else eyes.pose_z + 0.05
        floor = floor_est(pts, below=guard)
        rel = pts[:, 2] - floor
        ahead, left = robot_frame(pts, eyes.pose)
        fl, ob = floor_cells(ahead, left, rel)
        n_floor = int((np.abs(rel) <= FLOOR_TOL).sum())
        print(f" 점 {len(pts):,}개 · {len(eyes.frames[-args.frames:])}장 · 바닥 {floor:+.2f} m (odom)"
              f" · 바닥 ±{FLOOR_TOL * 100:.0f} cm 안의 점 {n_floor:,}개 · 몸 높이 {((eyes.pose_z or float('nan')) - floor):.2f} m")
        print()
        print(" 몸 끝에서 처음 바닥이 보이는 거리 · 몸 끝 1 m 안에서 바닥이 보인 칸의 비율")
        for name, band in (("앞", 0.30), ("뒤", 0.30), ("왼쪽", 0.40), ("오른쪽", 0.40)):
            d, frac = first_seen(ahead, left, rel, name, band)
            print(f"   {name:4} 처음 {('%.2f m' % d) if d is not None else '— (1 m 안에 없음)'}"
                  f" · 보인 칸 {frac * 100:3.0f} %   (몸 옆으로 ±{band:.1f} m 띠)")
        print()
        print(" 위에서 본 지도 (위쪽 = 개의 앞 · 칸 10 cm · '#' 몸 · '.' 보인 바닥 · 'o' 바닥 위 0.1~0.8 m · 빈칸 = 안 보임)")
        print(draw(fl, ob))
        os.makedirs("seen", exist_ok=True)
        out = os.path.join("seen", time.strftime("rear_%Y%m%d_%H%M%S.npz"))
        np.savez_compressed(out, pts=pts, pose=np.asarray(eyes.pose), pose_z=np.asarray(eyes.pose_z or np.nan), floor=floor)
        print()
        print(f" 점을 남겼습니다 → {out}")
        return 0
    finally:
        try:
            await conn.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(asyncio.run(main()) or 0)
