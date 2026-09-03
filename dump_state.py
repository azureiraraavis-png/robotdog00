# -*- coding: utf-8 -*-
"""
로봇이 내보내는 상태 메시지 안에 무엇이 들었는지 그냥 찍어봅니다.

  ★ 로봇에게 아무것도 보내지 않습니다. 버튼도 누를 필요 없습니다 ★
  ★ 소리도 안 납니다 ★  조용히 듣기만 하고 끝납니다.

  ── 왜 만들었나 ──
    리모컨 버튼 값을 찾으려고 lowstate 안에서 `wireless_remote` 같은
    이름을 뒤졌는데, 없었습니다. 그래서 또 다른 이름을 짐작해 넣고
    다시 돌리고... 그러다 보면 사람이 버튼을 여덟 번 누르고 있습니다.

    항목 이름을 맞히려 하지 말고, **뭐가 있는지 물어보면 됩니다.**
    이 프로젝트에서 몇 번이나 통한 방법입니다 — 라이브러리 소스를 읽고,
    응답 전문을 찍고, 로봇이 스스로 말하게 하는 것.

  쓰는 법

      .\\run dump_state.py                 lowstate 를 봅니다 (기본)
      .\\run dump_state.py SPORT_MOD_STATE 다른 토픽
      .\\run dump_state.py --list          볼 수 있는 토픽 이름들

  결과는 dump_<토픽>.json 에 통째로 저장됩니다.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

from unitree_webrtc_connect.constants import RTC_TOPIC

import common

LISTEN = 5.0        # 이만큼 듣습니다 (초)


def outline(obj, prefix="", depth=0, out=None):
    """무엇이 들었는지 나무 모양으로. 값은 짧게, 배열은 길이만."""
    out = out if out is not None else []
    if depth > 3:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.append((here, f"{{{len(v)}개}}"))
                outline(v, here, depth + 1, out)
            elif isinstance(v, list):
                kind = type(v[0]).__name__ if v else "빈"
                out.append((here, f"[{len(v)}개 · {kind}]"))
                # 바이트처럼 생긴 배열만 hex 로 — 리모컨 패킷 같은 것.
                # (실수 배열까지 hex 로 찍으면 자세 값이 00 00 00 으로 보여
                #  아무 정보도 안 됩니다)
                if (v and len(v) <= 64
                        and all(isinstance(x, int) and 0 <= x <= 255 for x in v)):
                    head = " ".join(f"{x:02x}" for x in v[:16])
                    out.append((here + "  (hex)", head))
                elif v and isinstance(v[0], float):
                    out.append((here + "  (앞부분)",
                                ", ".join(f"{x:.3f}" for x in v[:4])))
            else:
                s = repr(v)
                out.append((here, s if len(s) <= 60 else s[:60] + " …"))
    return out


async def run(conn, topic_name):
    key = topic_name.upper()
    if key not in RTC_TOPIC:
        print(f" '{topic_name}' 는 없는 토픽입니다. --list 로 확인하세요.")
        return

    box = {"last": None, "count": 0, "changed": []}

    def on(message):
        data = message.get("data")
        box["count"] += 1
        if data is None:
            return
        if box["last"] is None:
            box["last"] = data
        else:
            # 바뀌는 항목을 따로 모읍니다 — 리모컨처럼 눌러야 변하는 것들
            try:
                before = json.dumps(box["last"], sort_keys=True)
                after = json.dumps(data, sort_keys=True)
                if before != after:
                    box["changed"].append(time.time())
                    box["last"] = data
            except Exception:
                box["last"] = data

    conn.datachannel.pub_sub.subscribe(RTC_TOPIC[key], on)

    print(f"[듣기] {key}  ({RTC_TOPIC[key]})  — {LISTEN:.0f}초")
    await asyncio.sleep(LISTEN)

    print(f"[듣기] 메시지 {box['count']}개 받음, 그중 내용이 바뀐 적 "
          f"{len(box['changed'])}번")
    if box["last"] is None:
        print(" ★ 알맹이가 비어 있습니다 ★  이 토픽은 이 펌웨어에서 안 나오는 것 같습니다.")
        return

    rows = outline(box["last"])
    width = max((len(r[0]) for r in rows), default=10)
    print()
    print("=" * 78)
    print(f" {key} 안에 든 것")
    print("=" * 78)
    for name, val in rows:
        print(f"  {name:<{width}}  {val}")

    # 리모컨처럼 보이는 것 찾기
    hits = [n for n, _v in rows
            if any(w in n.lower() for w in
                   ("wireless", "remote", "key", "button", "joy", "rc"))]
    print()
    if hits:
        print(" ★ 리모컨과 관련되어 보이는 항목 ★")
        for h in hits:
            print(f"     {h}")
    else:
        print(" ※ 리모컨과 관련되어 보이는 항목이 없습니다.")
        print("   이 펌웨어는 리모컨 상태를 내보내지 않는 것 같습니다.")

    path = Path(__file__).parent / f"dump_{key.lower()}.json"
    path.write_text(json.dumps(box["last"], ensure_ascii=False, indent=2,
                               default=str), encoding="utf-8")
    print(f"\n 전문을 {path.name} 에 저장했습니다.")


async def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--list" in sys.argv:
        print(" 볼 수 있는 토픽:")
        for k in sorted(RTC_TOPIC):
            print(f"   {k}")
        return

    topic = args[0] if args else "LOW_STATE"
    print("=" * 78)
    print(" 상태 메시지 들여다보기  ★ 아무것도 보내지 않습니다 · 소리 안 납니다 ★")
    print("=" * 78)

    conn = await common.connect()
    try:
        await run(conn, topic)
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
