# -*- coding: utf-8 -*-
"""라이다 점구름을 받아 봅니다.  ★ 로봇은 움직이지 않습니다 ★

  ★ 무엇이 막고 있었는가 ★

    2026-09-14. 라이다 점이 한 개도 안 왔습니다. 그런데 라이다 상태
    메시지를 열어보니 이렇게 적혀 있었습니다.

        sys_rotation_speed  10785.5      돌고 있습니다
        cloud_frequency     13.9 Hz      초당 13.9번 만듭니다
        cloud_size          21275        한 번에 2만 1천 개
        error_state         0            이상 없음

    **라이다는 점을 만들고 있었습니다.** 우리에게만 안 온 것입니다.

    막은 것은 라이다가 아니라 **관**이었습니다. 데이터 채널에 통신량
    절약 모드가 걸려 있고, 그게 굵은 것을 흘려보내지 않습니다. 그래서
    rt/utlidar/switch 에 무엇을 보내든 소용이 없었습니다 —
    ★ 네 번 두드리고 네 번 다 틀렸습니다 ★

    답은 라이브러리 제 주석에 적혀 있었습니다.

        #Should turn it on when subscribed to ulidar topic
        async def disableTrafficSaving(self, switch: bool):

    라이다 상태를 5Hz 로 받으면서 **한 번도 안 열어본 것**이 이번의
    교훈입니다. 오는 것을 세기만 하고 안을 안 봤습니다.

  ★ 순서가 있습니다 ★

    주석이 "구독한 뒤에 켜라" 고 말합니다. 그래서 —

      1. 먼저 구독합니다
      2. 아무것도 안 하고 들어봅니다 (안 오는 것을 확인해야 켜진 것을 압니다)
      3. 절약 모드를 풉니다
      4. 다시 들어봅니다
      5. 그래도 없으면 그때 라이다 스위치도 건드려 봅니다

  ★ 끝나면 되돌립니다 ★

    공용 기체입니다. 절약 모드는 켜져 있던 것이니 도로 켭니다.
    켠 채로 두려면 --keep 을 주세요.

  쓰는 법

      .\\run lidar_on.py              받아보고, 확인하고, 되돌립니다
      .\\run lidar_on.py --keep       풀어둔 채로 둡니다
      .\\run lidar_on.py --seconds 10 더 오래 기다립니다
"""

import argparse
import asyncio

import common

try:
    from unitree_webrtc_connect.constants import RTC_TOPIC
except ImportError as e:                       # pragma: no cover
    raise SystemExit(f"unitree_webrtc_connect 를 못 읽었습니다: {e}")


class Points:
    """점이 오는지 셉니다. 두 주제를 같이 봅니다."""

    def __init__(self, conn):
        self.count = 0
        self.sample = None
        self.which = None
        for key in ("ULIDAR", "ULIDAR_ARRAY"):
            conn.datachannel.pub_sub.subscribe(
                RTC_TOPIC[key], lambda m, k=key: self._got(k, m))

    def _got(self, key, message):
        self.count += 1
        if self.sample is None:
            self.sample = message
            self.which = key

    def reset(self):
        self.count = 0


def describe(message):
    """받은 점 하나가 어떻게 생겼는지. 값이 아니라 모양만."""
    if not isinstance(message, dict):
        return type(message).__name__
    data = message.get("data", message)
    if not isinstance(data, dict):
        return f"[{len(data)}개]" if isinstance(data, (list, tuple)) else type(data).__name__
    bits = []
    for k, v in list(data.items())[:8]:
        if isinstance(v, (list, tuple)):
            bits.append(f"{k}[{len(v)}]")
        elif isinstance(v, (bytes, bytearray)):
            bits.append(f"{k}:{len(v)}바이트")
        elif isinstance(v, str):
            bits.append(f"{k}:글자{len(v)}")
        elif isinstance(v, dict):
            bits.append(f"{k}{{{len(v)}}}")
        else:
            bits.append(f"{k}={v}")
    return "{" + ", ".join(bits) + "}"


def count_points(message):
    """점이 몇 개나 들었는지 세어 봅니다. 못 세면 None."""
    if not isinstance(message, dict):
        return None
    data = message.get("data", {})
    if not isinstance(data, dict):
        return None
    inner = data.get("data")
    for spot in (inner, data.get("positions"), data.get("points")):
        if isinstance(spot, (list, tuple)):
            return len(spot)
        if isinstance(spot, dict):
            for v in spot.values():
                if isinstance(v, (list, tuple)):
                    return len(v)
    if isinstance(data.get("src_size"), (int, float)):
        return int(data["src_size"])
    return None


async def listen(points, seconds, label):
    points.reset()
    print(f"   {label} … ", end="", flush=True)
    await asyncio.sleep(seconds)
    if points.count:
        print(f"○ {points.count}번 왔습니다")
    else:
        print("✖ 조용합니다")
    return points.count


async def main():
    ap = argparse.ArgumentParser(description="라이다 점구름을 받아 봅니다")
    ap.add_argument("--seconds", type=float, default=6.0,
                    help="단계마다 몇 초 기다릴지 (기본 6)")
    ap.add_argument("--keep", action="store_true",
                    help="끝나도 절약 모드를 도로 켜지 않습니다")
    args = ap.parse_args()

    print("=" * 70)
    print(" 라이다 점구름 받아보기")
    print("=" * 70)
    print(" ※ 로봇은 움직이지 않습니다. 데이터 채널 설정만 건드립니다.")
    print()

    conn = await common.connect()
    if conn is None:
        print(" ✖ 못 붙었습니다.")
        return 1

    freed = False          # 절약 모드를 우리가 풀었는가
    switched = False       # 라이다 스위치를 우리가 건드렸는가
    won = None
    try:
        points = Points(conn)          # ★ 먼저 구독합니다 (주석이 그러랍니다)

        # ── 1. 아무것도 안 하고 ────────────────────────────────
        #   ★ 이게 없으면 채점이 안 됩니다 ★
        #     처음부터 오고 있었다면, 무엇을 해도 "내가 켰다" 가 거짓이 됩니다.
        print(" 손대기 전:")
        if await listen(points, args.seconds, "그대로"):
            print()
            print(" ★ 이미 오고 있습니다. 풀 것이 없습니다.")
            print(f"   {points.which} · {describe(points.sample)}")
            return 0
        print()

        # ── 2. 통신량 절약 모드를 풉니다 ──────────────────────
        print(" 통신량 절약 모드를 풉니다:")
        try:
            ok = await asyncio.wait_for(
                conn.datachannel.disableTrafficSaving(True), timeout=10.0)
            freed = True
            print(f"   보냈습니다 (로봇 대답: {'ok' if ok else '이상함'})")
        except asyncio.TimeoutError:
            print("   ✖ 대답이 없습니다 (10초). 이 기체에는 없는 기능일 수 있습니다.")
        except Exception as e:
            print(f"   ✖ 못 보냈습니다 — {type(e).__name__}: {e}")

        if await listen(points, args.seconds, "푼 뒤"):
            won = "절약 모드를 푸니 왔습니다"
        print()

        # ── 3. 그래도 없으면 라이다 스위치도 ──────────────────
        if not won:
            print(" 라이다 스위치도 켜 봅니다:")
            try:
                conn.datachannel.pub_sub.publish_without_callback(
                    RTC_TOPIC["ULIDAR_SWITCH"], "on")
                switched = True
                print("   보냈습니다 (대답은 안 옵니다 — 원래 그렇습니다)")
            except Exception as e:
                print(f"   ✖ 못 보냈습니다 — {type(e).__name__}: {e}")
            if await listen(points, args.seconds, "켠 뒤"):
                won = "절약 모드 + 라이다 스위치 둘 다 필요합니다"
            print()

        # ── 결과 ──────────────────────────────────────────────
        print("=" * 70)
        if won:
            n = count_points(points.sample)
            print(f" ○ 점이 옵니다 — {won}")
            print()
            print(f"   주제:  {points.which}")
            print(f"   모양:  {describe(points.sample)}")
            if n:
                print(f"   점 수: 한 번에 약 {n:,}개")
            print()
            print("   이제 할 수 있는 것")
            print("     · 옆벽까지의 거리를 로봇이 잽니다 — 줄자가 필요 없습니다")
            print("     · ROBOTODOM 과 합치면 층마다 지도를 쌓을 수 있습니다")
            print("     · 계단을 '앞이 갑자기 낮아지는 곳' 으로 알아볼 수 있습니다")
        else:
            print(" ✖ 아직 안 옵니다.")
            print()
            print("   그런데 라이다는 만들고 있습니다 (cloud_frequency 13.9Hz).")
            print("   그러니 이건 **관** 의 문제입니다. 다음에 볼 자리 —")
            print("     · 이 기체가 WebRTC 로는 점을 안 주는 등급인가")
            print("     · 유니트리 앱에서는 보이는가 (보이면 통로가 따로 있습니다)")
        print("=" * 70)
        return 0 if won else 1
    finally:
        # ★ 우리가 바꾼 것은 우리가 되돌립니다 ★
        #   공용 기체입니다. 다음 사람이 쓰는 상태를 말없이 바꿔놓고
        #   나가면 안 됩니다.
        if not args.keep:
            if switched:
                try:
                    conn.datachannel.pub_sub.publish_without_callback(
                        RTC_TOPIC["ULIDAR_SWITCH"], "off")
                except Exception:
                    pass
            if freed:
                try:
                    await asyncio.wait_for(
                        conn.datachannel.disableTrafficSaving(False), timeout=10.0)
                    print()
                    print(" 절약 모드를 도로 켰습니다. 풀어두려면 --keep 을 주세요.")
                except Exception:
                    print()
                    print(" ※ 절약 모드를 못 되돌렸습니다. 로봇을 껐다 켜면"
                          " 원래대로 돌아갑니다.")
        await common.disconnect(conn)


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
