# -*- coding: utf-8 -*-
"""
코스를 JSON 으로 읽고 씁니다 — **작업실의 바닥돌.**

  ★ 왜 JSON 인가 ★

    도구에서 코스를 고치려면 읽어들여야 합니다. 파이썬 파일을 읽어
    고치고 다시 쓰는 것도 됩니다 — 처음 한 번은요. 그런데 사람이 손으로
    쓴 주석과 계산식이 섞여 있으면 **왕복하면서 조용히 뭉갭니다.**
    이 저장소는 주석이 코드보다 깁니다.

    그리고 **폰은 파이썬을 못 읽습니다.** 어차피 한 번은 데이터로
    바꿔야 하니, 두 번 바꾸느니 처음부터 데이터로 둡니다.

    자세한 내력은 TOOL.md 에 있습니다.

  ★ 새 개념을 만들지 않습니다 ★

    scenario.py 의 Course · Stop · Move · Line 을 **그대로** 옮깁니다.
    이름도 그대로입니다 (지점의 이름표는 sid, 코스의 것은 id — 코드가
    그렇게 되어 있어서 예쁘게 고치지 않았습니다).

    실행기가 이미 아는 모양이어야 합니다. JSON 만의 모양을 새로
    만들면, 그 사이를 옮기는 코드가 또 생기고 거기서 또 틀립니다.

  ★ 손실 없이 왕복하는가 ★

    이 파일의 값어치는 **코스 → JSON → 코스 가 원래와 같은가** 에
    달렸습니다. 눈으로 봐서는 모릅니다. coursefile_test.py 가 진짜
    코스를 왕복시켜 낱낱이 견줍니다.

    한 곳만 일부러 다르게 둡니다 — 정차 지점은 **언제나 lines 로**
    적습니다. Stop 은 key/text 로 만들어도 안에서 Line 하나로 바꾸니,
    나가는 모양을 하나로 두는 편이 낫습니다. 갈래가 둘이면 둘 다
    시험해야 하고, 안 쓰는 쪽이 조용히 썩습니다.

  쓰는 법 (아직 도구가 없어서 직접 부릅니다)

      .\\run coursefile.py                등록된 코스를 JSON 으로 찍어봅니다
      .\\run coursefile.py --save         courses/<id>/course.json 로 씁니다
      .\\run coursefile.py --check        빠진 것·이상한 것을 짚습니다
"""

import json
import sys
from pathlib import Path

import scenario

HERE = Path(__file__).resolve().parent
COURSES_DIR = HERE / "courses"

VERSION = 1


# ── 코스 → 사전 ──────────────────────────────────────────────

def line_to_dict(line):
    return {
        "key": line.key,
        "text": line.text,
        "gesture": line.gesture,
        "pause": line.pause,
        "note": line.note,
    }


def step_to_dict(step):
    base = {
        "sid": step.sid,
        "place": step.place,
        "purpose": step.purpose,
        "notes": list(step.notes),
        "doc_seconds": getattr(step, "doc_seconds", None),
    }
    if isinstance(step, scenario.Move):
        base.update({
            "kind": "move",
            "key": step.key,
            "text": step.text,
            "meters": step.meters,
            "turn_deg": step.turn_deg,
            "turn_when": step.turn_when,
            "reposition": step.reposition,
            "narrow": step.narrow,
            "align": step.align,
        })
    else:
        # ★ 정차는 언제나 lines 로 ★ (위 설명글 참고)
        base.update({
            "kind": "stop",
            "lines": [line_to_dict(l) for l in step.lines],
            "face": step.face,
            "door_deg": step.door_deg,
            "face_back": step.face_back,
        })
    return base


def to_dict(course):
    return {
        "version": VERSION,
        "id": course.id,
        "name": course.name,
        "subtitle": course.subtitle,
        "route": course.route,
        "audience": course.audience,
        "steps": [step_to_dict(s) for s in course.steps],
        "optional": dict(course.optional),
    }


# ── 사전 → 코스 ──────────────────────────────────────────────

class CourseFileError(ValueError):
    """읽다가 막힌 이유를 사람 말로 담습니다."""


def _need(d, key, where):
    if key not in d:
        raise CourseFileError(f"{where} 에 '{key}' 가 없습니다.")
    return d[key]


def step_from_dict(d, n):
    where = f"{n}번째 지점"
    kind = _need(d, "kind", where)
    sid = _need(d, "sid", where)
    where = f"지점 {sid}"
    common = dict(
        notes=d.get("notes", ()),
    )
    if kind == "move":
        return scenario.Move(
            sid, d.get("place", ""), d.get("purpose", ""),
            _need(d, "key", where), d.get("text", ""),
            meters=d.get("meters"),
            doc_seconds=d.get("doc_seconds"),
            turn_deg=d.get("turn_deg", 0.0),
            turn_when=d.get("turn_when", "before"),
            reposition=d.get("reposition", False),
            narrow=d.get("narrow", False),
            align=d.get("align", False),
            **common)
    if kind == "stop":
        raw = _need(d, "lines", where)
        if not raw:
            raise CourseFileError(f"{where} 에 lines 가 비어 있습니다.")
        lines = [scenario.Line(_need(l, "key", f"{where}의 {i}번째 토막"),
                               l.get("text", ""),
                               gesture=l.get("gesture"),
                               pause=l.get("pause", 0.0),
                               note=l.get("note"))
                 for i, l in enumerate(raw, 1)]
        return scenario.Stop(
            sid, d.get("place", ""), d.get("purpose", ""),
            lines=lines,
            doc_seconds=d.get("doc_seconds"),
            face=d.get("face"),
            door_deg=d.get("door_deg"),
            face_back=d.get("face_back", True),
            **common)
    raise CourseFileError(f"{where} 의 kind 가 'stop' 도 'move' 도 아닙니다: {kind!r}")


def from_dict(d):
    got = d.get("version", VERSION)
    if got != VERSION:
        raise CourseFileError(
            f"코스 파일이 {got}판인데 이 프로그램은 {VERSION}판만 압니다.")
    return scenario.Course(
        _need(d, "id", "코스"),
        _need(d, "name", "코스"),
        d.get("subtitle", ""),
        [step_from_dict(s, i) for i, s in enumerate(_need(d, "steps", "코스"), 1)],
        d.get("optional") or {},
        route=d.get("route", ""),
        audience=d.get("audience", ""),
    )


# ── 파일로 ───────────────────────────────────────────────────

def dumps(course):
    return json.dumps(to_dict(course), ensure_ascii=False, indent=2) + "\n"


def loads(text):
    try:
        return from_dict(json.loads(text))
    except json.JSONDecodeError as e:
        raise CourseFileError(f"JSON 이 깨졌습니다 — {e}")


def path_of(cid, name="course.json"):
    return COURSES_DIR / cid / name


def save(course):
    p = path_of(course.id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(dumps(course), encoding="utf-8")
    return p


def load(cid):
    p = path_of(cid)
    if not p.exists():
        raise CourseFileError(f"{p} 가 없습니다.")
    return loads(p.read_text(encoding="utf-8"))


def found():
    """courses/ 안에 있는 코스 이름들."""
    if not COURSES_DIR.exists():
        return []
    return sorted(d.name for d in COURSES_DIR.iterdir()
                  if (d / "course.json").exists())


# ── 만든 것 · 올린 것 (built.json) ───────────────────────────
#
# ★ 왜 audio/ 가 아니라 courses/ 안에 두는가 ★
#
#   audio/ 는 .gitignore 에 들어 있습니다. 음성 파일이 무거워서인데,
#   그 안에 durations.json 도 같이 있어서 **잰 값이 저장소에 안
#   남습니다.** 다른 PC 로 옮기거나 audio/ 를 비우면 멘트 길이를
#   처음부터 다시 재야 하고, 그러려면 음성을 다시 만들어야 합니다.
#
#   built.json 은 courses/<id>/ 에 둡니다. 거기는 추적됩니다.
#   음성 파일은 여전히 안 올라가지만 **잰 값은 남습니다.**

def text_hash(text):
    """이 문장으로 만든 음성인가 — 를 가리는 지문.

    ※ TTS 에 실제로 넘긴 모양으로 셉니다. scenario.for_tts() 가 숫자나
      기호를 읽기 좋게 바꾸므로, 원문이 같아도 그쪽이 바뀌면 음성이
      달라집니다. 원문으로 세면 그 변화를 놓칩니다.
    """
    import hashlib
    spoken = scenario.for_tts(text or "")
    return hashlib.sha1(spoken.encode("utf-8")).hexdigest()[:16]


def built_path(cid):
    return path_of(cid, "built.json")


def load_built(cid):
    p = built_path(cid)
    if not p.exists():
        return {"version": VERSION, "keys": {}}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # 망가졌으면 버리고 새로 셉니다. 여기 있는 것은 전부 다시
        # 알아낼 수 있는 값입니다 — 잃어도 시간만 듭니다.
        return {"version": VERSION, "keys": {}, "damaged": True}
    d.setdefault("keys", {})
    return d


def save_built(cid, data):
    p = built_path(cid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                 encoding="utf-8")
    return p


def old_texts(audio_dir):
    """audio/texts.json — voices.py 가 남긴 "이 문장으로 만들었다" 기록.

    ★ built.json 이 없을 때 여기서 가져옵니다 ★

      built.json 은 새로 만든 것입니다. 처음 돌리면 비어 있고, 그러면
      **이미 맞는 음성 16개를 "문장이 바뀌었다" 고 판단해서 16분을
      다시 올리게 됩니다.**

      그런데 그 정보는 이미 있습니다. voices.py 가 오래전부터
      texts.json 에 "어떤 문장으로 만들었는지" 를 적어왔거든요.
      모르는 척하고 다시 만드는 것보다, 있는 기록을 읽는 편이 낫습니다.

      ※ 이 기록은 **지역 파일**에 대한 것입니다. 로봇에 무엇이 올라가
        있는지는 안 적혀 있어요. 그건 로봇에게 물어봅니다.

      ※ 폴더를 **받아서** 씁니다. 처음에는 여기서 config.AUDIO_DIR 을
        직접 봤는데, 그러면 오디오 폴더를 아는 곳이 둘이 됩니다.
        실제로 시험이 폴더를 바꿔쳤을 때 이 함수만 딴 데를 보고 있었고,
        "옛 기록이 있는데도 못 찾는" 모양이 됐습니다. 부르는 쪽이
        어디를 보는지 정하게 두는 편이 낫습니다.
    """
    p = Path(audio_dir) / "texts.json"
    if not p.exists():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except json.JSONDecodeError:
        return {}


def spoken_texts(course):
    """{오디오 이름: 문장} — 말이 있는 것만. 음성을 만들 대상입니다."""
    out = {}
    for step in course.steps:
        lines = getattr(step, "lines", None)
        if lines:
            for l in lines:
                if l.text.strip():
                    out[l.key] = l.text
        elif getattr(step, "key", None) and step.text.strip():
            out[step.key] = step.text
    for k, v in course.optional.items():
        if str(v).strip():
            out[k] = v
    return out


# ── 검사 ─────────────────────────────────────────────────────

LONG_LINE = 30.0        # 한 토막이 이보다 길면 지루합니다 (초)


def check(course):
    """복도에 나가기 전에 짚어둘 것들. [(무게, 말), …]

    ★ 무게가 둘입니다 ★
      '★' 는 이대로 돌리면 안 되는 것, '·' 는 알고만 있으면 되는 것.
      섞어두면 둘 다 안 보게 됩니다.
    """
    out = []
    seen_sid, seen_key = {}, {}

    for step in course.steps:
        if step.sid in seen_sid:
            out.append(("★", f"지점 이름표 '{step.sid}' 가 두 번 나옵니다."))
        seen_sid[step.sid] = True

        if isinstance(step, scenario.Move):
            if step.meters is None:
                out.append(("★", f"{step.sid}: 걸을 거리(meters)가 없습니다. "
                                 "줄자로 재서 넣으세요 — 짐작은 안 됩니다."))
            keys = [step.key]
        else:
            keys = [l.key for l in step.lines]
            if step.face == "door" and step.door_deg is None:
                out.append(("★", f"{step.sid}: 문을 보라고 했는데 "
                                 "door_deg 가 없습니다."))
            for l in step.lines:
                # ★ 대사가 비어도 되는 때가 있습니다 ★
                #   동작만 하는 토막입니다 — 마지막에 말없이 엎드리는
                #   s5e_rest 가 그렇습니다. "엎드리는 것이 '안내가 끝났다'
                #   는 가장 분명한 신호" 라고 대본에 적혀 있고, 거기에
                #   말을 얹으면 오히려 흐려집니다.
                #
                #   처음에는 빈 대사를 무조건 ★ 로 쳤다가 진짜 대본에서
                #   걸렸습니다. 검사가 대본보다 잘 알 수는 없습니다.
                if not l.text.strip() and not l.gesture:
                    out.append(("★", f"{step.sid}/{l.key}: 대사도 동작도 "
                                     "없습니다. 이 토막은 아무 일도 안 합니다."))
                if l.gesture and l.gesture not in scenario.GESTURE_SECONDS:
                    out.append(("★", f"{step.sid}/{l.key}: 모르는 동작 "
                                     f"'{l.gesture}'."))
                secs, real = scenario._line_seconds(l)
                if secs > LONG_LINE:
                    out.append(("·", f"{step.sid}/{l.key}: 한 토막이 "
                                     f"{secs:.0f}초입니다. 토막을 나누면 "
                                     "듣는 쪽이 덜 지칩니다."))
                if not real and l.text.strip():
                    out.append(("·", f"{step.sid}/{l.key}: 길이가 아직 "
                                     "어림값입니다 (음성을 안 만들었습니다)."))

        for k in keys:
            if k in seen_key:
                out.append(("★", f"오디오 이름 '{k}' 가 두 번 나옵니다."))
            seen_key[k] = True
            if not k.startswith(f"{course.id}_"):
                out.append(("★", f"오디오 이름 '{k}' 가 코스 이름으로 "
                                 f"시작하지 않습니다 ('{course.id}_')."))

    for k in course.optional:
        if not k.startswith(f"{course.id}_"):
            out.append(("★", f"선택 멘트 '{k}' 도 코스 이름으로 "
                             f"시작해야 합니다."))
    return out


def show_check(course):
    rows = check(course)
    bad = [r for r in rows if r[0] == "★"]
    print(f"─ {course.id} · {course.name}")
    for mark, why in rows:
        print(f"   {mark} {why}")
    if not rows:
        print("   ○ 짚을 것이 없습니다.")
    return not bad


# ── 직접 돌릴 때 ─────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    import courses
    courses.discover()
    if not courses.COURSES:
        print("등록된 코스가 없습니다.")
        return 1

    if "--check" in args:
        print("=" * 70)
        print(" 코스 검사")
        print("=" * 70)
        ok = True
        for c in courses.COURSES:
            ok = show_check(c) and ok
            print()
        print("모두 괜찮습니다." if ok else "★ 표시를 먼저 고치세요.")
        return 0 if ok else 1

    if "--save" in args:
        print("=" * 70)
        print(" JSON 으로 씁니다")
        print("=" * 70)
        for c in courses.COURSES:
            p = save(c)
            print(f"   {c.id:<12} → {p.relative_to(HERE)}  "
                  f"({p.stat().st_size:,} 바이트)")
        return 0

    for c in courses.COURSES:
        print(dumps(c))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except CourseFileError as e:
        print(f"★ {e}")
        sys.exit(1)
