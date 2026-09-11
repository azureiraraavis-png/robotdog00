# -*- coding: utf-8 -*-
"""
안내 코스 작업실 — 견주고, 만들고, 올립니다.

  ★ 19분이 이 도구의 설계를 지배합니다 ★

    코스 하나를 통째로 올리면 **약 19분**입니다 (잰 값: 1 MB 당 63초).
    용량이 아니라 시간이 제약입니다. 그래서 이 도구는 이렇게 만듭니다.

      · 이미 올라간 것은 **건너뜁니다** — 그리고 건너뛴 것이 보입니다
      · 올리기 전에 **무엇을 얼마나** 할지 먼저 말합니다
      · 19분 동안 **줄마다 진행**이 보입니다
      · 끊고 다시 눌러도 **남은 것만** 합니다

  ★ 끊겨도 이어지는 근거 ★

    파일 하나를 올릴 때마다 built.json 을 **그 자리에서** 씁니다.
    마지막에 몰아 쓰면, 18분째에 끊겼을 때 처음부터 다시 해야 합니다.

    무엇이 '바뀐 것' 인가는 **문장의 지문**으로 가립니다. 파일 시각이
    아니라요 — 시각은 파일을 다시 만들기만 해도 바뀌는데, 그러면 같은
    문장을 또 19분 걸려 올리게 됩니다.

  ★ 로봇에게 물어봅니다 ★

    built.json 이 "올렸다" 고 적어놨어도 로봇에 없을 수 있습니다
    (다른 사람이 지웠거나, 로봇을 초기화했거나). 그래서 올리기 전에
    **로봇의 목록을 읽습니다.** 기억을 믿는 것보다 물어보는 편이
    언제나 낫습니다.

  쓰는 법

      .\\run studio.py list                 코스와 로봇 상태
      .\\run studio.py plan ai_swe          무엇을 할지만 봅니다 (안 바꿉니다)
      .\\run studio.py plan ai_swe --offline  로봇 없이 (기억으로만)
      .\\run studio.py push ai_swe          만들고 올립니다
      .\\run studio.py push ai_swe --dry    올리지는 않고 음성만 만듭니다
      .\\run studio.py push ai_swe --rebuild  묻지 말고 전부 다시 (16분+)

  ※ 안내를 돌리지는 않습니다. 그건 guide.py 와 폰 앱의 일입니다.
"""

import asyncio
import sys
import time
from pathlib import Path

import coursefile

# 잰 값입니다 (audio_room.py). 예상 시간을 말할 때 씁니다.
SECONDS_PER_MB = 63.0


# ── 무엇을 할 것인가 ─────────────────────────────────────────

class Row:
    """이름 하나에 대해 무엇을 할지."""

    def __init__(self, key, text):
        self.key = key
        self.text = text
        self.hash = coursefile.text_hash(text)
        self.mp3 = None          # 지역 파일
        self.bytes = 0           # 올릴 크기 (wav 기준)
        self.on_robot = False
        self.robot_known = False   # 로봇에 물어봤는가 (안 물어봤으면 모릅니다)
        self.known = {}          # built.json 이 아는 것
        self.build = False       # 음성을 만들어야 하는가
        self.upload = False      # 올려야 하는가
        self.why = ""

    @property
    def seconds(self):
        return self.bytes / (1024 * 1024) * SECONDS_PER_MB if self.upload else 0.0


def _audio_dir():
    import config
    return Path(config.AUDIO_DIR)


def survey(course, on_robot=None, rebuild=False):
    """코스를 훑어 무엇을 할지 정합니다.

    on_robot 이 None 이면 **로봇에 안 물어본 것**입니다 — 그때는
    built.json 의 기억을 씁니다. 기억은 틀릴 수 있으니 화면에 그렇게
    적습니다.
    """
    import scenario
    audio = _audio_dir()
    built = coursefile.load_built(course.id)
    old = coursefile.old_texts(audio)
    rows = []
    for key, text in coursefile.spoken_texts(course).items():
        r = Row(key, text)
        r.known = built["keys"].get(key, {})
        mp3 = audio / f"{key}.mp3"
        wav = audio / f"{key}.wav"
        r.mp3 = mp3 if mp3.exists() else None
        r.bytes = wav.stat().st_size if wav.exists() else 0

        # ① 음성을 만들어야 하는가
        #
        # ★ '모른다' 와 '다르다' 를 갈라 말합니다 ★
        #   built.json 은 새로 만든 것이라 처음엔 비어 있습니다. 그때
        #   전부 "바뀌었다" 로 치면 이미 맞는 음성을 16분 걸려 다시
        #   올립니다. voices.py 가 texts.json 에 적어둔 기록이 있으니
        #   그걸 읽습니다.
        #
        #   그리고 그 기록이 **없는 것**과 **다른 것**은 다른 상황입니다.
        #   처음에는 둘을 같은 말로 뭉갰다가 시험이 잡았습니다. 화면에
        #   "모릅니다" 라고 떠 있는데 사실은 문장이 바뀐 것이었다면,
        #   보는 사람이 엉뚱한 데를 뒤집니다.
        seeded = False
        recorded = old.get(key)
        spoken = scenario.for_tts(text)
        if r.mp3 is None:
            r.build, r.why = True, "음성이 없습니다"
        elif "hash" in r.known:
            if r.known["hash"] != r.hash:
                r.build, r.why = True, "문장이 바뀌었습니다"
        elif recorded is None:
            r.build, r.why = True, "이 문장으로 만든 것인지 모릅니다"
        elif recorded != spoken:
            r.build, r.why = True, "문장이 바뀌었습니다 (옛 기록과 다릅니다)"
        else:
            r.known = dict(r.known, hash=r.hash)
            seeded = True
            r.why = "옛 기록으로 확인했습니다"

        # ② 올려야 하는가
        #
        # ★ 모르는 것은 모른다고 합니다 ★
        #
        #   --offline 일 때는 로봇에 안 물어본 것입니다. 그런데 처음에는
        #   그 자리에 "로봇에 없습니다" 라고 적었습니다. **없다고 단정할
        #   근거가 없는데요.** 게다가 고리에 걸려 있었습니다 —
        #   "로봇에 있으면 올린 것으로 친다" 고 해놓고, 로봇에 있는지를
        #   "올린 것으로 쳤는가" 로 판단했습니다. 그러니 영원히 거짓입니다.
        #
        #   화면 위에 "기억일 뿐입니다" 라고 적어뒀다고 해서, 아래 줄에서
        #   단정해도 되는 것은 아닙니다. 사람은 표를 봅니다.
        if on_robot is None:
            if r.known.get("uploaded_hash") == r.hash:
                r.on_robot, r.robot_known = True, True
            elif r.known.get("uploaded_hash"):
                r.on_robot, r.robot_known = True, True    # 옛 문장이 올라가 있음
            else:
                r.on_robot, r.robot_known = False, False  # 모릅니다
        else:
            r.on_robot, r.robot_known = key in on_robot, True

            # ★ 로봇에 있고 지역 파일도 맞으면 올린 것으로 봅니다 ★
            #   built.json 이 없던 시절에 올린 것들입니다. 로봇에 그
            #   이름이 있고 지역 파일이 지금 문장으로 만들어졌다면,
            #   로봇의 것도 같은 문장입니다 — 옛 upload_all 도
            #   texts.json 을 근거로 갈아치웠으니까요.
            #
            #   틀릴 수 있습니다. 그래서 --rebuild 를 뒀습니다.
            if seeded and r.on_robot and "uploaded_hash" not in r.known:
                r.known = dict(r.known, uploaded_hash=r.hash)

        if not r.robot_known:
            r.upload = True                      # 모르니 올릴 것으로 셉니다
            r.why = "로봇에 물어봐야 압니다"
        elif not r.on_robot:
            r.upload = True
            r.why = "로봇에 없습니다"
        elif r.known.get("uploaded_hash") != r.hash:
            r.upload = True
            r.why = r.why if r.build else "로봇의 것이 옛 문장입니다"
        elif not r.build:
            # ★ 어떻게 알았는지에 따라 말이 다릅니다 ★
            #   우리가 올린 것이면 "그대로" 가 맞습니다. 로봇 목록에서
            #   이름만 보고 적어둔 것이면 아직 짐작입니다 — remember()
            #   에 왜 그런지 적어뒀습니다.
            if r.known.get("how") == "목록":
                r.why = r.why or "로봇에 이름은 있습니다 (내용은 못 봤습니다)"
            else:
                r.why = r.why or "그대로입니다"
        if rebuild:
            r.build = r.upload = True
            r.why = "--rebuild"
        rows.append(r)
    return rows, built


def show(course, rows, guessed):
    todo_build = [r for r in rows if r.build]
    todo_up = [r for r in rows if r.upload]
    same = [r for r in rows if not r.build and not r.upload]

    print("=" * 70)
    print(f" {course.id} · {course.name}")
    print("=" * 70)
    if guessed:
        print(" ※ 로봇에 안 물어봤습니다 — 아래 '로봇' 칸은 기억일 뿐입니다.")
    print(f"   멘트 {len(rows)}개 · 그대로 {len(same)} · "
          f"만들 것 {len(todo_build)} · 올릴 것 {len(todo_up)}")
    print()
    print(f" {'이름':<26}{'크기':>9}  {'로봇':<5}{'할 일'}")
    print(" " + "-" * 66)
    for r in rows:
        kb = f"{r.bytes / 1024:.0f} KB" if r.bytes else "—"
        mark = "○" if r.on_robot else ("·" if r.robot_known else "?")
        job = []
        if r.build:
            job.append("만들기")
        if r.upload:
            job.append("올리기")
        print(f" {r.key:<26}{kb:>9}  {mark:<5}"
              f"{' + '.join(job) or '—':<12}{r.why}")

    secs = sum(r.seconds for r in todo_up)
    print()
    unsure = [r for r in todo_up if not r.robot_known]
    if todo_up:
        # ★ 모르는 크기를 채우는 자리입니다 — 그렇다고 말해야 합니다 ★
        #
        #   아직 안 만든 음성은 크기를 모릅니다. 있는 것들의 평균으로
        #   채우는데, **하나도 없으면 1 MB 라고 칩니다.** 그건 잰 값이
        #   아니라 그냥 정해둔 숫자입니다.
        #
        #   새 코스를 만들면 이 경우가 됩니다. 화면에는 "약 16분" 이
        #   딱 떨어지게 뜨고, 보는 사람은 그게 잰 값인 줄 압니다.
        #   어제 built.json 의 'how' 칸에 적은 것과 같은 문제입니다 —
        #   **짐작을 사실 칸에 적으면 구별이 안 됩니다.**
        known = [r.bytes for r in rows if r.bytes]
        blind = [r for r in todo_up if not r.bytes]
        avg = sum(known) / len(known) if known else 1024 * 1024
        secs += sum(avg for r in blind) / (1024 * 1024) * SECONDS_PER_MB
        print(f" 올리는 데 약 {secs / 60:.0f}분 걸립니다 "
              f"({len(todo_up)}개, 1 MB 당 {SECONDS_PER_MB:.0f}초)")
        if blind and not known:
            print(f" ※ {len(blind)}개는 **아직 안 만들어서 크기를 모릅니다.**")
            print(f"   하나에 {avg / 1024 / 1024:.1f} MB 라고 **치고** 셈한 값입니다 —")
            print("   잰 값이 아닙니다. 만들고 나면 정확해집니다.")
        elif blind:
            print(f" ※ 그중 {len(blind)}개는 아직 안 만들어서 크기를 모릅니다 —")
            print(f"   이미 있는 {len(known)}개의 평균 {avg / 1024 / 1024:.1f} MB "
                  "로 채워 셈했습니다.")
        if unsure:
            print(f" ※ 그중 {len(unsure)}개는 **로봇에 있는지 모릅니다** "
                  "('?' 표). 이미 있으면 그만큼 짧아집니다.")
            print("   로봇을 켜고 --offline 없이 돌리면 정확히 나옵니다.")
    else:
        print(" 올릴 것이 없습니다.")
    return todo_build, todo_up


# ── 만들기 ───────────────────────────────────────────────────

async def make_one(row):
    """멘트 하나를 만들고 길이를 잽니다."""
    import common
    import scenario
    import voices
    audio = _audio_dir()
    audio.mkdir(parents=True, exist_ok=True)
    for ext in (".mp3", ".wav"):        # 옛것을 먼저 치웁니다
        f = audio / f"{row.key}{ext}"
        if f.exists():
            f.unlink()
    mp3 = await common.make_tts(scenario.for_tts(row.text),
                                audio / f"{row.key}.mp3")
    wav = common.prepare_wav(mp3, verbose=False)
    row.mp3 = Path(mp3)
    row.bytes = Path(wav).stat().st_size
    secs = voices.wav_seconds(wav)
    if secs is not None:
        remember_length(row.key, secs)
    return secs


def remember_length(key, secs):
    """audio/durations.json 에도 적습니다.

    ★ 두 곳에 적는 것이 마음에 안 들지만, 지금은 이래야 합니다 ★

      길이는 built.json 에 들어갑니다 (거기가 저장소에 남으니까요).
      그런데 **시간표를 짜는 scenario.measured() 는 durations.json 을
      읽습니다.** 여기를 안 고치면 음성은 새로 만들어졌는데 시간표는
      옛 길이를 그대로 씁니다 — 화면의 '12초 실측' 이 거짓말이 되고,
      멘트가 끝나기 전에 다음으로 넘어갑니다.

      나중에 scenario 가 built.json 을 보게 되면 이 함수는 사라집니다.
      그때까지는 **적는 쪽이 두 곳을 다 챙깁니다.** 읽는 쪽이 두 곳을
      뒤지게 만드는 것보다 낫습니다.
    """
    import json
    import scenario
    p = _audio_dir() / "durations.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except json.JSONDecodeError:
        data = {}
    data[key] = round(secs, 2)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    scenario._MEASURED = None        # 다음에 읽을 때 새로 읽게 합니다


# ── 올리기 ───────────────────────────────────────────────────

async def push(course, hub, rows, built, dry=False):
    """만들고 올립니다. **한 개 끝날 때마다 built.json 을 씁니다.**"""
    import common
    todo = [r for r in rows if r.build or r.upload]
    if not todo:
        print(" 할 일이 없습니다.")
        return 0

    done = 0
    t0 = time.time()
    for n, r in enumerate(todo, 1):
        head = f" [{n}/{len(todo)}] {r.key}"
        try:
            if r.build:
                print(f"{head}  음성을 만듭니다…")
                secs = await make_one(r)
                built["keys"].setdefault(r.key, {})
                built["keys"][r.key].update(
                    {"hash": r.hash, "seconds": secs, "bytes": r.bytes})
                built["keys"][r.key].pop("uploaded_hash", None)  # 다시 올려야
                coursefile.save_built(course.id, built)
                print(f"          {secs:.1f}초 · {r.bytes / 1024:.0f} KB")

            if r.upload and not dry:
                mins = r.bytes / (1024 * 1024) * SECONDS_PER_MB / 60
                print(f"{head}  로봇에 올립니다 (약 {mins:.0f}분)…")
                took = time.time()
                await common.upload_phrase(hub, r.mp3, replace=True)
                built["keys"].setdefault(r.key, {})
                built["keys"][r.key]["uploaded_hash"] = r.hash
                built["keys"][r.key]["how"] = "올림"   # 우리가 올린 것입니다
                coursefile.save_built(course.id, built)
                print(f"          ○ {time.time() - took:.0f}초")
                done += 1
            elif r.upload and dry:
                print(f"{head}  (올리지는 않습니다 — --dry)")
        except KeyboardInterrupt:
            raise
        except Exception as e:
            # ★ 하나가 넘어져도 나머지는 갑니다 ★
            #   19분짜리 일이 8분째에 하나 때문에 통째로 멈추면,
            #   다시 8분을 기다려야 합니다.
            print(f"          ★ {type(e).__name__}: {e}")

    print()
    print(f" {done}개를 올렸습니다 · {(time.time() - t0) / 60:.0f}분 걸렸습니다.")
    return done


def remember(course, rows, built):
    """로봇 목록에서 본 것을 built.json 에 적습니다.

    ★ plan 은 아무것도 안 바꾸는 것 아니었나 ★

      로봇과 음성 파일은 안 건드립니다. built.json 은 다릅니다 —
      그건 사이안 님 물건이 아니라 **도구가 스스로 기억하는 자리**
      입니다. 방금 로봇에 물어놓고 버리면, 다음 --offline 도 또
      '?' 로 나옵니다.

    ★ 여기서 '확인' 이라고 쓰려다 말았습니다 ★

      로봇 목록은 **이름만** 줍니다. 그 이름 아래 어떤 소리가
      들었는지는 안 알려줍니다. 그러니 이건 확인이 아니라 짐작
      입니다 — 이름이 있고 지역 파일이 지금 문장으로 만들어졌으니
      로봇의 것도 같겠거니, 하는.

      대개 맞습니다. 틀리는 경우는 하나입니다: 누가 음성을 새로
      만들어놓고 안 올렸을 때. 그래서 적기는 적되 **어디서 알았는지
      같이 적습니다.** 나중에 데모에서 엉뚱한 소리가 나면, 표에
      '내용은 못 봤습니다' 라고 적혀 있는 줄이 뒤져볼 첫 자리입니다.

      "그대로입니다" 라고 써버리면 그 줄은 뒤져볼 이유가 없어집니다.
    """
    n = 0
    for r in rows:
        if not r.robot_known or r.build or r.upload:
            continue
        was = built["keys"].get(r.key, {})
        if was.get("hash") == r.hash and was.get("uploaded_hash") == r.hash:
            continue                          # 이미 아는 것
        built["keys"].setdefault(r.key, {}).update(
            {"hash": r.hash, "uploaded_hash": r.hash, "bytes": r.bytes,
             "how": "목록"})                   # 이름만 봤습니다
        n += 1
    if n:
        coursefile.save_built(course.id, built)
    return n


# ── 로봇에게 묻기 ────────────────────────────────────────────

async def ask_robot():
    """(conn, hub, 로봇에 있는 이름들)."""
    import common
    conn = await common.connect()
    hub = common.make_audio_hub(conn)
    await common.set_play_once(hub, verbose=False)
    names = {i.get("CUSTOM_NAME") for i in await common._audio_list(hub)}
    return conn, hub, names


# ── 실행 ─────────────────────────────────────────────────────

def pick(cid):
    import courses
    courses.discover()
    if not cid:
        return None
    c = courses.get(cid)
    if c is None:
        have = ", ".join(x.id for x in courses.COURSES) or "(없음)"
        print(f"★ '{cid}' 라는 코스가 없습니다. 있는 것: {have}")
    return c


async def cmd_list():
    import courses
    courses.discover()
    print("=" * 70)
    print(" 코스")
    print("=" * 70)
    for c in courses.COURSES:
        built = coursefile.load_built(c.id)
        rows, _b = survey(c)
        up = sum(1 for r in rows if r.upload)
        print(f"   {c.id:<12}{c.name}")
        print(f"   {'':<12}지점 {len(c.steps)} · 멘트 {len(rows)} · "
              f"올릴 것 {up} (기억 기준 — 로봇엔 안 물어봤습니다)")
        if built.get("damaged"):
            print(f"   {'':<12}★ built.json 이 깨져 있습니다 — 새로 셉니다")
    print()
    print(" 로봇까지 보려면:  .\\run studio.py plan <코스>")
    return 0


async def cmd_plan(cid, offline, rebuild=False):
    c = pick(cid)
    if c is None:
        return 1
    if offline:
        rows, _b = survey(c, rebuild=rebuild)
        show(c, rows, guessed=True)
        return 0
    conn, _hub, names = await ask_robot()
    try:
        rows, built = survey(c, on_robot=names, rebuild=rebuild)
        show(c, rows, guessed=False)
        n = remember(c, rows, built)
        if n:
            print(f" 알아낸 것 {n}개를 built.json 에 적었습니다 — "
                  "다음엔 --offline 으로도 보입니다.")
    finally:
        import common
        await common.disconnect(conn)
    return 0


async def cmd_push(cid, dry, rebuild=False):
    c = pick(cid)
    if c is None:
        return 1
    bad = [w for m, w in coursefile.check(c) if m == "★"]
    if bad:
        print("★ 먼저 고칠 것이 있습니다:")
        for w in bad:
            print(f"   · {w}")
        print("   (.\\run coursefile.py --check 로 전부 봅니다)")
        return 1

    conn, hub, names = await ask_robot()
    try:
        rows, built = survey(c, on_robot=names, rebuild=rebuild)
        _b, todo_up = show(c, rows, guessed=False)
        print()
        if not dry and todo_up:
            print(" 시작합니다. Ctrl+C 로 멈춰도 다음에 남은 것만 합니다.")
        print("─" * 70)
        await push(c, hub, rows, built, dry=dry)
    finally:
        import common
        await common.disconnect(conn)
    return 0


def main():
    args = sys.argv[1:]
    what = args[0] if args else "list"
    cid = args[1] if len(args) > 1 and not args[1].startswith("--") else None
    if what == "list":
        return asyncio.run(cmd_list())
    if what == "plan":
        return asyncio.run(cmd_plan(cid, "--offline" in args,
                                    "--rebuild" in args))
    if what == "push":
        return asyncio.run(cmd_push(cid, "--dry" in args,
                                    "--rebuild" in args))
    print(__doc__)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        print("\n멈췄습니다. 올린 데까지는 기억해 뒀습니다 — "
              "다시 돌리면 남은 것만 합니다.")
        sys.exit(1)
