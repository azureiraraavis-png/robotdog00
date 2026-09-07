# -*- coding: utf-8 -*-
"""
짧은 코스 — 대본을 채우는 중입니다.

  ★ 아직 초안입니다 ★
    아래 DRAFT = True 가 있는 동안에는 휴대폰 메뉴에 뜨지 않습니다.
    반쯤 쓴 코스가 메뉴에 있으면 시연 중에 누군가 그걸 누릅니다.
    **대본을 다 쓰고 나서 그 줄을 지우세요.** 그러면 뜹니다.

  ── 남은 순서 ──

    1) 대본을 채웁니다 (아래 STEPS).
    2) 다 되면 DRAFT = True 줄을 지웁니다.

    courses.py 는 손대지 않습니다. 폴더에 course_ 로 시작하는 파일이
    있으면 저절로 찾습니다.

  ── 확인 (로봇 없이 됩니다) ──

           .\\run courses.py                     찾았는지, 이름이 겹치지 않는지
           .\\run guide.py --dry --course SHORT   순서가 말이 되는지
           .\\run voices.py                      멘트를 만들고 길이를 잽니다

  ★ 왜 PREFIX 가 제일 중요한가 ★

    로봇에 올라가는 음성은 **이름 하나에 파일 하나**입니다. 두 코스가
    's1a_greet' 를 같이 쓰면 나중에 올린 쪽이 앞의 것을 덮어씁니다.
    그러면 화면에는 이 코스의 문장이 찍히는데 스피커에서는 저 코스의
    문장이 나옵니다. 로그는 멀쩡합니다 — 그래서 제일 나쁩니다.

    courses.register() 가 겹치면 거부하지만, 애초에 앞말을 다르게
    붙이면 부딪힐 일이 없습니다.

  ── 건물의 사실은 여기 적지 않습니다 ──

    복도 폭, 문 위치, 실측 거리, 회전 모델은 scenario.py 에 있습니다.
    코스가 달라져도 건물은 그대로입니다. 여기는 **대본만** 적습니다.

    다만 구간마다 '몇 미터인지' 와 '몇 도 도는지' 는 그 코스의
    경로이므로 여기 적습니다. 새 경로를 만들었다면 줄자로 재세요 —
    measure.py 와 MEASURE.md 가 그 일을 합니다. 짐작한 숫자를
    적어두면 나중에 그것이 실측인 줄 알고 씁니다.
"""

# ★ 이 줄이 있는 동안에는 메뉴에 안 뜹니다 ★  대본을 다 쓰면 지우세요.
# DRAFT = True

# ★ 코스 파일은 scenario 하나만 봅니다 ★
#   courses 를 import 하면 courses 가 이 파일을 부르고 이 파일이
#   courses 를 부르는 고리가 됩니다 — 처음에 그렇게 만들어서 터졌습니다.
from scenario import Course, Line, Move, Stop

# ★ 이 코스만의 앞말 ★  다른 코스와 절대 겹치면 안 됩니다.
PREFIX = "SHORT"


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
    "짧은 코스",                               # 화면에 크게 뜨는 이름
    "아직 대본을 안 썼습니다.",                 # 한 줄 설명
    STEPS,
    OPTIONAL,
    route="3층 엘리베이터 홀 → 어딘가",
    audience="",
)
