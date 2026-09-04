# -*- coding: utf-8 -*-
"""
리모컨 버튼 값 실시간 관찰 — 누르는 대로 화면에 뜹니다.

  ★ 로봇에게 아무것도 보내지 않습니다. 듣기만 합니다 ★

  ── 무엇을 찾는가 ──
    게임패드 라벨:  Searchlight Switch = L2 + SELECT

    전방 서치라이트는 **모션 명령이 아니라 컨트롤러 기능**입니다. 그래서
    라이브러리 명령표 어디에도 없습니다. 그런데 우리는 이미 컨트롤러와
    같은 통로를 씁니다 — rt/wirelesscontroller.  joystick() 이 매번
    보내는 메시지에 `keys` 칸이 있고, 지금은 0 으로 비워 둡니다.

    그 칸에 어떤 값이 라이트인지만 알면, 음성 명령에 붙일 수 있습니다.
    "불 켜줘" 로요.

  ── 짐작하지 않습니다 ──
    라벨을 보세요. R1+A 는 **Jump Forward** 입니다. 16비트 중 2비트
    조합이 120가지고 그중 하나가 실내 점프입니다. 배치를 모르는 채로
    값을 만들어 보내는 일은 하지 않습니다.

    대신 컨트롤러가 스스로 말하게 합니다. 누르면 값이 흐르고, 우리는 봅니다.

  ── 1차 시도가 실패한 이유 ──
    두 번 헛돌았습니다.
      1) 버튼을 누르라고 하기 **전에** 3초를 기다리고 "신호 없음" 판정.
         아무도 안 누르는 동안 값이 올 리가 없었습니다.
      2) 그다음엔 8개 버튼 × 4초 강제 대기. 그런데 그때 게임패드는
         **방전되어 로봇과 연결조차 안 되어 있었습니다.**
         실험이 실패한 게 아니라 성립하지 않았습니다.

    그래서 이번엔 묻지 않습니다. 그냥 켜 두고 **누르는 대로 보여줍니다.**
    아무 때나 Ctrl+C 로 끝내면 됩니다.

  ★ 먼저 확인하세요 ★
    게임패드가 **충전되어 있고 로봇과 연결**되어 있어야 합니다.
    확인하는 가장 쉬운 방법: 게임패드로 로봇을 조금 움직여 보세요.
    움직이면 연결된 것이고, 그럼 값도 흐를 것입니다.

  쓰는 법

      .\\run keys_test.py            90초 동안 관찰 (Ctrl+C 로 언제든 종료)
      .\\run keys_test.py 300        시간을 늘려서

    눌러볼 것 (전부 로봇을 움직이지 않습니다)
      L2 · SELECT · X · Y · A · B  를 하나씩
      그다음 ★ L2 + SELECT ★ — 라이트가 켜질 것입니다

    값이 뜨면 무엇을 눌렀는지 함께 적어두세요. 그 짝이 곧 배치표입니다.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from unitree_webrtc_connect.constants import RTC_TOPIC

import common

LOG = Path(__file__).parent / "keys_log.txt"
DEFAULT_SECONDS = 90.0
QUIET_NOTE = 8.0        # 이만큼 조용하면 한 줄 알려줍니다 (초)


def bits(value):
    """켜진 비트를 사람이 읽게. 0x0028 → '0x0008 + 0x0020'"""
    on = [1 << i for i in range(16) if value & (1 << i)]
    return " + ".join(f"0x{b:04X}" for b in on) if on else "—"


class Monitor:
    """두 곳을 동시에 듣습니다. 보내지 않습니다."""

    def __init__(self, conn):
        self.rows = []          # (경과초, 출처, 값)
        self.last = {}
        self.heard = set()
        self.started = time.time()
        self.quiet_since = time.time()

        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["WIRELESS_CONTROLLER"], self._on_wireless)
        conn.datachannel.pub_sub.subscribe(
            RTC_TOPIC["LOW_STATE"], self._on_lowstate)

    def _note(self, source, keys):
        if self.last.get(source) == keys:
            return
        self.last[source] = keys
        t = time.time() - self.started
        self.rows.append((t, source, keys))
        self.quiet_since = time.time()
        mark = "  ← 무언가 눌렸습니다" if keys else "  (뗌)"
        print(f"  {t:6.1f}초  [{source:9}]  0x{keys:04X} ({keys:5d})"
              f"   {bits(keys):28}{mark}")

    def _on_wireless(self, message):
        self.heard.add("wirelesscontroller")
        data = message.get("data")
        if isinstance(data, dict) and data.get("keys") is not None:
            self._note("wireless", int(data["keys"]))

    def _on_lowstate(self, message):
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
            self._note("lowstate", raw[2] | (raw[3] << 8))

    def pressed(self):
        """0 이 아닌, 실제로 눌린 값들."""
        return sorted({k for _t, _s, k in self.rows if k})


async def run(conn, seconds):
    print("=" * 74)
    print(" 리모컨 버튼 값 실시간 관찰")
    print("=" * 74)
    print(" ★ 로봇에게 아무것도 보내지 않습니다 ★")
    print()
    print(" 눌러보세요 (전부 로봇을 움직이지 않습니다):")
    print("   L2 · SELECT · X · Y · A · B  를 하나씩")
    print("   그다음  ★ L2 + SELECT ★  — 라이트가 켜질 것입니다")
    print()
    print(" ⚠ R1+A 는 앞으로 점프입니다. 누르지 마세요.")
    print()
    print(f" {seconds:.0f}초 동안 봅니다. 다 됐으면 Ctrl+C.")
    print("-" * 74)

    mon = Monitor(conn)
    deadline = time.time() + seconds
    try:
        while time.time() < deadline:
            await asyncio.sleep(0.3)
            quiet = time.time() - mon.quiet_since
            if quiet > QUIET_NOTE:
                left = deadline - time.time()
                if not mon.rows:
                    print(f"       …아직 아무 값도 안 옵니다 "
                          f"(남은 {left:.0f}초)  ← 게임패드가 로봇과 "
                          f"연결되어 있는지 확인해 주세요")
                mon.quiet_since = time.time()
    except KeyboardInterrupt:
        print("\n  (끝냅니다)")

    # ── 정리 ──
    print("-" * 74)
    lines = ["=" * 74, " 본 값들", "=" * 74]
    if not mon.heard:
        lines.append(" 두 토픽 어디에서도 메시지가 오지 않았습니다.")
    else:
        lines.append(f" 메시지가 온 곳: {', '.join(sorted(mon.heard))}")

    got = mon.pressed()
    if got:
        lines.append("")
        lines.append(" 눌린 값 (누른 순서대로):")
        for t, src, k in mon.rows:
            if k:
                lines.append(f"   {t:6.1f}초  0x{k:04X} ({k:5d})   "
                             f"{bits(k)}   [{src}]")
        lines.append("")
        lines.append(" ★ 무엇을 눌렀는지 옆에 적어두세요 ★")
        lines.append("   그 짝이 배치표입니다. 두 비트가 켜진 값이 L2+SELECT 입니다.")
        singles = [k for k in got if bin(k).count("1") == 1]
        doubles = [k for k in got if bin(k).count("1") == 2]
        if singles:
            lines.append(f"   한 비트짜리: {', '.join(f'0x{k:04X}' for k in singles)}")
        if doubles:
            lines.append(f"   두 비트짜리: {', '.join(f'0x{k:04X}' for k in doubles)}"
                         f"   ← 조합키. 라이트가 이 안에 있습니다")
    elif mon.heard:
        lines.append("")
        lines.append(" 메시지는 오는데 버튼 값은 0 뿐이었습니다.")
        lines.append(" 이 토픽에는 버튼이 안 실리거나, 컨트롤러가 로봇에")
        lines.append(" 연결되어 있지 않은 것입니다.")
        lines.append("")
        lines.append(" 확인하는 법: 게임패드로 로봇을 조금 움직여 보세요.")
        lines.append(" 안 움직이면 연결이 안 된 것이고, 그러면 이 실험은 성립하지 않습니다.")

    for l in lines:
        print(l)
    LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{LOG.name} 에 저장했습니다.")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    seconds = float(args[0]) if args else DEFAULT_SECONDS

    conn = await common.connect()
    try:
        await run(conn, seconds)
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
