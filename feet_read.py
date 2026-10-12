# -*- coding: utf-8 -*-
"""feet_read.py — sim_go2.py 의 --feet-log 자취(CSV)를 읽어 헛발질을 셉니다. 시뮬레이터가 필요 없습니다.

    python feet_read.py sim\\feet\\51_see_1400_up_0.18_at2.0.csv [...]   (--list 면 사건을 하나씩, --table 이면 묶음 표,
                                                                        --slip 이면 디딘 발의 미끄러짐 — --contacts 자취만, README 61,
                                                                        --slip2 이면 닿는 점을 계단 모양에서 구한 미끄러짐 — README 62-1 (못 믿음),
                                                                        --slip3 이면 발 공이 닿아 있을 때만 · 정강이 얹힘 따로 — README 62-3)

 세는 것 (README 51-3 의 정의)
   턱 치기    발이 다음 칸의 세운 면에 닿은 채(면에서 1.5 cm 안) 디딤판 위 3 cm 넘는 높이에서 0.05초 넘게 멈춤
   다시 딛기  같은 발이 같은 칸을 0.4초 안에 다시 디딤 (앞 디딤이 0.25초보다 짧을 때)
   모서리 디딤 칸 앞 모서리에서 3 cm 안에 디딤 (오르기) / 칸 끝 모서리에서 3 cm 안 (내려가기)
   앞선 발 바뀜  칸마다 먼저 닿은 앞발(FL/FR)이 앞 칸과 다름
 발끝 = 종아리 자리 + 종아리 방향 · (0, 0, −0.213).  사원수는 xyzw (평지에서 디딘 발이 덜 움직이는 쪽으로 확인).
   멈춤 = 발끝 빠르기 0.20 m/s 아래.  시간은 모두 물리 시간(한 줄 0.01초), 사건의 때만 무대시계.
"""
import sys
import numpy as np

LEGS = ["FL", "FR", "RL", "RR"]
CALF, R0 = 0.213, 0.0235
DT = 0.01                      # 한 줄 = 물리 걸음 둘 = 0.01초 (무대시계는 이보다 4/3 빨리 갑니다 — 흠 25)
V_STILL, T_MIN = 0.20, 0.05
FACE, HIGH, EDGE, RE_GAP, RE_SHORT = 0.015, 0.03, 0.03, 0.40, 0.25


def load(fn):
    h = open(fn, encoding="utf-8").readline()
    meta = dict(kv.split("=", 1) for kv in h[1:].split() if "=" in kv)
    return meta, np.genfromtxt(fn, delimiter=",", skip_header=2)


def tip(p, q):
    x, y, z, w = q.T
    u = np.stack([x, y, z], 1)
    v = np.broadcast_to(np.array([0.0, 0.0, -CALF]), u.shape)
    t = 2 * np.cross(u, v)
    return p + v + w[:, None] * t + np.cross(u, t)


def read(fn):
    meta, a = load(fn)
    n = len(a)
    k = np.polyfit(np.arange(n), a[:, 0], 1)
    t, dt = k[0] * np.arange(n) + k[1], DT      # t 는 무대시계(자취·영상과 맞춤), 길이와 빠르기는 물리 시간
    ck = DT / k[0]
    steps, at = int(meta["steps"]), float(meta["at"])
    run, rise, down = float(meta["run"]), float(meta["rise"]), int(meta["down"])

    def kno(x):
        return np.clip(np.floor((x - at) / run) + 1, 0, steps).astype(int)

    def gnd(x):
        if steps == 0:
            return np.zeros_like(x)
        return ((steps - kno(x)) if down else kno(x)) * rise

    res = {"file": fn, "meta": meta, "legs": {}, "ev": []}
    first = {}
    for i, leg in enumerate(LEGS):
        c = 8 + 7 * i
        f = tip(a[:, c:c + 3], a[:, c + 3:c + 7])
        v = np.linalg.norm(np.gradient(f, axis=0), axis=1) / dt
        h = f[:, 2] - gnd(f[:, 0]) - R0
        on = v < V_STILL
        st, j = [], 0
        while j < n:
            if on[j]:
                e = j
                while e < n and on[e]:
                    e += 1
                if (e - j) * dt >= T_MIN:
                    x = float(f[j:e, 0].mean())
                    st.append(dict(t0=t[j], t1=t[e - 1], x=x, h=float(h[j:e].mean()),
                                   k=int(kno(np.array([x]))[0]), into=(x - at) % run))
                j = e
            else:
                j += 1
        onst = steps > 0
        strikes = edges = redo = 0
        prev = None
        for s in st:
            inside = onst and at - run < s["x"] < at + steps * run
            # 내려가기에서는 '세운 면'이 뒤에 있으므로 턱 치기는 오르기에서만 셉니다
            if onst and not down and at - run < s["x"] < at + (steps - 1) * run + run \
                    and s["h"] > HIGH and (run - s["into"]) - R0 < FACE and s["k"] < steps:
                strikes += 1
                res["ev"].append((s["t0"], leg, "턱 치기", s["k"] + 1, (s["t1"] - s["t0"]) * ck, s["h"]))
                continue                      # 디딘 것이 아니므로 아래 셈에 넣지 않습니다
            if s["h"] > 0.02:
                continue
            if onst and 1 <= s["k"] <= steps and at <= s["x"] < at + steps * run:
                d_edge = (run - s["into"]) if down else s["into"]
                if d_edge < EDGE:
                    edges += 1
                    res["ev"].append((s["t0"], leg, "모서리 디딤", s["k"], (s["t1"] - s["t0"]) * ck, d_edge))
                if prev and prev["k"] == s["k"] and (s["t0"] - prev["t1"]) * ck < RE_GAP \
                        and (prev["t1"] - prev["t0"]) * ck < RE_SHORT:
                    redo += 1
                    res["ev"].append((s["t0"], leg, "다시 딛기", s["k"], (s["t1"] - s["t0"]) * ck, s["into"]))
                if leg in ("FL", "FR") and (s["k"] not in first or s["t0"] < first[s["k"]][0]):
                    first[s["k"]] = (s["t0"], leg)
            prev = s
        res["legs"][leg] = dict(strikes=strikes, edges=edges, redo=redo,
                                lift=float(h[n // 4:].max()) if steps == 0 else None)
    res["reached"] = max(first) if first else 0          # 앞발이 디딘 가장 먼 칸
    lead = [first[k][1] for k in sorted(first)]
    res["lead"] = lead
    res["lead_changes"] = [(sorted(first)[i], lead[i - 1], lead[i]) for i in range(1, len(lead)) if lead[i] != lead[i - 1]]
    res["ev"].sort()
    return res


def table(files):
    """묶음 표 — 정책 종류 · 방향마다, 디딘 칸 열 칸에 몇 번인지 (판마다 셈한 뒤 가운데값 · 가장 적은 판 ~ 많은 판)."""
    import os
    grp = {}
    for fn in files:
        r = read(fn)
        m = r["meta"]
        if int(m["steps"]) == 0:
            continue
        key = ("눈" if int(m["see"]) else "눈 없음", "내려가기" if int(m["down"]) else "오르기", m["rise"])
        n = max(r["reached"], 1)
        L = r["legs"]
        row = dict(reached=r["reached"], full=int(r["reached"] >= int(m["steps"])),
                   lead=len(r["lead_changes"]) * 10.0 / n)
        for k in ("strikes", "redo", "edges"):
            row[k + "_f"] = (L["FL"][k] + L["FR"][k]) * 10.0 / n
            row[k + "_r"] = (L["RL"][k] + L["RR"][k]) * 10.0 / n
            row[k] = row[k + "_f"] + row[k + "_r"]
        grp.setdefault(key, []).append(row)
    print("열 칸에 몇 번 — 가운데값 (가장 적은 판 ~ 가장 많은 판)")
    for key in sorted(grp):
        rows = grp[key]
        def q(c):
            v = np.array([x[c] for x in rows])
            return f"{np.median(v):.1f} ({v.min():.1f}~{v.max():.1f})"
        print(f"\n  {key[0]} · {key[1]} {key[2]} · {len(rows)}판 · 앞발이 끝 칸까지 디딘 판 {sum(x['full'] for x in rows)}")
        print(f"    턱 치기      모두 {q('strikes')}   앞발 {q('strikes_f')}   뒷발 {q('strikes_r')}")
        print(f"    다시 딛기    모두 {q('redo')}   앞발 {q('redo_f')}   뒷발 {q('redo_r')}")
        print(f"    모서리 디딤  모두 {q('edges')}   앞발 {q('edges_f')}   뒷발 {q('edges_r')}")
        print(f"    앞선 발 바뀜 {q('lead')}")


F_ON = 20.0                    # 61: 이 힘(N)보다 세게 누르는 동안만 '디딘 발'로 셉니다
STAIR_PAD = 0.30               # 61: 계단 구간 = 첫 칸 앞 30 cm ~ 끝 칸 끝


def _rotvec(q1, q2):
    """줄마다 종아리가 돈 양(세계 좌표 회전 벡터, rad) — q2 ⊗ q1⁻¹, 사원수 xyzw."""
    x1, y1, z1, w1 = (-q1[:, 0], -q1[:, 1], -q1[:, 2], q1[:, 3])
    x2, y2, z2, w2 = q2.T
    w = w2 * w1 - x2 * x1 - y2 * y1 - z2 * z1
    v = np.stack([w2 * x1 + x2 * w1 + y2 * z1 - z2 * y1,
                  w2 * y1 - x2 * z1 + y2 * w1 + z2 * x1,
                  w2 * z1 + x2 * y1 - y2 * x1 + z2 * w1], 1)
    v = np.where(w[:, None] < 0, -v, v)
    w = np.abs(w)
    s = np.linalg.norm(v, axis=1)
    ang = 2 * np.arctan2(s, w)
    k = np.where(s > 1e-12, ang / np.maximum(s, 1e-12), 2.0)
    return v * k[:, None]


def slip(fn):
    """61 — 디딘 발의 미끄러짐. 발마다 '닿는 점'의 수평 이동(cm)을, 수직 힘이 F_ON 넘는 동안만 더합니다.
    닿는 점 = 발끝 공 중심 + 종아리가 돈 양 × (0, 0, −R0) — 공이 굴러서 생기는 중심 이동은 미끄러짐이 아니므로 뺍니다.
    stairs = 발끝 x 가 계단 구간에 있을 때만, all = 판 전체.  --contacts 없이 적은 자취면 None."""
    meta, a = load(fn)
    if a.shape[1] < 48:
        return None
    steps, at, run = int(meta["steps"]), float(meta["at"]), float(meta["run"])
    out = {"file": fn, "meta": meta, "legs": {}}
    for i, leg in enumerate(LEGS):
        c = 8 + 7 * i
        f = tip(a[:, c:c + 3], a[:, c + 3:c + 7])
        q = a[:, c + 3:c + 7]
        dc = np.diff(f, axis=0) + np.cross(_rotvec(q[:-1], q[1:]), np.array([0.0, 0.0, -R0]))
        dn = np.diff(f, axis=0)
        fz = a[:, 36 + 3 * i + 2]
        on = (fz[1:] > F_ON) & (fz[:-1] > F_ON)
        xm = 0.5 * (f[1:, 0] + f[:-1, 0])
        inst = on & (xm > at - STAIR_PAD) & (xm < at + steps * run) if steps else on & False
        hs = np.linalg.norm(dc[:, :2], axis=1)
        out["legs"][leg] = dict(stairs=float(hs[inst].sum() * 100), all=float(hs[on].sum() * 100),
                                center_all=float(np.linalg.norm(dn[on, :2], axis=1).sum() * 100),
                                n_on=int(np.sum(np.diff(on.astype(int)) == 1)),
                                stairs_s=float(inst.sum() * DT))
    return out


def _who(meta):
    p = meta.get("policy", "").replace(chr(92), "/").split("/")
    run = p[-3] if len(p) >= 3 else "?"
    ck = p[-1].replace("policy_", "").replace(".pt", "")
    return run, ck


def slip_table(files):
    """61-3 — 판마다 미끄러짐, 묶음마다 가운데값, 그리고 61-3 의 두 물음을 미리 정한 문턱으로 읽습니다."""
    grp = {}
    for fn in files:
        r = slip(fn)
        if r is None:
            print(f"  (접촉 힘 없음 — 건너뜀) {fn}")
            continue
        m, L = r["meta"], r["legs"]
        run, ck = _who(m)
        if int(m["steps"]) == 0:
            print(f"  평지 {fn} · 판 전체 " + " ".join(f"{l} {L[l]['all']:.1f}" for l in LEGS)
                  + f" cm · (구름을 빼지 않은 중심 이동 " + " ".join(f"{L[l]['center_all']:.1f}" for l in LEGS) + ")")
            continue
        key = (run, ck, "내려가기" if int(m["down"]) else "오르기", m["rise"])
        fr = L["FL"]["stairs"] + L["FR"]["stairs"]
        rr = L["RL"]["stairs"] + L["RR"]["stairs"]
        grp.setdefault(key, []).append(dict(fn=fn, tot=fr + rr, fr=fr, rr=rr, ratio=fr / rr if rr > 0.1 else float("inf"),
                                             all=sum(L[l]["all"] for l in LEGS), legs=L, t=L["FL"]["stairs_s"]))
    print("디딘 발의 미끄러짐 (cm · 수직 힘 > %.0f N 인 동안 닿는 점의 수평 이동 · 계단 구간) — 판마다" % F_ON)
    for key in sorted(grp):
        print(f"\n  {key[0]} · {key[1]} · {key[2]} {key[3]} · {len(grp[key])}판")
        for x in grp[key]:
            L = x["legs"]
            print(f"    {x['fn'].replace(chr(92), '/').split('/')[-1]:34s} 모두 {x['tot']:5.1f}  "
                  + " ".join(f"{l} {L[l]['stairs']:4.1f}" for l in LEGS)
                  + f"  앞÷뒤 {x['ratio']:4.2f}  (판 전체 {x['all']:5.1f})")
        v = np.array([x["tot"] for x in grp[key]])
        rt = np.array([x["ratio"] for x in grp[key]])
        print(f"    가운데값  모두 {np.median(v):.1f} ({v.min():.1f}~{v.max():.1f})  앞÷뒤 {np.median(rt):.2f}")

    def verdict(r, hi, lo, a, b):
        return f"{r:.2f} → " + (a if r > 1.5 else b if r < 0.67 else "비슷하다")
    best = [k for k in grp if k[0] == "2026-10-08_12-46-57" and k[1] == "1498"]
    dn = [k for k in best if k[2] == "내려가기"]
    up = [k for k in best if k[2] == "오르기"]
    print("\n61-3 의 물음 (문턱은 docs 61-3 에 미리 적은 대로)")
    if dn and up:
        r1 = np.median([x["tot"] for x in grp[dn[0]]]) / max(np.median([x["tot"] for x in grp[up[0]]]), 1e-6)
        print("  물음 1 · 1498 내려가기 ÷ 오르기 가운데값 = " + verdict(r1, 1.5, 0.67, "내려갈 때 더 미끄러진다", "오를 때 더 미끄러진다"))
    allr = [x["ratio"] for k in grp if k[2] == "내려가기" for x in grp[k]]
    if allr:
        r2 = float(np.median(allr))
        print(f"  물음 2 · 내려가기 {len(allr)}판의 앞÷뒤 가운데값 = " + verdict(r2, 1.5, 0.67, "앞발이 더 미끄러진다", "뒷발이 더 미끄러진다"))


R_EFF = 0.0244                 # 62: 평지에서 디딘 동안 공 중심 높이의 가운데값 (61_on · 네 발 2.43~2.45 cm)
ST_BACK, KINDS = -1.5, ("디딤판", "세운 면", "모서리", "구석")


def stair_poly(meta):
    """62 — sim_go2.py 가 만드는 계단을 옆에서 본 꺾은선 (x, z) 과 꼭짓점의 종류 (2 = 볼록한 모서리 · 3 = 오목한 구석)."""
    N, rise, run, at = int(meta["steps"]), float(meta["rise"]), float(meta["run"]), float(meta["at"])
    if N <= 0:
        return np.array([[-100.0, 0.0], [100.0, 0.0]]), np.array([-1, -1])
    if int(meta["down"]):
        P, K = [(ST_BACK, N * rise)], [-1]
        for j in range(N):
            x = at + j * run
            P += [(x, (N - j) * rise), (x, (N - j - 1) * rise)]
            K += [2, 3]
        P.append((at + (N - 1) * run + 20.0, 0.0)); K.append(-1)
    else:
        P, K = [(at - 20.0, 0.0)], [-1]
        for i in range(N):
            x = at + i * run
            P += [(x, i * rise), (x, (i + 1) * rise)]
            K += [3, 2]
        end = at + N * run + float(meta.get("landing", 10.0))
        P += [(end, N * rise)]; K += [-1]
    return np.array(P, float), np.array(K)


def closest(cxz, P, K):
    """공 중심(x, z) 마다 꺾은선의 가장 가까운 점 · 거리 · 닿는 곳의 종류 (0 디딤판 · 1 세운 면 · 2 모서리 · 3 구석)."""
    A, B = P[:-1], P[1:]
    d = B - A
    L2 = (d ** 2).sum(1)
    t = np.clip(((cxz[:, None, :] - A[None]) * d[None]).sum(2) / L2[None], 0.0, 1.0)
    Q = A[None] + t[..., None] * d[None]
    D = np.linalg.norm(cxz[:, None, :] - Q, axis=2)
    s = D.argmin(1)
    r = np.arange(len(cxz))
    p, dist, ts = Q[r, s], D[r, s], t[r, s]
    kind = np.where(np.abs(d[s, 1]) < 1e-9, 0, 1)
    end = np.where(ts < 0.5, s, s + 1)
    vk = K[end]
    at_v = (np.minimum(ts, 1 - ts) * np.sqrt(L2[s]) < 1e-4) & (vk >= 2)
    kind = np.where(at_v, vk, kind)
    return p, dist, kind


def slip2_core(c, q, F, P, K, region, r_eff=R_EFF):
    """62 — 줄마다(앞뒤 두 줄 사이) 미끄러짐(m)과 닿는 곳의 종류 · 중심-꺾은선 거리 · 힘과 면 방향의 각(도).
    닿는 점의 살점 이동 = 중심 이동 + 돈 양 × (닿는 점 − 중심), 그중 면에 수직인 몫을 뺀 크기."""
    m = 0.5 * (c[1:] + c[:-1])
    p, dist, kind = closest(m[:, [0, 2]], P, K)
    n = np.stack([m[:, 0] - p[:, 0], np.zeros(len(m)), m[:, 2] - p[:, 1]], 1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    rr = -r_eff * n                                     # 중심 → 닿는 점
    dp = np.diff(c, axis=0) + np.cross(_rotvec(q[:-1], q[1:]), rr)
    tan = dp - (dp * n).sum(1, keepdims=True) * n
    Fm = np.linalg.norm(F, axis=1)
    on = (Fm[1:] > F_ON) & (Fm[:-1] > F_ON) & region
    Fh = 0.5 * (F[1:] + F[:-1])
    cosang = (Fh * n).sum(1) / np.maximum(np.linalg.norm(Fh, axis=1), 1e-9)
    ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    return dict(slip=np.linalg.norm(tan, axis=1), on=on, kind=kind, gap=dist - r_eff, ang=ang)


def slip2(fn):
    """62 — 한 판의 발마다: 미끄러짐(cm · 계단 구간) · 닿는 곳 넷의 몫 · 판 전체 · 믿음 확인용 거리 · 각."""
    meta, a = load(fn)
    if a.shape[1] < 48:
        return None
    steps, at, run = int(meta["steps"]), float(meta["at"]), float(meta["run"])
    P, K = stair_poly(meta)
    out = {"file": fn, "meta": meta, "legs": {}}
    for i, leg in enumerate(LEGS):
        cc = 8 + 7 * i
        c = tip(a[:, cc:cc + 3], a[:, cc + 3:cc + 7])
        q = a[:, cc + 3:cc + 7]
        F = a[:, 36 + 3 * i:39 + 3 * i]
        xm = 0.5 * (c[1:, 0] + c[:-1, 0])
        reg = (xm > at - STAIR_PAD) & (xm < at + steps * run) if steps else np.ones(len(xm), bool)
        r = slip2_core(c, q, F, P, K, reg)
        allr = slip2_core(c, q, F, P, K, np.ones(len(xm), bool))
        on = r["on"]
        out["legs"][leg] = dict(stairs=float(r["slip"][on].sum() * 100), all=float(allr["slip"][allr["on"]].sum() * 100),
                                by={k: float(r["slip"][on & (r["kind"] == j)].sum() * 100) for j, k in enumerate(KINDS)},
                                t={k: float((on & (r["kind"] == j)).sum() * DT) for j, k in enumerate(KINDS)},
                                gap=r["gap"][on], ang=r["ang"][on])
    return out


def slip2_selftest(R_EFF=R_EFF):
    """62-1 의 꾸민 움직임 셋. (가) 모서리를 축으로 구름 (나) 판판한 면에서 구름 (다) 돌지 않고 5 cm 미끄러짐."""
    def qy(a):
        return np.stack([np.zeros_like(a), np.sin(a / 2), np.zeros_like(a), np.cos(a / 2)], 1)
    P1 = np.array([[-5.0, 0.1], [0.0, 0.1], [0.0, 0.0], [5.0, 0.0]]); K1 = np.array([-1, 2, 3, -1])
    P0 = np.array([[-5.0, 0.0], [5.0, 0.0]]); K0 = np.array([-1, -1])
    res = []
    ph = np.radians(np.linspace(5, 60, 200))
    c = np.stack([R_EFF * np.sin(ph), np.zeros_like(ph), 0.1 + R_EFF * np.cos(ph)], 1)
    F = 50 * (c - np.array([0, 0, 0.1])) / R_EFF
    r = slip2_core(c, qy(ph), F, P1, K1, np.ones(len(ph) - 1, bool), R_EFF)
    res.append(("가 모서리를 축으로 구름", r["slip"][r["on"]].sum() * 100, 0.0, set(r["kind"].tolist())))
    th = np.linspace(0, 2.0, 200)
    c = np.stack([R_EFF * th, np.zeros_like(th), np.full_like(th, R_EFF)], 1)
    F = np.tile([0, 0, 50.0], (len(th), 1))
    r = slip2_core(c, qy(th), F, P0, K0, np.ones(len(th) - 1, bool), R_EFF)
    res.append(("나 판판한 면에서 구름", r["slip"][r["on"]].sum() * 100, 0.0, set(r["kind"].tolist())))
    x = np.linspace(0, 0.05, 200)
    c = np.stack([x, np.zeros_like(x), np.full_like(x, R_EFF)], 1)
    r = slip2_core(c, qy(np.zeros_like(x)), F, P0, K0, np.ones(len(x) - 1, bool), R_EFF)
    res.append(("다 돌지 않고 5 cm 미끄러짐", r["slip"][r["on"]].sum() * 100, 5.0, set(r["kind"].tolist())))
    ok = True
    for name, got, want, kinds in res:
        good = abs(got - want) < 0.1
        ok &= good
        print(f"  {name:22s} {got:7.3f} cm (바라는 값 {want:.1f}) {'○' if good else '✖'}  닿는 곳 {sorted(KINDS[k] for k in kinds)}")
    return ok


def slip2_table(files):
    """62-1 의 자를 믿는 조건과 세 물음을 미리 적은 문턱으로 읽습니다."""
    print("62-1 · 꾸민 움직임 셋")
    ok = slip2_selftest()
    grp, gaps, angs = {}, [], []
    for fn in files:
        r = slip2(fn)
        if r is None:
            print(f"  (접촉 힘 없음 — 건너뜀) {fn}")
            continue
        m, L = r["meta"], r["legs"]
        if int(m["steps"]) == 0:
            want = {"FL": 2.3, "FR": 2.1, "RL": 1.4, "RR": 1.2}
            good = all(abs(L[l]["all"] - want[l]) <= max(0.05 * want[l], 0.1) for l in LEGS)
            ok &= good
            print("62-1 · 평지 판 (61-2 의 값과 5 % 또는 0.1 cm 안) " + " ".join(f"{l} {L[l]['all']:.2f}/{want[l]}" for l in LEGS)
                  + f"  {'○' if good else '✖'}")
            continue
        for l in LEGS:
            gaps.append(L[l]["gap"]); angs.append(L[l]["ang"])
        run, ck = _who(m)
        key = (run, ck, "내려가기" if int(m["down"]) else "오르기", m["rise"])
        fr = L["FL"]["stairs"] + L["FR"]["stairs"]
        rr = L["RL"]["stairs"] + L["RR"]["stairs"]
        tot = fr + rr
        by = {k: sum(L[l]["by"][k] for l in LEGS) for k in KINDS}
        tt = {k: sum(L[l]["t"][k] for l in LEGS) for k in KINDS}
        grp.setdefault(key, []).append(dict(fn=fn, tot=tot, ratio=fr / rr if rr > 0.1 else float("inf"),
                                             edge=by["모서리"] / tot if tot > 0 else 0.0, by=by, tt=tt, legs=L,
                                             left=L["FL"]["stairs"] + L["RL"]["stairs"], right=L["FR"]["stairs"] + L["RR"]["stairs"]))
    if gaps:
        g = np.concatenate(gaps); an = np.concatenate(angs)
        f5 = float(np.mean(np.abs(g) < 0.005)); am = float(np.median(an))
        print(f"62-1 · 계단 판 누르는 동안 {len(g)}줄: 중심-꺾은선 거리 − {R_EFF * 100:.2f} cm 가 ±5 mm 안 {f5 * 100:.1f} % "
              f"(가운데값 {np.median(g) * 1000:+.1f} mm)  {'○' if f5 > 0.9 else '✖'}")
        print(f"        힘과 면 방향의 각 가운데값 {am:.1f}도 (90 % 값 {np.percentile(an, 90):.1f}도)  {'○' if am < 10 else '✖'}")
        ok &= (f5 > 0.9) and (am < 10)
    print("62-1 · 자를 믿는가: " + ("○ 믿는다 — 아래 판정을 쓴다" if ok else "✖ 못 믿는다 — 아래 숫자로 판정하지 않는다"))
    print("\n디딘 발의 미끄러짐 (cm · 힘 > %.0f N · 닿는 점의 살점이 면을 따라 움직인 양 · 계단 구간) — 판마다" % F_ON)
    for key in sorted(grp):
        print(f"\n  {key[0]} · {key[1]} · {key[2]} {key[3]} · {len(grp[key])}판")
        for x in grp[key]:
            L = x["legs"]
            print(f"    {x['fn'].replace(chr(92), '/').split('/')[-1]:30s} 모두 {x['tot']:5.1f} "
                  + " ".join(f"{l} {L[l]['stairs']:4.1f}" for l in LEGS)
                  + f"  앞÷뒤 {x['ratio']:4.2f}  모서리 몫 {x['edge']:.2f}  (" + " · ".join(f"{k} {x['by'][k]:.1f}" for k in KINDS) + ")")
        def md(f):
            return float(np.median([f(x) for x in grp[key]]))
        print(f"    가운데값  모두 {md(lambda x: x['tot']):.1f}  앞÷뒤 {md(lambda x: x['ratio']):.2f}  모서리 몫 {md(lambda x: x['edge']):.2f}"
              f"  왼 {md(lambda x: x['left']):.1f} · 오른 {md(lambda x: x['right']):.1f}")
        print("    닿아 누른 시간(초, 네 발 합) " + " · ".join(f"{k} {md(lambda x, k=k: x['tt'][k]):.2f}" for k in KINDS))

    def verdict(r, a, b):
        return f"{r:.2f} → " + (a if r > 1.5 else b if r < 0.67 else "비슷하다")
    best = [k for k in grp if k[0] == "2026-10-08_12-46-57" and k[1] == "1498"]
    dn = [k for k in best if k[2] == "내려가기"]; up = [k for k in best if k[2] == "오르기"]
    print("\n62-1 의 물음 (문턱은 docs 62-1 에 미리 적은 대로)" + ("" if ok else " — ✖ 자를 못 믿으므로 판정 아님"))
    if dn and up:
        r1 = np.median([x["tot"] for x in grp[dn[0]]]) / max(np.median([x["tot"] for x in grp[up[0]]]), 1e-6)
        print("  물음 1 · 1498 내려가기 ÷ 오르기 가운데값 = " + verdict(r1, "내려갈 때 더 미끄러진다", "오를 때 더 미끄러진다"))
    allr = [x["ratio"] for k in grp if k[2] == "내려가기" for x in grp[k]]
    if allr:
        print(f"  물음 2 · 내려가기 {len(allr)}판의 앞÷뒤 가운데값 = "
              + verdict(float(np.median(allr)), "앞발이 더 미끄러진다", "뒷발이 더 미끄러진다"))
    if dn:
        e = float(np.median([x["edge"] for x in grp[dn[0]]]))
        print(f"  물음 3 · 1498 내려가기의 모서리 몫 가운데값 = {e:.2f} → "
              + ("주로 모서리에서 미끄러진다" if e > 0.5 else "주로 판판한 면에서 미끄러진다" if e < 0.25 else "둘 다"))


TOUCH, SHIN = 0.005, 0.015    # 62-3: 발 공이 닿음 = 중심-꺾은선 거리가 R0 ± 5 mm · 정강이 얹힘 = 정강이 선이 모서리에서 15 mm 안


def _seg_dist(E, A, B):
    """점 E(x, z) 에서 선분 A–B (줄마다) 까지의 거리."""
    d = B - A
    t = np.clip(((E[None] - A) * d).sum(1) / np.maximum((d * d).sum(1), 1e-12), 0, 1)
    return np.linalg.norm(E[None] - (A + t[:, None] * d), axis=1)


def slip3(fn):
    """62-3 — 공 크기 R0(2.35 cm) · 발 공이 땅에 닿아 있을 때만 센 미끄러짐과, 정강이가 모서리에 얹힌 시간."""
    meta, a = load(fn)
    if a.shape[1] < 48:
        return None
    steps, at, run = int(meta["steps"]), float(meta["at"]), float(meta["run"])
    P, K = stair_poly(meta)
    E = P[K == 2]
    out = {"file": fn, "meta": meta, "legs": {}}
    for i, leg in enumerate(LEGS):
        cc = 8 + 7 * i
        knee = a[:, cc:cc + 3]
        c = tip(knee, a[:, cc + 3:cc + 7])
        q = a[:, cc + 3:cc + 7]
        F = a[:, 36 + 3 * i:39 + 3 * i]
        xm = 0.5 * (c[1:, 0] + c[:-1, 0])
        reg = (xm > at - STAIR_PAD) & (xm < at + steps * run) if steps else np.ones(len(xm), bool)
        r = slip2_core(c, q, F, P, K, np.ones(len(xm), bool), R0)
        Fm = np.linalg.norm(F, axis=1)
        load_ = (Fm[1:] > F_ON) & (Fm[:-1] > F_ON) & reg
        touch = np.abs(r["gap"]) <= TOUCH
        if len(E):
            cm = 0.5 * (c[1:] + c[:-1])[:, [0, 2]]
            km = 0.5 * (knee[1:] + knee[:-1])[:, [0, 2]]
            sd = np.min(np.stack([_seg_dist(e, cm, km) for e in E]), 0)
        else:
            sd = np.full(len(xm), np.inf)
        near = sd <= SHIN
        cnt = load_ & touch
        out["legs"][leg] = dict(
            stairs=float(r["slip"][cnt].sum() * 100),
            by={k: float(r["slip"][cnt & (r["kind"] == j)].sum() * 100) for j, k in enumerate(KINDS)},
            t={k: float((cnt & (r["kind"] == j)).sum() * DT) for j, k in enumerate(KINDS)},
            t_load=float(load_.sum() * DT), t_foot=float(cnt.sum() * DT), t_both=float((cnt & near).sum() * DT),
            t_shin=float((load_ & ~touch & near).sum() * DT), t_unk=float((load_ & ~touch & ~near).sum() * DT),
            ang=r["ang"][cnt])
    return out


def slip3_table(files):
    """62-3 의 자를 믿는 조건과 세 물음을 미리 적은 문턱으로 읽습니다."""
    print("62-3 · 꾸민 움직임 셋 (공 크기 %.2f cm)" % (R0 * 100))
    ok = slip2_selftest(R0)
    grp, angs, tl, tu = {}, [], 0.0, 0.0
    for fn in files:
        r = slip3(fn)
        if r is None:
            print(f"  (접촉 힘 없음 — 건너뜀) {fn}")
            continue
        m, L = r["meta"], r["legs"]
        if int(m["steps"]) == 0:
            want = {"FL": 2.3, "FR": 2.1, "RL": 1.4, "RR": 1.2}
            good = all(abs(L[l]["stairs"] - want[l]) <= max(0.05 * want[l], 0.1) for l in LEGS)
            ok &= good
            print("62-3 · 평지 판 (61-2 의 값과 5 % 또는 0.1 cm 안) " + " ".join(f"{l} {L[l]['stairs']:.2f}/{want[l]}" for l in LEGS)
                  + f"  {'○' if good else '✖'}")
            continue
        for l in LEGS:
            angs.append(L[l]["ang"]); tl += L[l]["t_load"]; tu += L[l]["t_unk"]
        run, ck = _who(m)
        key = (run, ck, "내려가기" if int(m["down"]) else "오르기", m["rise"])
        fr = L["FL"]["stairs"] + L["FR"]["stairs"]
        rr = L["RL"]["stairs"] + L["RR"]["stairs"]
        tot = fr + rr
        by = {k: sum(L[l]["by"][k] for l in LEGS) for k in KINDS}
        grp.setdefault(key, []).append(dict(
            fn=fn, tot=tot, ratio=fr / rr if rr > 0.1 else float("inf"), edge=by["모서리"] / tot if tot > 0 else 0.0,
            by=by, legs=L, left=L["FL"]["stairs"] + L["RL"]["stairs"], right=L["FR"]["stairs"] + L["RR"]["stairs"],
            **{k: sum(L[l][k] for l in LEGS) for k in ("t_load", "t_foot", "t_shin", "t_both", "t_unk")}))
    if angs:
        an = np.concatenate(angs)
        am = float(np.median(an)) if len(an) else 99.0
        print(f"62-3 · 계단 판 센 때 {len(an)}줄: 힘과 면 방향의 각 가운데값 {am:.1f}도 (90 % 값 {np.percentile(an, 90):.1f}도)  "
              f"{'○' if am < 10 else '✖'}")
        fu = tu / max(tl, 1e-9)
        print(f"        힘 > {F_ON:.0f} N 인 {tl:.1f}초 가운데 발도 정강이도 아닌 몫 {fu * 100:.1f} %  {'○' if fu < 0.05 else '✖'}")
        ok &= (am < 10) and (fu < 0.05)
    print("62-3 · 자를 믿는가: " + ("○ 믿는다 — 아래 판정을 쓴다" if ok else "✖ 못 믿는다 — 아래 숫자로 판정하지 않는다"))
    print("\n디딘 발의 미끄러짐 (cm · 발 공이 닿아 %.0f N 넘게 누르는 동안 · 닿는 점의 살점이 면을 따라 움직인 양 · 계단 구간) — 판마다" % F_ON)
    for key in sorted(grp):
        print(f"\n  {key[0]} · {key[1]} · {key[2]} {key[3]} · {len(grp[key])}판")
        for x in grp[key]:
            L = x["legs"]
            print(f"    {x['fn'].replace(chr(92), '/').split('/')[-1]:30s} 모두 {x['tot']:5.1f} "
                  + " ".join(f"{l} {L[l]['stairs']:4.1f}" for l in LEGS)
                  + f"  앞÷뒤 {x['ratio']:4.2f}  모서리 몫 {x['edge']:.2f}  정강이 얹힘 {x['t_shin']:.2f}초")
        def md(f):
            return float(np.median([f(x) for x in grp[key]]))
        print(f"    가운데값  모두 {md(lambda x: x['tot']):.1f}  앞÷뒤 {md(lambda x: x['ratio']):.2f}  모서리 몫 {md(lambda x: x['edge']):.2f}"
              f"  왼 {md(lambda x: x['left']):.1f} · 오른 {md(lambda x: x['right']):.1f}")
        print("    곳마다 미끄러짐 " + " · ".join(f"{k} {md(lambda x, k=k: x['by'][k]):.1f}" for k in KINDS))
        print(f"    힘 > {F_ON:.0f} N 인 시간(초 · 네 발 합) {md(lambda x: x['t_load']):.2f} = 발 {md(lambda x: x['t_foot']):.2f}"
              f" (그중 정강이도 함께 {md(lambda x: x['t_both']):.2f}) + 정강이만 {md(lambda x: x['t_shin']):.2f} + 모름 {md(lambda x: x['t_unk']):.2f}")
        print("    정강이만 얹힌 시간 발마다 " + " ".join(f"{l} {md(lambda x, l=l: x['legs'][l]['t_shin']):.2f}" for l in LEGS))

    def verdict(r, a, b):
        return f"{r:.2f} → " + (a if r > 1.5 else b if r < 0.67 else "비슷하다")
    best = [k for k in grp if k[0] == "2026-10-08_12-46-57" and k[1] == "1498"]
    dn = [k for k in best if k[2] == "내려가기"]; up = [k for k in best if k[2] == "오르기"]
    print("\n62-3 의 물음 (문턱은 docs 62-3 에 미리 적은 대로)" + ("" if ok else " — ✖ 자를 못 믿으므로 판정 아님"))
    if dn and up:
        r1 = np.median([x["tot"] for x in grp[dn[0]]]) / max(np.median([x["tot"] for x in grp[up[0]]]), 1e-6)
        print("  물음 1 · 1498 내려가기 ÷ 오르기 가운데값 = " + verdict(r1, "내려갈 때 더 미끄러진다", "오를 때 더 미끄러진다"))
    allr = [x["ratio"] for k in grp if k[2] == "내려가기" for x in grp[k]]
    if allr:
        print(f"  물음 2 · 내려가기 {len(allr)}판의 앞÷뒤 가운데값 = "
              + verdict(float(np.median(allr)), "앞발이 더 미끄러진다", "뒷발이 더 미끄러진다"))
    if dn:
        e = float(np.median([x["edge"] for x in grp[dn[0]]]))
        print(f"  물음 3 · 1498 내려가기의 모서리 몫 가운데값 = {e:.2f} → "
              + ("주로 모서리에서 미끄러진다" if e > 0.5 else "주로 판판한 면에서 미끄러진다" if e < 0.25 else "둘 다"))


if __name__ == "__main__":
    show = "--list" in sys.argv
    if "--slip3" in sys.argv:
        slip3_table([x for x in sys.argv[1:] if not x.startswith("--")])
        sys.exit(0)
    if "--slip2" in sys.argv:
        slip2_table([x for x in sys.argv[1:] if not x.startswith("--")])
        sys.exit(0)
    if "--slip" in sys.argv:
        slip_table([x for x in sys.argv[1:] if not x.startswith("--")])
        sys.exit(0)
    if "--table" in sys.argv:
        table([x for x in sys.argv[1:] if not x.startswith("--")])
        sys.exit(0)
    for fn in [x for x in sys.argv[1:] if not x.startswith("--")]:
        r = read(fn)
        L = r["legs"]
        print(f"\n{fn}")
        if int(r["meta"]["steps"]) == 0:
            print("  평지 · 발 들림(가장 높을 때, cm): " + "  ".join(f"{l} {L[l]['lift'] * 100:.1f}" for l in LEGS))
            continue
        for key, name in (("strikes", "턱 치기"), ("redo", "다시 딛기"), ("edges", "모서리 디딤")):
            print(f"  {name:6s} " + "  ".join(f"{l} {L[l][key]}" for l in LEGS)
                  + f"   앞발 {L['FL'][key] + L['FR'][key]} · 뒷발 {L['RL'][key] + L['RR'][key]}")
        print("  칸마다 먼저 닿은 앞발: " + " ".join(r["lead"])
              + "   바뀜 " + (", ".join(f"{k}칸에서 {a}→{b}" for k, a, b in r["lead_changes"]) or "없음"))
        if show:
            for t0, leg, what, k, dur, val in r["ev"]:
                print(f"    {t0:6.2f}초 {leg} {what} · {k}칸 · {dur:.2f}초 · {val:+.3f}")
