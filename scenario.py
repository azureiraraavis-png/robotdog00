# -*- coding: utf-8 -*-
"""
안내 시나리오 — AI응용소프트웨어과 3층.  ★ 로봇을 움직이지 않습니다 ★

  이 파일은 **자료입니다.** 코드가 아닙니다.
  출처: `AI응용소프트웨어과_로봇개_안내시나리오_2.docx`

  ★ 왜 따로 파일로 두는가 ★
    멘트는 학과 사정에 따라 계속 바뀝니다. 과목이 바뀌고, 호실이 바뀌고,
    방문객에 따라 길이가 바뀝니다. 그걸 고칠 때마다 로봇 코드를 열어야
    한다면, 결국 아무도 안 고치거나 코드를 부수거나 둘 중 하나입니다.
    멘트는 여기, 로봇 다루는 법은 저기. 섞지 않습니다.

  ★ 원문을 손대지 않았습니다 ★
    멘트는 문서의 글자 그대로입니다. 우리 실측이 문서의 가정과 어긋나는
    곳이 몇 군데 있는데, 멘트를 고치는 대신 REALITY 에 무엇이 왜 다른지
    적어 두었습니다. 문서를 고칠지는 사람이 정할 일입니다.

  혼자 돌려볼 수 있습니다 (로봇도 네트워크도 필요 없습니다)

      .\\run scenario.py            시간표와 점검 결과
      .\\run scenario.py --tts      TTS 에 넣을 문장 (발음 교정 적용)
      .\\run scenario.py --text     멘트 전문만
"""

import sys
import unicodedata


def _w(text):
    """콘솔에서 이 글자들이 차지하는 칸 수. 한글은 두 칸입니다.

    ★ 파이썬의 len() 은 글자 수지 칸 수가 아닙니다 ★
    f"{s:20}" 로 표를 맞추면 한글에서 통째로 어긋납니다.

    'A'(ambiguous) 도 두 칸으로 셉니다. → ★ — · 같은 글자들인데,
    한국어 윈도우 콘솔에서는 두 칸으로 그려집니다. 영문 로케일에서는
    한 칸이라 조금 어긋나지만, 이 프로젝트는 한국어 콘솔에서 돌아갑니다.
    """
    return sum(2 if unicodedata.east_asian_width(c) in "WFA" else 1 for c in text)


def _pad(text, width, right=False):
    """칸 수 기준으로 자리를 맞춥니다."""
    gap = " " * max(0, width - _w(text))
    return gap + text if right else text + gap

# ─────────────────────────────────────────────────────────────
# 0. 이 시나리오가 무엇인가
# ─────────────────────────────────────────────────────────────

TITLE = "AI응용소프트웨어과 외빈 안내"
ROUTE = "3층 엘리베이터 홀 → 301호 → 303호 → 304호 프로젝트실 **안**"
# ※ 문서 원문은 301 → 302 → 303 이었습니다. 이 층에 302호가 없어
#   한 칸씩 밀렸습니다. 역할(전반기 강의실 / 후반기 강의실 / 프로젝트실)은
#   그대로이고 호실 번호만 바뀌었습니다.
AUDIENCE = "외부 방문객(외빈), 산업체 관계자, 학부모·수험생"

# 문서 §1-1 의 원칙. 코드가 이걸 지키는지 check() 가 봅니다.
PRINCIPLES = [
    "발화는 반드시 '정차 후'에 시작한다. 이동 중 발화는 보행 소음으로 전달력이 떨어진다.",
    "한 정차 지점의 멘트는 15~25초 이내로 유지한다.",
    "멘트 종료 후 2초의 여유(Q&A 대기)를 두고 다음 구간으로 출발한다.",
    "출발 직전에는 반드시 '이동하겠습니다' 예고 멘트를 재생한다.",
    "경로 상 사람·장애물이 감지되면 즉시 정지하고, 대기 멘트를 재생한 뒤 재개한다.",
]

MENT_MIN_SECONDS = 15.0    # 문서 §1-1
MENT_MAX_SECONDS = 25.0
QA_PAUSE = 2.0             # 멘트 끝나고 다음 구간까지


# ─────────────────────────────────────────────────────────────
# 0-2. 건물  (출처: 3층 평면도, 가나건축사사무소 2015.07, 축척 1/150)
# ─────────────────────────────────────────────────────────────
#
# ★★ 이 도면은 '계획도' 입니다. 방 구획은 현재와 다릅니다 ★★
#
#   현장과 대조한 결과 (실제로 가서 본 사람의 확인):
#     · 도면에 **302호가 없습니다.** 지금의 302호는 도면에서 301호나
#       303호에 해당하는 공간에 합쳐져 있는 것으로 보입니다.
#     · 유리문의 배치가 조금씩 다르고, 실제 유리는 안이 안 보이게 흐립니다.
#     · 사물함·긴 의자는 당연히 안 그려져 있습니다 (가구니까요).
#     · 도면의 '301', '302' 는 **계단실 번호**입니다. 강의실이 아닙니다.
#
#   그래서 **방 단위로는 이 도면을 쓰지 않습니다.** 아래 FRONTAGE 는
#   "복도가 대충 이렇게 생겼다" 를 보기 위한 참고일 뿐이고, 정차 지점
#   거리로 옮기면 안 됩니다.
#
#   ★ 그래도 복도의 뼈대는 쓸 수 있습니다 ★
#     폭·길이·막다른 끝·자동문은 구조라서 잘 안 바뀝니다. 그리고 그중
#     복도 폭은 실측(1.15m)과 앞뒤가 맞았습니다. 아래 BUILDING 이 그것입니다.
#
#   정차 지점 거리는 **줄자로 잰 값**으로 채웁니다 (MEASURE.md 참고).

BUILDING = {
    "출처": "3층 평면도 (가나건축사사무소, 2015.07, 1/150)",
    "건물": "17,200 × 27,100 mm",
    "복도 폭": 2.20,          # m — 7,000(남쪽 방) + 2,200(복도) + 8,000(북쪽 방)
    "복도 길이": 21.40,       # m — 27,100 에서 계단·화장실 구역 5,700 을 뺀 값
    "방 깊이 남": 7.00,
    "방 깊이 북": 8.00,
}

# 복도를 따라 늘어선 방들의 **정면 폭** (mm). 엘리베이터 쪽부터 순서대로.
#   이 값이 있으면 "몇 번째 문 앞" 을 거리로 바꿀 수 있습니다.
FRONTAGE_SOUTH = [        # 깊이 7.0 m 쪽
    ("계단·화장실 구역", 7200),
    ("프로젝트실", 3000),
    ("프로젝트실", 3300),
    ("프로젝트실", 3750),
    ("교수연구실", 3750),
    ("프로젝트실", 6100),
]
FRONTAGE_NORTH = [        # 깊이 8.0 m 쪽
    ("엘리베이터 홀·계단", 5700),
    ("실습실 (7.5×7.0)", 7500),
    ("준비실 (2.9×8.0)", 2900),
    ("실습실 (11.0×8.0)", 11000),
]


# ─────────────────────────────────────────────────────────────
# 1. 구간
# ─────────────────────────────────────────────────────────────
#
# 한 걸음씩 순서대로입니다. 두 종류뿐입니다.
#
#   Stop  멈춰서 말한다        ← 안내의 본체
#   Move  말하고 나서 걷는다   ← 이동. 걷는 동안에는 말하지 않는다
#
# ★ meters 를 반드시 채워야 합니다 ★
#   문서는 이동을 '몇 초'로 적었습니다. 그런데 우리 실측에서 시간 기반
#   이동은 25% 까지 어긋났습니다. 22 m 를 그렇게 가면 5.5 m 가 틀립니다 —
#   302호 앞에서 멘트하려다 303호를 지나칠 거리입니다.
#   그래서 '몇 미터'로 다시 적습니다. 줄자로 재세요.
#   doc_seconds 는 문서의 값이고, 참고용으로만 남겨둡니다.


class Step:
    kind = "?"

    def __init__(self, sid, place, purpose, notes=()):
        self.sid = sid
        self.place = place
        self.purpose = purpose
        self.notes = list(notes)


# ── 동작에 걸리는 시간 (초) ──────────────────────────────────
# 어림값입니다. 실제로 재면 고치세요.
GESTURE_SECONDS = {
    None: 0.0,
    "hello": 4.7,      # 고개 숙여 인사          ★ 실측 2026-09-04 ★
    "sit": 7.0,        # 앉기                    ★ 실측 ★
    "stand": 7.0,      # 일어서기                ★ 실측 ★
    "lie": 6.4,        # 엎드리기 — 안내가 끝났다는 신호   ★ 실측 ★
    "tilt": 1.5,       # 몸통만 기울이기 (Euler) — 아직 안 만들었습니다
}
# ★ 어림값이 전부 절반이었습니다 ★
#   인사 3.0→4.7, 앉기 3.5→7.0, 일어서기 3.5→7.0, 엎드리기 3.5→6.4.
#   guide.py 가 돌면서 재준 값입니다. 시간표를 어림으로 짜면 안 되는 이유가
#   여기 있습니다 — 동작 넷이면 15초가 통째로 빕니다.
#
# ※ 앉기가 7초인 것은 **먼저 일어서기 때문**입니다.
#   Posture.sit() 은 어떤 자세에서 오든 stand() 를 거칩니다. 서 있는데도
#   또 일으켜 세우는 것은 이 기체의 mode 값을 못 믿어서 건너뛰기를
#   막아둔 탓입니다. 높이로 판단하도록 고쳤으니 다음 실행에서는 줄어듭니다.


class Line:
    """정차 지점 안의 한 토막.  멘트 하나 + 그 시작에 맞춰 하는 동작 하나.

    ★ 왜 토막을 내는가 ★
      S1(환영 인사)이 실측 46초였습니다. 문서가 정한 기준의 두 배입니다.
      그런데 **줄이는 것만이 답은 아닙니다.** 46초가 문제인 이유는 길이
      자체가 아니라, 그동안 방문객이 볼 것이 없다는 데 있습니다.
      말을 토막 내고 사이에 동작을 넣으면, 시간은 오히려 조금 늘지만
      보는 사람에게는 훨씬 짧게 느껴집니다.

      그래서 판정 기준도 바뀝니다. **한 지점의 총 길이가 아니라
      한 토막의 길이**를 봅니다. 쉬지 않고 이어지는 말의 덩어리가
      얼마나 큰가 — 그게 실제로 지루함을 만드는 값입니다.

      gesture 는 그 토막이 **시작될 때** 함께 합니다. 끝날 때까지 기다리지
      않습니다 (인사하면서 "안녕하십니까" 를 말해야 자연스럽습니다).
      pause 는 그 토막이 끝나고 쉬는 시간입니다.
    """

    def __init__(self, key, text, gesture=None, pause=0.0, note=None):
        self.key = key
        self.text = text
        self.gesture = gesture
        self.pause = pause
        self.note = note

    def seconds(self):
        secs, _real = _line_seconds(self)
        return secs


class Stop(Step):
    """멈춰서 말하는 지점.

    멘트가 하나면 key/text 를, 토막을 내려면 lines 를 줍니다.
    """
    kind = "정차"

    def __init__(self, sid, place, purpose, key=None, text=None, lines=None,
                 doc_seconds=None, gesture=None, face=None, door_deg=None,
                 notes=()):
        super().__init__(sid, place, purpose, notes)
        # ★ 문을 보려면 복도 방향에서 몇 도 돌아야 하는가 ★
        #   + 가 왼쪽. None 이면 아직 안 쟀습니다.
        #
        #   measure.py 가 기록한 '방향변화' 는 **지점과 지점 사이의 알짜
        #   변화**입니다. 그 안에 '문 쪽으로 돌기' 와 '다시 복도 쪽으로 돌기'
        #   가 섞여 있어서, 문 각도만 따로 뽑을 수 없습니다.
        #
        #   실행기는 이 값이 있어야 합니다.
        #       가운데로 자리 잡기 → door_deg 만큼 돌기 → 라이트 → 멘트
        #       → 라이트 끄기 → 되돌리기 → 출발
        #   다음에 3층 가실 때, 각 문 앞에서 복도 방향으로 세우고
        #   문 정면을 볼 때까지 돌려서 그 각도를 재면 됩니다.
        self.door_deg = door_deg
        if lines:
            self.lines = list(lines)
            self.key = None                    # 토막마다 따로 있습니다
            self.text = " ".join(l.text for l in self.lines)
        else:
            self.lines = [Line(key, text, gesture=gesture)]
            self.key = key
            self.text = text
        self.doc_seconds = doc_seconds
        self.gesture = gesture    # 토막이 하나일 때의 동작
        self.face = face          # "visitor" 방문객 쪽 | "door" 문 쪽


class Move(Step):
    """예고 멘트를 재생하고 나서 걷는 구간."""
    kind = "이동"

    def __init__(self, sid, place, purpose, key, text,
                 meters=None, doc_seconds=None, turn_deg=0.0,
                 reposition=False, narrow=False, notes=()):
        super().__init__(sid, place, purpose, notes)
        self.key = key
        self.text = text
        self.meters = meters      # 실측 (m)
        self.doc_seconds = doc_seconds
        self.turn_deg = turn_deg  # 출발 전 돌아야 하는 각도 (+ 가 왼쪽)
        # ★ 좁은 통로 구간 ★
        # 문틀처럼 옆이 빠듯한 곳. 여기서는 옆 안전장치를 그대로 두면
        # 스스로 멈춰버립니다. 대신 좌우를 보며 가운데를 맞춰 지나갑니다.
        # (304호 문: 통로 0.70m, 몸통 0.31m → 양옆 0.19m)
        self.narrow = narrow

        # 짧게 자리만 고쳐 잡는 구간. 예고 멘트가 없어도 됩니다.
        # (문서 원칙은 "출발 전 반드시 예고" 인데, 한 걸음 물러나 방문객을
        #  마주보는 것까지 예고하면 오히려 어색합니다)
        self.reposition = reposition


SCENARIO = [
    Stop(
        "S1", "3층 엘리베이터 홀", "환영 인사 및 학과 소개",
        doc_seconds=30, face="visitor",
        lines=[
            # 문서 §2: "인사 동작은 멘트 첫 문장과 동기화한다"
            Line("s1a_greet", gesture="hello", pause=0.5, text=(
                "안녕하십니까. 저는 AI응용소프트웨어과 안내를 맡은 로봇입니다. "
                "저희 학과를 방문해 주셔서 진심으로 감사합니다."
            )),
            # 여기서 앉습니다. 서서 40초를 떠드는 것보다, 자리를 잡고
            # 이야기하는 편이 자연스럽고 볼 것도 생깁니다.
            Line("s1b_intro", gesture="sit", pause=0.3, text=(
                "지금부터 AI응용소프트웨어과를 안내해 드리겠습니다. "
                "저희 학과는 인공지능과 데이터 분석, 그리고 응용 소프트웨어 개발을 "
                "함께 배우는 학과입니다."
            )),
            # 앉은 채로 이어갑니다
            Line("s1c_program", pause=0.3, text=(
                "한 해에 두 개의 하이테크 과정을 운영하며, 전공 기초부터 인공지능 응용, "
                "그리고 현장 중심 프로젝트로 이어지는 교육과정을 진행하고 있습니다."
            )),
            # 일어서면서 "따라오세요" — 동작이 말을 예고합니다
            Line("s1d_lead", gesture="stand", text=(
                "오늘은 저희 학과의 강의실과 프로젝트실을 차례로 안내해 드리겠습니다. "
                "제 뒤를 따라 천천히 이동해 주시기 바랍니다."
            )),
        ],
        notes=[
            "★ 원문 그대로입니다. 글자는 하나도 안 바꿨습니다 ★ "
            "한 덩어리 46초를 네 토막으로 나누고 사이에 동작을 넣었을 뿐입니다.",
            "일어서는 동작이 '따라오세요' 를 예고합니다. 말보다 동작이 먼저 "
            "읽히므로, 방문객이 출발 준비를 할 시간이 생깁니다.",
            "방문객이 여러 명일 경우, 인원이 모두 모인 것을 확인한 뒤 발화를 시작한다.",
            "앉기→일어서기 뒤에 바로 걷는 것은 실측으로 확인했습니다 "
            "(StopMove 를 먼저 보내는 것이 핵심 — README 참고).",
        ],
    ),
    Move(
        "M1", "홀 → 301호 앞", "이동 예고 후 저속 주행",
        key="m1_to_301",
        meters=3.06, doc_seconds=25, turn_deg=-167,
        text=("지금부터 301호 강의실로 이동하겠습니다. "
              "통로가 좁으니 한 줄로 천천히 따라와 주시기 바랍니다."),
        notes=[
            "이동 중에는 발화하지 않는다. 보행 소음으로 전달력이 크게 떨어진다.",
            "방문객이 뒤처지면 정지하고 '잠시 기다리겠습니다.' 재생 후 재출발.",
        ],
    ),
    Stop(
        "S2", "301호 강의실 앞", "301호 소개 (대표 강의실 / 전반기 과정)",
        key="s2_room301",
        doc_seconds=20, face="door", door_deg=+130,
        text=(
            "여기는 301호 강의실입니다. AI응용소프트웨어과 대표 강의실입니다. "
            "이곳에서는 하이테크 과정 학생들이 전공 기초 과목을 배웁니다. "
            "프로그래밍 기초, 머신비전, 클라우드, AI 모델링과 같은 기초 과목이 "
            "이 강의실에서 진행됩니다."
        ),
        notes=[
            "문이 열려 있으면 내부가 보이도록 30도 정도 비켜서 정차한다.",
            "수업 중일 경우 TTS 음량을 한 단계 낮춘다 (권장 60% → 45%).",
            "과목명 나열 시 쉼표에서 0.3초 휴지.",
        ],
    ),
    Move(
        "M2", "301호 → 303호", "이동",
        key="m2_to_303",
        meters=9.66, doc_seconds=15, turn_deg=-138,
        text="이어서 303호 강의실로 이동하겠습니다.",
        notes=["코스에서 가장 긴 구간입니다. 주행거리계가 흐르면 여기서 가장 크게 틀립니다."],
    ),
    Stop(
        "S3", "303호 강의실 앞", "303호 소개 (후반기 과정)",
        key="s3_room303",
        doc_seconds=15, face="door", door_deg=+129,
        text=(
            "여기는 303호 강의실입니다. "
            "AI응용소프트웨어과는 한 해에 두 과정의 하이테크 과정을 운영하는데, "
            "후반기에 입학한 학생들이 학습하는 강의실입니다. "
            "이 강의실의 교과 과정은 전반기 과정과 동일합니다."
        ),
        notes=[
            "★ 문서 원문은 '302호' 였습니다. 302호는 이 층에 없습니다 — "
            "역할(후반기 하이테크 과정 강의실)은 그대로 두고 호실만 303호로 "
            "옮겼습니다.",
            "'전반기 과정과 동일합니다'는 301호 설명을 전제로 한다. "
            "301호를 건너뛰면 이 구간도 함께 조정해야 한다.",
            "'운영하는데,' 뒤에 0.4초 휴지.",
        ],
    ),
    Move(
        "M3", "303호 → 304호", "이동",
        key="m3_to_304",
        meters=1.19, doc_seconds=15, turn_deg=-127,
        text="다음은 304호 프로젝트실입니다. 이쪽으로 이동하겠습니다.",
    ),
    Stop(
        "S4", "304호 문 앞 (복도)", "프로젝트실 소개 — 들어가기 전에",
        key="s4_room304",
        doc_seconds=25, face="door", door_deg=-72,
        text=(
            "여기는 304호 프로젝트실입니다. "
            "학생들이 여러 가지 프로젝트를 진행하기 위해 토의하고 작업하는 공간입니다. "
            "수업에서 배운 내용을 실제 결과물로 완성하는 곳으로, "
            "졸업작품과 각종 공모전 출품작이 이곳에서 만들어집니다. "
            "학생들은 기획과 설계, 개발, 그리고 발표까지 전 과정을 "
            "팀 단위로 직접 경험하게 됩니다."
        ),
        notes=[
            "★ 문서 원문은 '303호' 였습니다. 302호가 없어 한 칸씩 밀렸습니다 — "
            "역할(학생 프로젝트 공간)은 그대로 두고 호실만 304호로 옮겼습니다.",
            "내부에 학생이 작업 중이면 문 앞에서 멈추고 입장은 하지 않는다.",
            "선택 멘트 s4_extra 는 학생 개발 결과물임을 강조할 때만 재생.",
        ],
    ),
    Move(
        "M4", "304호 문 통과", "문틀을 지나 방 안으로",
        key="m4_enter",
        meters=1.07, turn_deg=0.0, narrow=True,
        text="안으로 들어가 보겠습니다.",     # ★ 문구 미확정 — 문서에 없는 새 멘트
        notes=[
            "★ 코스에서 가장 위험한 구간입니다 ★",
            "통로 0.70 m, 몸통 0.31 m → 양옆 0.19 m 씩. 지나갈 수는 있지만 "
            "**돌 수는 없습니다** (회전에 사방 0.48 m 필요). "
            "실제로 로봇 자신이 문틀에서 큰 회전을 거부했습니다.",
            "그래서 방향은 **복도에서 미리** 잡습니다 (S4 의 door_deg).",
            "그리고 여기서는 주행거리계를 쓰지 않습니다. 누적 오차가 0.4~0.9 m "
            "인데 여유가 0.19 m 입니다. 대신 좌우를 보며 가운데를 맞춰 갑니다 — "
            "문틀은 양쪽이 다 보이므로 그 방법이 잘 맞습니다.",
            "옆 안전장치(0.35 m)를 그대로 두면 문틀에서 스스로 멈춥니다. "
            "이 구간만 예외로 하되, 가운데 맞추기가 그 자리를 대신합니다.",
            "★ 멘트 문구가 아직 확정이 아닙니다 ★ 문서에 없는 새 문장입니다. "
            "코스가 복도에서 끝나지 않고 방 안으로 들어가게 바뀌면서 필요해졌습니다.",
        ],
    ),
    Move(
        "M5", "304호 안으로", "방 안 마무리 자리까지",
        key="m5_inside",
        meters=3.58, turn_deg=+166, reposition=True,
        text="",
        notes=[
            "실측: 문틀에서 3.58 m, 방향 +166도 (방문객을 마주보려고 돌아섬).",
            "★ 어디서 도는지가 미정입니다 ★ 마무리 자리(304_안)는 좌우합 0.85 m "
            "= 가운데로 서도 0.42 m 라 **거기서는 못 돕니다** (0.48 m 필요). "
            "실측 때는 오는 도중 넓은 데서 돈 것으로 보입니다. "
            "다음에 갈 때 '어디서 돌 수 있는지' 를 따로 찾아 표시해야 합니다.",
        ],
    ),
    Stop(
        "S5", "304호 안", "마무리 인사 및 배웅",
        doc_seconds=20, face="visitor",
        lines=[
            # 방문객 쪽으로 도는 것은 앞의 M4 가 합니다 (실측 -127도)
            Line("s5a_close", pause=0.3, text=(
                "이상으로 AI응용소프트웨어과 안내를 마치겠습니다."
            )),
            Line("s5b_program", gesture="sit", pause=0.3, text=(
                "저희 학과는 전공 기초부터 인공지능 응용, 그리고 현장 중심 "
                "프로젝트로 이어지는 교육과정을 한 해 두 차례의 하이테크 과정으로 "
                "운영하고 있습니다."
            )),
            Line("s5c_thanks", gesture="stand", pause=0.3, text=(
                "오늘 방문해 주셔서 다시 한번 감사드립니다."
            )),
            # 문서 §2: "인사 동작은 마지막 '감사합니다'에 맞춰 실행한다"
            Line("s5d_bye", gesture="hello", pause=5.0, text=(
                "남은 일정도 편안하게 보내시기 바랍니다. 감사합니다."
            )),
            # ★ 말 없는 토막 ★ 동작만 합니다.
            # 앞 토막의 pause 5초가 문서의 "복귀 전 5초간 정지" 입니다.
            # 질문이 나올 수 있는 시간을 두고 나서 엎드립니다.
            Line("s5e_rest", "", gesture="lie",
                 note="엎드리는 것이 '안내가 끝났다' 는 가장 분명한 신호입니다"),
        ],
        notes=[
            "★ 원문 그대로입니다. 자르고 동작을 넣었을 뿐입니다 ★",
            "앉기 → 일어서기 → 인사 → 엎드리기. 마지막 인사가 '감사합니다'와 "
            "겹칩니다 (문서 §2 요구).",
            "엎드리기 전 5초는 문서의 '질문이 이어질 수 있으므로 복귀 전 "
            "5초간 정지'. 엎드린 뒤에도 말은 할 수 있으니 질의응답은 계속됩니다.",
        ],
    ),
]


# ── 선택 멘트 ────────────────────────────────────────────────
OPTIONAL = {
    "s4_extra": "제가 수행하는 안내 프로그램도 이 프로젝트실에서 "
                "학생들이 직접 개발한 것입니다.",
}

# ── S1 이 길 때 쓸 대안 ──────────────────────────────────────
# 문서의 15~25초 기준을 S1 만 두 배 가까이 넘깁니다. 뒤의 두 문장은
# S5 에서 거의 같은 내용이 반복되므로, 옮기면 기준 안에 들어옵니다.
# ★ 원문을 대신 쓰지는 않습니다. 쓸지 말지는 사람이 정합니다. ★
S1_SHORT = (
    "안녕하십니까. 저는 AI응용소프트웨어과 안내를 맡은 로봇입니다. "
    "저희 학과를 방문해 주셔서 진심으로 감사합니다. "
    "저희 학과는 인공지능과 데이터 분석, 그리고 응용 소프트웨어 개발을 "
    "함께 배우는 학과입니다. "
    "오늘은 저희 학과의 강의실과 프로젝트실을 차례로 안내해 드리겠습니다. "
    "제 뒤를 따라 천천히 이동해 주시기 바랍니다."
)


# ─────────────────────────────────────────────────────────────
# 2. 예외 상황  (문서 §4)
# ─────────────────────────────────────────────────────────────
#
# key, 상황, 멘트, 동작
#
# ★ 이름 앞에 alert_ 를 붙입니다 ★
#   처음에는 그냥 excuse_me 였는데, config.PHRASES 에 **같은 이름의 다른
#   문장**이 있었습니다. 키가 곧 파일 이름이고 파일 이름이 곧 로봇에
#   올라가는 이름이라, 둘이 서로를 덮어씁니다. 실제로 한 번 당했습니다 —
#   문서의 새 문장을 넣었는데 옛날 파일이 그대로 쓰였고, 로그에는
#   아무 문제 없이 찍혔습니다.
#
#   로봇이 엉뚱한 문장을 말하면서 정상으로 보이는 것이 제일 나쁩니다.
#   층이 늘고 코스가 늘면 이런 충돌은 더 자주 생깁니다. 이름 공간을
#   나눠두면 애초에 안 부딪힙니다.
EXCEPTIONS = {
    "alert_excuse_me": (
        "경로에 사람이 서 있음",
        "잠시 지나가겠습니다. 조금만 비켜 주시면 감사하겠습니다.",
        "3초 대기 후 재시도.  ★ 문서의 '우회 주행' 은 이 복도에서 불가능합니다 ★",
    ),
    "alert_please_wait": (
        "방문객이 뒤처짐",
        "잠시 기다리겠습니다.",
        "정지 후 최대 15초 대기. 판단은 운영자가 합니다.",
    ),
    "alert_blocked": (
        "장애물로 경로 차단",
        "경로에 장애물이 있어 잠시 멈추겠습니다. 담당자를 불러 주시기 바랍니다.",
        "정지. 운영자에게 알립니다.",
    ),
    "alert_keep_back": (
        "방문객이 만지려 함",
        "안전을 위해 조금만 떨어져서 봐 주시기 바랍니다.",
        "동작 일시 정지.",
    ),
    "alert_low_battery": (
        "배터리 부족 (20% 이하)",
        "안내를 마치고 충전 위치로 돌아가겠습니다.",
        "마무리 멘트로 건너뛰고 종료.",
    ),
}


# ─────────────────────────────────────────────────────────────
# 3. TTS 발음 교정  (문서 §5)
# ─────────────────────────────────────────────────────────────
#
# 순서가 중요합니다. 긴 것부터 바꿔야 짧은 것이 안쪽을 깨뜨리지 않습니다.
# (예: "AI" 를 먼저 바꾸면 "AI응용소프트웨어과" 규칙이 영영 안 걸립니다)
TTS_FIXES = [
    ("AI응용소프트웨어과", "에이아이 응용 소프트웨어과"),
    ("AI 모델링", "에이아이 모델링"),
    ("AI", "에이아이"),
    ("301호", "삼백일 호"),
    ("302호", "삼백이 호"),     # 이 층에 없지만, 남겨둡니다 (다른 층에서 쓸 수 있음)
    ("303호", "삼백삼 호"),
    ("304호", "삼백사 호"),
]


def for_tts(text):
    """TTS 에 넣기 좋게 발음을 고칩니다."""
    for a, b in TTS_FIXES:
        text = text.replace(a, b)
    return text


# ─────────────────────────────────────────────────────────────
# 4. 부록 — 멘트가 근거로 삼는 교육과정  (문서 부록)
# ─────────────────────────────────────────────────────────────
#
# ★ 실제 교육과정과 다르면 여기를 먼저 고치고, 그 다음 멘트를 고치세요 ★
# ─────────────────────────────────────────────────────────────
# 4-2. 정차 지점 실측  (measure.py, 2026-09-03)
# ─────────────────────────────────────────────────────────────
#
# 실제 코스대로 로봇을 몰면서 지점마다 기록한 값입니다.
#   왼 / 오른 / 앞 — 로봇 기준 여유 (m). None 은 못 잰 것(트였거나 유리).
#
# ★ 여기서 보는 것은 '합' 이 아니라 '가장 좁은 쪽' 입니다 ★
#   로봇은 자기 중심으로 돕니다. 왼 0.38 / 오른 1.76 은 합이 2.14 라
#   널찍해 보여도, 돌면 왼쪽 벽에 닿습니다.
CLEARANCE = {
    # sid:  (왼, 오른, 앞)      2026-09-04 실측
    "S1": (0.69, None, None),     # 엘리베이터 홀 — 한쪽이 트여 폭을 못 쟀습니다
    "S2": (0.71, 0.72, None),     # 301호 앞 — 폭 1.43 m
    "S3": (0.70, 1.20, None),     # 303호 앞 — 폭 1.90 m
    "S4": (0.64, 0.89, None),     # 304호 문 앞 — 폭 1.53 m
    "M4": (0.37, 0.33, None),     # ★ 문틀 — 폭 0.70 m. 통과는 되나 회전 불가 ★
    "S5": (0.38, 0.47, None),     # 304호 안 — 폭 0.85 m. 여기서도 회전 불가
}

# ★ '앞' 값을 일부러 비워 두었습니다 ★
#   그날의 앞 숫자들은 **못 믿습니다.** 그때 clearance 계산이 로봇 중심에서
#   10cm 앞이면 전부 '앞' 으로 셌고, 그 바람에 어깨 옆에 붙은 문틀 기둥이
#   '정면 0.11 m' 로 보고됐습니다. 지금은 코앞부터 보도록 고쳤지만,
#   고치기 **전에** 받은 값이라 그대로 옮기면 안 됩니다.
#   다음에 갈 때 다시 재서 채웁니다.

# ── 주행거리계가 얼마나 흐르는가 (2026-09-04 폐합오차) ──────────
#
#   출발점에 테이프를 붙이고 코스를 돈 뒤 그 자리로 돌아와 다시 찍었습니다.
#   주행거리계가 정확하다면 두 좌표가 같아야 합니다. 다른 만큼이 오차입니다.
#   ★ 절대 길이를 몰라도 오차를 알 수 있습니다 — 줄자가 필요 없습니다 ★
ODOMETRY = {
    "표시 거리": 35.45,      # m — 표시 지점들을 이은 직선의 합
    "어긋남": 1.66,          # m — 출발점으로 돌아왔을 때
    "오차율": 0.047,         # 4.7%
}
# ※ 이 4.7% 는 **최악으로 잡은 값**입니다. 그날 조종이 서툴러 헛걸음이
#   있었는데, 오차는 실제로 걸은 거리만큼 쌓이므로 실제 경로가 길수록
#   진짜 오차율은 낮습니다. 깔끔하게 몰면 3% 안쪽일 것입니다.
#
# ★ 그래도 문은 못 지납니다 ★
#   304호 도착까지 18.6 m → 가장 낙관적인 2% 로 봐도 누적 0.37 m.
#   문틀 여유는 양옆 0.19 m 씩입니다. 오차가 여유의 두 배입니다.
#   → 문 통과는 주행거리계가 아니라 **좌우를 보며 가운데 맞추기**로 합니다.

# 제자리에서 돌려면 사방으로 이만큼 (m).
#   몸통 0.70 × 0.31 → 중심에서 모서리까지 0.383. 여유 0.10 을 더합니다.
TURN_RADIUS = 0.383
TURN_NEED = TURN_RADIUS + 0.10

# 앞으로 출발하려면 이만큼은 비어야 합니다 (m). avoid_test 의 GUARD_FRONT.
START_NEED = 0.90


def narrowest(sid):
    """그 지점에서 가장 좁은 쪽 (m). 못 재면 None.

    ※ 이 값은 **그날 어디에 세웠는지**에 달렸습니다. 복도의 성질이 아닙니다.
    """
    seen = [d for d in CLEARANCE.get(sid, ()) if d is not None]
    return min(seen) if seen else None


def corridor_half(sid):
    """복도 가운데에 섰을 때의 좌우 여유 (m). 못 재면 None.

    ★ 이쪽이 복도의 성질입니다 ★
    왼·오른 각각은 세운 자리에 따라 달라지지만, 둘의 합은 복도 폭이라
    어디에 세우든 같습니다. 그래서 '여기서 돌 수 있는가' 는 합의 절반으로
    판단합니다.

    실제로 이걸 헷갈려서 한 번 틀린 결론을 냈습니다 —
    왼 0.38 / 오른 1.76 을 보고 "회전 불가" 라고 했는데,
    복도는 2.14 m 였고 로봇이 한쪽 벽에 붙어 있었을 뿐입니다.
    """
    left, right = CLEARANCE.get(sid, (None, None, None))[:2]
    if left is None or right is None:
        return None
    return (left + right) / 2


CURRICULUM = [
    ("하이테크 과정 (전반기)", "전반기 입학", "301호 강의실",
     "프로그래밍 기초, 머신비전, 클라우드, AI 모델링"),
    ("하이테크 과정 (후반기)", "후반기 입학", "302호 강의실",
     "전반기 과정과 동일"),
    ("프로젝트 실습", "전 과정 공통", "303호 프로젝트실",
     "팀 프로젝트, 졸업작품, 공모전 출품작"),
]


# ─────────────────────────────────────────────────────────────
# 5. 문서의 가정 vs 우리가 실제로 잰 것
# ─────────────────────────────────────────────────────────────
#
# ★ 이 표가 이 파일에서 가장 중요합니다 ★
#   문서는 잘 쓰였지만, 몇 가지는 이 기체와 이 건물에서 성립하지 않습니다.
#   그걸 조용히 지우면 나중에 현장에서 발견하게 됩니다. 남겨둡니다.
#
#   (문서의 요구, 실제, 그래서 어떻게)
REALITY = [
    ("전방 장애물 감지 시 즉시 정지",
     "로봇 내장 회피는 동작하지 않음. SwitchAvoidMode 가 코드 0 을 주지만 "
     "1.38m→0.89m 로 들어오는 동안 느려지지도 비켜가지도 않음 (실측)",
     "우리 라이다(perception.Eyes)로 직접 봅니다. 실험에서 0.89m 에 잡혔습니다."),

    ("'301호 문 앞 마커(또는 좌표) 도달' 을 트리거로",
     "마커도 지도도 없음. 시간 기반 이동은 25% 어긋남 → 22m 에서 5.5m 오차",
     "rt/utlidar/robot_pose 로 '몇 미터 갔는지'를 보고 멈춥니다. "
     "그 전 단계로는 운영자가 다음 구간을 눌러 진행합니다."),

    ("전방 3m 이내 사람 2초 이상 지속 감지 시 시작",
     "라이다는 '뭔가 있다'만 앎. 사람과 사물함을 구분 못 함",
     "운영자 수동 시작을 1순위로. 문서에도 대안으로 적혀 있습니다."),

    ("후방 추종 대상 3m 이상 이탈 감지",
     "특정인을 추적하는 기능 없음",
     "운영자가 눈으로 보고 '잠시 기다리겠습니다'를 누릅니다."),

    ("사람이 서 있으면 3초 대기 후 우회 주행",
     "복도 폭 1.15m (로봇 높이 실측). 로봇 0.31m, 양옆 0.42m 씩 — "
     "사람 옆을 지나갈 수 없음",
     "멘트는 그대로. 동작은 '기다리기'로. 우회는 뺍니다."),

    ("S6 충전 거치대 자율 복귀",
     "도킹 기능 없음. 공용 장비",
     "사람이 들고 갑니다 (park.py / carry.py)."),

    ("헤드로 문 지시 / 헤드 LED 점멸",
     "Go2 는 머리가 몸통에 고정. LED 제어는 미확인",
     "몸통을 문 쪽으로 돌려 가리킵니다. LED 는 나중에."),

    ("(도면) 방 구획으로 정차 지점을 정한다",
     "도면은 계획도. 현장 대조 결과 302호가 도면에 없음 — 301호나 303호에 "
     "합쳐진 것으로 보임. 유리문 배치도 실제와 다름",
     "★ 방 단위로는 도면을 쓰지 않습니다 ★  정차 지점 거리는 줄자로 잽니다. "
     "도면에서 가져오는 것은 복도의 뼈대뿐입니다 (MEASURE.md)."),

    ("(도면) 복도 폭 2,200 mm",
     "로봇 높이(0.05~0.6m)에서 실측 1,150 mm — 도면보다 1,050 mm 좁음",
     "차이는 긴 의자와 사물함입니다. 도면이 아니라 실측으로 다닙니다. "
     "치울 수 있으면 폭이 두 배가 됩니다 — 운영 체크리스트의 '복도 장애물 정리'."),

    ("(도면) 복도 양쪽이 유리벽",
     "도면 범례의 하늘색 = 유리벽. 복도를 따라 거의 전 구간. "
     "눈높이(0.6~1.6m) 실측 폭이 3.13 m 로 도면 2.20 m 보다 0.93 m 넓게 나옴",
     "★ 라이다는 유리를 제대로 못 봅니다 ★  눈높이 폭 측정값은 믿지 않습니다. "
     "우리가 다니는 판단은 0.05~0.6 m 구간(단단한 의자·사물함)만 씁니다."),

    ("(도면) 복도 동쪽 끝은 막다른 곳 — 창문",
     "도면상 복도가 외벽에서 끝남. 사진에서도 정면 끝에 창문",
     "안내 마지막 지점이 유리를 향합니다. 마지막 구간은 거리를 짧게 잡고, "
     "끝에서 회전할 때 특히 조심합니다. 여기서는 라이다를 믿지 않습니다."),

    ("(도면) 엘리베이터 홀과 복도 사이에 자동문",
     "도면 주기: '석고벽 신설 후 자동문 설치'",
     "S1(홀)에서 M1(복도)로 넘어갈 때 문을 지납니다. 문이 열려 있는 동안 "
     "지나가야 하고, 문틀은 폭이 더 좁습니다. 이 구간만 사람이 데리고 넘어가는 "
     "편이 안전할 수 있습니다."),

    ("정차 지점 멘트 15~25초",
     "S1 은 227자 — 추정 46초. 문서 스스로 정한 기준의 두 배",
     "S1_SHORT 를 준비해 뒀습니다. 쓸지는 사람이 정합니다."),
]


# ─────────────────────────────────────────────────────────────
# 6. 계산
# ─────────────────────────────────────────────────────────────

# 한국어 TTS 대략 초당 글자 수 (공백 제외).
#   ★ 어림값입니다 ★ 실제 mp3 를 만들어 재보면 정확합니다.
#   그 전까지는 '문서의 표가 맞는지' 를 의심하는 용도로만 쓰세요.
CHARS_PER_SECOND = 5.5
COMMA_PAUSE = 0.3
PERIOD_PAUSE = 0.45


def estimate_seconds(text):
    """멘트를 읽는 데 걸리는 대략적인 시간 (초)."""
    n = len(text.replace(" ", ""))
    return n / CHARS_PER_SECOND + text.count(",") * COMMA_PAUSE \
        + text.count(".") * PERIOD_PAUSE


_MEASURED = None


def measured():
    """voices.py 가 실제로 재둔 길이 {key: 초}. 없으면 빈 사전.

    ★ 있으면 추정보다 이쪽을 씁니다 ★
    어림값으로 "25초를 넘었다/아니다" 를 따지는 건 의미가 없습니다.
    파일을 만들어 재본 값이 있으면 그걸 봐야 합니다.
    """
    global _MEASURED
    if _MEASURED is None:
        _MEASURED = {}
        try:
            import json
            from pathlib import Path
            import config
            p = Path(config.AUDIO_DIR) / "durations.json"
            if p.exists():
                _MEASURED = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _MEASURED


def _line_seconds(line):
    """토막 하나의 멘트 길이 (초)와 그것이 실측인지. 동작·쉼은 뺀 값."""
    m = measured().get(line.key)
    if m is not None:
        return float(m), True
    return estimate_seconds(line.text), False


def seconds_for(step):
    """이 구간에 걸리는 시간 (초)와 그것이 실측인지. (초, 실측여부)

    ★ 멘트만이 아니라 동작과 쉼까지 더합니다 ★
    토막을 내고 동작을 넣으면 총 시간은 오히려 늘어납니다. 그걸 숨기면
    안 됩니다. 대신 '한 토막의 길이' 를 따로 봅니다 (longest_line).
    """
    lines = getattr(step, "lines", None)
    if not lines:
        m = measured().get(step.key)
        if m is not None:
            return float(m), True
        return estimate_seconds(step.text), False

    total = 0.0
    all_real = True
    for l in lines:
        secs, real = _line_seconds(l)
        total += secs + l.pause + GESTURE_SECONDS.get(l.gesture, 0.0)
        all_real = all_real and real
    return total, all_real


def longest_line(step):
    """쉬지 않고 이어지는 말의 최대 덩어리 (초, 토막). 없으면 (0, None).

    ★ 지루함을 만드는 건 지점의 총 길이가 아니라 이 값입니다 ★
    """
    lines = getattr(step, "lines", None) or []
    best, who = 0.0, None
    for l in lines:
        secs, _real = _line_seconds(l)
        if secs > best:
            best, who = secs, l
    return best, who


def find(key):
    """이 오디오 키가 어느 구간의 어느 토막인지. (구간, 토막) 또는 (None, None)."""
    for s in SCENARIO:
        for l in getattr(s, "lines", None) or []:
            if l.key == key:
                return s, l
        if getattr(s, "key", None) == key:
            return s, None
    return None, None


def ordered_keys():
    """음성을 만들 순서대로의 키 목록 (코스 순, 토막 순)."""
    out = []
    for s in SCENARIO:
        for l in getattr(s, "lines", None) or []:
            if l.text.strip():
                out.append(l.key)
        if not getattr(s, "lines", None) and s.text.strip():
            out.append(s.key)
    return out


def phrases():
    """key → 멘트.  TTS 로 만들 것 전부입니다."""
    out = {}
    for s in SCENARIO:
        lines = getattr(s, "lines", None)
        if lines:
            for l in lines:
                if l.text.strip():
                    out[l.key] = l.text
        elif s.text.strip():        # M4 처럼 말 없는 구간은 음성도 없습니다
            out[s.key] = s.text
    out.update(OPTIONAL)
    for key, (_situation, text, _action) in EXCEPTIONS.items():
        out[key] = text
    return out


def stops():
    return [s for s in SCENARIO if isinstance(s, Stop)]


def moves():
    return [s for s in SCENARIO if isinstance(s, Move)]


def unmeasured():
    """아직 줄자로 재지 않은 이동 구간."""
    return [m for m in moves() if m.meters is None]


def total_distance():
    """실제로 걷는 총 거리 (m). 하나라도 안 재었으면 None."""
    if unmeasured():
        return None
    return sum(m.meters for m in moves())


# ─────────────────────────────────────────────────────────────
# 7. 점검
# ─────────────────────────────────────────────────────────────

def check(verbose=True):
    """시나리오가 스스로 앞뒤가 맞는지 봅니다. 돌려주는 값: 문제 목록."""
    problems = []

    # ★ 보는 것은 '한 토막' 입니다 ★
    #   지점의 총 길이가 아니라, 쉬지 않고 이어지는 말의 덩어리를 봅니다.
    #   동작을 사이에 넣어 나눈 지점은 총 길이가 오히려 늘지만, 방문객이
    #   느끼는 지루함은 덩어리 크기가 만듭니다.
    for s in stops():
        chunk, line = longest_line(s)
        if chunk > MENT_MAX_SECONDS:
            _secs, real = _line_seconds(line)
            how = "실측" if real else "추정"
            where = f" ({line.key})" if len(s.lines) > 1 else ""
            problems.append(
                f"{s.sid} 에 쉬지 않고 이어지는 말이 깁니다{where} — "
                f"{how} {chunk:.0f}초 (기준 {MENT_MAX_SECONDS:.0f}초). "
                f"토막을 나누고 사이에 동작을 넣으면 됩니다")

    missing = unmeasured()
    if missing:
        problems.append(
            "이동 거리가 비어 있습니다: "
            + ", ".join(m.sid for m in missing)
            + "  → 줄자로 재서 scenario.py 의 meters 에 적으세요")

    keys = ordered_keys() + list(OPTIONAL) + list(EXCEPTIONS)
    dup = {k for k in keys if keys.count(k) > 1}
    if dup:
        problems.append(f"오디오 파일 이름이 겹칩니다: {sorted(dup)}")
    bad = [k for k in keys if not k.replace("_", "").isalnum() or not k.isascii()]
    if bad:
        problems.append(f"오디오 파일 이름에 영문/숫자/밑줄만 쓰세요: {bad}")

    # ★ 다른 곳의 멘트와 이름이 겹치면 안 됩니다 ★
    # 키가 곧 파일 이름이고, 파일 이름이 곧 로봇에 올라가는 이름입니다.
    # 겹치면 서로 덮어쓰고, 로봇이 엉뚱한 문장을 말하면서 로그는 정상입니다.
    try:
        import config as _c
        mine = phrases()
        clash = [k for k in mine
                 if k in _c.PHRASES and _c.PHRASES[k] != mine[k]]
        if clash:
            problems.append(
                f"config.PHRASES 에 같은 이름의 다른 문장이 있습니다: {clash}. "
                f"한쪽 이름을 바꾸세요 — 파일이 서로 덮어씁니다")
    except Exception:
        pass

    # 문서 원칙: 출발 전에는 반드시 예고 멘트
    for m in moves():
        if not m.text.strip() and not m.reposition:
            problems.append(f"{m.sid} 에 이동 예고 멘트가 없습니다")

    # ── 실측이 말해주는 것 ──
    #
    # ★ 복도 폭만 씁니다. 왼·오른 각각은 안 씁니다 ★
    #   실측은 리모컨으로 몰면서 세운 자리에서 잰 것이라, 한쪽에 치우쳐
    #   섰으면 그쪽이 좁게 나옵니다. 그건 복도의 성질이 아니라 그날의
    #   주차 위치입니다. 반면 **합(복도 폭)은 어디에 세우든 같습니다.**
    #   그래서 판정은 '가운데로 섰을 때' 를 기준으로 합니다.
    # 문을 보고 서야 하는데 몇 도 돌아야 하는지 모르는 지점
    blind = [s.sid for s in stops() if s.face == "door" and s.door_deg is None]
    if blind:
        problems.append(
            f"문 쪽으로 몇 도 돌아야 하는지 모릅니다: {', '.join(blind)}. "
            f"각 문 앞에서 복도 방향으로 세운 뒤 문 정면까지 돌려 재세요 "
            f"(measure.py 의 '방향변화' 에는 이 값이 섞여 있어 못 뽑습니다)")

    # 좁아서 못 도는 곳은 문 쪽이든 아니든 알려줍니다.
    # (S5 는 방문객을 마주봐야 하는데, 방 안이 0.42 m 라 그 자리에서는 못 돕니다)
    for s in SCENARIO:
        half = corridor_half(s.sid)
        if half is not None and half < TURN_NEED \
                and getattr(s, "face", None) != "door":
            problems.append(
                f"{s.sid}({s.place}) 에서는 제자리 회전이 안 됩니다 — "
                f"가운데로 서도 {half:.2f} m (필요 {TURN_NEED:.2f} m). "
                f"방향은 그 자리에 닿기 **전에** 잡아야 합니다")

    for s in stops():
        half = corridor_half(s.sid)
        if half is None or s.face != "door":
            continue
        if half < TURN_NEED:
            problems.append(
                f"{s.sid}({s.place}) 는 복도가 좁아 제자리 회전이 어렵습니다 — "
                f"가운데로 서도 {half:.2f} m (필요 {TURN_NEED:.2f} m). "
                f"발을 돌리지 말고 몸통만 기울여 가리키세요")

    # 정면은 세운 자리에 달린 값이라 '문제' 가 아니라 '주의' 로만 남깁니다.
    # (문을 가리키려고 바짝 붙였을 수 있습니다)

    if verbose:
        print()
        if problems:
            print(" 점검 — 손볼 곳 %d 군데" % len(problems))
            for p in problems:
                print(f"   ★ {p}")
        else:
            print(" 점검 — 이상 없습니다.")
    return problems


def timetable():
    print("=" * 70)
    print(f" {TITLE}")
    print(f" {ROUTE}")
    print("=" * 70)
    any_real = bool(measured())
    head = "실측" if any_real else "추정"
    print(f"{_pad('구간', 6)}{_pad('종류', 6)}{_pad('장소', 24)}"
          f"{_pad(head, 7, right=True)}{_pad('문서', 7, right=True)}"
          f"{_pad('거리', 9, right=True)}")
    print("-" * 70)

    total_est = total_doc = 0.0
    for s in SCENARIO:
        est, real = seconds_for(s)
        doc = s.doc_seconds or 0
        total_est += est + (QA_PAUSE if isinstance(s, Stop) else 0)
        total_doc += doc
        if isinstance(s, Move):
            dist = f"{s.meters:.1f} m" if s.meters is not None else "  미측정"
            # 이동은 멘트 시간이 아니라 걷는 시간이 지배합니다
            if s.meters is not None:
                walk = s.meters / 0.4          # 문서의 0.4 m/s
                total_est += walk
        else:
            dist = "—"
        chunk = longest_line(s)[0] if isinstance(s, Stop) else 0.0
        parts = len(getattr(s, "lines", []) or [])
        mark = "  ←" if chunk > MENT_MAX_SECONDS else ""
        if parts > 1:
            mark += f"  {parts}토막"
        if not real:
            mark += "  (추정)"
        print(f"{_pad(s.sid, 6)}{_pad(s.kind, 6)}{_pad(s.place, 24)}"
              f"{_pad(f'{est:.0f}초', 7, right=True)}"
              f"{_pad(f'{doc:.0f}초', 7, right=True)}"
              f"{_pad(dist, 9, right=True)}{mark}")

    print("-" * 70)
    d = total_distance()
    print(f" 멘트+대기 추정 {total_est:5.0f}초 = {total_est/60:.1f}분"
          f"    (문서 합계 {total_doc:.0f}초)")
    if d is None:
        print(" 총 이동 거리 — 미측정 (문서의 시간으로 역산하면 약 22 m)")
    else:
        print(f" 총 이동 거리 {d:.1f} m  (0.4 m/s 로 {d/0.4:.0f}초)")


def show_building():
    print()
    print("=" * 70)
    print(" 건물 — 도면에서 읽은 것")
    print("=" * 70)
    for k, v in BUILDING.items():
        v = f"{v:.2f} m" if isinstance(v, float) else v
        print(f"   {_pad(k, 12)}{v}")

    print("\n   복도를 따라 늘어선 방 (엘리베이터 쪽부터)")
    for label, side in (("남쪽 (깊이 7.0 m)", FRONTAGE_SOUTH),
                        ("북쪽 (깊이 8.0 m)", FRONTAGE_NORTH)):
        print(f"\n     {label}")
        pos = 0
        for name, mm in side:
            print(f"       {_pad(f'{pos/1000:5.1f} ~ {(pos+mm)/1000:5.1f} m', 20)}"
                  f"{_pad(name, 22)}{mm/1000:.2f} m 폭")
            pos += mm

    print("\n   ★ 위 방 구획은 참고용입니다 — 정차 지점 거리로 쓰지 마세요 ★")
    print("     이 도면은 계획도이고, 현장과 대조해 보니 302호가 도면에 없습니다.")
    print("     (지금의 302호는 301호나 303호 공간에 합쳐져 있는 것으로 보입니다)")
    print("     도면의 '301', '302' 는 계단실 번호이지 강의실이 아닙니다.")
    print("     쓸 수 있는 것은 복도의 뼈대(폭·길이·막다른 끝·자동문)뿐입니다.")


def show_reality():
    print()
    print("=" * 70)
    print(" 문서의 가정 vs 우리가 실제로 잰 것")
    print("=" * 70)
    for want, real, plan in REALITY:
        print(f"\n 요구  {want}")
        print(f" 실제  {real}")
        print(f" 방법  {plan}")


def show_text(tts=False):
    for s in SCENARIO:
        lines = getattr(s, "lines", None) or []
        if not s.text.strip():
            continue
        if len(lines) > 1:
            total, real = seconds_for(s)
            print(f"\n[{s.sid}]  {total:.0f}초 ({'실측' if real else '추정'}) "
                  f"— {len(lines)}토막, 동작 포함")
            for l in lines:
                secs, r = _line_seconds(l)
                act = f"  ⟨{l.gesture}⟩" if l.gesture else ""
                print(f"\n  [{l.key}]  {secs:.0f}초{act}")
                print("  " + (for_tts(l.text) if tts else l.text))
            continue
        t = for_tts(s.text) if tts else s.text
        secs, real = seconds_for(s)
        print(f"\n[{s.sid} / {s.key}]  {secs:.0f}초 ({'실측' if real else '추정'})")
        print(t)
    print("\n── 선택 ──")
    for k, t in OPTIONAL.items():
        print(f"\n[{k}]")
        print(for_tts(t) if tts else t)
    print("\n── 예외 상황 ──")
    for k, (sit, t, act) in EXCEPTIONS.items():
        print(f"\n[{k}]  {sit}")
        print(for_tts(t) if tts else t)
        print(f"  → {act}")


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--tts":
        show_text(tts=True)
        return
    if arg == "--text":
        show_text(tts=False)
        return

    timetable()
    check()
    show_building()
    show_reality()
    print()
    print(" 다음 할 일")
    print("   1. 이동 구간을 줄자로 재서 meters 에 적기")
    print("   2. 멘트 음성 만들고 실제 길이 재기 (추정 대신 실측으로)")
    print("   3. robot_pose 기반 '거리로 걷기' + 라이다 가드")


if __name__ == "__main__":
    main()
