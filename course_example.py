# -*- coding: utf-8 -*-
"""
안내 코스 본보기 — 이 파일을 복사해서 새 코스를 만듭니다.

  ── 만드는 순서 (이게 전부입니다) ──

    1) 이 파일을 복사합니다.       course_short.py 처럼 이름을 붙이세요.
                                  ★ 이름이 course_ 로 시작해야 합니다 ★
    2) PREFIX 를 바꿉니다.
    3) 대본을 채웁니다.
    4) 다 되면 아래 DRAFT = True 줄을 **지웁니다.**

    courses.py 는 손대지 않습니다. 폴더에 있으면 저절로 찾습니다.

  ── 확인 (로봇 없이 됩니다) ──

      .\\run courses.py         찾았는지, 이름이 겹치지 않는지
      .\\run guide.py --dry --course <PREFIX>    순서가 말이 되는지
      .\\run voices.py          멘트를 만들고 길이를 잽니다

  ★ DRAFT 는 왜 있는가 ★

    반쯤 쓴 코스가 휴대폰 메뉴에 떠 있으면, 시연 중에 누군가 그걸
    누릅니다. 다 쓸 때까지는 안 보이는 편이 안전합니다.
    안 보이는 이유는 courses.py 가 말해줍니다 — 조용히 사라지지
    않습니다.

  ★ 왜 PREFIX 가 중요한가 ★

    로봇에 올라가는 음성은 **이름 하나에 파일 하나**입니다. 두 코스가
    's1_greet' 를 같이 쓰면 나중에 올린 쪽이 앞의 것을 덮어씁니다.
    그러면 화면에는 이 코스의 문장이 찍히는데 스피커에서는 저 코스의
    문장이 나옵니다. 로그는 멀쩡합니다 — 그래서 제일 나쁩니다.

    겹치면 등록이 거부되고 어느 파일과 겹쳤는지 나오지만, 애초에
    앞말을 다르게 붙이면 부딪힐 일이 없습니다.

  ── 건물의 사실은 여기 적지 않습니다 ──

    복도 폭, 문 위치, 실측 거리, 회전 모델은 scenario.py 에 있습니다.
    코스가 달라져도 건물은 그대로입니다. 여기는 **대본만** 적습니다.

    다만 구간마다 '몇 미터인지' 와 '몇 도 도는지' 는 그 코스의
    경로이므로 여기 적습니다. 새 경로를 만들었다면 줄자로 재세요 —
    measure.py 와 MEASURE.md 가 그 일을 합니다. 짐작한 숫자를
    적어두면 나중에 그것이 실측인 줄 알고 씁니다.

  ── 적을 수 있는 것 ──

    Stop(sid, place, purpose, doc_seconds=, face=, door_deg=, lines=[...])
        face="visitor"  방문객을 보고 말합니다
        face="door"     문 쪽으로 돌아 라이트로 가리키고 말합니다
                        (그때 door_deg 이 필요합니다. + 가 왼쪽)
        face_back=False 설명이 끝나도 문을 본 채로 둡니다 (그 문으로 들어갈 때)

    Line(오디오이름, text=..., gesture=None, pause=0.0)
        gesture: "hello" · "sit" · "stand" · "lie"

    Move(sid, place, purpose, 오디오이름, text,
         meters=, turn_deg=, turn_when=, narrow=, align=)
        turn_when="before"  출발 전에 돕니다
        turn_when="after"   도착한 뒤에 돕니다
        narrow=True         문틀처럼 좁은 곳 (화면에 경고가 뜹니다)
"""

# ★ 이 줄이 있는 동안에는 메뉴에 안 뜹니다 ★  다 쓰면 지우세요.
DRAFT = True

# ★ 코스 파일은 scenario 하나만 봅니다 ★
#   courses 를 import 하면 courses 가 이 파일을 부르고 이 파일이
#   courses 를 부르는 고리가 생깁니다. 실제로 그렇게 만들었다가
#   코스를 하나 추가하려는 첫 시도가 ImportError 로 끝났습니다.
from scenario import Course, Line, Move, Stop

# ★ 이 코스만의 앞말 ★  다른 코스와 절대 겹치면 안 됩니다.
PREFIX = "ex"


def k(name):
    """오디오 이름에 앞말을 붙입니다. 손으로 붙이면 언젠가 하나를 빠뜨립니다."""
    return f"{PREFIX}_{name}"


STEPS = [
    Stop(
        "S1", "3층 엘리베이터 홀", "환영 인사",
        doc_seconds=20, face="visitor",
        lines=[
            Line(k("s1_greet"), gesture="hello", pause=0.5, text=(
                "여기에 첫 인사를 적습니다. "
                "한 토막은 15초에서 25초 사이가 좋습니다."
            )),
        ],
    ),
    Move(
        "M1", "홀 → 어딘가", "복도로 나가기",
        k("m1_go"),           # 오디오 이름
        "이동하기 전에 방문객에게 하는 예고 멘트입니다.",
        meters=3.06,          # ★ 줄자로 잰 값만 적습니다 ★
        turn_deg=-180,        # 출발 전에 도는 각도 (도면 기준)
        turn_when="before",   # "before" 출발 전 · "after" 도착 후
    ),
    Stop(
        "S2", "어딘가 앞", "방 소개",
        doc_seconds=20, face="door", door_deg=+130,
        lines=[
            Line(k("s2_room"), text="이 방에 대한 설명을 적습니다."),
        ],
    ),
]

OPTIONAL = {
    k("extra"): "시간이 남을 때만 하는 멘트입니다.",
}

COURSE = Course(
    PREFIX,                                   # 메뉴에서 이 코스를 부르는 이름
    "본보기 코스",                             # 화면에 크게 뜨는 이름
    "복사해서 쓰는 틀입니다.",                  # 한 줄 설명
    STEPS,
    OPTIONAL,
    route="3층 엘리베이터 홀 → 어딘가",
    audience="",
)
