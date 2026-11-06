# scuff.py — 95: 발 자취 csv (v2 계단 · 가 오르기) 에서 "긁기" 와 "몸 세우기" 를 셈 (읽기만 · numpy 만).
#   쓰는 법:  python scuff.py "이름=경로\*.csv" "이름2=..." ...      (판마다 셈 → 묶음마다 가운데 [가장 작은 ~ 가장 큰])
#   계단 모양은 sim_go2.py 의 --sb-v2 (README 79-1) 를 글자 그대로 다시 지음 — 칸 · 참 바닥판 (x0 x1 y0 y1 z0 z1).
#   발끝 = 종아리 자리 + 종아리 자세 (x y z w 로 적힘) 로 돌린 (0, 0, −0.213) · 발 공 반지름 0.022 (Go2) — 디딜 때 발끝 틈이 0 안팎인지로 맞는지 봄.
#   옆면 닿음 (95-1 의 긁기 · 95-2 에서 94 의 긁기를 못 잡음) = 발 공이 칸의 **옆면** (앞면 · 모서리) 에 닿음: 공 가운데가 칸 윗면보다 0.5 cm 넘게 아래이고, 칸의 바닥 모양까지의 수평 거리가 반지름 + 0.5 cm 안.
#          발끝이 수평 0.10 m/s 넘게 움직이는 중일 때만 (디딘 채 앞면에 기댄 것은 뺌) · 닿기 시작한 때를 한 번 (같은 발 0.3초 안은 한 번) · 걷는 100초당 · 네 발 따로 (앞 FL FR · 뒤 RL RR).
#   끌기 (95-3 · 95-4 에서 94 의 긁기를 못 잡음 — 적기만) = 발 공이 디딤면에 닿은 채 (공 아래 끝이 그 아래 가장 높은 윗면에서 0.5 cm 안) 발끝이 수평 0.15 m/s 넘게 · 0.03초 넘게 · 같은 발 0.3초 안은 한 번 · 걷는 100초당.
#   몸 세우기 (95-2 에서 맞음 · 쓰는 자) = 몸통 앞뒤 기울기 (머리 듦 쪽) 가 그 판 단 위 기울기의 가운데보다 10° (--th= 로 바꿈) 넘게 큼 (0.5초 안은 한 번) · 단 위에 있는 100초당.
#   앞발 높이 = 휘두르는 앞발끝이 그 아래 디딤면보다 높은 만큼 — 걸음마다 가장 높은 값의 95 %.
import glob
import math
import sys

import numpy as np

R_FOOT, L_CALF = 0.022, 0.213
TOL = 0.005


def boxes(at, entry=True):
    N, r, u, W, D, gp = 10, 0.20, 0.24, 1.25, 1.30, 0.40
    K, F = 2, 1.30
    NE = 4 if entry else 0
    Z0 = NE * r
    xt, xl, yB = at + N * u, at + N * u + D, W + gp
    H, xF, TS, TL, TT = 2 * N * r, at - F, 0.10, 0.20, 1.00
    st, lnd = [], []                                   # 칸 · 참 (이름, x0, x1, y0, y1, z0, z1)
    for f in range(K):
        b = f * H + Z0
        for i in range(N):
            tp = b + (i + 1) * r
            st.append((f"F{f+1}_A{i}", at + i * u, at + (i + 1) * u, -W / 2, W / 2, tp - r - TS, tp))
        tp = b + N * r
        lnd.append((f"F{f+1}_Mid", xt, xl, -W / 2, yB + W / 2, tp - TL, tp))
        for j in range(1, N + 1):
            tp = b + (N + j) * r
            st.append((f"F{f+1}_B{j}", xt - j * u, xt - (j - 1) * u, yB - W / 2, yB + W / 2, tp - r - TS, tp))
        tp = b + H
        lnd.append((f"F{f+2}_Floor", xF, at, -W / 2, yB + W / 2, tp - (TT if f == K - 1 else TL), tp))
    if NE:
        ex0, ex1, ue = at - 1.20, at, 0.28
        ey0 = -W / 2 + 1.60
        lnd.append(("F1_Entry_Land", ex0, ex1, -W / 2, ey0, 0.0, Z0))
        for i in range(NE - 1):
            st.append((f"F1_E{i}", ex0, ex1, ey0 + (NE - 2 - i) * ue, ey0 + (NE - 1 - i) * ue, 0.0, (i + 1) * r))
    return np.array([b[1:] for b in st]), np.array([b[1:] for b in lnd])


def quat_rot(q, v):
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    vx, vy, vz = v
    # R(q) @ v
    rx = (1 - 2 * (y * y + z * z)) * vx + 2 * (x * y - w * z) * vy + 2 * (x * z + w * y) * vz
    ry = 2 * (x * y + w * z) * vx + (1 - 2 * (x * x + z * z)) * vy + 2 * (y * z - w * x) * vz
    rz = 2 * (x * z - w * y) * vx + 2 * (y * z + w * x) * vy + (1 - 2 * (x * x + y * y)) * vz
    return np.stack([rx, ry, rz], 1)


def load(p):
    hdr = open(p, encoding="utf-8").readline()
    at = float(hdr.split(" at=")[1].split()[0])
    a = np.genfromtxt(p, delimiter=",", comments="#", skip_header=2)
    return at, a


def one(p, th=6.0):
    at, a = load(p)
    t = a[:, 0]
    dt = float(np.median(np.diff(t)))
    n5 = max(1, int(round(0.5 / dt)))
    sp = np.hypot(np.gradient(a[:, 1], t), np.gradient(a[:, 2], t))
    sp = np.convolve(sp, np.ones(n5) / n5, mode="same")
    mv = sp > 0.10
    T = mv.sum() * dt
    if T < 10:
        return None
    S, L = boxes(at)
    allb = np.vstack([S, L])
    tips = []
    for i in range(4):
        c = a[:, 8 + 7 * i: 8 + 7 * i + 3]
        q = a[:, 8 + 7 * i + 3: 8 + 7 * i + 7][:, [3, 0, 1, 2]]   # 종아리 자세는 (x y z w) 로 적혀 있음 (get_link_transforms) → (w x y z) · 몸통은 (w x y z)
        tips.append(c + quat_rot(q, (0.0, 0.0, -L_CALF)))
    out = dict(T=T)
    # 디딤면 높이 (발끝 아래 가장 높은 윗면) · 옆면 닿음
    side_ev = []
    clr_all, stance_gap, drag_ev = [], [], []
    for i, P in enumerate(tips):
        x, y, z = P[:, 0:1], P[:, 1:2], P[:, 2:3]
        dx = np.maximum(0, np.maximum(S[:, 0] - x, x - S[:, 1]))
        dy = np.maximum(0, np.maximum(S[:, 2] - y, y - S[:, 3]))
        dh = np.hypot(dx, dy)                                     # 칸 바닥 모양까지 수평 거리 (안이면 0)
        below = (z < S[:, 5] - TOL) & (z > S[:, 4])
        fs = np.hypot(np.gradient(P[:, 0], t), np.gradient(P[:, 1], t))
        side = ((dh > 0) & (dh <= R_FOOT + TOL) & below).any(1) & mv & (fs > 0.10)   # 휘두르는 중 (발끝 수평 0.10 m/s 넘음) — 디딘 채 단 앞면에 기댄 것은 뺌
        idx = np.where(side[1:] & ~side[:-1])[0] + 1
        c, last = 0, -1e9
        for k in idx:
            if t[k] - last > 0.3:
                c += 1
                last = t[k]
        side_ev.append(c)
        inside = (allb[:, 0] <= P[:, 0:1]) & (P[:, 0:1] <= allb[:, 1]) & (allb[:, 2] <= P[:, 1:2]) & (P[:, 1:2] <= allb[:, 3]) & (allb[:, 5] <= P[:, 2:3] + 0.05)
        top = np.where(inside, allb[:, 5], -1.0).max(1)
        top = np.where(top < -0.5, 0.0, top)                     # 바깥 = 1층 바닥 (0)
        gap = P[:, 2] - R_FOOT - top
        stn = (fs < 0.05) & mv
        stance_gap.append(gap[stn])
        dr = (gap <= TOL) & (fs > 0.15) & mv                  # 95-3: 디딤면에 닿은 채 끌기
        idx = np.where(dr[1:] & ~dr[:-1])[0] + 1
        c, last = 0, -1e9
        for k in idx:
            j = k
            while j < len(dr) and dr[j]:
                j += 1
            if (t[min(j, len(t) - 1)] - t[k]) > 0.03 and t[k] - last > 0.3:
                c += 1
                last = t[k]
        drag_ev.append(c)
        if i < 2:
            clr_all.append((gap, stn))
    out["side"] = [c * 100.0 / T for c in side_ev]
    out["side_f"] = (side_ev[0] + side_ev[1]) * 100.0 / T
    out["side_r"] = (side_ev[2] + side_ev[3]) * 100.0 / T
    out["drag"] = sum(drag_ev) * 100.0 / T
    out["drag_f"] = (drag_ev[0] + drag_ev[1]) * 100.0 / T
    out["drag_r"] = (drag_ev[2] + drag_ev[3]) * 100.0 / T
    out["stance_gap_cm"] = float(np.median(np.concatenate(stance_gap))) * 100
    # 앞발 높이: 걸음 (디딤 사이) 마다 가장 높은 gap
    sw_max = []
    for gap, stn in clr_all:
        sw = ~stn & mv
        k = 0
        while k < len(sw):
            if sw[k]:
                j = k
                while j < len(sw) and sw[j]:
                    j += 1
                if (j - k) * dt > 0.08:
                    sw_max.append(gap[k:j].max())
                k = j
            else:
                k += 1
    out["lift95_cm"] = float(np.percentile(sw_max, 95)) * 100 if sw_max else float("nan")
    # 몸 세우기 (단 위)
    w, x, y, z = a[:, 4], a[:, 5], a[:, 6], a[:, 7]
    pitch = np.degrees(np.arcsin(np.clip(2 * (w * y - z * x), -1, 1)))
    bx, by = a[:, 1], a[:, 2]
    onflt = np.zeros(len(t), bool)
    for b in S:
        onflt |= (b[0] <= bx) & (bx <= b[1]) & (b[2] <= by) & (by <= b[3])
    fl = onflt & mv
    out["T_fl"] = fl.sum() * dt
    out["pitch_fl"] = float(np.median(pitch[fl])) if fl.sum() else float("nan")
    out["pitch"] = pitch
    out["fl"] = fl
    out["t"] = t
    return out


def rear_count(o, th):
    """머리 듦 쪽이 + 가 되게 (단 위 가운데의 부호로 정함) · 가운데보다 th° 넘게."""
    pitch, fl, t = o["pitch"], o["fl"], o["t"]
    if o["T_fl"] < 5:
        return float("nan"), float("nan")
    med = np.median(pitch[fl])
    sgn = 1.0 if med > 0 else -1.0           # 오를 때 머리를 듦 → 단 위 가운데의 쪽이 "머리 듦"
    ex = sgn * (pitch - med)
    s = (ex > th) & fl
    idx = np.where(s[1:] & ~s[:-1])[0] + 1
    c, last = 0, -1e9
    for k in idx:
        if t[k] - last > 0.5:
            c += 1
            last = t[k]
    return c * 100.0 / o["T_fl"], float(np.max(ex[fl]))


def main():
    th = 10.0                                   # 95-1: 2600 의 15판에서 가장 많이 세운 값 (7.0~10.2°) 의 위쪽 끝
    args = []
    for a in sys.argv[1:]:
        if a.startswith("--th="):
            th = float(a[5:])
        else:
            args.append(a)
    print(f"   묶음  판수 · 디딤 때 발끝 틈 cm (0 안팎이어야 함) · 옆면 닿음 /100초 (앞발 · 뒷발) · 끌기 /100초 (네 발 · 앞발 · 뒷발) · 앞발 높이 95 % cm · 몸 세우기 (+{th:g}°) /단 위 100초 · 가장 많이 세움 °   (가운데 [가장 작은 ~ 가장 큰])")
    for arg in args:
        name, pat = arg.split("=", 1)
        rs = []
        for p in sorted(glob.glob(pat)):
            o = one(p)
            if o is None:
                continue
            o["rear"], o["rearmax"] = rear_count(o, th)
            rs.append(o)
        if not rs:
            print(f"   {name:5s} 판 없음 ({pat})")
            continue

        def m(k, f="{:.1f}"):
            v = np.array([r[k] for r in rs], float)
            return (f + " [" + f + "~" + f + "]").format(np.nanmedian(v), np.nanmin(v), np.nanmax(v))
        print(f"   {name:5s} {len(rs):2d}판 · {m('stance_gap_cm')} · {m('side_f')} · {m('side_r')} · {m('drag')} · {m('drag_f')} · {m('drag_r')} · {m('lift95_cm')} · {m('rear')} · {m('rearmax')}")


if __name__ == "__main__":
    main()
