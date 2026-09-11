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

import json as _json
import tempfile as _tempfile
from pathlib import Path

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


def send(path, blob):
    """본문이 있는 요청. 폰이 녹음을 보내는 것과 같습니다.

    ★ 본문 있는 요청을 처음 받습니다 ★
      여태 리모컨은 본문을 버렸습니다. 폰이 20 KB 를 보내기 시작하면
      그러면 안 됩니다 — 안 읽은 본문이 소켓에 남아 다음 요청 줄로
      읽히고, 그 연결은 어긋납니다. 조종판이 같은 연결을 쓰니
      **조종이 통째로 먹통이 됩니다.** 그래서 이 시험이 있습니다.
    """
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}", data=blob,
        headers={"Content-Type": "audio/webm"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode()
    except urllib.error.HTTPError as e:
        return str(e.code)


async def post(path, blob):
    return await asyncio.to_thread(send, path, blob)


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
        # 접두어 없는 이름 — 거부당해야 합니다
        # (예전에는 기본 코스와 '겹쳐서' 거부됐는데, 이제는
        #  't_dup_' 로 시작하지 않아서 그 앞에서 걸립니다)
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
                           lines=[scenario.Line("t_second_hello",
                                                text="시험입니다.")])],
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
            s.check("규칙을 어긴 코스는 거부하고 어느 파일인지 말합니다",
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

        # ★ 코스 이름으로 시작하지 않으면 거부해야 합니다 ★
        #
        #   로봇의 오디오 이름은 폴더 없이 평평합니다. 두 코스가 같은
        #   이름을 쓰면 로봇에서는 한 파일이 되고, 나중에 올린 쪽이 앞의
        #   것을 덮어씁니다. 화면에는 맞는 문장이 찍히는데 스피커에서는
        #   다른 코스의 말이 나옵니다 — 로그가 멀쩡해서 못 찾습니다.
        #
        #   겹칠 때 잡는 검사는 원래 있었지만 그건 **부딪힌 뒤에** 잡습니다.
        #   규칙을 두면 애초에 안 부딪힙니다.
        loose = courses.Course("t_loose", "접두어 없는 코스", "",
                               [scenario.Stop("S1", "어딘가", "시험",
                                              doc_seconds=10,
                                              lines=[scenario.Line(
                                                  "hello", text="시험")])])
        s.check("접두어가 없는 이름을 찾아냅니다",
                courses.unprefixed(loose), ["hello"])
        why = ""
        try:
            courses.register(loose)
        except ValueError as e:
            why = str(e)
        s.check("접두어가 없으면 등록을 거부합니다", bool(why), True)
        s.check("무엇이 잘못됐는지 말해줍니다", "hello" in why, True)
        s.check("어떻게 고치는지도 말해줍니다", "t_loose_" in why, True)
        s.check("거부당한 것은 안 들어옵니다",
                courses.get("t_loose") is None, True)

        # 규칙을 지키는 코스는 통과해야 합니다 — 검사가 다 막으면 안 됩니다
        s.check("규칙을 지키면 통과합니다",
                courses.unprefixed(courses.get("t_second")), [])

        # ★ 겹치는 이름은 거부해야 합니다 — 둘째 방어선 ★
        #
        #   접두어 규칙을 지키면 원래 안 부딪힙니다. 그래도 겹침 검사를
        #   남겨둡니다. 규칙이 언젠가 새면(코스 이름을 잘못 짓는다든지)
        #   그때 잡아줄 것이 하나는 있어야 합니다.
        #
        #   ※ register() 를 거쳐 시험하면 **접두어 검사가 먼저 걸립니다.**
        #     그러면 겹침 검사는 한 번도 안 돌면서 시험은 통과합니다 —
        #     조용히 아무것도 안 지키는 검사가 되는 것이죠.
        #     그래서 collisions() 를 직접 부릅니다.
        twin_a = courses.Course(
            "t_twin_a", "쌍둥이 가", "",
            [scenario.Stop("S1", "어딘가", "시험", doc_seconds=10,
                           lines=[scenario.Line("t_twin_hello", text="가")])])
        twin_b = courses.Course(
            "t_twin_b", "쌍둥이 나", "",
            [scenario.Stop("S1", "어딘가", "시험", doc_seconds=10,
                           lines=[scenario.Line("t_twin_hello", text="나")])])
        bad = courses.collisions([twin_a, twin_b])
        s.check("같은 이름을 쓰는 두 코스를 찾아냅니다",
                [k for k, _who in bad], ["t_twin_hello"])
        s.check("어느 코스들인지도 알려줍니다",
                sorted(bad[0][1]), ["t_twin_a", "t_twin_b"])

        # 그리고 register() 를 거쳐도 거부되는지 (이유는 접두어 쪽입니다)
        dup = courses.Course("t_dup", "겹치는 코스", "",
                             scenario.SCENARIO, scenario.OPTIONAL)
        refused = False
        try:
            courses.register(dup)
        except ValueError:
            refused = True
        s.check("남의 코스 대본을 그대로 쓰면 거부합니다", refused, True)

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

            # ★ 자기가 자기를 덮어쓰는 CSS 도 잡는가 ★
            #   `#burger{margin-left:auto; … ; margin:0}` 이 실제로
            #   있었습니다. 뒤쪽 margin:0 이 앞의 것을 없애서, 햄버거를
            #   오른쪽 끝으로 밀라는 규칙이 **쓰인 날부터 한 번도 안
            #   들었습니다.** 브라우저는 안 알려줍니다 — 화면이 멀쩡해
            #   보이거든요. 배터리를 달다가 우연히 드러났습니다.
            remote.PAGE = base.replace(
                "#burger{background:transparent",
                "#burger{margin-left:auto;background:transparent", 1)
            s.check("죽은 CSS 를 잡습니다",
                    any("덮어씁니다" in x for x in remote.check_page()), True)
        finally:
            remote.PAGE = base
        s.check("검사가 끝나고 화면은 그대로입니다", remote.check_page(), [])

        # ── 8. 폰이 보낸 말이 버튼과 같은 길을 지나는가 ─────
        #
        # ★ 여기가 오늘 바뀐 자리입니다 ★
        #   여태 PC 마이크가 늘 열려 있어서, 로봇이 말하는 동안 귀를
        #   막는 문지기(ear_gate)가 필요했습니다. 안 막으면 대본의
        #   "지금부터 … 안내해 드리겠습니다" 에 있는 '안내' 를 듣고
        #   **로봇이 자기 말로 자기 안내를 넘겼습니다.**
        #
        #   이제 안 누르면 안 듣습니다. 문지기가 사람 손가락이 됐고,
        #   그래서 그 시험 자리를 이걸로 바꿉니다.
        print()
        print("─" * 70)
        print(" 폰이 보낸 말")
        print("─" * 70)
        import guide

        # ★ 앞 자리가 남긴 것을 비우고 시작합니다 ★
        #   처음에 안 비웠더니 '앉아' 를 넣고 꺼낸 것이 앞 자리에서
        #   남은 'stand' 였습니다. 시험은 틀렸다고 했지만 코드는
        #   멀쩡했습니다 — 그리고 **우연히 맞을 수도 있었습니다.**
        #   같은 큐를 여럿이 쓰면 앞자리를 비우고 재야 합니다.
        while not hand.jobs.empty():
            hand.jobs.get_nowait()
        while not hand.said.empty():
            hand.said.get_nowait()
        hand.action = None

        heard = []

        async def fake_ear(raw):
            """진짜 whisper 대신. 보낸 바이트를 글자로 돌려줍니다."""
            heard.append(raw)
            return raw.decode("utf-8"), len(raw) / 1000.0

        # ㄱ. 귀가 꺼져 있으면 거절합니다 — 조용히 삼키지 않습니다
        r = _json.loads(await post("/heard", "다음".encode()))
        s.check("귀가 꺼져 있으면 그렇게 말해줍니다",
                "마이크가 꺼져" in r.get("error", ""), True)
        s.check("꺼져 있을 때는 옮기지도 않습니다", heard, [])

        hand.ear = fake_ear

        # ㄴ. 빈 녹음 — 잘못 스친 것입니다
        r = _json.loads(await post("/heard", b""))
        s.check("빈 녹음은 거절합니다", "빈 녹음" in r.get("error", ""), True)

        # ㄷ. 들은 말이 큐에 들어갑니다
        r = _json.loads(await post("/heard", "다음".encode()))
        s.check("들은 것을 되돌려줍니다", r.get("text"), "다음")
        s.check("길이도 알려줍니다", "secs" in r, True)
        s.check("큐에 들어갔습니다", hand.said.qsize(), 1)

        # ㄹ. ear_loop 가 꺼내서 **버튼과 같은 자리**로 흘려보냅니다
        hand.action = None
        loop_task = asyncio.ensure_future(guide.ear_loop({}, hand, None))
        try:
            await asyncio.sleep(0.3)
            s.check("'다음' 은 '다음' 버튼과 같은 자리로 갑니다",
                    hand.action, "go")

            hand.said.put_nowait("앉아")
            await asyncio.sleep(0.3)
            s.check("'앉아' 는 메뉴와 같은 자리로 갑니다",
                    hand.jobs.get_nowait(), "sit")

            hand.action = None
            hand.said.put_nowait("멈춰")
            await asyncio.sleep(0.3)
            s.check("'멈춰' 는 '멈춤' 버튼과 같은 자리로 갑니다",
                    hand.action, "stop")

            # ★ 모르는 말에 아무 일도 안 일어나야 합니다 ★
            #   방문객이 지나가며 한 말이 명령이 되면 안 됩니다.
            hand.action = None
            hand.said.put_nowait("오늘 날씨가 좋네요")
            await asyncio.sleep(0.3)
            s.check("모르는 말은 흘려보냅니다", hand.action, None)
            s.check("모르는 말로 일감이 생기지도 않습니다",
                    hand.jobs.qsize(), 0)
        finally:
            loop_task.cancel()
            hand.ear = None

        # ㅁ. ★ 본문을 다 읽었는가 — 그 다음 요청이 멀쩡한가 ★
        #     안 읽은 본문이 남으면 다음 readline 이 소리 조각을
        #     요청 줄로 읽습니다. 그러면 조종이 먹통이 됩니다.
        #     같은 연결을 쓰는지까지는 여기서 못 보지만, 서버가
        #     어긋나지 않았다는 것은 볼 수 있습니다.
        hand.ear = fake_ear
        await post("/heard", "다음".encode())
        s.check("소리를 보낸 뒤에도 조종이 됩니다",
                await press("/drive/w"), "ok")
        s.check("소리를 보낸 뒤에도 화면이 옵니다",
                _json.loads(await press("/state")).get("sid") is not None, True)
        await press("/drive/-")
        hand.ear = None
        while not hand.said.empty():
            hand.said.get_nowait()

        # ㅂ. 너무 큰 것은 안 받습니다
        s.check("상한이 정해져 있습니다", remote.MAX_BODY > 0, True)

        # ── 8-2. 배터리 ─────────────────────────────────────
        #
        # ★ 시연에서 정작 아슬아슬했던 것은 이것이었습니다 (30-1) ★
        #   로봇은 bms_state.soc 로 계속 보내주고 있었는데 아무도 안
        #   읽었습니다. 사람은 로봇 옆구리의 초록 점 네 개로 '기색' 만
        #   봤고요 — 한 칸이 25% 인데 준비 목록은 '40% 이상' 을 묻습니다.
        print()
        print("─" * 70)
        print(" 배터리")
        print("─" * 70)
        import common

        class FakeConn:
            """구독만 받아둡니다. 로봇은 없습니다."""

            class _PS:
                def __init__(self):
                    self.fn = None

                def subscribe(self, topic, fn):
                    self.fn = fn

            class _DC:
                def __init__(self):
                    self.pub_sub = FakeConn._PS()

            def __init__(self):
                self.datachannel = FakeConn._DC()

        conn = FakeConn()
        bat = common.Battery(conn)
        s.check("듣기 전에는 모릅니다", bat.percent, None)
        s.check("모를 때는 신선하지도 않습니다", bat.fresh(), False)
        s.check("모를 때는 판단을 안 합니다", bat.enough_for(220), None)

        send = conn.datachannel.pub_sub.fn
        s.check("구독은 붙었습니다", callable(send), True)

        # 로봇이 실제로 보내는 모양 그대로 (dump_low_state.json 에서)
        send({"data": {"bms_state": {"soc": 88, "current": -1541},
                       "power_v": 31.04, "temperature_ntc1": 43}})
        s.check("퍼센트를 읽습니다", bat.percent, 88)
        s.check("볼트도 읽습니다", round(bat.volts, 1), 31.0)
        s.check("쓰는 중인 것도 압니다", bat.current < 0, True)
        s.check("신선합니다", bat.fresh(), True)

        # ★ 이상한 값은 안 받습니다 ★
        #   soc 가 None 이나 255 로 오는 순간이 있을 수 있습니다.
        #   그때 화면이 "255%" 나 "0%" 로 바뀌면, 사람은 배터리가
        #   아니라 프로그램을 의심하게 됩니다.
        send({"data": {"bms_state": {"soc": None}}})
        s.check("None 은 무시합니다", bat.percent, 88)
        send({"data": {"bms_state": {"soc": 255}}})
        s.check("범위 밖도 무시합니다", bat.percent, 88)
        send({"data": {}})
        s.check("빈 메시지도 견딥니다", bat.percent, 88)

        # ★ 끊긴 값을 신선하다고 하면 안 됩니다 ★
        #   배터리는 줄기만 하므로, 멎은 값은 **언제나 낙관적인 쪽으로**
        #   거짓말합니다.
        bat.stamp -= 60
        s.check("오래된 값은 안 믿습니다", bat.fresh(), False)
        s.check("안 믿으면 판단도 안 합니다", bat.enough_for(220), None)
        s.check("그래도 마지막 값은 들고 있습니다", bat.percent, 88)

        # 코스를 돌 만큼 남았는가 — 경고등이 아니라 계기판
        send({"data": {"bms_state": {"soc": 80}}})
        s.check("넉넉하면 된다고 합니다", bat.enough_for(220), True)
        send({"data": {"bms_state": {"soc": 5}}})
        s.check("모자라면 모자란다고 합니다", bat.enough_for(220), False)

        # ★ 남겨둘 몫(RESERVE)을 넘어서 따지는가 ★
        #   처음에는 남은 전부로 따졌습니다. 그러면 25% 남았을 때
        #   "3%짜리 코스 되겠네" 라고 답하는데, 돌고 나면 22% 입니다.
        #   20% 아래로는 안 쓰기로 했으니 거짓말입니다.
        s.check("남겨둘 몫이 정해져 있습니다", common.RESERVE, 20)
        send({"data": {"bms_state": {"soc": common.RESERVE + 2}}})
        s.check("남겨둘 몫 바로 위면 모자랍니다",
                bat.enough_for(600), False)
        send({"data": {"bms_state": {"soc": 99}}})
        s.check("가득 차 있으면 넉넉합니다", bat.enough_for(600), True)

        # ★ 한 바퀴를 적어두는가 ★
        #   이것이 짐작을 잰 값으로 바꾸는 자리입니다.
        real = common.battery_log_path
        tmp = Path(_tempfile.mkdtemp()) / "battery_log.json"
        common.battery_log_path = lambda: tmp
        try:
            s.check("기록이 없으면 잰 값도 없습니다",
                    common.measured_per_minute(), None)
            row = common.log_lap("ai_swe01", 91, 87, 600.0)
            s.check("쓴 만큼을 적습니다", row["used"], 4)
            s.check("분당으로도 적습니다", row["per_minute"], 0.4)
            s.check("한 번으로는 안 씁니다",
                    common.measured_per_minute(), None)
            common.log_lap("ai_swe01", 87, 82, 600.0)
            common.log_lap("ai_swe01", 82, 78, 600.0)
            # 4 + 5 + 4 = 13% / 30분 = 0.4333…
            s.check("세 번 쌓이면 씁니다",
                    round(common.measured_per_minute(), 3), 0.433)

            # ★ 바퀴마다 나눠 세지 않습니다 ★
            #   soc 가 정수라, 3% 짜리 한 바퀴의 분당값에는 ±33% 가
            #   붙습니다. 실제로 잰 두 바퀴가 같은 3% 인데 0.47 과
            #   0.55 로 갈렸습니다. 통째로 세면 그 오차가 묽어집니다.
            #   짧은 판 하나가 전체를 끌고 가지 않는지 봅니다.
            common.log_lap("ai_swe01", 78, 77, 60.0)      # 1% / 1분
            s.check("짧은 판 하나에 안 끌립니다",
                    common.measured_per_minute() < 0.6, True)
            # ★ 셈이 안 되는 것은 안 적습니다 ★
            #   중간에 충전했거나 값을 못 읽었으면 0.0 %/분 같은 것이
            #   섞여 들어갑니다. 그 한 줄이 가운뎃값을 끌어내리면
            #   "아직 넉넉하다" 는 거짓말이 됩니다.
            s.check("충전한 판은 안 적습니다",
                    common.log_lap("x", 50, 60, 600.0), None)
            s.check("모르는 값도 안 적습니다",
                    common.log_lap("x", None, 60, 600.0), None)
            # 셈이 안 되는 판은 파일에 아예 안 들어갔는가 —
            # 값으로 견주면 다른 이유로도 맞을 수 있으니 줄 수를 셉니다.
            s.check("셈이 안 되는 판은 파일에 없습니다",
                    len(_json.loads(tmp.read_text(encoding="utf-8"))), 4)
        finally:
            common.battery_log_path = real

        # 화면이 그 값을 그대로 나릅니다
        hand.flag(battery=17, battery_stale=False, battery_note="시험")
        got = _json.loads(await press("/state"))["flags"]
        s.check("화면까지 갑니다", got["battery"], 17)
        s.check("끊김 표시도 갑니다", got["battery_stale"], False)
        s.check("한 줄 설명도 갑니다", got["battery_note"], "시험")
        hand.flag(battery=None, battery_stale=False, battery_note="")
        s.check("처음에는 비어 있습니다",
                hand.state["flags"]["battery"], None)

        # ── 9. 인사 뒤에 다시 세우는가 ──────────────────────
        #
        # ★ 왜 이걸 지키는가 ★
        #   안내 끝에서만 로봇이 철푸덕 주저앉았습니다. 범인은 인사
        #   였습니다 — Hello 가 로봇을 '서 있지 않은' 자세로 남기는데
        #   우리 상태 기계는 여전히 서 있다고 믿어서, 다음 엎드리기의
        #   stand() 가 "이미 서 있습니다" 하고 건너뛰었습니다.
        #
        #       그냥        1.6초
        #       인사 뒤     0.5초    ← 세 번 다
        #
        #   고친 뒤로도 이 한 줄이 지워지면 조용히 되돌아옵니다.
        #   로봇 없이 지킬 수 있는 자리라 여기서 지킵니다.
        print()
        print("─" * 70)
        print(" 인사 뒤에 '서 있다' 는 믿음을 버리는가")
        print("─" * 70)
        import common

        # __init__ 을 건너뜁니다 — disturbed 는 walk_ready 만 만지고,
        # 진짜 Posture 를 만들려면 연결이 필요합니다.
        posture = common.Posture.__new__(common.Posture)
        posture.state = "stand"
        posture.walk_ready = True
        posture.disturbed("인사")
        s.check("인사 뒤에는 믿음을 버립니다", posture.walk_ready, False)
        s.check("자세 이름은 그대로입니다 (엎드린 건 아니니까)",
                posture.state, "stand")

        sent = []

        async def fake_sport(conn, cmd, *a, **kw):
            sent.append(cmd)

        class FakeTimer:
            async def run(self, name, coro):
                return await coro

        posture.walk_ready = True
        real_sport, common.sport = common.sport, fake_sport
        try:
            await guide._gesture({"conn": None, "posture": posture},
                                 "hello", FakeTimer())
        finally:
            common.sport = real_sport
        s.check("인사 명령이 나갑니다", sent, ["Hello"])
        s.check("안내의 인사도 다시 세우기를 예약합니다",
                posture.walk_ready, False)

        # ── 10. 조종판은 그대로입니다 ───────────────────────
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
