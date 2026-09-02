# -*- coding: utf-8 -*-
"""
안내 음성 재생 점검.  (로봇은 움직이지 않습니다)

  ★ 원인은 밝혀졌습니다 — 로봇의 재생 모드 ★

    single_cycle  한 곡 반복    ← 로봇의 기본값
    no_cycle      한 번만 재생  ← 안내에는 이것이 맞습니다
    list_loop     목록 반복

  기본값이 '한 곡 반복'이라, play_by_uuid 를 한 번 부르면 그 멘트가
  **끝없이 되풀이됩니다.** 04 에서 "두 번 말한다"고 느껴졌던 것도 사실은
  무한 반복이었고, 다음 명령이 우연히 끊어준 것뿐이었습니다.

  common.upload_all() 이 이제 시작할 때 no_cycle 로 맞추고 **읽어서
  확인합니다.** 이 스크립트는 그것이 실제로 통하는지 귀로 확인합니다.

  로봇이 지금 떠들고 있다면 먼저:  .\\run hush.py

    .\\run audio_check.py

  로봇이 소리만 냅니다. 움직이지 않으니 공간은 필요 없습니다.
"""

import asyncio
import sys

import common
import config

conn = None
LINE = "─" * 62


def head(title):
    print(f"\n{LINE}\n {title}\n{LINE}")


async def ask_count(what):
    """몇 번 들렸는지 묻습니다."""
    ans = await common.ask(f"  '{what}' 이(가) 몇 번 들렸습니까? (1 / 2 / 0=안들림) ")
    ans = (ans or "").strip()
    if ans.startswith("2"):
        return 2
    if ans.startswith("0"):
        return 0
    return 1


async def look_at_list(hub):
    """로봇에 올라간 오디오 목록. 이름이 겹치는지 봅니다."""
    head("1. 로봇에 무엇이 올라가 있나")
    items = await common._audio_list(hub)
    print(f"  총 {len(items)}개\n")

    seen = {}
    for item in items:
        name = item.get("CUSTOM_NAME")
        uid = item.get("UNIQUE_ID")
        seen.setdefault(name, []).append(uid)
        print(f"    {str(name):16} {uid}")

    dups = {n: u for n, u in seen.items() if len(u) > 1}
    print()
    if dups:
        print("  ★ 같은 이름이 여러 개 올라가 있습니다 ★")
        for name, uids in dups.items():
            print(f"    {name}: {len(uids)}개")
        print("  이것만으로 두 번 재생되지는 않지만(우리는 UUID 하나로 재생),")
        print("  로봇이 이름으로 재생한다면 원인일 수 있습니다.")
    else:
        print("  ✔ 이름이 겹치는 것은 없습니다.")
        print("    → 목록 중복은 원인이 아닙니다.")
    return items, dups


async def look_at_mode(hub):
    """재생 모드를 읽고, 반복이면 고칩니다. ★ 원인이 여기였습니다 ★"""
    head("2. 재생 모드 — 원인이 여기였습니다")
    mode = await common.get_play_mode(hub)
    print(f"  현재 모드: {mode or '읽지 못함'}")
    print()
    print("    single_cycle  한 곡 반복   ← 기본값. 멘트가 끝없이 되풀이됩니다")
    print("    no_cycle      한 번만 재생 ← 안내에는 이것이 맞습니다")
    print("    list_loop     목록 반복")
    print()
    if mode == "single_cycle":
        print("  ★ 반복 모드입니다. 이것이 '두 번 말하는' 증상의 원인입니다.")
        print("    사실 두 번이 아니라 무한 반복이었고, 다음 명령이 끊었던 것입니다.")
    ok = await common.set_play_once(hub)
    return mode, ok


def look_at_hub(hub):
    """AudioHub 가 어떤 기능을 갖고 있는지 봅니다."""
    head("2-2. 라이브러리가 제공하는 재생 관련 기능")
    names = [n for n in dir(hub)
             if not n.startswith("_")
             and any(w in n.lower()
                     for w in ("play", "stop", "loop", "repeat", "volume", "audio"))]
    for n in sorted(names):
        print(f"    {n}")
    print()
    if any("stop" in n.lower() for n in names):
        print("  ✔ 정지 기능이 있습니다 — 두 번째 재생을 끊어볼 수 있습니다.")
    if any(w in " ".join(names).lower() for w in ("loop", "repeat")):
        print("  ★ 반복 재생 설정이 보입니다. 기본값이 2회일 수 있습니다.")
    return names


async def test_single(hub, uuids):
    """재생 모드를 고친 뒤, 한 번만 재생되는지 확인합니다."""
    head("3. 고친 뒤에 — 한 번만 나오는가")
    key = "wait"          # 짧은 멘트로 셉니다
    text = config.PHRASES.get(key, "")
    print(f'  재생할 멘트: "{text}"')
    print("  ★ 요청은 딱 한 번 보냅니다 ★\n")
    await common.ask("  준비되면 Enter 를 누르세요 (귀로 세어 주세요) ")

    await hub.play_by_uuid(uuids[key])
    await asyncio.sleep(6.0)

    n = await ask_count(text)
    if n == 2:
        print("\n  → 아직 반복됩니다. 재생 모드 변경이 안 먹은 것입니다.")
        print("    .\\run hush.py 로 멈추고, 아래 4번 결과를 봐주세요.")
    elif n == 1:
        print("\n  ★ 한 번만 재생됩니다 — 해결되었습니다 ★")
    else:
        print("\n  → 소리가 안 났습니다. 볼륨이나 오디오 채널을 먼저 보세요.")
    return n


async def test_stop(hub, uuids, names):
    """반복을 정지(pause)로 끊을 수 있는지 — 모드 변경이 안 먹었을 때의 보험."""
    stop_name = next((n for n in names
                      if n.lower().startswith(("stop", "pause"))), None)
    if not stop_name:
        return None

    head("4. 재생 중간에 끊을 수 있는가")
    key = "wait"
    print(f"  재생하고 3초 뒤에 {stop_name}() 을 부릅니다.")
    print("  두 번째 재생이 시작되기 전에 끊기면 대책이 생깁니다.\n")
    await common.ask("  준비되면 Enter ")

    await hub.play_by_uuid(uuids[key])
    await asyncio.sleep(3.0)
    try:
        await getattr(hub, stop_name)()
        print(f"  {stop_name}() 보냄")
    except Exception as e:
        print(f"  {stop_name}() 실패: {type(e).__name__}: {str(e)[:80]}")
        return None
    await asyncio.sleep(4.0)

    n = await ask_count("멘트")
    if n == 1:
        print("\n  ★ 정지로 끊을 수 있습니다 ★")
        print("    say() 가 재생 뒤 일정 시간이 지나면 정지를 보내도록 하면 됩니다.")
    else:
        print("\n  정지로는 막지 못했습니다.")
    return n


async def offer_cleanup(hub, dups):
    if not dups:
        return
    head("5. 중복 정리")
    print("  같은 이름으로 여러 개 올라간 것을 지울 수 있습니다.")
    print("  (다음 실행 때 필요한 것은 다시 올라갑니다)")
    if not await common.confirm("중복된 오디오를 지울까요?"):
        return
    for name in dups:
        items = await common._audio_list(hub)
        matches = [i for i in items if i.get("CUSTOM_NAME") == name]
        for item in matches[1:]:            # 첫 개만 남깁니다
            try:
                await hub.delete_record(item["UNIQUE_ID"])
                print(f"    지움: {name} ({item['UNIQUE_ID']})")
            except Exception as e:
                print(f"    실패: {name} — {type(e).__name__}")
            await asyncio.sleep(0.5)
    print("  정리 완료.")


async def run(conn_):
    print("[준비] 안내 멘트 확인...")
    paths = await common.make_all_phrases()

    await common.set_volume(conn_)
    hub, uuids = await common.upload_all(conn_, paths)

    items, dups = await look_at_list(hub)
    mode, mode_ok = await look_at_mode(hub)
    names = look_at_hub(hub)
    n = await test_single(hub, uuids)

    stop_ok = None
    if n == 2:
        stop_ok = await test_stop(hub, uuids, names)
    else:
        await common.hush(hub, verbose=False)

    await offer_cleanup(hub, dups)

    head("정리")
    print(f"  처음 재생 모드: {mode or '읽지 못함'}"
          f"   →  변경 {'성공' if mode_ok else '실패'}")
    print()
    if n == 1:
        print("  ★ 해결되었습니다 ★")
        print("  common.upload_all() 이 이제 시작할 때 자동으로 한 번만 재생하도록")
        print("  맞춥니다. 04 도, 05 도 그대로 고쳐집니다.")
        print()
        print("  혹시 로봇이 다시 떠들면:  .\\run hush.py")
    elif n == 2:
        print("  요청 한 번 → 재생 두 번. 우리 코드의 문제가 아닙니다.")
        if stop_ok == 1:
            print("  정지 명령으로 끊을 수 있으므로, say() 에 그 처리를 넣겠습니다.")
        else:
            print("  정지로도 안 끊깁니다. 남은 방법:")
            print("    · 멘트 사이 대기 시간을 늘려 겹치지 않게 한다")
            print("    · 라이브러리의 다른 재생 함수를 시험한다")
            print("    · 위 2-2 목록의 다른 재생 함수를 시험한다")
            print("    · 멘트마다 재생 뒤 pause 를 보낸다 (say(stop_after=True))")
    else:
        print("  소리가 안 났습니다. 볼륨과 오디오 채널을 먼저 확인하세요.")
    print()
    print("  이 화면을 그대로 알려주시면 다음 수를 정하겠습니다.")


async def main():
    global conn
    print("=" * 62)
    print(" 안내 음성이 두 번 나오는 이유 찾기")
    print("=" * 62)
    print(__doc__.split("로봇이 지금 떠들고")[0])

    conn = await common.connect()
    try:
        await run(conn)
    finally:
        print("\n정리합니다...")
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단됨")
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
