# -*- coding: utf-8 -*-
"""
코스가 JSON 을 왕복해도 그대로인가 — **로봇 없이 확인합니다.**

  ★ 왜 이 시험이 먼저인가 ★

    작업실(studio.py)이 하려는 일의 바닥은 "코스를 읽어서 고치고 다시
    쓴다" 입니다. 그 왕복에서 무언가 조용히 없어지면, 도구를 쓸수록
    코스가 닳습니다. 그리고 **없어진 것은 복도에서 발견됩니다** —
    회전각이 사라진 이동 구간이 그냥 직진해 버리는 식으로요.

    눈으로 봐서는 모릅니다. 진짜 코스를 왕복시켜 **낱낱이** 견줍니다.

  ★ 무엇을 보는가 ★

      1. 진짜 코스가 왕복해도 그대로인가 (사전 단위로 전부)
      2. 파일로 쓰고 읽어도 그대로인가
      3. 망가진 JSON 을 물면 **왜인지 말하는가**
      4. 검사가 실제로 잡는가 — 일부러 흠집을 내서 봅니다

  ※ 로봇에 연결하지 않습니다. 라이브러리도 안 씁니다.

  쓰는 법

      .\\run coursefile_test.py
"""

import json
import sys
import tempfile
from pathlib import Path

import coursefile
import scenario


def differences(a, b):
    """두 코스를 **객체 단위로** 견줍니다.

    ★ 사전끼리 견주면 못 잡는 것이 있습니다 ★

      to_dict() 가 어떤 항목을 아예 빠뜨리면, 왕복한 사전에도 그 항목이
      없습니다. 양쪽 다 없으니 **같아 보입니다.** 물건을 잃어버려 놓고
      양쪽 주머니를 뒤져 "둘 다 없네, 맞네" 하는 셈입니다.

      객체에서 직접 꺼내 보면 원본에는 있고 왕복한 쪽에는 기본값이
      들어 있으니 드러납니다.
    """
    out = []
    for name in ("id", "name", "subtitle", "route", "audience", "optional"):
        if getattr(a, name) != getattr(b, name):
            out.append(f"코스.{name}")
    if len(a.steps) != len(b.steps):
        return out + [f"지점 수 {len(a.steps)} → {len(b.steps)}"]
    for x, y in zip(a.steps, b.steps):
        if type(x) is not type(y):
            out.append(f"{x.sid} 종류")
            continue
        for name, va in vars(x).items():
            if name == "lines":
                for la, lb in zip(va, getattr(y, name, [])):
                    for ln, lva in vars(la).items():
                        if lva != getattr(lb, ln, "<없음>"):
                            out.append(f"{x.sid}/{la.key}.{ln}")
                continue
            if va != getattr(y, name, "<없음>"):
                out.append(f"{x.sid}.{name}")
    return out


# ★ 알고 버리는 것 둘 ★
#
#   정차 지점을 언제나 lines 로 적기로 했습니다 (coursefile 설명글 참고).
#   그러면 key/text 로 적은 지점의 Stop.key 와 Stop.gesture 는 왕복 뒤에
#   None 이 됩니다. Stop 이 lines 를 받으면 스스로 그렇게 하거든요.
#
#   버려도 되는지 찾아봤습니다. 읽는 데가 셋인데 전부 안 걸립니다.
#
#       guide.py 의 step.key      이동 구간(Move)입니다
#       scenario._line_seconds    'if not lines' 로 막힌 가지 —
#       scenario.phrases          정차는 언제나 lines 라 안 갑니다
#
#   동작(gesture)도 마찬가지입니다. do_gesture 는 line.gesture 만 봅니다.
#   그래도 **말없이 버리지는 않습니다.** 여기 적어두고, 시험이 "딱 이
#   둘만 없어졌는지" 를 확인합니다. 하나라도 더 없어지면 걸립니다.
KNOWN_DROPS = ("key", "gesture")


class Score:
    def __init__(self):
        self.rows = []

    def check(self, name, got, want=True):
        ok = (got == want)
        self.rows.append((ok, name, got, want))
        print(f" {'○' if ok else '★'} {name}")
        if not ok:
            print(f"     받은 것: {got!r}")
            print(f"     바라던 것: {want!r}")
        return ok

    def report(self):
        bad = [r for r in self.rows if not r[0]]
        print()
        print("=" * 70)
        if not bad:
            print(f" 모두 통과했습니다 ({len(self.rows)}가지)")
            print(" 코스는 JSON 을 왕복해도 닳지 않습니다.")
            return True
        print(f" ★ {len(bad)}가지가 어긋납니다 ★")
        for _o, name, got, _w in bad:
            print(f"   · {name}")
        return False


def a_course():
    """시험용 코스 하나 — 있을 법한 것은 다 넣습니다."""
    return scenario.Course(
        "t_rt", "왕복 시험 코스", "이 시험에서만 씁니다.",
        [
            scenario.Stop(
                "S1", "홀", "환영", doc_seconds=20, face="visitor",
                notes=["여기 쪽지 하나"],
                lines=[
                    scenario.Line("t_rt_s1a", "첫 마디입니다.",
                                  gesture="hello", pause=0.5, note="쪽지"),
                    scenario.Line("t_rt_s1b", "둘째 마디입니다.",
                                  gesture="sit", pause=0.3),
                ]),
            scenario.Move(
                "M1", "홀 → 어딘가", "이동", "t_rt_m1", "갑니다.",
                meters=3.06, doc_seconds=12, turn_deg=-180.0,
                turn_when="after", reposition=True, narrow=True, align=True,
                notes=["좁은 데"]),
            scenario.Stop(
                "S2", "어딘가 앞", "소개", face="door", door_deg=+130.0,
                face_back=False,
                lines=[scenario.Line("t_rt_s2", "설명입니다.")]),
        ],
        {"t_rt_extra": "선택 멘트입니다."},
        route="홀 → 어딘가", audience="외빈",
    )


def main():
    print("=" * 70)
    print(" 코스가 JSON 을 왕복해도 그대로인가")
    print("=" * 70)
    print(" 로봇에 연결하지 않습니다.")
    print()
    s = Score()

    # ── 1. 만들어 본 코스 ───────────────────────────────────
    print("─" * 70)
    print(" 있을 법한 것을 다 넣은 코스로")
    print("─" * 70)
    src = a_course()
    once = coursefile.to_dict(src)
    twice = coursefile.to_dict(coursefile.from_dict(once))
    s.check("왕복해도 사전이 같습니다", twice, once)

    back = coursefile.from_dict(once)
    s.check("이동 구간의 회전각이 남습니다", back.steps[1].turn_deg, -180.0)
    s.check("회전 시점도 남습니다", back.steps[1].turn_when, "after")
    s.check("좁은 통로 표시가 남습니다", back.steps[1].narrow, True)
    s.check("문 각도가 남습니다", back.steps[2].door_deg, 130.0)
    s.check("되돌리지 않음(face_back)이 남습니다",
            back.steps[2].face_back, False)
    s.check("토막의 동작이 남습니다",
            [l.gesture for l in back.steps[0].lines], ["hello", "sit"])
    s.check("토막의 쉼도 남습니다",
            [l.pause for l in back.steps[0].lines], [0.5, 0.3])
    s.check("쪽지가 남습니다", back.steps[0].notes, ["여기 쪽지 하나"])
    s.check("선택 멘트가 남습니다", back.optional,
            {"t_rt_extra": "선택 멘트입니다."})
    s.check("오디오 이름이 그대로입니다", back.keys(), src.keys())
    s.check("원본 객체와 견줘도 없어진 것이 없습니다",
            differences(src, back), [])

    # ── 2. 진짜 코스 ────────────────────────────────────────
    print()
    print("─" * 70)
    print(" 진짜 코스로 — 이게 진짜 시험입니다")
    print("─" * 70)
    #
    # ★ 만들어 본 코스만으로는 모자랍니다 ★
    #   시험용 코스는 제가 아는 것만 넣습니다. 진짜 대본에는 제가
    #   잊은 것이 들어 있을 수 있고, 그게 바로 왕복에서 없어질 것입니다.
    #
    import courses
    courses.discover()
    real = [c for c in courses.COURSES]
    s.check("등록된 코스가 있습니다", bool(real), True)
    for c in real:
        one = coursefile.to_dict(c)
        two = coursefile.to_dict(coursefile.from_dict(one))
        s.check(f"'{c.id}' — 두 번 왕복해도 사전이 같습니다",
                [k for k in one if one[k] != two.get(k)], [])

        # ★ 여기가 진짜입니다 ★ 원본 **객체**와 견줍니다.
        gone = differences(c, coursefile.from_dict(one))
        unexpected = [g for g in gone
                      if not g.endswith(tuple("." + d for d in KNOWN_DROPS))]
        s.check(f"'{c.id}' — 원본과 견줘도 알고 버린 것 말고는 없습니다",
                unexpected, [])
        if gone:
            print(f"     (알고 버린 것 {len(gone)}개: {', '.join(gone[:4])}"
                  f"{' …' if len(gone) > 4 else ''})")

    # ── 2-1. 저장소에 넣어둔 JSON 이 대본과 같은가 ──────────
    print()
    print("─" * 70)
    print(" 저장소의 JSON 이 대본과 같은 말을 하는가")
    print("─" * 70)
    #
    # ★ 같은 것을 두 곳에 두면 언젠가 갈라집니다 ★
    #
    #   지금 코스는 scenario.py 와 courses/<id>/course.json 두 곳에
    #   있습니다. 실행기는 아직 .py 쪽을 읽습니다. 대본을 고치고
    #   coursefile.py --save 를 잊으면 JSON 이 조용히 옛말을 합니다.
    #
    #   이 저장소에서 그런 것을 겪었습니다 — 도면의 호실 용도 표가
    #   대사와 다른 말을 하고 있었고, 아무도 안 물어보면 몇 달을
    #   그대로 갔을 것입니다.
    #
    #   나중에 JSON 이 원본이 되면 이 검사는 필요 없어집니다. 그때까지는
    #   **갈라지는 순간 여기서 걸립니다.**
    #
    for c in real:
        p = coursefile.path_of(c.id)
        if not p.exists():
            print(f"   · {c.id}: 아직 저장소에 없습니다 "
                  f"(coursefile.py --save 로 만듭니다)")
            continue
        try:
            saved = coursefile.to_dict(coursefile.loads(
                p.read_text(encoding="utf-8")))
        except coursefile.CourseFileError as e:
            s.check(f"'{c.id}' 의 JSON 을 읽을 수 있습니다", str(e), "읽힘")
            continue
        now = coursefile.to_dict(c)
        drift = [k for k in now if now[k] != saved.get(k)]
        if drift:
            print(f"     → 대본이 바뀌었습니다. "
                  f".\\run coursefile.py --save 로 맞추세요.")
        s.check(f"'{c.id}' 의 JSON 이 대본과 같습니다", drift, [])

    # ── 3. 파일로 ───────────────────────────────────────────
    print()
    print("─" * 70)
    print(" 파일로 쓰고 읽기")
    print("─" * 70)
    with tempfile.TemporaryDirectory() as tmp:
        old = coursefile.COURSES_DIR
        coursefile.COURSES_DIR = Path(tmp)
        try:
            p = coursefile.save(src)
            s.check("파일이 생겼습니다", p.exists(), True)
            s.check("한글이 그대로 들어 있습니다",
                    "첫 마디입니다." in p.read_text(encoding="utf-8"), True)
            s.check("읽어도 그대로입니다",
                    coursefile.to_dict(coursefile.load("t_rt")), once)
            s.check("폴더에서 찾아냅니다", coursefile.found(), ["t_rt"])
        finally:
            coursefile.COURSES_DIR = old

    # ── 4. 망가진 것을 물었을 때 ────────────────────────────
    print()
    print("─" * 70)
    print(" 망가진 것을 물면 왜인지 말하는가")
    print("─" * 70)
    #
    #   조용히 실패하면 안 됩니다. 코스 파일은 사람이 손으로도 고칠 수
    #   있어야 하고, 그러면 반드시 망가뜨립니다.
    #
    for label, text, want in (
            ("JSON 이 아니면", "{{{", "JSON 이 깨졌습니다"),
            ("판이 다르면", '{"version": 99}', "99판"),
            ("id 가 없으면", '{"version": 1, "name": "x", "steps": []}', "'id'"),
            ("kind 가 이상하면",
             json.dumps({"version": 1, "id": "x", "name": "x",
                         "steps": [{"kind": "날기", "sid": "S1"}]}),
             "kind"),
            ("lines 가 비면",
             json.dumps({"version": 1, "id": "x", "name": "x",
                         "steps": [{"kind": "stop", "sid": "S1",
                                    "lines": []}]}),
             "비어 있습니다")):
        why = ""
        try:
            coursefile.loads(text)
        except coursefile.CourseFileError as e:
            why = str(e)
        s.check(f"{label} → 이유를 말해줍니다", want in why, True)

    # ── 5. 검사가 실제로 잡는가 ─────────────────────────────
    print()
    print("─" * 70)
    print(" 검사가 흠집을 잡는가")
    print("─" * 70)
    #
    # ★ 조용히 아무것도 안 잡는 검사는 없는 것보다 나쁩니다 ★
    #   이 저장소에서 두 번 겪었습니다. 그래서 일부러 흠집을 냅니다.
    #
    s.check("멀쩡한 코스에는 ★ 가 없습니다",
            [w for m, w in coursefile.check(src) if m == "★"], [])

    def hurt(fn):
        c = a_course()
        fn(c)
        return [w for m, w in coursefile.check(c) if m == "★"]

    def has(rows, word):
        return any(word in w for w in rows)

    s.check("거리가 없는 이동을 잡습니다",
            has(hurt(lambda c: setattr(c.steps[1], "meters", None)),
                "거리"), True)
    s.check("접두어 없는 이름을 잡습니다",
            has(hurt(lambda c: setattr(c.steps[1], "key", "m1")),
                "시작하지 않습니다"), True)
    s.check("같은 이름이 두 번 나오면 잡습니다",
            has(hurt(lambda c: setattr(c.steps[2].lines[0], "key",
                                       "t_rt_s1a")), "두 번"), True)
    s.check("대사도 동작도 없는 토막을 잡습니다",
            has(hurt(lambda c: (setattr(c.steps[2].lines[0], "text", "  "),
                                setattr(c.steps[2].lines[0], "gesture", None))),
                "아무 일도 안 합니다"), True)
    # ★ 동작만 하는 토막은 멀쩡합니다 ★
    #   진짜 대본의 마지막이 그렇습니다 — 말없이 엎드려서 끝을 알립니다.
    #   처음에는 이것도 ★ 로 쳤다가 진짜 코스에서 걸렸습니다.
    s.check("동작만 하는 토막은 안 잡습니다",
            has(hurt(lambda c: (setattr(c.steps[2].lines[0], "text", ""),
                                setattr(c.steps[2].lines[0], "gesture", "lie"))),
                "아무 일도 안 합니다"), False)
    s.check("모르는 동작을 잡습니다",
            has(hurt(lambda c: setattr(c.steps[0].lines[0], "gesture",
                                       "공중제비")), "모르는 동작"), True)
    s.check("문을 보라면서 각도가 없으면 잡습니다",
            has(hurt(lambda c: setattr(c.steps[2], "door_deg", None)),
                "door_deg"), True)
    s.check("지점 이름표가 겹치면 잡습니다",
            has(hurt(lambda c: setattr(c.steps[2], "sid", "S1")),
                "이름표"), True)
    s.check("선택 멘트의 접두어도 봅니다",
            has(hurt(lambda c: c.optional.update({"extra": "x"})),
                "선택 멘트"), True)

    return 0 if s.report() else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
