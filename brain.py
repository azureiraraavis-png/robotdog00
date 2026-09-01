# -*- coding: utf-8 -*-
"""
들은 말을 무엇으로 볼지 판단합니다.

두 갈래로만 나눕니다.

  1. 등록된 명령    → 정해진 동작. 항상 받습니다.
  2. 그 밖의 말     → 자유 질의응답. ★ 로봇이 멈춰 있을 때만 ★

이 분리가 이 프로젝트의 안전선입니다.
LLM 이 로봇을 움직이게 하지 않습니다. LLM 은 말만 만듭니다.
움직임은 오직 config.py 의 COMMANDS 에 적힌 것만 나갈 수 있습니다.
"""

import difflib
import re

import config

_CLEAN = re.compile(r"[\s.,!?~…·'\"()\[\]]+")


def normalize(text):
    """비교하기 좋게 다듬습니다. 공백과 문장부호를 없앱니다."""
    return _CLEAN.sub("", (text or "")).lower()


# 로봇을 실제로 움직이는 동작들. 여기에 해당하면 판정을 엄격하게 합니다.
# ("stop" 은 일부러 제외했습니다 — 잘못 멈추는 건 안전한 실패입니다)
LOOSE_ACTIONS = {"none", "stop"}


def _allowed(cleaned, phrase, spec):
    """긴 문장 안에 명령어가 우연히 들어간 경우를 걸러냅니다.

    이게 없으면 "앞으로 계획이 어떻게 되나요?" 라는 질문에
    로봇이 앞으로 걸어갑니다. 사람들 사이에서는 위험한 오작동입니다.

    그래서 몸을 움직이는 명령은 '짧은 발화'일 때만 받습니다.
      "앞으로", "앞으로 가"          → 받습니다
      "앞으로 계획이 어떻게 되나요"    → 무시합니다
    """
    if spec.get("action") in LOOSE_ACTIONS:
        return True
    if len(cleaned) <= len(phrase) + config.COMMAND_EXTRA_CHARS:
        return True
    # 문장 전체가 명령어와 매우 비슷하면 길어도 인정합니다
    return difflib.SequenceMatcher(None, cleaned, phrase).ratio() >= 0.8


def match_command(text):
    """등록된 명령이면 (이름, 정의) 를, 아니면 (None, None) 을 돌려줍니다."""
    name, spec, _, _ = match_detail(text)
    return name, spec


def match_detail(text):
    """match_command 와 같지만 어떻게 맞았는지도 알려줍니다.

    돌려주는 값: (이름, 정의, 방식, 점수)
      방식 = "exact"  문장 안에 등록된 표현이 그대로 들어 있음
             "fuzzy"  비슷해서 추정함 (인식이 뭉개졌을 때 복구되는 경로)
             None     명령이 아님

    추측으로 맞은 것이 잦다면 그 말투를 phrases 에 정식으로 추가하는 게 좋습니다.

    판단 순서
      1) 등록된 표현이 문장 안에 들어 있으면 채택 — "저기, 앉아 볼래?" 도 잡힙니다
      2) 못 찾으면 유사도로 한 번 더 봅니다 — 인식이 살짝 어긋났을 때를 위해
    """
    cleaned = normalize(text)
    if not cleaned:
        return None, None, None, 0.0

    # 1) 포함 관계 — 긴 표현부터 봐야 "정지" 가 "정지하지마" 를 삼키지 않습니다
    candidates = []
    for name, spec in config.COMMANDS.items():
        for phrase in spec["phrases"]:
            candidates.append((len(phrase), normalize(phrase), name))
    for _, phrase, name in sorted(candidates, reverse=True):
        if phrase and phrase in cleaned:
            if _allowed(cleaned, phrase, config.COMMANDS[name]):
                return name, config.COMMANDS[name], "exact", 1.0

    # 2) 유사도 — 인식 오차 보정
    best_name, best_score = None, 0.0
    for name, spec in config.COMMANDS.items():
        for phrase in spec["phrases"]:
            score = difflib.SequenceMatcher(None, cleaned, normalize(phrase)).ratio()
            if score > best_score:
                best_name, best_score = name, score

    if best_score >= config.COMMAND_FUZZY_THRESHOLD:
        return best_name, config.COMMANDS[best_name], "fuzzy", best_score

    return None, None, None, best_score


# ═════════════════════════════════════════════════════════════
# 자유 질의응답 (선택 사항)
# ═════════════════════════════════════════════════════════════

_client = None
_unavailable_reason = None


def llm_available():
    """질의응답을 쓸 수 있는 상태인지."""
    return _prepare() is not None


def _prepare():
    global _client, _unavailable_reason
    if _client is not None:
        return _client
    if _unavailable_reason is not None:
        return None

    key = config.ANTHROPIC_API_KEY
    if not key:
        _unavailable_reason = (
            "API 키가 없습니다. 질의응답 없이 명령어만 동작합니다.\n"
            "       쓰시려면:  $env:ANTHROPIC_API_KEY = \"키\""
        )
        return None
    try:
        import anthropic
        _client = anthropic.Anthropic(api_key=key)
        return _client
    except ImportError:
        _unavailable_reason = (
            "anthropic 패키지가 없습니다.\n"
            "       설치:  .\\.venv\\Scripts\\python.exe -m pip install anthropic"
        )
        return None


def unavailable_reason():
    _prepare()
    return _unavailable_reason


def ask(question, timeout=12):
    """방문객의 질문에 짧은 한국어 문장으로 답합니다.

    ※ 답변은 소리로 나갑니다. 그래서 짧고, 목록이나 기호 없이,
      읽어서 자연스러운 문장이어야 합니다.
    """
    client = _prepare()
    if client is None:
        return None

    try:
        message = client.messages.create(
            model=config.LLM_MODEL,
            max_tokens=200,
            system=config.LLM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
            timeout=timeout,
        )
        parts = [b.text for b in message.content if getattr(b, "type", "") == "text"]
        answer = " ".join(parts).strip()
        # 소리로 나갈 것이므로 줄바꿈과 기호를 정리합니다
        answer = re.sub(r"[*#`\-•]+", " ", answer)
        answer = re.sub(r"\s+", " ", answer).strip()
        return answer or None
    except Exception as e:
        print(f"[질의응답] 실패: {type(e).__name__}: {e}")
        return None
