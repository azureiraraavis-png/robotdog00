# -*- coding: utf-8 -*-
"""로봇이 줄 수 있는 것을 전부 물어보고, 오는 것을 다 셉니다.
   ★ 로봇은 움직이지 않습니다 ★

  ★ 왜 이게 필요한가 ★

    sense_check.py 는 제가 **골라둔 17개**만 들었습니다. 그리고 라이다
    점이 안 오자 이름을 짐작하기 시작했습니다 — 스위치에 뭘 보낼지
    네 번, 절약 모드가 범인일 거라고 한 번. 다 틀렸습니다.

    그런데 물어본 적이 없는 것이 있습니다. **로봇이 실제로 무엇을
    보내줄 수 있는가.**

    라이브러리의 subscribe() 는 로봇에게 "이거 보내줘" 라고 진짜로
    말합니다 (SUBSCRIBE 메시지를 띄웁니다). 즉 안 물어본 것은 안 옵니다.
    17개만 물어봤으니 나머지 32개는 **한 번도 청한 적이 없습니다.**

    그래서 이번에는 아는 것을 전부 청하고, 데이터 채널로 들어오는
    **모든** 메시지를 셉니다. 점구름이 다른 이름으로 나오고 있다면
    여기서 잡힙니다. 짐작이 아니라 목록으로요.

  ★ 어떻게 다 보는가 ★

    라이브러리의 메시지는 전부 한 곳을 지나갑니다 —
    pub_sub.run_resolve(). 글자든 이진이든, 라이다든 배터리든 거기로
    모입니다 (webrtc_datachannel.py 의 on_message 가 그렇게 부릅니다).

    그 자리에 세는 눈을 하나 얹습니다. 원래 하던 일은 그대로 합니다.

  ★ 두 번 봅니다 ★

    통신량 절약 모드를 풀기 전과 푼 뒤를 나눠 셉니다. 푼 뒤에만
    나타나는 것이 있으면 그게 절약 모드가 막던 것입니다.

  ★ 되돌립니다 ★

    공용 기체입니다. 청한 것은 물리고, 절약 모드는 도로 켭니다.

  쓰는 법

      .\\run topics_seen.py                 각 12초씩
      .\\run topics_seen.py --seconds 20    더 오래
      .\\run topics_seen.py --save          처음 받은 것을 seen/ 에 남깁니다
"""

import argparse
import asyncio
import json
from pathlib import Path

import common

try:
    from unitree_webrtc_connect.constants import RTC_TOPIC
except ImportError as e:                       # pragma: no cover
    raise SystemExit(f"unitree_webrtc_connect 를 못 읽었습니다: {e}")

HERE = Path(__file__).parent

# 이름에 이런 말이 들어 있으면 눈여겨봅니다 — 우리가 찾는 것들입니다.
INTERESTING = ("lidar", "voxel", "cloud", "map", "odom", "slam", "pose", "point")


class Spy:
    """지나가는 것을 다 셉니다. 원래 하던 일은 안 건드립니다.

    ★ 왜 가로채는가 ★
      subscribe() 는 **우리가 이름을 아는 것만** 받습니다. 이름을
      모르는 것이 오면 조용히 버려집니다. 그러면 '안 온다' 와
      '왔는데 우리가 안 받았다' 를 구별할 수 없습니다.
    """

    def __init__(self, conn):
        self.pub_sub = conn.datachannel.pub_sub
        self.original = self.pub_sub.run_resolve
        self.phase = "before"
        self.counts = {}        # 주제 → {"before": n, "after": n}
        self.sample = {}        # 주제 → 처음 받은 것
        self.pub_sub.run_resolve = self._watch

    def _watch(self, message):
        try:
            topic = ""
            if isinstance(message, dict):
                topic = message.get("topic") or f"(주제없음·{message.get('type','?')})"
            else:
                topic = f"(dict 아님·{type(message).__name__})"
            row = self.counts.setdefault(topic, {"before": 0, "after": 0})
            row[self.phase] += 1
            if topic not in self.sample:
                self.sample[topic] = message
        except Exception:
            pass                # 세다가 죽어서 로봇 통신을 막으면 안 됩니다
        return self.original(message)

    def stop(self):
        self.pub_sub.run_resolve = self.original


def posture_now(spy):
    """이 결과를 낼 때 로봇이 어떤 자세였는지.

    ★ 왜 결과지에 자세를 적는가 (2026-09-14) ★

      라이다 점이 안 오는 것을 놓고 짐작을 다섯 번 했습니다. 스위치에
      뭘 보낼지 넷, 절약 모드가 범인이라고 하나. 다 틀렸습니다.

      그동안 **로봇은 계속 엎드려 있었습니다.** 그런데 제 체크리스트에는
      "엎드려 있어도 됩니다" 라고 적혀 있었습니다 — 확인해 본 적 없이
      쓴 안심입니다. 사이안 님이 물어보시기 전까지 아무도 그 줄을
      의심하지 않았습니다.

      실험은 조건을 적어야 실험입니다. 같은 표를 두 번 찍어놓고 어느
      쪽이 선 것이고 어느 쪽이 누운 것인지 모르면, 비교할 수가 없습니다.
    """
    message = spy.sample.get("rt/lf/sportmodestate")
    if not isinstance(message, dict):
        return "모름 (동작 상태가 안 왔습니다)"
    h = (message.get("data") or {}).get("body_height")
    if not isinstance(h, (int, float)):
        return "모름 (몸높이가 없습니다)"
    # 실측: 완전히 선 상태 0.31, 엎드림 0.08 (StateProbe.STANDING = 0.24)
    how = "서 있음" if h >= 0.24 else ("엎드림" if h < 0.15 else "중간")
    return f"몸높이 {h:.3f} m — {how}"


def describe(message):
    """모양만 한 줄로. 값이 아니라 어떤 항목이 들었는지."""
    if not isinstance(message, dict):
        return type(message).__name__
    data = message.get("data", message)
    if isinstance(data, str):
        return f"글자 {len(data)}자"
    if isinstance(data, (bytes, bytearray)):
        return f"{len(data)}바이트"
    if isinstance(data, (list, tuple)):
        return f"[{len(data)}개]"
    if not isinstance(data, dict):
        return type(data).__name__
    bits = []
    for k, v in list(data.items())[:5]:
        if isinstance(v, (list, tuple)):
            bits.append(f"{k}[{len(v)}]")
        elif isinstance(v, (bytes, bytearray)):
            bits.append(f"{k}:{len(v)}B")
        elif isinstance(v, dict):
            bits.append(f"{k}{{}}")
        else:
            bits.append(k)
    more = "…" if len(data) > 5 else ""
    return "{" + ", ".join(bits) + more + "}"


async def main():
    ap = argparse.ArgumentParser(description="로봇이 보내는 것을 전부 셉니다")
    ap.add_argument("--seconds", type=float, default=12.0,
                    help="단계마다 몇 초 (기본 12)")
    ap.add_argument("--save", action="store_true",
                    help="처음 받은 것을 seen/ 에 남깁니다")
    args = ap.parse_args()

    print("=" * 74)
    print(" 로봇이 무엇을 보내는가 — 아는 것을 전부 청해봅니다")
    print("=" * 74)
    print(" ※ 로봇은 움직이지 않습니다. 듣기만 하고, 절약 모드만 잠깐 풉니다.")
    print()

    conn = await common.connect()
    if conn is None:
        print(" ✖ 못 붙었습니다.")
        return 1

    spy = None
    asked = []
    freed = False
    try:
        spy = Spy(conn)

        # ── 아는 것을 전부 청합니다 ─────────────────────────
        for key, topic in sorted(RTC_TOPIC.items()):
            try:
                conn.datachannel.pub_sub.subscribe(topic)
                asked.append(topic)
            except Exception:
                pass
        print(f" {len(asked)}가지를 청했습니다 (17가지만 듣던 것에서 늘렸습니다).")
        print()

        print(f" [1단계] 절약 모드 그대로 — {args.seconds:.0f}초")
        await asyncio.sleep(args.seconds)
        posture = posture_now(spy)
        print(f"         이때 자세: {posture}")

        print(" [2단계] 절약 모드를 풉니다")
        try:
            await asyncio.wait_for(
                conn.datachannel.disableTrafficSaving(True), timeout=10.0)
            freed = True
        except Exception as e:
            print(f"         ✖ 못 풀었습니다 — {type(e).__name__}")
        spy.phase = "after"
        await asyncio.sleep(args.seconds)
        print()

        # ── 결과 ────────────────────────────────────────────
        known = {v: k for k, v in RTC_TOPIC.items()}
        rows = sorted(spy.counts.items(),
                      key=lambda kv: -(kv[1]["before"] + kv[1]["after"]))

        print("=" * 74)
        print(f" 자세: {posture}   ← ★ 이 표는 이 자세에서 나온 것입니다 ★")
        print("      선 자세로도 한 번 더 찍어서 견줘보세요.")
        print("-" * 74)
        print(f" {'주제':44} {'전':>6} {'후':>6}  모양")
        print("-" * 74)
        for topic, n in rows:
            name = known.get(topic, topic)
            star = "★" if any(w in topic.lower() for w in INTERESTING) else " "
            new = "☆" if n["before"] == 0 and n["after"] else " "
            shape = describe(spy.sample.get(topic))[:22]
            print(f"{star}{new}{name[:42]:42} {n['before']:>6} {n['after']:>6}  {shape}")
        print("=" * 74)
        print(" ★ 우리가 찾는 갈래 (라이다·지도·위치)   ☆ 절약 모드를 푼 뒤에만 온 것")
        print()

        silent = [known.get(t, t) for t in asked if t not in spy.counts]
        print(f" 청했는데 한 번도 안 온 것: {len(silent)}가지")
        if silent:
            print("   " + ", ".join(sorted(silent)[:14]))
            if len(silent) > 14:
                print(f"   … 그 밖에 {len(silent) - 14}가지")
        print()

        if args.save:
            out = HERE / "seen"
            out.mkdir(exist_ok=True)
            for topic, message in spy.sample.items():
                safe = topic.replace("/", "_").replace("(", "").replace(")", "") or "empty"
                try:
                    (out / f"{safe}.json").write_text(
                        json.dumps(message, ensure_ascii=False, indent=2,
                                   default=str)[:200000],
                        encoding="utf-8")
                except Exception:
                    pass
            print(f" seen/ 에 {len(spy.sample)}개를 남겼습니다.")
            print()

        hits = [t for t in spy.counts
                if any(w in t.lower() for w in ("voxel", "cloud", "point"))]
        if hits:
            print(" ★ 점구름으로 보이는 것이 있습니다:")
            for t in hits:
                print(f"     {t} — {describe(spy.sample[t])}")
        else:
            print(" ✖ 점구름으로 보이는 주제가 하나도 안 왔습니다.")
            print("   라이브러리가 아는 이름 전부를 청했는데도요.")
            print("   → 이 기체는 이 통로로 점을 안 줍니다. 이름 문제가 아닙니다.")
        return 0
    finally:
        if spy:
            spy.stop()
        # ★ 청한 것은 물립니다 ★ 공용 기체입니다.
        for topic in asked:
            try:
                conn.datachannel.pub_sub.unsubscribe(topic)
            except Exception:
                pass
        if freed:
            try:
                await asyncio.wait_for(
                    conn.datachannel.disableTrafficSaving(False), timeout=10.0)
            except Exception:
                print(" ※ 절약 모드를 못 되돌렸습니다. 로봇을 껐다 켜면 돌아갑니다.")
        await common.disconnect(conn)


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
