# -*- coding: utf-8 -*-
"""로봇이 무엇을 말해주는지 듣기만 합니다.  ★ 로봇은 움직이지 않습니다 ★

  ★ 왜 이것부터인가 ★

    8층 정찰견 계획은 두 가지에 달려 있습니다 —

      · 로봇이 **주변을 재서** 알려주는가 (라이다·거리)
      · 로봇이 **지도를 스스로 만드는가** (SLAM·매핑 서비스)

    그런데 우리가 쓰는 라이브러리(unitree_webrtc_connect)의 주제 목록에는
    이미 이런 것들이 **이름만** 올라와 있습니다.

        ULIDAR  GRID_MAP  ROBOTODOM  SLAM_ODOMETRY
        LIDAR_MAPPING_PCD_FILE  LIDAR_NAVIGATION_GLOBAL_PATH ...

    ★ 이름이 있다는 것과 우리 기체가 대답한다는 것은 다릅니다 ★

      유니트리의 SLAM·내비게이션은 상위 등급 기능일 수 있습니다. 저수준
      제어 때와 똑같은 모양의 질문인데, **이번에는 듣기만 해도 답이
      나옵니다.** 시도가 곧 위험이었던 그쪽과 다릅니다.

    이 한 장이 정할 것 —

      지도가 오면   유니트리 것을 받아 쓰면 됩니다
      안 오면       ULIDAR + ROBOTODOM 으로 우리가 만들어야 합니다
      둘 다 없으면  지도 이야기는 처음부터 다시입니다

  ★ 대조군을 같이 봅니다 ★

    맨 위에 LOW_STATE 를 넣었습니다. 이건 **이미 되는 것**입니다 —
    배터리 표시가 그걸로 돕니다.

    이게 ✖ 로 나오면 나머지 ✖ 는 아무 뜻이 없습니다. 로봇이 조용한 게
    아니라 **제 듣는 코드가 틀린 것**이니까요. 대조군 없는 '아무것도 안
    왔습니다' 는 로봇 탓인지 제 탓인지 못 가립니다 — 이 저장소에서
    여러 번 당한 자리입니다.

  ★ 모르는 것은 안 두드립니다 ★

    요청을 보내는 것은 **이미 쓰고 있는 둘**뿐입니다 (모션 모드 조회,
    회피 상태 조회). 나머지는 전부 가만히 듣기만 합니다. 공용 기체에
    모르는 api_id 를 찔러보는 것은 이 파일이 할 일이 아닙니다.

  쓰는 법

      .\\run sense_check.py              20초 듣습니다
      .\\run sense_check.py --seconds 60  더 오래 (지도는 느릴 수 있습니다)
      .\\run sense_check.py --save        받은 것 한 개씩 파일로 남깁니다

  실행 전 체크리스트
      □ 로봇 전원 켜짐, 같은 공유기
      □ **지금 로봇이 선 자세인지 엎드린 자세인지 적어두세요**
      □ 라이다가 도는 소리가 나는지 귀로 확인 (안 돌면 점이 안 옵니다)

  ※ 여기 "엎드려 있어도 됩니다" 라고 적어뒀었습니다. 이 스크립트가 로봇을
    안 움직이는 것은 맞지만, **로봇이 무엇을 보내주느냐가 자세에 달렸을
    수 있습니다.** 확인해 본 적 없이 쓴 안심이었고, 그 줄 때문에 라이다가
    왜 조용한지를 엎드린 채로만 다섯 번 짐작했습니다 (2026-09-14).
    자세를 함께 적는 표는 topics_seen.py 에 있습니다.
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

import common

try:
    from unitree_webrtc_connect.constants import RTC_TOPIC
except ImportError as e:                       # pragma: no cover
    raise SystemExit(f"unitree_webrtc_connect 를 못 읽었습니다: {e}")

HERE = Path(__file__).parent


# ═════════════════════════════════════════════════════════════
# 들어볼 것들
#
#   (주제 이름, 한글 이름, 이게 오면 무엇을 할 수 있나)
#
#   맨 앞은 대조군입니다 — 이미 되는 것.
# ═════════════════════════════════════════════════════════════

WATCH = [
    ("LOW_STATE", "저수준 상태 ★대조군★", "배터리·관절. 이건 이미 됩니다"),

    ("LF_SPORT_MOD_STATE", "동작 상태", "몸높이·속도 (StateProbe 가 씁니다)"),
    ("MULTIPLE_STATE", "여러 상태", "서비스들이 보고하는 값"),
    ("SERVICE_STATE", "서비스 목록", "어떤 서비스가 살아 있는지"),
    ("BMS_STATE", "배터리", "잔량 (Battery 가 씁니다)"),

    ("ULIDAR", "라이다 점구름", "★ 벽까지 거리 — 줄자 없이 재는 열쇠"),
    ("ULIDAR_ARRAY", "라이다 배열", "같은 것의 다른 모양"),
    ("ULIDAR_STATE", "라이다 상태", "라이다가 켜져 있는가"),
    ("SECONDARY_IMU", "보조 IMU", "기울기 — 계단에서 몇 도인지"),

    ("ROBOTODOM", "주행 거리계", "★ 내가 어디로 얼마나 왔나"),
    ("GRID_MAP", "격자 지도", "★ 로봇이 만든 점유 격자"),

    ("SLAM_ODOMETRY", "SLAM 위치", "SLAM 서비스가 살아 있는가"),
    ("SLAM_PC_TO_IMAGE_LOCAL", "SLAM 국소 지도", "주변을 그린 것"),
    ("LIDAR_MAPPING_ODOM", "매핑 위치", "매핑 서비스의 위치"),
    ("LIDAR_MAPPING_CLOUD_POINT", "매핑 점구름", "지도를 쌓는 중인가"),
    ("LIDAR_LOCALIZATION_ODOM", "측위 위치", "저장된 지도 위에서의 내 자리"),
    ("LIDAR_NAVIGATION_GLOBAL_PATH", "길찾기 경로", "★ 목적지까지의 길"),
]


class Ear:
    """한 주제를 듣고 세어둡니다."""

    def __init__(self, key, name, why):
        self.key = key
        self.name = name
        self.why = why
        self.count = 0
        self.first_at = None
        self.last_at = None
        self.bytes = 0
        self.sample = None          # 처음 받은 것 하나

    def heard(self, message):
        now = time.monotonic()
        if self.first_at is None:
            self.first_at = now
            self.sample = message
        self.last_at = now
        self.count += 1
        try:
            self.bytes += len(json.dumps(message, default=str))
        except Exception:
            pass

    def rate(self):
        """초당 몇 번. 한 번만 왔으면 None."""
        if self.count < 2 or self.first_at is None:
            return None
        span = self.last_at - self.first_at
        return (self.count - 1) / span if span > 0 else None

    def mark(self):
        return "○" if self.count else "✖"


def shape_of(message, depth=0):
    """받은 것이 어떻게 생겼는지 한 줄로. 값이 아니라 **모양**만 봅니다."""
    if depth > 2:
        return "…"
    if isinstance(message, dict):
        data = message.get("data", message)
        if depth == 0 and data is not message:
            return shape_of(data, depth + 1)
        keys = list(data.keys())[:6] if isinstance(data, dict) else []
        if not isinstance(data, dict):
            return shape_of(data, depth + 1)
        more = "…" if len(data) > 6 else ""
        return "{" + ", ".join(keys) + more + "}"
    if isinstance(message, list):
        return f"[{len(message)}개]"
    if isinstance(message, str):
        return f"글자 {len(message)}자"
    return type(message).__name__


async def main():
    ap = argparse.ArgumentParser(description="로봇이 무엇을 말해주는지 듣습니다")
    ap.add_argument("--seconds", type=float, default=20.0,
                    help="몇 초 들을지 (기본 20)")
    ap.add_argument("--save", action="store_true",
                    help="받은 것을 주제마다 하나씩 sense/ 에 남깁니다")
    args = ap.parse_args()

    print("=" * 70)
    print(" 로봇이 무엇을 말해주는가 — 듣기만 합니다")
    print("=" * 70)
    print(" ※ 이 스크립트는 로봇을 움직이지 않습니다. 엎드려 있어도 됩니다.")
    print()

    conn = await common.connect()
    if conn is None:
        print(" ✖ 못 붙었습니다.")
        return 1

    try:
        # ── 먼저, 이미 쓰고 있는 둘만 물어봅니다 ──────────────
        #   모르는 서비스는 안 두드립니다.
        mode = await common.get_motion_mode(conn)
        print(f"[모드] 모션 모드: {mode}")

        avoid = await common.avoid_get(conn, verbose=False)
        shown = {True: "켜짐", False: "꺼짐", None: "모름 (서비스가 없는 듯)"}[avoid]
        print(f"[회피] 장애물 회피: {shown}")
        if avoid:
            print("       ※ 이게 켜져 있으면 벽에서 떨어뜨려 주고,")
            print("         **계단 앞에서도 멈춥니다.** 같은 기능입니다.")
        print()

        # ── 이제 듣습니다 ────────────────────────────────────
        ears = []
        missing = []
        for key, name, why in WATCH:
            if key not in RTC_TOPIC:
                missing.append((key, name))
                continue
            ear = Ear(key, name, why)
            ears.append(ear)
            conn.datachannel.pub_sub.subscribe(
                RTC_TOPIC[key], lambda m, e=ear: e.heard(m))

        if missing:
            print(" 이 라이브러리에 없는 주제 (판이 다릅니다):")
            for key, name in missing:
                print(f"   · {key} — {name}")
            print()

        print(f" {len(ears)}가지를 {args.seconds:.0f}초 동안 듣습니다…")
        await asyncio.sleep(args.seconds)
        print()

        # ── 결과 ─────────────────────────────────────────────
        print("=" * 70)
        print(f" {'':2} {'무엇':22} {'몇 번':>7}  {'초당':>6}  모양")
        print("-" * 70)
        for ear in ears:
            rate = ear.rate()
            rate_s = f"{rate:.1f}" if rate else ("1회" if ear.count else "—")
            shape = shape_of(ear.sample) if ear.count else ""
            print(f" {ear.mark()}  {ear.name:22} {ear.count:>7}  {rate_s:>6}  {shape[:28]}")
        print("=" * 70)
        print()

        if args.save:
            out = HERE / "sense"
            out.mkdir(exist_ok=True)
            kept = 0
            for ear in ears:
                if not ear.count:
                    continue
                path = out / f"{ear.key.lower()}.json"
                path.write_text(
                    json.dumps(ear.sample, ensure_ascii=False,
                               indent=2, default=str),
                    encoding="utf-8")
                kept += 1
            print(f" sense/ 에 {kept}개를 남겼습니다. 안을 들여다볼 때 씁니다.")
            print()

        verdict(ears)
        return 0
    finally:
        await common.disconnect(conn)


def verdict(ears):
    """무엇이 왔고 안 왔는지가 계획에 무슨 뜻인지 적습니다."""
    got = {e.key for e in ears if e.count}

    print(" 이것이 뜻하는 것")
    print(" " + "-" * 68)

    # ★ 대조군을 먼저 ★
    if "LOW_STATE" not in got:
        print("   ✖ 대조군(LOW_STATE)이 안 왔습니다.")
        print("     **아래 ✖ 들은 아무 뜻이 없습니다** — 로봇이 조용한 게")
        print("     아니라 듣는 쪽이 틀렸을 수 있습니다. 이것부터 고쳐야")
        print("     나머지를 읽을 수 있습니다.")
        return
    print("   ○ 대조군이 왔습니다 — 듣는 코드는 멀쩡합니다.")
    print("     그러니 아래의 ✖ 는 **로봇이 정말 안 주는 것**입니다.")
    print()

    # 거리
    #
    #   ★ '라이다가 죽었다' 와 '점만 안 온다' 는 다릅니다 ★
    #
    #     처음에는 점(ULIDAR)만 보고 "라이다가 꺼져 있거나" 라고 적었습니다.
    #     그런데 2026-09-14 에 실제로 돌려보니 **상태(ULIDAR_STATE)는 5Hz 로
    #     오고 있었습니다.** 펌웨어 버전까지 말하면서요. 라이다는 멀쩡히
    #     살아 있고 점만 안 보내는 것이었는데, 제 채점은 그것을 "꺼져
    #     있다" 로 뭉뚱그렸습니다.
    #
    #     고치는 방법이 정반대입니다 — 죽었으면 손댈 수 없고, 점만 안
    #     오는 것이면 **켜면 됩니다** (rt/utlidar/switch).
    #     둘을 한 줄로 적으면 엉뚱한 데를 뒤지게 됩니다.
    points = got & {"ULIDAR", "ULIDAR_ARRAY"}
    alive = "ULIDAR_STATE" in got
    if points:
        print("   ○ 라이다 점이 옵니다.")
        print("     → 줄자 없이 휘어짐을 잴 수 있습니다. 출발할 때와 도착할")
        print("       때 옆벽까지의 거리 차이가 곧 휜 양입니다.")
        print("     ※ 점구름은 눌려서 옵니다. 푸는 것이 다음 일입니다.")
    elif alive:
        print("   ◐ 라이다는 **살아 있는데 점만 안 옵니다.**")
        print("     → 상태는 오는데 점구름이 안 옵니다. 꺼진 게 아니라")
        print("       **안 켠 것**일 가능성이 큽니다 (rt/utlidar/switch).")
        print("     → .\\run lidar_on.py 로 켜보세요.")
    else:
        print("   ✖ 라이다가 아무 말도 안 합니다.")
        print("     → 상태조차 안 옵니다. 이건 정말 꺼졌거나 없는 것입니다.")
        print("       거리를 스스로 못 재면 계단도 지도도 어렵습니다.")
    print()

    # 위치
    if got & {"ROBOTODOM", "SLAM_ODOMETRY", "LIDAR_MAPPING_ODOM"}:
        print("   ○ 자기 위치를 말해줍니다.")
        print("     → '얼마나 왔나' 를 시간이 아니라 거리로 셀 수 있습니다.")
    else:
        print("   ✖ 위치를 안 말해줍니다.")
        print("     → 지금처럼 **시간과 속도로 추측**해야 합니다.")
        print("       코스마다 거리를 재둔 지금 방식이 계속 필요합니다.")
    print()

    # 지도
    mapping = got & {"GRID_MAP", "LIDAR_MAPPING_CLOUD_POINT",
                     "LIDAR_MAPPING_ODOM", "SLAM_PC_TO_IMAGE_LOCAL",
                     "LIDAR_LOCALIZATION_ODOM", "LIDAR_NAVIGATION_GLOBAL_PATH"}
    if mapping:
        print(f"   ○ 지도 쪽이 살아 있습니다 ({len(mapping)}가지).")
        print("     → 유니트리의 매핑·측위를 받아 쓰는 쪽을 먼저 보겠습니다.")
        print("       SLAM 을 새로 짜는 것보다 훨씬 빠릅니다.")
    else:
        print("   ✖ 지도 쪽이 조용합니다.")
        print("     → 이 기체에서는 그 서비스가 안 도는 것으로 봅니다.")
        print("       지도는 라이다와 위치로 **우리가** 쌓아야 합니다.")
        print("       8개 층이면 층마다 한 장 + 계단이 어디를 잇는지까지.")
    print()

    print("   ※ 여기서 '안 옵니다' 는 '이 기체·이 펌웨어·이 통로로는' 입니다.")
    print("     따로 켜야 하는 것일 수도 있습니다. 다음에 볼 자리입니다.")


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))
