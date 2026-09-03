# -*- coding: utf-8 -*-
"""
리모컨 버튼 배치 알아내기 — 리모컨이 스스로 가르쳐주게 합니다.

  ★ 이 스크립트는 로봇에게 아무것도 보내지 않습니다 (듣기만 합니다) ★

  ── 왜 필요한가 ──
    리모컨 라벨:

        Function            Button
        Searchlight Switch  L2 + SELECT
        Avoidance ON        X
        Avoidance OFF       Y (3초 길게)
        Buzzer Switch       F1 (세 번)

    전방 라이트는 **모션 명령이 아니라 리모컨 기능**입니다. 그래서 VUI 를
    아무리 찔러도 안 나왔고, 라이브러리 어디에도 라이트 명령이 없습니다.

    그런데 우리는 이미 리모컨과 같은 통로를 씁니다 — rt/wirelesscontroller.
    joystick() 이 매번 보내는 메시지에 **`keys` 칸이 있고 0 으로 비워 둡니다.**
    버튼은 거기에 실립니다.

  ── 짐작하지 않습니다 ──
    "L2 는 0x20 이겠지" 하고 만들어 보내면 안 됩니다. 라벨을 보세요 —
    R1+A 는 **Jump Forward** 입니다. 비트를 잘못 짚으면 실내에서 뜁니다.
    그래서 리모컨에게 물어봅니다.

  ── 1차 실패에서 배운 것 ──
    처음에는 "3초 동안 신호가 오나" 를 먼저 확인하고, 안 오면 멈추게
    했습니다. 그런데 그 3초 동안 **아무도 버튼을 안 누르고 있었습니다.**
    리모컨은 눌릴 때만 값을 보내는 듯한데, 눌러보라고 하기도 전에
    포기한 것입니다. 관측 도구가 관측 대상을 막고 있었습니다.

    이번에는 먼저 눌러보게 하고, 끝까지 아무것도 못 들었을 때만 그렇게
    보고합니다. 그리고 **듣는 곳을 두 군데로** 늘렸습니다.
        rt/wirelesscontroller        — 조이스틱과 같은 통로
        rt/lf/lowstate 의 원본 바이트 — 리모컨 패킷이 통째로 실려 옵니다

  쓰는 법

      .\\run keys_test.py

    ★ 리모컨 전원을 켜고 로봇과 연결된 상태여야 합니다 ★
    시키는 버튼만 누르세요 — 전부 로봇을 움직이지 않는 것들입니다.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from unitree_webrtc_connect.constants import RTC_TOPIC

import common

MAP_FILE = Path(__file__).parent / "keys_map.json"
LOG = Path(__file__).parent / "keys_test_log.txt"

# 눌러볼 버튼. ★ 전부 로봇을 움직이지 않는 것들입니다 ★
ASK = [
    ("아무거나", "아무 버튼이나 몇 번 눌러보세요 — 듣기가 되는지부터 봅니다"),
    ("L2", "왼쪽 뒤 큰 버튼 L2 를 누른 채로"),
    ("SELECT", "SELECT 를 누른 채로"),
    ("X", "X 를 누른 채로  (회피 켜기 — 움직이지 않습니다)"),
    ("Y", "Y 를 누른 채로  (회피 끄기)"),
    ("A", "A 를 누른 채로"),
    ("B", "B 를 누른 채로"),
    ("L2+SELECT", "★ L2 와 SELECT 를 함께 — 라이트가 켜질 것입니다 ★"),
]

WATCH = 4.0        # 한 버튼당 지켜보는 시간 (초)


class Ears:
    """리모컨 상태를 듣습니다. 두 군데를 동시에. 보내지는 않습니다."""

    def __init__(self, conn):
        self.seen = []          # (시각, 출처, keys 값)
        self.raw = []           # (시각, 원본 바이트 hex)
        self.last = {}
        self.heard = set()      # 어느 토픽에서 메시지가 오긴 했는가

        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["WIRELESS_CONTROLLER"], self._on_wireless)
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["LOW_STATE"], self._on_lowstate)

    def _note(self, source, keys):
        if self.last.get(source) == keys:
            return
        self.last[source] = keys
        self.seen.append((time.time(), source, int(keys)))

    def _on_wireless(self, message):
        self.heard.add("wirelesscontroller")
        data = message.get("data")
        if isinstance(data, dict) and data.get("keys") is not None:
            self._note("wireless", int(data["keys"]))

    def _on_lowstate(self, message):
        """lowstate 안에 리모컨 패킷이 통째로 실려 옵니다.

        이름이 펌웨어마다 조금씩 다릅니다 (wireless_remote / wirelessRemote).
        버튼은 보통 3~4번째 바이트에 16비트로 들어 있습니다. 하지만
        **그것조차 짐작하지 않습니다** — 원본을 그대로 찍어두고,
        눌렀을 때 어느 바이트가 변하는지 눈으로 봅니다.
        """
        self.heard.add("lowstate")
        data = message.get("data")
        if not isinstance(data, dict):
            return
        blob = (data.get("wireless_remote") or data.get("wirelessRemote")
                or data.get("wireless_remote_data"))
        if not blob:
            return
        try:
            raw = bytes(int(b) & 0xFF for b in blob)
        except (TypeError, ValueError):
            return
        if len(raw) >= 4:
            keys = raw[2] | (raw[3] << 8)          # 흔한 배치. 확인은 눈으로.
            self._note("lowstate", keys)
        hexed = raw[:8].hex(" ")
        if not self.raw or self.raw[-1][1] != hexed:
            self.raw.append((time.time(), hexed))

    def collect(self, since):
        """since 이후에 본 0 이 아닌 값들. {출처: [값...]}"""
        out = {}
        for t, src, k in self.seen:
            if t >= since and k:
                out.setdefault(src, []).append(k)
        return out

    def raw_since(self, since):
        return [h for t, h in self.raw if t >= since]


def bits(value):
    on = [1 << i for i in range(16) if value & (1 << i)]
    return " + ".join(f"0x{b:04X}" for b in on) if on else "—"


async def run(conn):
    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    ears = Ears(conn)
    await asyncio.sleep(1.0)

    out("=" * 72)
    out(" 리모컨 버튼 배치 알아내기")
    out("=" * 72)
    out(" ★ 로봇에게 아무것도 보내지 않습니다. 듣기만 합니다 ★")
    out(" ★ 리모컨 전원이 켜져 있어야 합니다 ★")
    out()

    found = {}
    for name, how in ASK:
        print("-" * 72)
        print(f" [{name}]  {how}")
        input(f"     Enter 를 누르고, {WATCH:.0f}초 동안 버튼을 누르고 계세요: ")
        start = time.time()
        print(f"     {WATCH:.0f}초 동안 봅니다...")
        await asyncio.sleep(WATCH)

        got = ears.collect(start)
        raws = ears.raw_since(start)

        if not got:
            note = ""
            if raws:
                note = f"   (원본은 바뀌었습니다: {' | '.join(raws[:3])})"
            out(f" {name:12} — 값이 안 잡혔습니다{note}")
            continue

        # 두 출처 중 비트가 가장 많이 켜진 값을 대표로
        best_src, best = None, 0
        for src, vals in got.items():
            v = max(vals, key=lambda x: bin(x).count("1"))
            if bin(v).count("1") > bin(best).count("1"):
                best_src, best = src, v
        if name != "아무거나":
            found[name] = best
        out(f" {name:12} = 0x{best:04X} ({best})   {bits(best)}   [{best_src}]")

    # ── 정리 ──
    out()
    out("=" * 72)
    out(" 정리")
    out("=" * 72)

    if not ears.heard:
        out(" ★ 두 토픽 어디에서도 메시지가 오지 않았습니다 ★")
        out("   리모컨 전원이 꺼져 있었거나, 이 펌웨어가 리모컨 상태를")
        out("   내보내지 않는 것입니다.")
        out("   후자라면 이 방법으로는 배치를 알 수 없습니다. 짐작해서 보내는")
        out("   것은 하지 않습니다 — R1+A 가 Jump Forward 입니다.")
    else:
        out(f" 메시지가 온 곳: {', '.join(sorted(ears.heard))}")

    combo = found.get("L2+SELECT")
    l2, sel = found.get("L2"), found.get("SELECT")
    if combo:
        out()
        out(f" 전방 라이트 = keys 0x{combo:04X} ({combo})")
        if l2 and sel:
            expect = l2 | sel
            ok = "맞습니다" if expect == combo else "★ 단순 OR 가 아닙니다 ★"
            out(f"   L2(0x{l2:04X}) | SELECT(0x{sel:04X}) = 0x{expect:04X}  → {ok}")
        out()
        out(" 이 값을 joystick() 의 keys 에 실으면 리모컨을 누른 것과 같습니다.")
        out(" 다만 **한 번 보내고 바로 0 으로 돌려야** 합니다 — 계속 눌린 것으로")
        out(" 보이면 토글이 계속 뒤집힙니다.")
    elif ears.heard:
        out()
        out(" L2+SELECT 값을 못 잡았습니다.")
        out(" 잡힌 값이 있다면 그것만이라도 보여주세요 — 배치를 읽어보겠습니다.")

    if found:
        MAP_FILE.write_text(json.dumps(found, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        out(f"\n {MAP_FILE.name} 에 저장했습니다.")

    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{LOG.name} 에 저장했습니다.")


async def main():
    print("=" * 72)
    print(" 리모컨 버튼 배치 알아내기  ★ 듣기만 합니다 ★")
    print("=" * 72)
    print(" 로봇은 엎드려 있어도 됩니다. 시키는 버튼만 누르세요 —")
    print(" 전부 로봇을 움직이지 않는 것들입니다.")
    print()

    conn = await common.connect()
    try:
        await run(conn)
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
