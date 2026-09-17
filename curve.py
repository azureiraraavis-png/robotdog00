#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""학습 곡선을 판끼리 나란히 놓고 봅니다 — tensorboard 없이.

왜 있는가
---------
`tensorboard` 는 Isaac Sim 의 파이썬 안에만 있고 PowerShell 의 PATH 에는
없습니다. 그리고 우리가 볼 것은 보통 **곡선 하나**뿐입니다
(`Curriculum/terrain_levels` — README 39). 브라우저를 띄우고 그래프를
눈으로 견주는 대신, 숫자를 표로 찍습니다.

읽는 방식은 tfevents 파일을 직접 뜯는 것입니다. 바깥 라이브러리를
하나도 안 씁니다 (파이썬 표준만). 그래서 어느 파이썬으로 돌려도 됩니다.

쓰는 법
-------
    C:\\isaacsim\\python.bat D:\\workspace_raraavis\\robotdog00\\curve.py `
        C:\\Users\\user123\\IsaacLab\\logs\\rsl_rl\\unitree_go2_guide_rough

    (뒤에 글자를 더 붙이면 그 글자가 든 곡선을 찾습니다)
    ... curve.py <로그폴더> reward        # 상 곡선
    ... curve.py <로그폴더> --list        # 이 판에 있는 곡선 이름 전부

읽는 법
-------
세로가 판(날짜), 가로가 반복 횟수입니다. 같은 칸끼리 위아래로 견주면
됩니다. 맨 밑에 판마다 **꼭대기**와 **끝**이 따로 나옵니다 — 우리 관심은
"끝"이 아니라 "꼭대기가 어디였나" 이기 때문입니다 (1500번을 돌려도
1100번이 꼭대기였습니다, README 38).
"""
import os
import sys
import math
import struct
from collections import defaultdict


# ── tfevents 뜯기 ────────────────────────────────────────────────────
#   tfevents 는 TFRecord 로 감싼 protobuf 입니다. 우리는 그중
#   "스칼라" 하나만 꺼내면 되므로, protobuf 라이브러리 없이
#   필요한 자리만 직접 읽습니다.

def _varint(buf, i):
    r = 0
    s = 0
    while True:
        b = buf[i]
        i += 1
        r |= (b & 0x7F) << s
        if not (b & 0x80):
            return r, i
        s += 7


def _fields(buf):
    """(번호, 종류, 값) 을 차례로 내놓습니다."""
    i = 0
    n = len(buf)
    while i < n:
        key, i = _varint(buf, i)
        fn, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(buf, i)
            yield fn, wt, v
        elif wt == 1:
            v = buf[i:i + 8]; i += 8; yield fn, wt, v
        elif wt == 2:
            ln, i = _varint(buf, i)
            v = buf[i:i + ln]; i += ln; yield fn, wt, v
        elif wt == 5:
            v = buf[i:i + 4]; i += 4; yield fn, wt, v
        else:
            raise ValueError("모르는 종류 %d" % wt)


def _records(path):
    with open(path, "rb") as f:
        data = f.read()
    i = 0
    n = len(data)
    while i + 12 <= n:
        ln = struct.unpack_from("<Q", data, i)[0]
        i += 12                       # 길이 8 + 길이의 검사값 4
        if i + ln + 4 > n:
            break                     # 아직 쓰는 중인 파일 — 여기서 멈춥니다
        yield data[i:i + ln]
        i += ln + 4                   # 몸통 + 몸통의 검사값 4


def read_scalars(path):
    """{곡선 이름: [(반복, 값), ...]}"""
    out = defaultdict(list)
    for rec in _records(path):
        step = None
        summary = None
        try:
            for fn, wt, v in _fields(rec):
                if fn == 2 and wt == 0:
                    step = v
                elif fn == 5 and wt == 2:
                    summary = v
        except Exception:
            continue
        if summary is None:
            continue
        try:
            for fn, wt, v in _fields(summary):
                if fn != 1 or wt != 2:
                    continue
                tag = val = None
                for f2, w2, v2 in _fields(v):
                    if f2 == 1 and w2 == 2:
                        tag = v2.decode("utf-8", "replace")
                    elif f2 == 2 and w2 == 5:
                        val = struct.unpack("<f", v2)[0]
                if tag is not None and val is not None:
                    out[tag].append((step if step is not None else 0, val))
        except Exception:
            continue
    for t in out:
        out[t].sort()
    return out


# ── 판 모으기 ────────────────────────────────────────────────────────

def find_runs(root):
    """[(판이름, tfevents 경로)] — 판이름은 폴더 이름(보통 날짜)."""
    runs = []
    if os.path.isfile(root):
        return [(os.path.basename(os.path.dirname(root)), root)]
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            if "tfevents" in fn:
                name = os.path.relpath(dirpath, root)
                if name == ".":
                    name = os.path.basename(os.path.abspath(root))
                runs.append((name, os.path.join(dirpath, fn)))
    runs.sort()
    return runs


def pick_tag(tags, want):
    """찾는 글자가 든 곡선 이름 하나. 여럿이면 가장 짧은 것."""
    hits = [t for t in tags if want.lower() in t.lower()]
    if not hits:
        return None
    hits.sort(key=lambda t: (len(t), t))
    return hits[0]


def at(series, step):
    """그 반복에서의 값 (없으면 바로 앞의 값). 아예 없으면 None."""
    best = None
    for s, v in series:
        if s <= step:
            best = v
        else:
            break
    return best


def main():
    args = [a for a in sys.argv[1:]]
    if not args:
        print(__doc__)
        return 1
    root = args[0]
    want = args[1] if len(args) > 1 else "terrain_levels"

    if not os.path.exists(root):
        print("✖ 그런 폴더가 없습니다: %s" % root)
        return 1

    runs = find_runs(root)
    if not runs:
        print("✖ tfevents 파일을 못 찾았습니다: %s" % root)
        print("  로그 폴더는 보통 ...\\logs\\rsl_rl\\<실험이름>\\<날짜>\\ 입니다.")
        return 1

    print("판 %d개를 찾았습니다.\n" % len(runs))

    # --list 면 곡선 이름만 찍고 끝냅니다
    if want in ("--list", "-l", "목록"):
        name, path = runs[-1]
        sc = read_scalars(path)
        print("가장 최근 판(%s)에 있는 곡선 %d개:" % (name, len(sc)))
        for t in sorted(sc):
            print("   " + t)
        return 0

    # 판마다 곡선 하나씩
    curves = []          # (판이름, 곡선이름, [(반복, 값)])
    for name, path in runs:
        sc = read_scalars(path)
        tag = pick_tag(sc.keys(), want)
        if tag is None:
            print("   %-22s '%s' 가 든 곡선이 없습니다 — 건너뜁니다" % (name, want))
            continue
        curves.append((name, tag, sc[tag]))
    if not curves:
        print("✖ 어느 판에도 '%s' 가 든 곡선이 없습니다." % want)
        print("  이름 목록을 보시려면:  curve.py <로그폴더> --list")
        return 1

    tag = curves[0][1]
    if len({c[1] for c in curves}) > 1:
        print("※ 판마다 곡선 이름이 다릅니다: %s"
              % ", ".join(sorted({c[1] for c in curves})))
    print("곡선: %s\n" % tag)

    last = max(c[2][-1][0] for c in curves)
    # 가로 눈금 — 12칸 안쪽으로 떨어지는 100 의 배수
    span = max(1, last)
    step = 100
    while span / step > 12:
        step += 100
    cols = list(range(0, last + 1, step))
    if cols[-1] != last:
        cols.append(last)

    head = "%-22s" % "판"
    head += "".join("%8d" % c for c in cols)
    print(head)
    print("-" * len(head))
    for name, _t, series in curves:
        row = "%-22s" % name[:22]
        for c in cols:
            v = at(series, c)
            row += ("%8.2f" % v) if v is not None and math.isfinite(v) else "       ·"
        print(row)

    print()
    print("%-22s %9s %8s %9s %8s" % ("판", "꼭대기", "그때", "끝", "마지막"))
    print("-" * 60)
    for name, _t, series in curves:
        vals = [(v, s) for s, v in series if math.isfinite(v)]
        if not vals:
            continue
        top, top_at = max(vals)
        print("%-22s %9.3f %8d %9.3f %8d"
              % (name[:22], top, top_at, series[-1][1], series[-1][0]))

    # 우리가 늘 보는 곡선이면 한 줄 덧붙입니다
    if "terrain_level" in tag:
        print()
        print("※ 승급선은 원점에서 4.0 m 입니다 (판 크기 8 m 의 절반, README 39).")
        print("  15~18 cm 층간 계단은 지형 단계 5~6 쯤입니다. 2.31 은 9.6 cm 언저리입니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
