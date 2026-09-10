# -*- coding: utf-8 -*-
"""
안내 코스 등록소 — 폴더에 있는 코스를 스스로 찾습니다.

  ★ 코스를 하나 더 만드는 법 (이게 전부입니다) ★

      1. course_example.py 를 복사합니다.   예: course_short.py
      2. 대본을 채웁니다.
      3. 다 되면 파일 위쪽의  DRAFT = True  줄을 지웁니다.

    끝입니다. **이 파일은 손대지 않습니다.** 휴대폰 메뉴에 저절로 뜹니다.

  ★ 왜 이렇게 바꿨는가 ★

    처음에는 여기 COURSES 목록에 한 줄을 넣게 만들었습니다. 그랬더니

      · courses.py 가 course_short.py 를 부르고
        course_short.py 가 courses.py 를 부르는 **고리**가 생겼습니다.
        코스를 하나 추가하려는 첫 시도가 ImportError 로 끝났습니다.

      · 그리고 코스 하나를 넣는 데 **별도의 설명서**가 필요해졌습니다.
        복사하고, 앞말 바꾸고, 다른 파일을 열어서, import 문법을
        기억해서 한 줄 넣고… 시연 전날 할 일이 아닙니다.

    둘 다 "사람이 규칙을 기억한다" 에 기대고 있었습니다. 그러지 않게
    바꿨습니다. **폴더에 파일을 두면 그게 코스입니다.**

  ★ 규칙은 셋뿐입니다 ★

      이름이  course_ 로 시작하는 .py 파일
      그 안에 COURSE 라는 이름의 Course 하나
      DRAFT = True 가 없을 것        ← 있으면 아직 초안입니다

    안 되면 조용히 넘기지 않고 **말합니다.** 코스가 메뉴에 안 뜨는데
    아무도 이유를 말해주지 않는 것이 제일 나쁩니다.

  ★ 오디오 이름은 코스마다 달라야 합니다 ★

    로봇에 올리는 음성은 이름 하나에 파일 하나입니다. 두 코스가
    's1a_greet' 를 같이 쓰면 나중에 올린 쪽이 앞의 것을 덮어씁니다.
    화면에는 이 코스의 문장이 찍히는데 스피커에서는 저 코스의 문장이
    나옵니다 — 로그가 멀쩡해서 알아채기 어렵습니다.

    그래서 겹치면 **등록을 거부하고 어느 파일과 겹쳤는지 말합니다.**
    사람이 조심하는 것에 기대지 않습니다.

  쓰는 법

      .\\run courses.py     찾은 코스 · 초안 · 문제를 봅니다
"""

import importlib
from pathlib import Path

import scenario
# Course 는 scenario 에 있습니다 (고리를 끊으려고 옮겼습니다).
# 예전처럼 `from courses import Course` 로 써도 되게 여기서도 내놓습니다.
from scenario import Course

# ── 기본 코스 ────────────────────────────────────────────────
#
# scenario.py 가 들고 있는 대본입니다. 1,300줄을 옮기지 않았습니다 —
# 옮기는 것 자체가 위험하고, 얻는 것이 없습니다. 여기서 이름표만
# 붙여 등록합니다.
#
# ★ import 할 때의 값을 붙잡습니다 ★
#   use() 는 scenario 의 이름을 다시 묶을 뿐 목록을 바꾸지 않으므로,
#   여기 붙잡아 둔 것은 코스를 몇 번 바꿔도 원래 그대로입니다.
AI_SWE = Course(
    "ai_swe",
    scenario.TITLE,
    "3층 엘리베이터 홀에서 301 · 303 · 304호를 도는 기본 코스입니다.",
    scenario.SCENARIO,
    scenario.OPTIONAL,
    route=scenario.ROUTE,
    audience=scenario.AUDIENCE,
)

COURSES = [AI_SWE]

# 찾다가 생긴 일들. 조용히 넘기지 않습니다.
PROBLEMS = []       # 못 읽었거나 거부한 것 — 사람이 고쳐야 합니다
DRAFTS = []         # 아직 초안이라 건너뛴 것 — 알려만 줍니다


# ── 등록소 ───────────────────────────────────────────────────

def all_courses():
    return list(COURSES)


def default():
    return COURSES[0]


def get(cid):
    """이름으로 찾습니다. 없으면 None — 짐작해서 아무거나 주지 않습니다."""
    for c in COURSES:
        if c.id == cid:
            return c
    return None


def collisions(pool=None):
    """코스끼리 겹치는 오디오 이름. [(이름, [코스…]), …]"""
    seen = {}
    for c in (pool if pool is not None else COURSES):
        for k in c.keys():
            seen.setdefault(k, []).append(c.id)
    return sorted((k, v) for k, v in seen.items() if len(v) > 1)


def unprefixed(course):
    """코스 이름으로 시작하지 않는 오디오 이름들.

    ★ 왜 이걸 강제하는가 ★

      로봇의 오디오 이름은 **평평합니다.** 폴더가 없습니다. 그래서 두
      코스가 같은 이름을 쓰면 로봇에서는 한 파일이 되고, 나중에 올린
      쪽이 앞의 것을 덮어씁니다. 화면에는 맞는 문장이 찍히는데
      스피커에서는 다른 코스의 말이 나옵니다.

      겹칠 때 거부하는 검사(collisions)는 이미 있었습니다. 그런데 그건
      **부딪힌 뒤에** 잡습니다. 코스가 셋 넷이 되면 "이번엔 뭐랑
      겹쳤지" 를 매번 풀어야 합니다.

      규칙을 하나 두면 애초에 안 부딪힙니다 — **오디오 이름은 코스
      이름으로 시작한다.** 사람이 기억할 필요는 없습니다. 여기서
      확인하니까요.

      ※ alert_* 와 config.PHRASES(greet · settle · power_ready 등)는
        코스에 안 딸린 **공용** 멘트라 이 규칙 밖입니다. 애초에
        Course 안에 없어서 여기까지 오지 않습니다.
    """
    want = f"{course.id}_"
    return [k for k in course.keys() if not k.startswith(want)]


def register(course):
    """코스를 등록합니다. 겹치는 이름이 있으면 거부합니다."""
    if not isinstance(course, Course):
        raise ValueError("COURSE 가 Course 가 아닙니다.")
    if get(course.id):
        raise ValueError(f"'{course.id}' 라는 코스가 이미 있습니다.")
    loose = unprefixed(course)
    if loose:
        shown = ", ".join(loose[:6]) + (" …" if len(loose) > 6 else "")
        raise ValueError(
            f"'{course.id}' 의 오디오 이름 {len(loose)}개가 코스 이름으로\n"
            f"      시작하지 않습니다: {shown}\n"
            f"      로봇의 오디오 이름은 평평합니다 — 폴더가 없어서, 다른\n"
            f"      코스와 같은 이름을 쓰면 한쪽이 다른 쪽을 덮어씁니다.\n"
            f"      '{course.id}_' 를 앞에 붙이세요."
        )
    bad = collisions(COURSES + [course])
    if bad:
        lines = "\n".join(f"      {k} — {', '.join(v)}" for k, v in bad)
        raise ValueError(
            f"'{course.id}' 의 오디오 이름이 다른 코스와 겹칩니다.\n{lines}\n"
            "      같은 이름은 로봇에서 한 파일입니다. 나중에 올린 쪽이\n"
            "      앞의 것을 덮어써서 다른 코스의 문장이 나옵니다.\n"
            "      그 파일의 PREFIX 를 다른 말로 바꾸세요."
        )
    COURSES.append(course)
    return course


def discover(folder=None, verbose=False):
    """폴더에서 course_*.py 를 찾아 등록합니다.

    ★ 조용히 넘기는 것이 없습니다 ★
      파일을 못 읽었거나, COURSE 가 없거나, 이름이 겹치면 PROBLEMS 에
      적습니다. 아직 초안(DRAFT)이면 DRAFTS 에 적습니다. 둘 다
      courses.check() 와 guide.py 시작할 때 화면에 나옵니다.

      코스가 메뉴에 안 뜨는데 아무도 이유를 말해주지 않는 것이
      제일 나쁩니다. 시연 30분 전에 그걸 찾고 있을 수는 없습니다.
    """
    import sys
    here = Path(folder) if folder else Path(__file__).resolve().parent
    if str(here) not in sys.path:
        sys.path.insert(0, str(here))
    for path in sorted(here.glob("course_*.py")):
        name = path.stem
        try:
            mod = importlib.import_module(name)
        except Exception as e:
            PROBLEMS.append(f"{path.name} 를 읽지 못했습니다 — "
                            f"{type(e).__name__}: {e}")
            continue
        if getattr(mod, "DRAFT", False):
            DRAFTS.append(path.name)
            continue
        course = getattr(mod, "COURSE", None)
        if course is None:
            PROBLEMS.append(f"{path.name} 안에 COURSE 라는 이름이 없습니다 "
                            f"(맨 아래에 COURSE = Course(...) 가 있어야 합니다)")
            continue
        try:
            register(course)
            if verbose:
                print(f"[코스] {path.name} → {course.id}")
        except ValueError as e:
            PROBLEMS.append(f"{path.name} — {e}")
    return COURSES


def report():
    """찾다가 생긴 일을 한 줄씩. 없으면 빈 목록."""
    out = []
    for d in DRAFTS:
        out.append(f"{d} 는 아직 초안이라 건너뜁니다 "
                   f"(다 쓰면 파일 위쪽의 DRAFT = True 줄을 지우세요)")
    out += list(PROBLEMS)
    return out


def check(verbose=True):
    """등록 상태를 봅니다. 돌려주는 값: 문제 없으면 True."""
    bad = collisions()
    if verbose:
        print("=" * 70)
        print(" 안내 코스")
        print("=" * 70)
        for c in COURSES:
            mark = " (기본)" if c is COURSES[0] else ""
            d = c.summary()
            extra = d["ments"] - d["spoken"]
            print(f"\n {c.id}{mark}")
            print(f"   {c.name}")
            if c.route:
                print(f"   {c.route}")
            print(f"   {c.brief()['facts']}")
            print(f"   구간 {len(c.steps)}개 "
                  f"(정차 {d['stops']} · 이동 {d['moves']}) · "
                  f"멘트 {d['spoken']}개"
                  + (f" (+ 선택 멘트 {extra}개)" if extra else ""))
            if d["guessed"]:
                print(f"   ※ 멘트 {d['guessed']}/{d['spoken']}개는 음성을 아직 "
                      f"안 재서 글자 수로 어림한 값입니다 (.\\run voices.py)")
            if d["unmeasured"]:
                print(f"   ※ 이동 {d['unmeasured']}개 구간은 줄자로 안 쟀습니다 "
                      f"(MEASURE.md)")

        notes = report()
        if notes:
            print()
            print("─" * 70)
            for n in notes:
                print(f" · {n}")

        print()
        if bad:
            print(" ★ 오디오 이름이 겹칩니다 ★")
            for k, v in bad:
                print(f"   · {k} — {', '.join(v)}")
            print("   같은 이름은 로봇에서 한 파일입니다. 덮어씁니다.")
        else:
            print(" 겹치는 오디오 이름은 없습니다.")
        if len(COURSES) == 1 and not DRAFTS:
            print()
            print(" ※ 아직 코스가 하나입니다. 하나 더 만들려면")
            print("   course_example.py 를 복사해서 채우고, 다 되면")
            print("   그 파일의 DRAFT = True 줄을 지우면 됩니다.")
            print("   이 파일(courses.py)은 손댈 필요가 없습니다.")
    return not bad and not PROBLEMS


# 폴더를 훑는 것은 **불러올 때 한 번**입니다. guide.py 든 voices.py 든
# scenario.py 든, courses 를 import 하는 쪽은 아무것도 안 해도 같은
# 목록을 봅니다. 두 벌이 생길 자리가 없습니다.
discover()


if __name__ == "__main__":
    import sys
    sys.exit(0 if check() else 1)
