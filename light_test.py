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
    """응답에서 알맹이만 꺼냅니다. 못 꺼내면 None."""
    if not isinstance(reply, dict):
        return None
    for key in ("data", "body", "result"):
        v = reply.get(key)
        if isinstance(v, dict):
            inner = v.get("data", v)
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


async def send(conn, api_id, param):
    try:
        reply = await conn.datachannel.pub_sub.publish_request_new(
            RTC_TOPIC["VUI"], {"api_id": api_id, "parameter": param})
        return common.status_code(reply), reply
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

    alive = []
    for api_id in API_RANGE:
        code, reply = await send(conn, api_id, {})
        mark = "  ← 살아 있음" if code == 0 else ""
        out(f"   {api_id}   코드 {code}{mark}")
        if code == 0:
            alive.append((api_id, reply))
        await asyncio.sleep(0.25)

    if not alive:
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
    out(" 3단계 — 값을 넣어 실제로 켜 보기")
    out("=" * 72)
    out(" 코드가 0 이면 눈으로 확인합니다. 코드는 믿지 않습니다.")
    out()

    # 응답에서 찾은 이름을 우선 씁니다
    tries = [{n: 10} for n in interesting if "color" not in n.lower()]
    tries += [{n: "white"} for n in interesting if "color" in n.lower()]
    tries += GUESSES

    seen_any = []
    for api_id, _r in alive:
        for param in tries:
            code, reply = await send(conn, api_id, param)
            if code != 0:
                continue
            out(f"   [{api_id}] {brief(param, 60)}  → 코드 0")
            if await common.confirm("지금 불이 보이거나 바뀌었습니까?"):
                out("     ★ 보였습니다 ★")
                seen_any.append((api_id, param))
            await asyncio.sleep(0.4)

    out()
    out("=" * 72)
    out(" 정리")
    out("=" * 72)
    if seen_any:
        out(" ★ 실제로 켜진 방법 ★")
        for api_id, param in seen_any:
            out(f"     api_id {api_id}   {brief(param, 80)}")
        out()
        out(" 이제 복도에서 두 가지만 더 보세요.")
        out("   1. 실내조명이 켜진 낮에도 보이는가")
        out("   2. 앞을 '비추는' 가, 아니면 얼굴처럼 '빛나기만' 하는가")
        out("      후자면 문을 가리키는 용도로는 못 씁니다")
    else:
        out(" 받아주기는 하는데 눈에 보이는 변화는 없었습니다.")
        out(" 라이트는 포인터로 못 씁니다 — 몸통 기울이기만으로 갑니다.")
        out(" (기울이기는 바닥 공간이 필요 없어서, 좁은 이 복도에는 오히려 맞습니다)")

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
