# walked.py — 99-8: 발 자취 csv 에서 몸이 움직인 길이 · 처음과 끝 사이 거리 · 오른 높이 (읽기만 · numpy 만).
#   쓰는 법:  python walked.py <csv> ...
import sys

import numpy as np

for p in sys.argv[1:]:
    try:
        a = np.genfromtxt(p, delimiter=",", comments="#", skip_header=2)
    except Exception as e:
        print(f"   {p} : ✖ 못 읽음 ({e})")
        continue
    t, x, y, z = a[:, 0], a[:, 1], a[:, 2], a[:, 3]
    path = float(np.sum(np.hypot(np.diff(x), np.diff(y))))
    net = float(np.hypot(x[-1] - x[0], y[-1] - y[0]))
    print(f"   {p.replace(chr(92), '/').split('/')[-1]} : {t[-1] - t[0]:.0f}초 · 몸이 움직인 길이 {path:.1f} m · 처음 → 끝 {net:.2f} m · 오른 높이 {z.max() - z[0]:+.2f} m")
