# -*- coding: utf-8 -*-
"""
오디오 이름에 코스 이름을 붙입니다 — **파일과 로봇까지 같이.**

  ★ 무엇을 왜 ★

    로봇의 오디오 이름은 폴더 없이 평평합니다. 코스가 늘면 두 코스가
    같은 이름을 쓰게 되고, 로봇에서는 한 파일이 됩니다. 나중에 올린
    쪽이 앞의 것을 덮어써서 **화면에는 맞는 문장이 찍히는데 스피커에서는
    다른 코스의 말이 나옵니다.**

    그래서 규칙을 둡니다 — **오디오 이름은 코스 이름으로 시작한다.**

        s1a_greet   →   ai_swe_s1a_greet

    scenario.py 의 16곳은 이미 고쳤습니다. 이 스크립트는 **나머지 셋**을
    맞춥니다.

        audio/ 의 파일 이름          mp3 16개 + wav 16개
        texts.json · durations.json  키 16개씩
        로봇에 올라간 이름           16개  ← 다시 안 올립니다. 이름만 바꿉니다

    로봇 쪽이 핵심입니다. 다시 올리면 19분인데, 이름 바꾸기는 **10초**
    입니다 (webrtc_audiohub.rename_record).

  ★ 조용히 틀릴 자리가 있습니다 ★

    하나를 빠뜨리면 **오류 없이** 그 멘트만 재생이 안 됩니다. 로봇에는
    옛 이름이 남아 있고 대본은 새 이름을 찾으니까요. 복도에서 발견하게
    되는 종류입니다.

    그래서 이 스크립트는 이렇게 만들었습니다.

      · 기본값은 **아무것도 안 바꿉니다.** 무엇이 바뀔지 보여만 줍니다
      · 바꾸기 전에 **되돌릴 사본**을 남깁니다 (.bak)
      · 새 이름이 이미 있으면 **멈춥니다** (덮어쓰지 않습니다)
      · 우리가 계산한 옛 이름 목록에 있는 것만 건드립니다
      · 끝나고 **대조합니다** — 대본의 키가 파일에도 로봇에도 있는지

  ★ 공용 멘트는 안 건드립니다 ★
    alert_* 와 greet · settle · power_ready · lift_ready 같은 것들은
    코스에 안 딸립니다. park.py 와 carry.py 가 쓰는 **안전 멘트**라
    이름이 바뀌면 그쪽이 조용히 벙어리가 됩니다. 코스의 keys() 에만
    있는 것을 바꿉니다.

  쓰는 법

      .\\run rename_keys.py                무엇이 바뀔지 봅니다 (안 바꿉니다)
      .\\run rename_keys.py --local        파일과 json 만 바꿉니다
      .\\run rename_keys.py --robot        로봇의 이름만 바꿉니다
      .\\run rename_keys.py --check        지금 어긋난 데가 있는지 대조만
      .\\run rename_keys.py --undo-local   .bak 으로 되돌립니다
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIO = HERE / "audio"


# ── 무엇을 무엇으로 ──────────────────────────────────────────

def candidates():
    """{옛 이름: 새 이름} **후보**. 실제로 옮길지는 따로 봅니다.

    ★ 여기서 한 번 틀렸습니다 ★

      처음에는 이 사전을 그대로 "옮길 목록" 으로 썼습니다. 새 이름에서
      접두어를 떼어 옛 이름을 만들어내는 방식이었는데, 그러면 **이미
      제대로 붙어 있는 것까지** 옮길 것으로 셉니다.

          SHORT_s1_greet  →  옛 이름을 's1_greet' 로 계산
                             그런데 's1_greet' 라는 파일은 없습니다
                             (SHORT 코스는 처음부터 접두어를 썼습니다)

      문자열만 보고 계산했고 **실제로 무엇이 있는지 안 봤습니다.**
      겉보기에는 무해합니다 — 없는 파일은 안 옮겨지니까요. 그런데
      "20개 중 16개만 바뀌었다" 를 보고 **남은 4개가 할 일인지 이미
      끝난 일인지 구별할 수가 없습니다.** 그게 위험한 자리입니다.

      그래서 이제 후보만 만들고, 옮길지 말지는 파일과 로봇을 **보고**
      정합니다. 세 갈래로 갈립니다.

          옮길 것        옛 이름이 실제로 있습니다
          이미 된 것      새 이름이 이미 있습니다
          아직 없는 것    둘 다 없습니다 (안 만든 멘트)
    """
    import courses
    courses.discover()
    out, own = {}, {}
    for c in courses.COURSES:
        want = f"{c.id}_"
        for new in c.keys():
            own[new] = c.id
            if not new.startswith(want):
                continue                       # 규칙 밖 — register 가 막습니다
            old = new[len(want):]
            if old:
                out[old] = new
    return out, own


def _has_local(name):
    return (AUDIO / f"{name}.mp3").exists() or (AUDIO / f"{name}.wav").exists()


def split(cands, have):
    """후보를 셋으로 가릅니다. have(이름) 이 '있는가' 를 답합니다.

    돌려주는 값: (옮길 것, 이미 된 것, 아직 없는 것, 부딪힌 것)
    """
    move, done, none, clash = {}, [], [], []
    for old, new in sorted(cands.items()):
        old_there, new_there = have(old), have(new)
        if old_there and new_there:
            clash.append(new)          # 둘 다 있습니다 — 덮어쓰면 안 됩니다
        elif old_there:
            move[old] = new
        elif new_there:
            done.append(new)
        else:
            none.append(new)
    return move, done, none, clash


# ── 파일과 json ──────────────────────────────────────────────

def move_files(mapping, dry):
    done, missing = [], []
    for old, new in sorted(mapping.items()):
        for ext in (".mp3", ".wav"):
            src, dst = AUDIO / f"{old}{ext}", AUDIO / f"{new}{ext}"
            if not src.exists():
                if ext == ".mp3":
                    missing.append(old)
                continue
            if not dry:
                src.rename(dst)
            done.append(f"{old}{ext}")
    return done, missing


def fix_json(name, mapping, dry):
    path = AUDIO / name
    if not path.exists():
        return 0, f"{name} 이 없습니다"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return 0, f"{name} 이 사전이 아닙니다"
    hit = [k for k in data if k in mapping]
    if not dry and hit:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        for k in hit:
            data[mapping[k]] = data.pop(k)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return len(hit), ""


# ── 로봇 ─────────────────────────────────────────────────────

async def robot_names():
    import common
    conn = await common.connect()
    hub = common.make_audio_hub(conn)
    items = await common._audio_list(hub)
    return conn, hub, items


async def rename_on_robot(cands, dry):
    """로봇 쪽. **파일과 따로 가릅니다** — 로봇에만 옛 이름이 남아 있을
    수도, 로봇만 이미 되어 있을 수도 있습니다."""
    import common
    conn, hub, items = await robot_names()
    try:
        uuid = {i.get("CUSTOM_NAME"): i.get("UNIQUE_ID") for i in items}
        move, done, none, clash = split(cands, lambda n: n in uuid)

        print(f"   로봇에 {len(items)}개")
        print(f"   옮길 것 {len(move)} · 이미 된 것 {len(done)} · "
              f"로봇에 없는 것 {len(none)}")
        if clash:
            print(f"   ★ 옛 이름과 새 이름이 둘 다 있습니다: {', '.join(clash)}")
            print("     덮어쓰지 않습니다. 어느 쪽이 맞는지 정하고 지우세요.")
            return 0
        if dry:
            for o, n in sorted(move.items()):
                print(f"     {o}  →  {n}")
            return 0

        ok = 0
        for o, n in sorted(move.items()):
            try:
                await hub.rename_record(uuid[o], n)
                ok += 1
                print(f"     ○ {o}  →  {n}")
                await asyncio.sleep(0.4)
            except Exception as e:
                print(f"     ★ {o} — {type(e).__name__}: {e}")
        return ok
    finally:
        await common.disconnect(conn)


# ── 대조 ─────────────────────────────────────────────────────

async def verify(with_robot=True):
    """대본의 키가 파일에도 로봇에도 있는가. **이게 이 일의 마무리입니다.**

    ★ '없다' 를 두 가지로 가릅니다 ★

      대본이 쓰는 이름이 안 보일 때, 까닭이 둘인데 뜻이 정반대입니다.

          아직 안 만들었다     옛 이름도 없습니다. 정상입니다 —
                              다음 build 때 새 이름으로 생깁니다
          이름이 어긋났다      **옛 이름이 아직 있습니다.** 옮기다 만
                              것입니다. 이게 위험한 자리입니다

      처음에는 둘을 같이 세어서, 한 번도 안 만든 선택 멘트 하나 때문에
      "어긋난 데가 있습니다" 가 떴습니다. 그런 경보는 곧 무시하게 되고,
      그러면 진짜가 왔을 때도 넘어갑니다.
    """
    import courses
    courses.discover()
    cands, _own = candidates()
    back = {new: old for old, new in cands.items()}    # 새 이름 → 옛 이름
    want = set()
    for c in courses.COURSES:
        want |= set(c.keys())

    def report(where, missing, has_old):
        drift = sorted(k for k in missing if has_old(back.get(k, "")))
        unbuilt = sorted(k for k in missing if k not in drift)
        if drift:
            print(f"   ★ {where}에서 이름이 어긋났습니다 {len(drift)}개: "
                  f"{', '.join(drift[:8])}")
            print(f"     옛 이름이 아직 있습니다 — 옮기다 만 것입니다.")
        if unbuilt:
            print(f"   · 아직 안 만든 것 {len(unbuilt)}개: "
                  f"{', '.join(unbuilt[:8])}  (정상입니다)")
        if not missing:
            print(f"   ○ 전부 {where}에 있습니다")
        return not drift

    print(f"   대본이 쓰는 이름 {len(want)}개")
    ok = report("audio/", [k for k in want if not (AUDIO / f"{k}.mp3").exists()],
                lambda old: bool(old) and _has_local(old))

    if not with_robot:
        return ok

    import common
    conn, _hub, items = await robot_names()
    try:
        have = {i.get("CUSTOM_NAME") for i in items}
        ok2 = report("로봇", [k for k in want if k not in have],
                     lambda old: bool(old) and old in have)
        return ok and ok2
    finally:
        await common.disconnect(conn)


def undo_local():
    n = 0
    for p in AUDIO.glob("*.bak"):
        target = p.with_suffix("")
        shutil.move(str(p), str(target))
        print(f"   되돌림: {target.name}")
        n += 1
    bak = Path("/tmp/scenario.py.bak")
    print(f"   json {n}개를 되돌렸습니다.")
    print("   ※ 파일 이름과 scenario.py 는 git 으로 되돌리세요:")
    print("       git checkout -- scenario.py")
    print("       (audio/ 는 추적 밖이라 이름은 손으로 되돌려야 합니다)")
    return 0


# ── 실행 ─────────────────────────────────────────────────────

async def main():
    args = sys.argv[1:]
    if "--undo-local" in args:
        return undo_local()

    if "--check" in args:
        print("=" * 70)
        print(" 대조 — 대본 · 파일 · 로봇이 같은 이름을 보고 있는가")
        print("=" * 70)
        return 0 if await verify() else 1

    cands, own = candidates()
    move, done, none, clash = split(cands, _has_local)

    print("=" * 70)
    print(" 오디오 이름에 코스 이름 붙이기")
    print("=" * 70)
    print(f" 코스가 쓰는 이름 {len(own)}개")
    print()
    print(f"   옮길 것        {len(move):>3}개   audio/ 에 옛 이름이 있습니다")
    print(f"   이미 된 것      {len(done):>3}개   새 이름으로 벌써 있습니다")
    print(f"   아직 없는 것    {len(none):>3}개   안 만든 멘트입니다")
    if clash:
        print(f"   ★ 부딪힌 것    {len(clash):>3}개   옛 이름과 새 이름이 둘 다")
    print()

    if move:
        print(" ── 옮길 것 ──")
        for old, new in sorted(move.items()):
            wav = "○" if (AUDIO / f"{old}.wav").exists() else "·"
            print(f"   {old:<18} → {new:<26} wav {wav}")
    if done:
        print()
        print(" ── 이미 된 것 (안 건드립니다) ──")
        print("   " + ", ".join(done))
    if none:
        print()
        print(" ── 아직 없는 것 (다음 build 때 새 이름으로 생깁니다) ──")
        print("   " + ", ".join(none))

    if clash:
        print()
        print(f" ★ 옛 이름과 새 이름이 둘 다 있습니다: {', '.join(clash)}")
        print("   덮어쓰지 않습니다. 어느 쪽이 맞는지 정하고 하나를 지우세요.")
        return 1

    do_local = "--local" in args
    do_robot = "--robot" in args
    if not (do_local or do_robot):
        print()
        if not move:
            print(" audio/ 에서 옮길 것은 없습니다.")
            print("   로봇 쪽은 따로 봅니다:  .\\run rename_keys.py --robot")
        else:
            print(" 아무것도 안 바꿨습니다.")
            print("   파일과 json:  .\\run rename_keys.py --local")
            print("   로봇:         .\\run rename_keys.py --robot")
            print("   ※ --local 을 먼저 하세요. 로봇만 바꾸면 대본이 못 찾습니다.")
        return 0

    if do_local:
        print()
        print("─" * 70)
        print(" 파일과 json")
        print("─" * 70)
        moved, missing = move_files(move, dry=False)
        print(f"   파일 {len(moved)}개 이름을 바꿨습니다.")
        if missing:
            print(f"   ※ mp3 가 없던 것 {len(missing)}개: {', '.join(missing[:6])}")
            print("     (아직 안 만든 멘트입니다 — 다음 build 때 새 이름으로 생깁니다)")
        for name in ("texts.json", "durations.json"):
            n, why = fix_json(name, move, dry=False)
            print(f"   {name}: 키 {n}개 바꿈{('  — ' + why) if why else ''}")

    if do_robot:
        print()
        print("─" * 70)
        print(" 로봇")
        print("─" * 70)
        n = await rename_on_robot(cands, dry=False)
        print(f"   {n}개를 바꿨습니다.")

    print()
    print("=" * 70)
    print(" 대조")
    print("=" * 70)
    ok = await verify(with_robot=do_robot)
    print()
    if ok:
        print(" ○ 대본 · 파일" + (" · 로봇" if do_robot else "") + " 이 다 맞습니다.")
    else:
        print(" ★ 어긋난 데가 있습니다. 위의 ★ 줄을 보세요.")
        if do_local and not do_robot:
            print("   로봇을 아직 안 바꿨다면 그건 정상입니다:")
            print("       .\\run rename_keys.py --robot")
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()) or 0)
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
