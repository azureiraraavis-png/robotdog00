# contact_sum.py — 95-5: 발 힘 (--contacts) 이 적힌 발 자취 csv 에서 걸림 · 쿵 · 톡톡 을 셈 (읽기만 · numpy 만).
#   쓰는 법:  python contact_sum.py "이름=경로\*.csv" ...                 (판마다 셈 → 묶음마다 가운데 [가장 작은 ~ 가장 큰])
#             python contact_sum.py --same 힘판.csv 옛판.csv            (힘을 켠 판과 끈 판의 몸통 자취가 같은지)
#   힘 = 종아리 (발 공 포함) 가 받는 알짜 접촉 힘 · 세계 좌표 N · 0.01초마다. 닿음 = |F| > 5 N.
#   걸림 = 닿은 동안 수평 힘이 수직 힘보다 큼 (|Fxy| > |Fz|) 이고 |F| > 30 N — 발 · 정강이가 단 앞면 · 모서리를 밀어냄. 같은 발 0.3초 안은 한 번.
#   쿵   = 발이 0.05초 넘게 떠 있다가 닿은 뒤 0.05초 안 가장 큰 Fz 가 몸무게 (걷는 동안 네 발 Fz 합의 평균) 를 넘음.
#   톡톡 = 0.05초 넘게 떠 있다가 닿았는데 0.04초 안에 다시 뜸 (짧게 건드림).
#   모두 걷는 (몸 0.10 m/s 넘게) 100초당 · 네 발 합 · 앞발 · 뒷발 따로.
import glob
import sys

import numpy as np

THR_ON, THR_HIT = 5.0, 30.0


def load(p):
    hdr = open(p, encoding="utf-8").readlines()[1].strip().split(",")
    a = np.genfromtxt(p, delimiter=",", comments="#", skip_header=2)
    if "FL_fx" not in hdr:
        return None, hdr
    return a, hdr


def runs(b):
    """참인 구간들 (시작, 끝+1)."""
    d = np.diff(np.concatenate([[0], b.astype(int), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def one(p):
    a, hdr = load(p)
    if a is None:
        return None
    t = a[:, 0]
    dt = float(np.median(np.diff(t)))
    n5 = max(1, int(round(0.5 / dt)))
    sp = np.hypot(np.gradient(a[:, 1], t), np.gradient(a[:, 2], t))
    sp = np.convolve(sp, np.ones(n5) / n5, mode="same")
    mv = sp > 0.10
    T = mv.sum() * dt
    if T < 10:
        return None
    i0 = hdr.index("FL_fx")
    F = [a[:, i0 + 3 * k: i0 + 3 * k + 3] for k in range(4)]
    if any(np.isnan(f).all() for f in F):
        return dict(bad=True)
    W = float(np.nanmean(sum(f[:, 2] for f in F)[mv]))
    hit, thump, tap = [0] * 4, [0] * 4, [0] * 4
    for k, f in enumerate(F):
        fn = np.linalg.norm(f, axis=1)
        on = np.nan_to_num(fn) > THR_ON
        h = on & (np.hypot(f[:, 0], f[:, 1]) > np.abs(f[:, 2])) & (fn > THR_HIT) & mv
        last = -1e9
        for s, e in runs(h):
            if t[s] - last > 0.3:
                hit[k] += 1
                last = t[s]
        prev_end = -1
        for s, e in runs(on):
            air = (t[s] - t[prev_end]) if prev_end >= 0 else 1.0
            prev_end = e - 1
            if not mv[s] or air <= 0.05:
                continue
            w = slice(s, min(len(t), s + max(1, int(round(0.05 / dt))) + 1))
            if np.nanmax(f[w, 2]) > W:
                thump[k] += 1
            if (t[e - 1] - t[s]) < 0.04:
                tap[k] += 1
    per = 100.0 / T
    o = dict(T=T, W=W)
    for nm, c in (("hit", hit), ("thump", thump), ("tap", tap)):
        o[nm] = sum(c) * per
        o[nm + "_f"] = (c[0] + c[1]) * per
        o[nm + "_r"] = (c[2] + c[3]) * per
    return o


def same(p1, p2):
    a1 = np.genfromtxt(p1, delimiter=",", comments="#", skip_header=2)
    a2 = np.genfromtxt(p2, delimiter=",", comments="#", skip_header=2)
    n = min(len(a1), len(a2))
    d = np.abs(a1[:n, 1:4] - a2[:n, 1:4]).max()
    print(f"   몸통 자취 · 줄 {len(a1)} · {len(a2)} · 앞 {n} 줄의 가장 큰 차 {d * 100:.3f} cm"
          + ("  → 같음 (힘을 켜도 물리는 그대로)" if (len(a1) == len(a2) and d < 1e-4) else "  → ✖ 다름 (힘을 켜니 판이 바뀜)"))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "--same":
        same(sys.argv[2], sys.argv[3])
        return
    print("   묶음  판수 · 몸무게 N · 걸림 /100초 (네 발 · 앞 · 뒤) · 쿵 (네 발 · 앞 · 뒤) · 톡톡 (네 발 · 앞 · 뒤)   (가운데 [가장 작은 ~ 가장 큰])")
    for arg in sys.argv[1:]:
        name, pat = arg.split("=", 1)
        rs = [r for r in (one(p) for p in sorted(glob.glob(pat))) if r is not None]
        if any(r.get("bad") for r in rs):
            print(f"   {name:5s} ✖ 힘 칸이 비어 있는 판이 있습니다 (접촉 뷰를 못 만듦)")
            rs = [r for r in rs if not r.get("bad")]
        if not rs:
            print(f"   {name:5s} 판 없음 · 또는 힘 칸 없음 ({pat})")
            continue

        def m(k, f="{:.1f}"):
            v = np.array([r[k] for r in rs], float)
            return (f + " [" + f + "~" + f + "]").format(np.median(v), v.min(), v.max())
        print(f"   {name:5s} {len(rs):2d}판 · {np.median([r['W'] for r in rs]):.0f} · {m('hit')} · {m('hit_f')} · {m('hit_r')} · "
              f"{m('thump')} · {m('thump_f')} · {m('thump_r')} · {m('tap')} · {m('tap_f')} · {m('tap_r')}")


if __name__ == "__main__":
    main()
