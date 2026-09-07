# -*- coding: utf-8 -*-
"""
버튼이 뜻대로 움직이는가 — 로봇 없이 확인합니다.

  ★ 왜 이 시험이 있는가 ★

    같은 종류의 실수를 세 번 했습니다.

        '다시' 를 만들어놓고 allow 에 안 넣어서 죽었습니다.
        메뉴 자바스크립트를 안 넣고 "넣었다" 고 적었습니다.
        '멈춤' 이 allow 를 빠져나가서 구간을 되살렸습니다.

    셋 다 **로봇 앞에 서서** 발견했습니다. 복도까지 걸어가고, 로봇을
    켜고, 안내를 절반쯤 돌리고 나서요. 버튼의 뜻은 로봇과 아무 상관이
    없습니다 — 여기서 확인할 수 있는 일이었습니다.

    이 시험은 진짜 서버를 열고 진짜 HTTP 로 누릅니다. 로봇에는 한 줄도
    보내지 않습니다.

  ★ 무엇을 보는가 ★

    멈춤
      1. 기다리는 중에 '멈춤' → 아무 일도 없어야 합니다.
         (예전에는 이것이 wait() 를 빠져나가 구간을 처음부터 돌렸습니다)
      2. 하는 중에 '멈춤'   → wait_stop() 이 바로 받아야 합니다.
      3. '안내 종료' 는 기다리는 중에도 살아 있어야 합니다.
      4. 기다리는 중에 눌린 '멈춤' 이 다음 구간에서 터지면 안 됩니다.

    메뉴
      5. 설명 중에는 다리를 쓰는 셋과 음성 인식이 잠깁니다.
      6. 라이트·음량은 설명 중에도 됩니다. '프로그램 종료' 도요.

    음성 인식
      7. 켜둔 채로 안내가 시작되면 **스스로 귀를 막습니다.**
         (안 막으면 로봇이 자기 말의 '안내' 를 '다음' 으로 듣습니다)
      8. 기다리는 자리로 오면 다시 듣고, 그동안 쌓인 소리는 버립니다.

    코스
      9. 오디오 이름이 겹치는 코스는 등록을 거부합니다.
         (같은 이름은 로봇에서 한 파일 — 나중 것이 앞의 것을 덮습니다)
     10. 안내 중에는 코스를 못 바꿉니다.
     11. 고르면 대본이 실제로 갈립니다.

    조종판
     12. 앞으로 가면서 도는 것이 됩니다 (두 키 동시).
     13. 한 손가락을 떼도 나머지는 그대로입니다.
     14. 앞뒤를 같이 누르면 상쇄되어 섭니다.
     15. 소식이 끊기면(DEADMAN) 멈춥니다.

  쓰는 법

      .\\run stop_test.py

    ★ 로봇에 연결하지 않습니다. 켜져 있지 않아도 됩니다 ★
"""

import asyncio
import sys
import urllib.error
import urllib.request

import remote

PORT = 8791          # 진짜 리모컨(8080)과 겹치지 않게


def push(path):
    """휴대폰이 누르는 것과 같은 요청을 보냅니다.

    거절당한 것도 결과입니다 — 코드를 그대로 돌려줍니다 ("404").
    """
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}",
                                    data=b"", timeout=3) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return str(e.code)


async def press(path):
    """서버는 같은 루프에 있습니다 — 요청은 다른 실에서 보냅니다."""
    return await asyncio.to_thread(push, path)


def _drop_course_files():
    """시험용 코스 파일 넷을 폴더에 잠깐 놓습니다. 끝나면 지웁니다.

    멀쩡한 것 · 초안 · 못 읽는 것 · 이름이 겹치는 것 — 네 경우를
    다 만들어 봅니다. 하나씩 손으로 만들어 보는 것보다 이게 빠르고,
    무엇보다 **다음 사람이 고칠 때도 그대로 돌아갑니다.**
    """
    from pathlib import Path
    here = Path(__file__).resolve().parent
    head = ("# -*- coding: utf-8 -*-\n"
            "from scenario import Course, Line, Stop\n")

    def body(cid, key):
        return (f"{head}"
                f"STEPS = [Stop('S1', '어딘가', '시험', doc_seconds=10,\n"
                f"              lines=[Line('{key}', text='시험입니다.')])]\n"
                f"COURSE = Course('{cid}', '{cid} 코스', '시험용', STEPS)\n")

    files = {
        "course_t_drop.py": body("t_drop", "t_drop_hello"),
        "course_t_draft.py": "DRAFT = True\n" + body("t_draft", "t_draft_hi"),
        "course_t_bad.py": "이건 파이썬이 아닙니다 ((((\n",
        "course_t_empty.py": head + "SOMETHING = 1\n",
        # 기본 코스와 같은 오디오 이름 — 거부당해야 합니다
        "course_t_dup.py": body("t_dup", "s1a_greet"),
    }
    made = []
    for name, text in files.items():
        p = here / name
        p.write_text(text, encoding="utf-8")
        made.append(p)
    return made


class Score:
    def __init__(self):
        self.rows = []

    def check(self, name, got, want):
        ok = got == want
        self.rows.append((ok, name, got, want))
        mark = "○" if ok else "★"
        print(f" {mark} {name}")
        if not ok:
            print(f"     받은 것: {got!r}   바라던 것: {want!r}")
        return ok

    def report(self):
        bad = [r for r in self.rows if not r[0]]
        print()
        print("=" * 70)
        if not bad:
            print(f" 모두 통과했습니다 ({len(self.rows)}가지)")
            print(" 버튼의 뜻은 맞습니다. 이제 로봇 앞에서는 로봇만 보면 됩니다.")
            return True
        print(f" ★ {len(bad)}가지가 어긋납니다 ★")
        for _ok, name, got, want in bad:
            print(f"   · {name}: {got!r} (바라던 것 {want!r})")
        return False


async def main():
    print("=" * 70)
    print(" 버튼이 뜻대로 움직이는가")
    print("=" * 70)
    print(" 로봇에 연결하지 않습니다. 진짜 서버를 열고 진짜로 누릅니다.")
    print()

    s = Score()
    hand = remote.Remote(port=PORT)
    await hand.start(verbose=False)
    try:
        # ── 1. 기다리는 중에 '멈춤' ──────────────────────────
        print("─" * 70)
        print(" 기다리는 중에 '멈춤' 을 누릅니다")
        print("─" * 70)
        waiter = asyncio.ensure_future(hand.wait())
        await asyncio.sleep(0.15)                  # waiting 이 켜지기를 기다립니다
        s.check("기다리는 중이라고 표시됩니다", hand.state["waiting"], True)

        before = hand.hits
        body = await press("/stop")
        await asyncio.sleep(0.15)

        s.check("서버가 '흘려보냈다' 고 답합니다", body, "idle")
        s.check("'멈춤' 은 기다리는 자리를 깨우지 않습니다", waiter.done(), False)
        s.check("눌린 것으로 세지 않습니다", hand.hits, before)
        s.check("흘려보낸 수가 올라갑니다", hand.ignored, 1)
        s.check("멈춤 신호가 남지 않습니다", hand.stop_event.is_set(), False)

        # 같은 자리에서 '다음' 은 그대로 됩니다
        await press("/go")
        act = await asyncio.wait_for(waiter, 2.0)
        s.check("'다음' 은 그대로 받습니다", act, "go")

        # ── 2. 하는 중에 '멈춤' ─────────────────────────────
        print()
        print("─" * 70)
        print(" 설명하는 중에 '멈춤' 을 누릅니다")
        print("─" * 70)
        hand.arm()
        s.check("이제는 기다리는 중이 아닙니다", hand.state["waiting"], False)
        stopper = asyncio.ensure_future(hand.wait_stop())
        await asyncio.sleep(0.05)
        body = await press("/stop")
        got = await asyncio.wait_for(stopper, 2.0)
        s.check("서버가 받았다고 답합니다", body, "ok")
        s.check("바로 끊깁니다", got, "stop")
        s.check("안내가 끝난 것은 아닙니다", hand.stopped, False)

        # ── 3. 기다리는 중에도 '안내 종료' 는 살아 있습니다 ──
        print()
        print("─" * 70)
        print(" 기다리는 중에 '안내 종료' 를 누릅니다")
        print("─" * 70)
        hand.arm()
        waiter = asyncio.ensure_future(hand.wait())
        await asyncio.sleep(0.15)
        await press("/end")
        got = await asyncio.wait_for(waiter, 2.0)
        s.check("'안내 종료' 는 기다리는 중에도 받습니다", got, "end")
        s.check("안내를 끝낸 것으로 적힙니다", hand.stopped, True)

        # ── 4. 묵은 '멈춤' 이 다음 구간에서 터지지 않습니다 ──
        print()
        print("─" * 70)
        print(" 기다리는 중에 누른 '멈춤' 이 다음 구간을 덮치는가")
        print("─" * 70)
        hand.stopped = False
        hand.arm()
        waiter = asyncio.ensure_future(hand.wait())
        await asyncio.sleep(0.15)
        await press("/stop")            # 흘려보내집니다
        await press("/go")
        await asyncio.wait_for(waiter, 2.0)
        hand.arm()                      # 다음 구간을 시작합니다
        stopper = asyncio.ensure_future(hand.wait_stop())
        await asyncio.sleep(0.3)
        s.check("다음 구간이 조용히 시작합니다", stopper.done(), False)
        stopper.cancel()

        # ── 5. 메뉴 — 다리를 쓰는 것만 잠깁니다 ─────────────
        print()
        print("─" * 70)
        print(" 설명 중의 메뉴")
        print("─" * 70)
        hand.arm()                      # 설명 중 (기다리는 중이 아님)
        while not hand.jobs.empty():
            hand.jobs.get_nowait()

        for job in ("stand", "sit", "lie", "mic"):
            body = await press(f"/job/{job}")
            s.check(f"설명 중에는 '{job}' 을 받지 않습니다", body, "idle")
        s.check("다리·귀 넷 다 안 들어왔습니다", hand.jobs.qsize(), 0)

        for job in ("light_on", "light_off", "vol_up", "vol_down"):
            body = await press(f"/job/{job}")
            s.check(f"설명 중에도 '{job}' 은 됩니다", body, "ok")
        s.check("라이트·음량 넷은 들어왔습니다", hand.jobs.qsize(), 4)

        # '프로그램 종료' 는 만일을 위해 설명 중에도 살아 있습니다
        hand.stopped = False
        stopper = asyncio.ensure_future(hand.wait_stop())
        await press("/end")
        got = await asyncio.wait_for(stopper, 2.0)
        s.check("'프로그램 종료' 는 설명 중에도 삽니다", got, "end")

        # 기다릴 때는 다리도 됩니다
        print()
        print("─" * 70)
        print(" 기다릴 때의 메뉴")
        print("─" * 70)
        hand.stopped = False
        hand.arm()
        while not hand.jobs.empty():
            hand.jobs.get_nowait()
        waiter = asyncio.ensure_future(hand.wait())
        await asyncio.sleep(0.15)
        for job in ("stand", "sit", "lie", "mic"):
            body = await press(f"/job/{job}")
            s.check(f"기다릴 때는 '{job}' 이 됩니다", body, "ok")
        s.check("넷 다 들어왔습니다", hand.jobs.qsize(), 4)
        s.check("메뉴는 '다음' 을 대신하지 않습니다", waiter.done(), False)
        waiter.cancel()

        # ── 6. 코스 고르기 ──────────────────────────────────
        print()
        print("─" * 70)
        print(" 안내 코스 고르기")
        print("─" * 70)
        import courses
        import scenario

        # 이 시험에서만 쓰는 둘째 코스입니다 — 코스가 하나뿐이면
        # '고르기' 가 되는지 확인할 수가 없습니다.
        second = courses.Course(
            "t_second", "시험용 둘째 코스", "이 시험에서만 씁니다.",
            [scenario.Stop("S1", "어딘가", "시험", doc_seconds=10,
                           lines=[scenario.Line("t_hello", text="시험입니다.")])],
        )
        s.check("겹치지 않으면 등록됩니다",
                courses.register(second).id, "t_second")

        # ★ 폴더에 파일을 두면 코스가 되는가 ★
        #   이게 이 저장소에서 코스를 만드는 유일한 방법입니다. 그런데
        #   처음에는 courses.py 를 편집하게 만들었고, 그 길이 순환
        #   참조로 막혔습니다. 그 일이 다시 생기지 않게 여기서 봅니다 —
        #   진짜 파일을 쓰고, 진짜로 찾게 하고, 지웁니다.
        made = _drop_course_files()
        try:
            before = {c.id for c in courses.all_courses()}
            n_prob = len(courses.PROBLEMS)
            n_draft = len(courses.DRAFTS)
            courses.discover()
            now = {c.id for c in courses.all_courses()}

            s.check("파일을 두면 코스가 됩니다", "t_drop" in now, True)
            s.check("초안은 메뉴에 안 뜹니다", "t_draft" in now, False)
            s.check("초안이라고 알려는 줍니다",
                    any("course_t_draft" in d
                        for d in courses.DRAFTS[n_draft:]), True)
            s.check("못 읽는 파일은 조용히 넘기지 않습니다",
                    any("course_t_bad" in p
                        for p in courses.PROBLEMS[n_prob:]), True)
            s.check("COURSE 가 없으면 그렇다고 말합니다",
                    any("course_t_empty" in p
                        for p in courses.PROBLEMS[n_prob:]), True)
            s.check("이름이 겹치면 거부하고 어느 파일인지 말합니다",
                    any("course_t_dup" in p
                        for p in courses.PROBLEMS[n_prob:]), True)
            s.check("거부당한 것은 안 들어옵니다", "t_dup" in now, False)
            s.check("멀쩡한 것만 늘었습니다", now - before, {"t_drop"})
        finally:
            for f in made:
                f.unlink(missing_ok=True)
            courses.COURSES[:] = [c for c in courses.COURSES
                                  if c.id != "t_drop"]
            del courses.PROBLEMS[n_prob:]
            del courses.DRAFTS[n_draft:]

        # ★ 목록 한 줄에 고를 만큼이 적혀 있는가 ★
        #   이름만 보내면 "이 무리에겐 어느 코스?" 를 못 정합니다.
        b = courses.AI_SWE.brief()
        s.check("한 줄에 시간이 적힙니다", "분" in b["facts"] or "초" in b["facts"],
                True)
        s.check("실측인지 추정인지 밝힙니다",
                ("실측" in b["facts"]) or ("추정" in b["facts"]), True)
        s.check("정차 곳수가 적힙니다", "정차 5곳" in b["facts"], True)
        s.check("경로도 같이 갑니다", bool(b["route"]), True)

        # ★ 말 없는 구간(M4)을 '안 잰 멘트' 로 세면 안 됩니다 ★
        #   그러면 어떤 코스도 영영 '실측' 이 못 됩니다. 실제로 한 번
        #   그렇게 만들었다가 여기서 잡았습니다.
        mute = [s2 for s2 in courses.AI_SWE.steps
                if not getattr(s2, "lines", None) and not s2.text.strip()]
        s.check("말 없는 구간이 실제로 있습니다 (M4)", bool(mute), True)
        s.check("그 이름은 잴 멘트에 안 들어갑니다",
                any(m.key in courses.AI_SWE.spoken_keys() for m in mute), False)

        # 멘트를 다 재두면 '실측' 이라고 나와야 합니다
        real = courses.Course(
            "t_real", "다 잰 코스", "",
            [scenario.Stop("S1", "어딘가", "시험", doc_seconds=10,
                           lines=[scenario.Line("t_measured", text="잰 멘트.")])],
        )
        keep = scenario._MEASURED
        scenario._MEASURED = {"t_measured": 18.0}
        try:
            s.check("다 잰 코스는 '실측' 으로 나옵니다",
                    "(실측)" in real.brief()["facts"], True)
            scenario._MEASURED = {}
            s.check("하나라도 안 재면 '추정' 으로 나옵니다",
                    "(추정)" in real.brief()["facts"], True)
        finally:
            scenario._MEASURED = keep
        s.check("이름으로 찾힙니다", courses.get("t_second") is second, True)
        s.check("모르는 이름은 None", courses.get("없는코스"), None)

        # ★ 겹치는 이름은 거부해야 합니다 ★
        #   같은 오디오 이름은 로봇에서 한 파일입니다. 나중 것이
        #   앞의 것을 덮어써서 다른 코스의 문장이 나옵니다.
        dup = courses.Course("t_dup", "겹치는 코스", "",
                             scenario.SCENARIO, scenario.OPTIONAL)
        refused = False
        try:
            courses.register(dup)
        except ValueError:
            refused = True
        s.check("오디오 이름이 겹치면 등록을 거부합니다", refused, True)

        hand.arm()
        hand.show(courses=[c.brief() for c in courses.all_courses()],
                  course={"id": "ai_swe", "name": "기본"}, can_pick=False)

        body = await press("/course/t_second")
        s.check("안내 중에는 코스를 못 바꿉니다", body, "idle")
        s.check("바꾸라는 신호도 안 옵니다", hand.course_want, None)

        hand.show(can_pick=True)
        waiter = asyncio.ensure_future(
            hand.wait(allow=("go", "end", "course")))
        await asyncio.sleep(0.15)

        body = await press("/course/nope")
        s.check("모르는 코스는 404", body, "404")
        s.check("모르는 코스는 깨우지 않습니다", waiter.done(), False)

        body = await press("/course/ai_swe")
        s.check("지금 코스를 또 고르면 아무 일도 없습니다", body, "same")
        s.check("그때는 깨우지 않습니다", waiter.done(), False)

        body = await press("/course/t_second")
        got = await asyncio.wait_for(waiter, 2.0)
        s.check("고르면 받습니다", body, "ok")
        s.check("기다리는 자리가 'course' 로 깨어납니다", got, "course")
        s.check("무엇을 골랐는지 전해집니다", hand.course_want, "t_second")

        # scenario.use 가 대본을 갈아 끼우는지 (로봇 없이 확인됩니다)
        before = len(scenario.SCENARIO)
        scenario.use(second)
        s.check("고른 코스의 대본으로 갈립니다", len(scenario.SCENARIO), 1)
        s.check("제목도 갈립니다", scenario.TITLE, "시험용 둘째 코스")
        scenario.use(courses.AI_SWE)
        s.check("되돌리면 원래 대본입니다", len(scenario.SCENARIO), before)

        courses.COURSES.remove(second)          # 시험 흔적을 지웁니다

        # ── 7. 화면 검사기 자체가 도는가 ────────────────────
        #
        # check_page() 는 이제 이 화면의 주된 안전장치입니다. 그것이
        # 조용히 아무것도 안 잡게 되면, 있는 것보다 나쁩니다.
        print()
        print("─" * 70)
        print(" 화면 검사기")
        print("─" * 70)
        s.check("지금 화면에는 문제가 없습니다", remote.check_page(), [])

        base = remote.PAGE
        try:
            # ★ 실제로 겪은 버그 ★ 바깥 이름을 함수 안에서 다시 선언
            remote.PAGE = base.replace("const micHeld = f.mic==='held';",
                                       "const held = f.mic==='held';")
            s.check("바깥 이름을 가리면 잡습니다",
                    any("held" in x for x in remote.check_page()), True)

            remote.PAGE = base.replace("$('volst')", "$('nosuchthing')")
            s.check("없는 자리를 찾으면 잡습니다",
                    any("nosuchthing" in x for x in remote.check_page()), True)

            remote.PAGE = base.replace("data-job=vol_up", "data-job=vol_updown")
            s.check("서버가 안 받는 메뉴는 잡습니다",
                    any("vol_updown" in x for x in remote.check_page()), True)
        finally:
            remote.PAGE = base
        s.check("검사가 끝나고 화면은 그대로입니다", remote.check_page(), [])

        # ── 8. 로봇이 말할 때 귀를 막는가 ───────────────────
        #
        # ★ 버튼을 잠그는 것만으로는 모자랍니다 ★
        #   기다릴 때 음성 인식을 켜두고 안내를 시작하면 그 뒤로도
        #   계속 켜져 있습니다. 그동안 로봇은 말하고, PC 마이크는 그
        #   소리를 담습니다. 대본의 "지금부터 … 안내해 드리겠습니다"
        #   에 '안내' 가 있고, 그게 '다음' 으로 번역됩니다 —
        #   로봇이 자기 말로 자기 안내를 넘깁니다.
        print()
        print("─" * 70)
        print(" 로봇이 말하는 동안 귀를 막는가")
        print("─" * 70)
        import guide

        class FakeEar:
            """진짜 whisper 대신. pause/resume 만 흉내 냅니다."""

            def __init__(self):
                self.deaf = False
                self.drained = 0

            def pause(self):
                self.deaf = True

            def resume(self, drain=True):
                self.deaf = False
                if drain:
                    self.drained += 1

        ear = FakeEar()
        hand.state["waiting"] = True
        gate = asyncio.ensure_future(guide.ear_gate(hand, ear))
        try:
            await asyncio.sleep(0.4)
            s.check("기다릴 때는 듣습니다", ear.deaf, False)

            hand.state["waiting"] = False          # 설명이 시작됩니다
            await asyncio.sleep(0.4)
            s.check("로봇이 말하면 귀를 막습니다", ear.deaf, True)
            s.check("화면에는 '잠깐 멈춤' 으로 뜹니다",
                    hand.state["flags"]["mic"], "deaf")

            hand.state["waiting"] = True           # 다시 기다리는 자리로
            await asyncio.sleep(0.4)
            s.check("기다리는 자리로 오면 다시 듣습니다", ear.deaf, False)
            s.check("막아둔 동안 쌓인 소리는 버립니다", ear.drained >= 1, True)
            s.check("화면도 '켜짐' 으로 돌아옵니다",
                    hand.state["flags"]["mic"], "on")
        finally:
            gate.cancel()
            hand.state["waiting"] = False
            hand.flag(mic="off")

        # ── 9. 조종판은 그대로입니다 ────────────────────────
        print()
        print("─" * 70)
        print(" 조종판")
        print("─" * 70)
        await press("/drive/w")
        s.check("앞으로 신호가 잡힙니다", hand.stick(), (1.0, 0.0, 0.0))

        # ★ 여기가 이번에 바뀐 곳입니다 ★
        await press("/drive/aw")
        s.check("앞으로 가면서 좌회전이 됩니다", hand.stick(), (1.0, 0.0, 1.0))
        s.check("눌린 키가 둘로 보입니다", hand.holding(), "aw")

        await press("/drive/ed")
        s.check("게걸음 오른쪽 + 우회전", hand.stick(), (0.0, 1.0, -1.0))

        await press("/drive/ws")
        s.check("앞뒤를 같이 누르면 상쇄되어 섭니다", hand.stick(), None)

        await press("/drive/wq")
        s.check("한 손가락을 떼면 나머지는 그대로", hand.stick(), (1.0, -1.0, 0.0))
        await press("/drive/w")
        s.check("떼고 난 뒤 남은 하나", hand.stick(), (1.0, 0.0, 0.0))

        await press("/drive/wZ9")
        s.check("모르는 글자는 흘려보냅니다", hand.holding(), "w")

        await press("/drive/-")
        s.check("손을 다 떼면 멈춥니다", hand.stick(), None)

        await press("/drive/wa")
        await asyncio.sleep(remote.DEADMAN + 0.1)
        s.check("소식이 끊기면 둘 다 멈춥니다", hand.stick(), None)

        return s.report()
    finally:
        await hand.close()


if __name__ == "__main__":
    try:
        ok = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
    sys.exit(0 if ok else 1)
