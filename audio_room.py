# -*- coding: utf-8 -*-
"""
로봇이 멘트를 몇 개나 들고 있을 수 있는가 — **재봅니다.**

  ★ 왜 이걸 먼저 재는가 ★

    안내 코스를 여럿 만들 참입니다. 코스 하나가 멘트 21개이고, 통째로
    올리는 데 **10분**입니다. 그러면 갈림길이 이렇게 납니다.

        코스 다섯 개가 다 올라간다   한 번 올려두고 전환은 **즉시**
        한 번에 하나만 올라간다     코스 바꿀 때마다 10분 → 시연장에서 못 씁니다

    이 답에 따라 **만들 도구의 모양이 달라집니다.** 안 재고 도구부터
    만들면 틀린 전제 위에 세우게 됩니다. 이 저장소에서 그렇게 지은 것을
    여러 번 헐었습니다.

  ★ 무엇을 어떻게 재는가 ★

    지금 올라가 있는 것을 먼저 적어둡니다. 그리고 **가장 긴 멘트**를
    가짜 이름으로 계속 올려봅니다. 가장 긴 것을 쓰는 이유는, 한계가
    개수가 아니라 **용량**일 수 있어서입니다. 큰 것으로 밀어야 빨리
    바닥에 닿습니다.

    로봇이 거절하거나, 정해둔 개수/시간에 닿으면 멈춥니다.

  ★ 자기가 어지른 것은 자기가 치웁니다 ★

    올린 가짜는 전부 지웁니다. Ctrl+C 로 끊어도 지웁니다. 그리고
    **치운 뒤에 처음 목록과 같은지 확인합니다** — 진짜 멘트를 하나라도
    건드렸으면 그때 알아야 합니다. 공용 기체입니다.

    끊긴 뒤에 남은 것이 있으면:   .\\run audio_room.py --clean

  ★ 소리는 안 납니다 ★
    올리기와 재생은 별개의 명령이고, 여기서는 재생을 안 부릅니다.
    그래도 재생 모드를 '한 번만' 으로 맞춰둡니다 — 로봇의 기본값이
    '한 곡 반복' 이라서요. 혹시 떠들면  .\\run hush.py

  ★ 걸리는 시간 — 생각보다 깁니다 ★
    잰 값으로 **1 MB 당 63초**입니다 (조각당 0.19초). 미는 파일이
    4 MB 면 한 개에 **4분**입니다. 기본값 12개면 **50분**이 걸립니다.

    그래서 --max 를 작게 주고 여러 번 나눠 재는 편이 낫습니다.
    로봇은 움직이지 않지만 그동안 다른 데 못 씁니다.

  쓰는 법

      .\\run audio_room.py                 기본 — 12개까지 밀어봅니다
      .\\run audio_room.py --max 30        더 밀어보기
      .\\run audio_room.py --minutes 20    시간 예산을 늘려서
      .\\run audio_room.py --clean         남은 가짜만 치우고 끝냅니다
      .\\run audio_room.py --list          지금 뭐가 올라가 있는지만 봅니다
      .\\run audio_room.py --file s4_room304   밀 파일을 직접 고르기
      .\\run audio_room.py --big            폴더에서 제일 큰 것으로 (느립니다)
"""

import asyncio
import sys
import time
from pathlib import Path

import common

# ★ 가짜에는 반드시 이 이름표를 붙입니다 ★
#   지우는 쪽은 이 이름표가 붙은 것만 건드립니다. 진짜 멘트와 헷갈릴
#   여지를 코드에서 없앱니다 — 공용 기체라 실수 한 번이 비쌉니다.
MARK = "zzz_room_"

MAX_FILES = 12
MINUTES = 15.0


def pick_payload(want=None):
    """밀어 넣을 파일 하나.

    ★ 1차에서 유물을 집었습니다 ★
      "제일 큰 것" 을 골랐더니 s1_welcome.wav (3971 KB) 가 나왔습니다.
      그런데 그건 **지금 코스의 멘트가 아닙니다** — 로봇에 올라간
      목록에도 없고, 옛 대본에서 남은 파일이 audio/ 에 굴러다니던
      것이었습니다.

      큰 것을 미는 발상 자체는 맞습니다(한계가 용량이면 빨리 닿으니까).
      다만 4 MB 는 한 개에 4분이라 여러 번 밀기가 버겁습니다.
      그래서 이제 고를 수 있게 둡니다.

          기본값        지금 코스에서 제일 긴 멘트
          --file <이름>  직접 지목
          --big         폴더에서 제일 큰 것 (옛 방식)
    """
    here = Path(__file__).parent / "audio"
    files = list(here.glob("*.wav")) + list(here.glob("*.mp3"))
    if not files:
        return None
    if want:
        hit = [p for p in files if p.stem == want or p.name == want]
        if hit:
            return hit[0]
        print(f"★ audio/ 에 '{want}' 가 없습니다. 기본값으로 갑니다.")
    if "--big" in sys.argv[1:]:
        return max(files, key=lambda p: p.stat().st_size)
    # 지금 대본이 쓰는 이름들 중에서 고릅니다
    try:
        import scenario
        keys = set()
        for step in getattr(scenario.ACTIVE, "steps", []) or []:
            for line in getattr(step, "lines", []) or []:
                if getattr(line, "key", None):
                    keys.add(line.key)
            if getattr(step, "key", None):
                keys.add(step.key)
        live = [p for p in files if p.stem in keys]
        if live:
            return max(live, key=lambda p: p.stat().st_size)
    except Exception:
        pass
    return max(files, key=lambda p: p.stat().st_size)


async def leftovers(hub):
    """지난번에 끊겨서 남은 가짜들."""
    return [i for i in await common._audio_list(hub)
            if str(i.get("CUSTOM_NAME", "")).startswith(MARK)]


async def sweep(hub, verbose=True):
    """가짜만 지웁니다. 돌려주는 값: 지운 개수."""
    gone = 0
    for item in await leftovers(hub):
        name = item.get("CUSTOM_NAME")
        try:
            await hub.delete_record(item["UNIQUE_ID"])
            gone += 1
            if verbose:
                print(f"   지웠습니다: {name}")
            await asyncio.sleep(0.4)
        except Exception as e:
            print(f"   ★ 못 지웠습니다: {name} — {type(e).__name__}: {e}")
    return gone


async def push_one(hub, src, index):
    """가짜 하나를 올립니다. 돌려주는 값: (됐는가, 걸린 초, 왜 안 됐나)."""
    name = f"{MARK}{index:03d}"
    dst = src.parent / f"{name}{src.suffix}"
    dst.write_bytes(src.read_bytes())          # 이름만 바꾼 같은 소리
    t0 = time.time()
    try:
        await common.upload_phrase(hub, dst, replace=True)
        return True, time.time() - t0, ""
    except Exception as e:
        return False, time.time() - t0, f"{type(e).__name__}: {e}"
    finally:
        try:
            dst.unlink()
            wav = dst.with_suffix(".wav")      # prepare_wav 가 만든 것
            if wav != dst and wav.exists():
                wav.unlink()
        except Exception:
            pass


def _arg(name, fallback):
    args = sys.argv[1:]
    if name in args and args.index(name) + 1 < len(args):
        return args[args.index(name) + 1]
    return fallback


async def main():
    args = sys.argv[1:]
    conn = await common.connect()
    try:
        hub = common.make_audio_hub(conn)

        # ★ 이 시험은 소리를 안 냅니다 — 그래도 조용한 쪽으로 맞춰둡니다 ★
        #   올리기(upload_audio_file)와 재생(play_by_uuid)은 별개의 명령이고,
        #   여기서는 재생을 한 번도 부르지 않습니다. 그러니 원래는 필요
        #   없습니다.
        #
        #   그런데 로봇의 **기본 재생 모드가 '한 곡 반복'** 입니다. 무슨
        #   까닭으로든 소리가 한 번 나기 시작하면 영원히 되풀이합니다.
        #   한 줄로 그 가능성을 지울 수 있는데 아낄 이유가 없습니다.
        #   "제가 안 틀렸다면 조용합니다" 보다 "조용하게 해뒀습니다" 가
        #   낫습니다.
        #
        #   그래도 로봇이 떠들면:  .\run hush.py
        await common.set_play_once(hub, verbose=False)

        before = await common._audio_list(hub)
        real = [i for i in before
                if not str(i.get("CUSTOM_NAME", "")).startswith(MARK)]
        stale = [i for i in before
                 if str(i.get("CUSTOM_NAME", "")).startswith(MARK)]

        print("=" * 70)
        print(" 로봇에 지금 올라가 있는 것")
        print("=" * 70)
        print(f"   진짜 멘트 {len(real)}개")
        if stale:
            print(f"   지난 시험이 남긴 가짜 {len(stale)}개  ← 치웁니다")

        if "--list" in args:
            for i in before:
                print(f"     {i.get('CUSTOM_NAME')}")
            return 0

        if stale:
            print()
            await sweep(hub)

        if "--clean" in args:
            print("\n치웠습니다.")
            return 0

        src = pick_payload(_arg("--file"))
        if src is None:
            print("\n★ audio/ 폴더에 올릴 파일이 없습니다.")
            print("  먼저  .\\run guide.py  를 한 번 돌려 멘트를 만들어 두세요.")
            return 1

        top = int(_arg("--max", MAX_FILES))
        budget = float(_arg("--minutes", MINUTES)) * 60.0
        kb = src.stat().st_size / 1024

        print()
        print("=" * 70)
        print(" 얼마나 더 들어가는가")
        print("=" * 70)
        print(f"   미는 것   {src.name}  ({kb:.0f} KB — 가진 것 중 제일 큽니다)")
        print(f"   한도      {top}개 또는 {budget / 60:.0f}분, 먼저 닿는 쪽")
        print("   ※ 올린 것은 끝나고 전부 지웁니다. Ctrl+C 로 끊어도 지웁니다.")
        print()

        added, times, why = 0, [], ""
        t0 = time.time()
        try:
            for n in range(1, top + 1):
                left = budget - (time.time() - t0)
                if left < 60:
                    why = f"시간 예산({budget / 60:.0f}분)이 다 됐습니다"
                    break
                ok, took, err = await push_one(hub, src, n)
                if not ok:
                    why = f"로봇이 거절했습니다 — {err}"
                    print(f"   ★ {n}번째에서 막혔습니다 · {took:.0f}초 · {err}")
                    break
                added += 1
                times.append(took)
                print(f"   ○ {n}번째 올라갔습니다 · {took:.0f}초"
                      f"   (여태 {len(real) + added}개)")
            else:
                why = f"정해둔 {top}개를 다 올렸는데도 안 막혔습니다"
        finally:
            print()
            print("─" * 70)
            print(" 치웁니다")
            print("─" * 70)
            gone = await sweep(hub)
            after = await common._audio_list(hub)
            left_real = [i for i in after
                         if not str(i.get("CUSTOM_NAME", "")).startswith(MARK)]
            print(f"   가짜 {gone}개를 지웠습니다.")
            if len(left_real) == len(real):
                print(f"   진짜 멘트 {len(real)}개는 그대로입니다.")
            else:
                print(f"   ★ 진짜 멘트가 {len(real)} → {len(left_real)} 로"
                      " 바뀌었습니다. 확인이 필요합니다.")
                names = {i.get("CUSTOM_NAME") for i in left_real}
                for i in real:
                    if i.get("CUSTOM_NAME") not in names:
                        print(f"     없어진 것: {i.get('CUSTOM_NAME')}")

        print()
        print("=" * 70)
        print(" 무엇을 알았는가")
        print("=" * 70)
        each = sum(times) / len(times) if times else 0.0
        print(f"   원래 있던 것    {len(real)}개")
        print(f"   더 올린 것      {added}개  ({added * kb / 1024:.1f} MB)")
        if each:
            print(f"   하나에          {each:.0f}초")
        print(f"   멈춘 까닭       {why}")
        print()

        total = len(real) + added
        if "거절" in why:
            print(f" ★ 한계를 봤습니다 — {total}개에서 막혔습니다 ★")
            print(f"   코스 하나가 21개이니 **약 {total // 21}개 코스분**입니다.")
            if total // 21 >= 3:
                print("   → 코스들을 다 올려두고 **즉시 전환**할 수 있습니다.")
                print("     도구는 '한 번 올리고 그 뒤엔 안 건드린다' 로 만듭니다.")
            else:
                print("   → 여러 코스를 동시에 두기엔 빠듯합니다.")
                print("     도구가 **쓸 코스만 남기고 나머지를 비우는** 일을")
                print("     해야 합니다. 전환에 시간이 걸린다는 뜻이니,")
                print("     시연 전에 미리 올려두는 절차가 필요합니다.")
        else:
            print(f" ★ 한계를 못 봤습니다 — {total}개까지는 들어갑니다 ★")
            print(f"   ({len(real)}개는 원래 있던 것이고 {added}개를 더 얹었습니다.")
            print(f"    더 얹은 것만 {added * kb / 1024:.0f} MB 입니다.)")
            print("   여기까지는 확실하고, 그 위는 모릅니다.")
            print(f"   더 알고 싶으면:  .\\run audio_room.py --max {top * 2}")
            print()
            print("   ※ 한계를 꼭 봐야 하는 건 아닙니다. 도구가 **로봇에게")
            print("     물어보고 없는 것만 올리는** 식이면, 한계가 40이든")
            print("     400이든 똑같이 돕니다. 재는 값이 도구를 바꾸지 않는")
            print("     지점에 왔으면 그만 재는 편이 낫습니다.")
        return 0
    finally:
        await common.disconnect(conn)


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()) or 0)
    except KeyboardInterrupt:
        print("\n멈췄습니다. (올린 가짜는 위에서 치웠습니다 —"
              " 미심쩍으면  .\\run audio_room.py --clean  을 한 번 더)")
        sys.exit(1)
    except Exception as e:
        common.explain_error(e)
        print("\n※ 가짜가 남았을 수 있습니다:  .\\run audio_room.py --clean")
        sys.exit(1)
