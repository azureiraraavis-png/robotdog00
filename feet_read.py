# -*- coding: utf-8 -*-
"""feet_read.py — sim_go2.py 의 --feet-log 자취(CSV)를 읽어 헛발질을 셉니다. 시뮬레이터가 필요 없습니다.

    python feet_read.py sim\\feet\\51_see_1400_up_0.18_at2.0.csv [...]   (--list 면 사건을 하나씩, --table 이면 묶음 표)

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


if __name__ == "__main__":
    show = "--list" in sys.argv
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
