# -*- coding: utf-8 -*-
"""
전방 라이트 확인 — 무엇을 받아주는지 로봇에게 직접 물어봅니다.

  ★ 로봇을 움직이지 않습니다 ★  자세도 그대로 둡니다.

  ── 1차 시험에서 알아낸 것 ──
    api_id 1005  →  코드 100 (거부)
    api_id 1004  →  코드 0   (수락, 그러나 눈에 보이는 변화 없음)
    api_id 1006  →  코드 0   (수락)

    이게 생각보다 좋은 소식입니다. **VUI 서비스는 api_id 를 실제로
    검사합니다.** 아무거나 0 을 주는 게 아니라 모르는 번호는 100 으로
    거부합니다. 회피 모드(SwitchAvoidMode)와는 다릅니다.
    즉 1004 와 1006 은 실재하는 명령이고, 우리가 **값의 모양을 틀린 것**입니다.

  ── 1차의 실수 ──
    1006 은 '읽기' 로 짐작한 명령이었는데, **응답 내용을 안 찍었습니다.**
    코드만 보고 "안 보였다" 로 넘겼습니다.

    읽기 명령의 응답이 곧 설명서입니다. {"brightness": 3} 이 돌아오면
    항목 이름과 값의 범위를 그 자리에서 알게 됩니다.
    짐작으로 값을 만들어 던지느니, 로봇이 스스로 말하게 하는 편이 낫습니다.

  ── 그래서 이번에는 ──
    1. api_id 를 1001~1012 까지 훑으면서 **어떤 번호가 살아 있는지** 봅니다
    2. 살아 있는 번호의 **응답 전문을 그대로 찍습니다**
    3. 응답에서 항목 이름이 보이면, 그 이름으로 값을 넣어 봅니다

  쓰는 법

      .\\run light_test.py           번호를 훑고 응답을 찍습니다 (눈 확인 없음)
      .\\run light_test.py --try     찾은 항목으로 실제로 켜 봅니다

  결과는 light_test_log.txt 에 남습니다. 그대로 보여주시면 됩니다.
"""

import asyncio
import json
import sys
from pathlib import Path

from unitree_webrtc_connect.constants import RTC_TOPIC

import common

LOG = Path(__file__).parent / "light_test_log.txt"

# 훑어볼 번호. 다른 서비스들이 1001 부터 쓰므로 그 언저리입니다.
API_RANGE = range(1001, 1013)

# 3단계에서 넣어볼 값들. 응답에서 항목 이름을 못 찾았을 때의 대비책입니다.
GUESSES = [
    {"brightness": 10},
    {"brightness": 10, "time": 5},
    {"level": 10},
    {"data": 10},
    {"on": True},
    {"enable": True},
    {"color": "white", "time": 5},
]


def brief(obj, limit=400):
    """응답을 사람이 읽을 수 있게. 길면 자릅니다."""
    try:
        s = json.dumps(obj, ensure_ascii=False)
    except Exception:
        s = repr(obj)
    return s if len(s) <= limit else s[:limit] + " …"


def payload(reply):
    """응답에서 알맹이만 꺼냅니다. 못 꺼내면 None.

    ★ 안쪽 data 는 dict 가 아니라 JSON **문자열** 입니다 ★
      {"data": {"header": {...}, "data": "{\\"brightness\\":0}"}}
                                        ^^^^^^^^^^^^^^^^^^^^ 이게 문자열
      처음에는 이걸 그냥 넘겨서, 눈으로는 brightness 가 뻔히 보이는데
      코드는 "빛 관련 항목 없음" 이라고 했습니다. 풀어서 봐야 합니다.
    """
    if not isinstance(reply, dict):
        return None
    for key in ("data", "body", "result"):
        v = reply.get(key)
        if isinstance(v, dict):
            inner = v.get("data", v)
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except Exception:
                    return None
            return inner
    return None


def field_names(obj, found=None):
    """응답 안에 나오는 항목 이름을 전부 모읍니다.

    ★ 이게 우리가 찾는 설명서입니다 ★
    로봇이 스스로 "나는 brightness 라는 걸 가지고 있다" 고 말해주는 셈입니다.
    """
    found = found if found is not None else set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            found.add(k)
            field_names(v, found)
    elif isinstance(obj, list):
        for v in obj[:5]:
            field_names(v, found)
    return found


# 한 번 물어보고 이만큼 안 오면 포기합니다 (초).
#
# ★ 이게 없어서 한 번 멈췄습니다 ★
#   1008 을 보냈더니 로봇이 응답을 안 보냈고, 우리는 영원히 기다렸습니다.
#   콘솔이 그 자리에 멈춰서 나머지 번호도, 응답 전문도 못 봤습니다.
#
#   그런데 이건 버그이자 **발견**이기도 합니다. 지금까지 응답은 두 가지뿐이라고
#   생각했습니다 — 0(수락) 아니면 100(거부). 세 번째가 있었습니다:
#   **받고서 대답을 안 하는 것.**
#
#   라이브러리에 전례가 있습니다. 회피 서비스의 MOVE(1003) 옆에
#   `(no-reply)` 라고 적혀 있습니다. 무응답 명령이 실제로 존재합니다.
#   그리고 무응답이라는 건 **아무 일도 안 했다는 뜻이 아닙니다.**
#   오히려 뭔가 했을 가능성이 있습니다.
CALL_TIMEOUT = 3.0


async def send(conn, api_id, param):
    """(코드, 응답). 코드가 None 이고 응답이 'TIMEOUT' 이면 무응답."""
    try:
        reply = await asyncio.wait_for(
            conn.datachannel.pub_sub.publish_request_new(
                RTC_TOPIC["VUI"], {"api_id": api_id, "parameter": param}),
            timeout=CALL_TIMEOUT)
        return common.status_code(reply), reply
    except asyncio.TimeoutError:
        return None, "TIMEOUT"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


async def run(conn, do_try=False):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    # ── 1단계: 어떤 번호가 살아 있는가 ──
    out("=" * 72)
    out(" 1단계 — VUI 가 어떤 api_id 를 받아주는가")
    out("=" * 72)
    out(" 모르는 번호는 코드 100 으로 거부합니다. 그래서 0 이 오면 실재하는 명령입니다.")
    out()

    alive, silent = [], []
    for api_id in API_RANGE:
        code, reply = await send(conn, api_id, {})
        if reply == "TIMEOUT":
            out(f"   {api_id}   응답 없음 ({CALL_TIMEOUT:.0f}초)"
                f"   ★ 무응답 명령일 수 있습니다 ★")
            silent.append(api_id)
        elif code == 0:
            out(f"   {api_id}   코드 {code}  ← 살아 있음")
            alive.append((api_id, reply))
        else:
            out(f"   {api_id}   코드 {code}")
        await asyncio.sleep(0.25)

    if silent:
        out()
        out(" ★ 응답이 없던 번호들 — 여기를 눈여겨보세요 ★")
        out(f"     {', '.join(str(i) for i in silent)}")
        out("   무응답은 '아무 일도 안 했다' 가 아닙니다. 라이브러리에도")
        out("   무응답 명령이 있습니다 (회피 서비스의 MOVE 옆에 no-reply).")
        out("   ★ 이 번호를 보낼 때 로봇에게 무슨 일이 있었는지 떠올려 보세요 ★")
        out("     불이 켜졌거나, 소리가 났거나, 무언가 달라졌습니까?")

    if not alive and not silent:
        out("\n 받아주는 번호가 없습니다. 이 펌웨어에서 VUI 가 막혀 있는 것 같습니다.")
        LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    # ── 2단계: 응답 전문 ──
    out()
    out("=" * 72)
    out(" 2단계 — 살아 있는 번호의 응답 전문")
    out("=" * 72)
    out(" ★ 여기가 핵심입니다 ★  응답 안의 항목 이름이 곧 설명서입니다.")
    out()
    if not alive:
        out("   응답을 준 번호가 없습니다 (전부 거부이거나 무응답).")

    names = set()
    for api_id, reply in alive:
        out(f"   [{api_id}]")
        out(f"     {brief(reply)}")
        inner = payload(reply)
        if inner is not None:
            got = field_names(inner)
            names |= got
            if got:
                out(f"     항목 이름: {', '.join(sorted(got))}")
        out()

    interesting = sorted(n for n in names
                         if any(w in n.lower() for w in
                                ("bright", "light", "led", "color", "lamp", "level")))
    if interesting:
        out(f" ★ 빛과 관련되어 보이는 항목: {', '.join(interesting)}")
    else:
        out(" ※ 응답에 빛 관련 항목 이름이 없습니다.")
        out("   응답이 비어 있다면, 이 번호들은 '읽기' 가 아니라 '쓰기' 일 수 있습니다.")

    # ── 3단계: 실제로 켜 보기 ──
    if not do_try:
        out()
        out(" 실제로 켜 보려면:  .\\run light_test.py --try")
        LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n{LOG.name} 에 저장했습니다.")
        return

    out()
    out("=" * 72)
    out(" 3단계 — 밝기를 올려 봅니다")
    out("=" * 72)
    out(" ★ 짐작이 아니라 규칙으로 갑니다 ★")
    out("   1002/1004/1006/1010 이 값을 돌려주고, 1001/1003/1005/1011 은")
    out("   빈 파라미터를 거부합니다. 홀수가 설정, 짝수가 조회입니다.")
    out("   그러니 1006(GET brightness)의 짝은 1005(SET brightness) 입니다.")
    out()
    out(" 그리고 **눈이 아니라 로봇에게 물어서** 확인합니다.")
    out("   올린 뒤 다시 읽어서 값이 실제로 바뀌었는지 봅니다.")
    out()

    # 조회 번호에서 찾은 밝기 항목 → 그 앞 홀수 번호가 설정
    targets = []
    for api_id, reply in alive:
        inner = payload(reply)
        if not isinstance(inner, dict):
            continue
        for field, value in inner.items():
            if "bright" in field.lower():
                targets.append((api_id - 1, api_id, field, value))

    if not targets:
        out("   밝기 항목을 못 찾았습니다. 여기서 멈춥니다.")
        LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    worked = []
    for set_id, get_id, field, before in targets:
        out(f"   {field}: 지금 {before}  (설정 {set_id} / 조회 {get_id})")
        for level in (10, 5, 1):
            code, _r = await send(conn, set_id, {field: level})
            await asyncio.sleep(0.6)
            _c, back = await send(conn, get_id, {})
            now = (payload(back) or {}).get(field)
            out(f"     {field}={level:<3} 보냄 → 코드 {code},  다시 읽으니 {now}")
            if code == 0 and now == level:
                worked.append((set_id, field, level))
                break
        out()

    if worked:
        set_id, field, level = worked[0]
        out(f" ★ 값이 실제로 바뀌었습니다 — api_id {set_id}, {{\"{field}\": N}} ★")
        out()
        seen = await common.confirm("로봇 앞쪽에 불이 켜졌습니까?")
        out(f"   → {'★ 켜졌습니다 ★' if seen else '값은 바뀌었지만 눈에는 안 보입니다'}")
        # 원래대로 되돌립니다
        for set_id2, get_id2, field2, before2 in targets:
            await send(conn, set_id2, {field2: before2})
        out(f"   (원래 값 {targets[0][3]} 로 되돌렸습니다)")
    else:
        seen = False

    out()
    out("=" * 72)
    out(" 정리")
    out("=" * 72)
    if worked and seen:
        set_id, field, level = worked[0]
        out(" ★ 전방 라이트를 코드로 켤 수 있습니다 ★")
        out()
        out("     conn.datachannel.pub_sub.publish_request_new(")
        out('         RTC_TOPIC["VUI"],')
        out(f'         {{"api_id": {set_id}, "parameter": {{"{field}": 0~10}}}})')
        out()
        out(" 이제 음성 명령에 붙일 수 있습니다. 그리고 복도에서 두 가지만 더 보세요.")
        out("   1. 실내조명이 켜진 낮에도 보이는가")
        out("   2. 앞을 '비추는' 가, 얼굴처럼 '빛나기만' 하는가")
        out("      후자면 문을 가리키는 용도로는 못 씁니다")
    elif worked:
        out(" 값은 바뀌는데 눈에 보이는 변화가 없습니다.")
        out(" 이 brightness 는 전방 라이트가 아니라 다른 것(얼굴 LED 등)일 수 있습니다.")
        out(" 어두운 곳에서 한 번 더 보시면 확실합니다.")
    else:
        out(" 값을 바꾸지 못했습니다. 항목 이름이나 범위가 다른 것 같습니다.")

    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{LOG.name} 에 저장했습니다.")


async def main():
    do_try = "--try" in sys.argv
    print("=" * 72)
    print(" 전방 라이트 확인  ★ 로봇을 움직이지 않습니다 ★")
    print("=" * 72)
    if do_try:
        print(" 로봇의 앞쪽이 보이는 자리에 계세요. 어두울수록 판단하기 쉽습니다.")
    print()

    conn = await common.connect()
    try:
        await run(conn, do_try=do_try)
    finally:
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨.")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
