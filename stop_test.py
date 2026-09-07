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

    1. 기다리는 중에 '멈춤' → 아무 일도 없어야 합니다.
       (예전에는 이것이 wait() 를 빠져나가 구간을 처음부터 돌렸습니다)
    2. 하는 중에 '멈춤'   → wait_stop() 이 바로 받아야 합니다.
    3. '안내 종료' 는 기다리는 중에도 살아 있어야 합니다.
    4. 흘려보낸 '멈춤' 은 hits 를 올리면 안 됩니다.
    5. 기다리는 중에 눌린 '멈춤' 이 다음 구간에서 터지면 안 됩니다.

  쓰는 법

      .\\run stop_test.py

    ★ 로봇에 연결하지 않습니다. 켜져 있지 않아도 됩니다 ★
"""

import asyncio
import sys
import urllib.request

import remote

PORT = 8791          # 진짜 리모컨(8080)과 겹치지 않게


def push(path):
    """휴대폰이 누르는 것과 같은 요청을 보냅니다."""
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}",
                                data=b"", timeout=3) as r:
        return r.read().decode()


async def press(path):
    """서버는 같은 루프에 있습니다 — 요청은 다른 실에서 보냅니다."""
    return await asyncio.to_thread(push, path)


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

        for job in ("stand", "sit", "lie"):
            body = await press(f"/job/{job}")
            s.check(f"설명 중에는 '{job}' 을 받지 않습니다", body, "idle")
        s.check("다리 쓰는 것은 하나도 안 들어왔습니다", hand.jobs.qsize(), 0)

        for job in ("light_on", "light_off"):
            body = await press(f"/job/{job}")
            s.check(f"설명 중에도 '{job}' 은 됩니다", body, "ok")
        s.check("라이트 둘은 들어왔습니다", hand.jobs.qsize(), 2)

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
        for job in ("stand", "sit", "lie"):
            body = await press(f"/job/{job}")
            s.check(f"기다릴 때는 '{job}' 이 됩니다", body, "ok")
        s.check("셋 다 들어왔습니다", hand.jobs.qsize(), 3)
        s.check("메뉴는 '다음' 을 대신하지 않습니다", waiter.done(), False)
        waiter.cancel()

        # ── 6. 조종판은 그대로입니다 ────────────────────────
        print()
        print("─" * 70)
        print(" 조종판")
        print("─" * 70)
        await press("/drive/w")
        s.check("앞으로 신호가 잡힙니다", hand.stick(), remote.DRIVE["w"])
        await asyncio.sleep(remote.DEADMAN + 0.1)
        s.check("손을 떼면(소식이 끊기면) 멈춥니다", hand.stick(), None)

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
