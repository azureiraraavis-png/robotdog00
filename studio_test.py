# -*- coding: utf-8 -*-
"""
작업실이 뜻대로 올리는가 — **가짜 로봇 허브로 확인합니다.**

  ★ 왜 가짜로 하는가 ★

    진짜로 재려면 한 번에 19분입니다. "끊었다 이어도 되는가" 를
    확인하려면 그걸 두 번 해야 하고요. 40분을 들여 알아낼 일이
    아닙니다.

    그리고 여기서 보는 것은 **판단**입니다 — 무엇을 다시 만들고 무엇을
    올릴지 정하는 규칙이요. 그 판단에는 로봇이 필요 없습니다.

  ★ 무엇을 보는가 ★

      1. 처음에는 전부 만들고 전부 올립니다
      2. 두 번째에는 **아무것도 안 합니다**
      3. 문장을 고치면 그것만 다시
      4. 로봇에서 사라지면 그것만 다시 (기억보다 로봇을 믿습니다)
      5. 끊겼다 이어도 **남은 것만** 합니다
      6. 하나가 넘어져도 나머지는 갑니다

  ※ 로봇에 연결하지 않습니다. TTS 도 안 부릅니다 (가짜로 바꿔칩니다).

  쓰는 법

      .\\run studio_test.py
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

import coursefile
import scenario
import studio


# ── 가짜 로봇 허브 ───────────────────────────────────────────

class FakeHub:
    """common 이 쓰는 만큼만 흉내 냅니다.

    ★ 받은 것을 진짜로 담아둡니다 ★
      "불렀는가" 만 세면 올리는 척만 해도 통과합니다. 여기서는 실제로
      목록에 넣고, 다음 번 조사가 그걸 보게 합니다.
    """

    def __init__(self, names=()):
        self.files = {n: f"uuid-{n}" for n in names}
        self.uploaded = []
        self.deleted = []
        self.blow_up_on = set()      # 이 이름은 일부러 터뜨립니다

    async def get_audio_list(self):
        return {"data": {"data": json.dumps({"audio_list": [
            {"CUSTOM_NAME": n, "UNIQUE_ID": u}
            for n, u in self.files.items()]})}}

    async def upload_audio_file(self, path):
        name = Path(path).stem
        if name in self.blow_up_on:
            raise RuntimeError("일부러 터뜨림")
        self.files[name] = f"uuid-{name}"
        self.uploaded.append(name)

    async def delete_record(self, uuid):
        self.deleted.append(uuid)
        for n, u in list(self.files.items()):
            if u == uuid:
                del self.files[n]

    async def set_play_mode(self, mode):
        return None

    async def get_play_mode(self):
        return "no_cycle"


class Score:
    def __init__(self):
        self.rows = []

    def check(self, name, got, want=True):
        ok = (got == want)
        self.rows.append((ok, name, got, want))
        print(f" {'○' if ok else '★'} {name}")
        if not ok:
            print(f"     받은 것: {got!r}")
            print(f"     바라던 것: {want!r}")
        return ok

    def report(self):
        bad = [r for r in self.rows if not r[0]]
        print()
        print("=" * 70)
        if not bad:
            print(f" 모두 통과했습니다 ({len(self.rows)}가지)")
            print(" 올릴 것만 올립니다. 끊겨도 이어집니다.")
            return True
        print(f" ★ {len(bad)}가지가 어긋납니다 ★")
        for _o, name, _g, _w in bad:
            print(f"   · {name}")
        return False


def a_course():
    return scenario.Course(
        "t_up", "올리기 시험 코스", "",
        [
            scenario.Stop("S1", "홀", "인사", lines=[
                scenario.Line("t_up_a", "첫째 문장입니다."),
                scenario.Line("t_up_b", "둘째 문장입니다."),
            ]),
            scenario.Move("M1", "가는 길", "이동", "t_up_m", "갑니다.",
                          meters=1.0),
        ],
        route="어딘가", audience="누구",
    )


async def main():
    print("=" * 70)
    print(" 작업실이 뜻대로 올리는가")
    print("=" * 70)
    print(" 로봇에 연결하지 않습니다. 가짜 허브에 올립니다.")
    print()
    s = Score()

    import common
    real_tts, real_wav_secs = common.make_tts, None
    tmp = tempfile.TemporaryDirectory()
    audio = Path(tmp.name) / "audio"
    audio.mkdir(parents=True)

    # ★ TTS 를 가짜로 바꿔칩니다 ★
    #   진짜로 부르면 인터넷이 필요하고 몇 초씩 걸립니다. 여기서 보는
    #   것은 "언제 다시 만드는가" 이지 음성의 품질이 아닙니다.
    made = []

    async def fake_tts(text, path):
        made.append(Path(path).stem)
        Path(path).write_bytes(b"MP3" + text.encode("utf-8"))
        return Path(path)

    def fake_prepare(mp3, verbose=True):
        wav = Path(mp3).with_suffix(".wav")
        wav.write_bytes(b"WAV" * 400)     # 그럴듯한 크기
        return wav

    import voices
    common.make_tts = fake_tts
    real_prepare = common.prepare_wav
    common.prepare_wav = fake_prepare
    real_secs = voices.wav_seconds
    voices.wav_seconds = lambda p: 3.5
    old_dir = studio._audio_dir
    studio._audio_dir = lambda: audio
    old_courses = coursefile.COURSES_DIR
    coursefile.COURSES_DIR = Path(tmp.name) / "courses"

    try:
        c = a_course()

        # ── 1. 처음 ─────────────────────────────────────────
        print("─" * 70)
        print(" 처음 — 아무것도 없습니다")
        print("─" * 70)
        hub = FakeHub()
        rows, built = studio.survey(c, on_robot=set())
        s.check("셋 다 만들어야 합니다", sum(r.build for r in rows), 3)
        s.check("셋 다 올려야 합니다", sum(r.upload for r in rows), 3)
        await studio.push(c, hub, rows, built)
        s.check("셋 다 올라갔습니다", sorted(hub.uploaded),
                ["t_up_a", "t_up_b", "t_up_m"])
        s.check("built.json 이 생겼습니다",
                coursefile.built_path("t_up").exists(), True)

        # ★ 시간표가 읽는 곳에도 적었는가 ★
        #   built.json 만 채우면 scenario.measured() 가 옛 길이를 씁니다.
        #   음성은 새것인데 시간표는 옛것 — 멘트가 끝나기 전에 다음으로
        #   넘어갑니다.
        import json as _json
        durs = _json.loads((audio / "durations.json").read_text(
            encoding="utf-8"))
        s.check("durations.json 에도 길이가 들어갑니다",
                sorted(durs), ["t_up_a", "t_up_b", "t_up_m"])
        s.check("길이 값이 맞습니다", durs["t_up_a"], 3.5)

        # ── 1-1. built.json 이 없고 옛 기록만 있을 때 ───────
        print()
        print("─" * 70)
        print(" built.json 없이, 옛 texts.json 만 있을 때")
        print("─" * 70)
        #
        # ★ 여기를 처음에 틀렸습니다 ★
        #   built.json 은 새로 만든 것이라 처음엔 비어 있습니다. 그때
        #   "모른다" 를 "바뀌었다" 로 쳤더니, 이미 맞는 음성 16개를
        #   16분 걸려 다시 올리겠다고 했습니다.
        #
        #   그 정보는 이미 texts.json 에 있었습니다.
        #
        coursefile.built_path("t_up").unlink()      # 새 기억을 지웁니다
        (audio / "texts.json").write_text(_json.dumps(
            {k: scenario.for_tts(v)
             for k, v in coursefile.spoken_texts(c).items()},
            ensure_ascii=False), encoding="utf-8")
        rows, _b = studio.survey(c, on_robot=set(hub.files))
        s.check("옛 기록이 맞으면 다시 안 만듭니다",
                sum(r.build for r in rows), 0)
        s.check("옛 기록이 맞으면 다시 안 올립니다",
                sum(r.upload for r in rows), 0)
        s.check("어디서 알았는지 말해줍니다",
                rows[0].why, "옛 기록으로 확인했습니다")

        # 옛 기록이 지금 문장과 다르면 다시 만들어야 합니다
        (audio / "texts.json").write_text(_json.dumps(
            {"t_up_a": "옛날 문장입니다."}, ensure_ascii=False),
            encoding="utf-8")
        rows, _b = studio.survey(c, on_robot=set(hub.files))
        # 셋 다 다시 만드는 것이 맞습니다 — 까닭이 다를 뿐입니다.
        # t_up_a 는 기록이 **다르고**, 나머지 둘은 기록이 **없습니다.**
        # 처음에 "t_up_a 만" 이라고 적었다가 시험이 바로잡았습니다.
        s.check("옛 기록이 다르면 그렇게 말해줍니다",
                [r.why for r in rows if r.key == "t_up_a"],
                ["문장이 바뀌었습니다 (옛 기록과 다릅니다)"])
        s.check("기록이 아예 없으면 '모릅니다' 라고 합니다",
                [r.why for r in rows if r.key == "t_up_b"],
                ["이 문장으로 만든 것인지 모릅니다"])
        s.check("까닭이 무엇이든 다시 만듭니다",
                sum(r.build for r in rows), 3)

        # --rebuild 는 묻지 않고 전부
        rows, _b = studio.survey(c, on_robot=set(hub.files), rebuild=True)
        s.check("--rebuild 는 전부 다시 합니다",
                sum(r.build and r.upload for r in rows), 3)

        (audio / "texts.json").unlink()
        coursefile.save_built("t_up", _json.loads(
            '{"version": 1, "keys": {}}'))
        rows, built = studio.survey(c, on_robot=set())
        await studio.push(c, hub, rows, built)   # 기억을 다시 채웁니다
        hub.uploaded.clear()
        made.clear()

        # ── 2. 두 번째 ──────────────────────────────────────
        print()
        print("─" * 70)
        print(" 두 번째 — 바뀐 것이 없습니다")
        print("─" * 70)
        made.clear()
        hub.uploaded.clear()
        rows, built = studio.survey(c, on_robot=set(hub.files))
        s.check("만들 것이 없습니다", sum(r.build for r in rows), 0)
        s.check("올릴 것이 없습니다", sum(r.upload for r in rows), 0)
        s.check("이유가 '그대로입니다'", rows[0].why, "그대로입니다")
        await studio.push(c, hub, rows, built)
        s.check("아무것도 안 올렸습니다", hub.uploaded, [])
        s.check("음성도 안 만들었습니다", made, [])

        # ── 3. 문장을 고치면 ────────────────────────────────
        print()
        print("─" * 70)
        print(" 문장 하나를 고칩니다")
        print("─" * 70)
        c.steps[0].lines[1].text = "둘째 문장을 고쳤습니다."
        rows, built = studio.survey(c, on_robot=set(hub.files))
        s.check("고친 것만 다시 만듭니다",
                [r.key for r in rows if r.build], ["t_up_b"])
        s.check("고친 것만 다시 올립니다",
                [r.key for r in rows if r.upload], ["t_up_b"])
        s.check("이유를 말해줍니다",
                [r.why for r in rows if r.build], ["문장이 바뀌었습니다"])
        await studio.push(c, hub, rows, built)
        s.check("하나만 올라갔습니다", hub.uploaded, ["t_up_b"])

        # ── 4. 로봇에서 사라지면 ────────────────────────────
        print()
        print("─" * 70)
        print(" 로봇에서 하나가 사라집니다 (다른 사람이 지웠다든지)")
        print("─" * 70)
        #
        # ★ 기억보다 로봇을 믿습니다 ★
        #   built.json 은 "올렸다" 고 적어놨습니다. 그래도 로봇에 없으면
        #   없는 것입니다. 기억을 믿으면 시연장에서 그 멘트만 조용히
        #   안 나옵니다.
        #
        del hub.files["t_up_m"]
        hub.uploaded.clear()
        made.clear()
        rows, built = studio.survey(c, on_robot=set(hub.files))
        s.check("사라진 것만 올립니다",
                [r.key for r in rows if r.upload], ["t_up_m"])
        s.check("음성은 다시 안 만듭니다", sum(r.build for r in rows), 0)
        s.check("이유가 '로봇에 없습니다'",
                [r.why for r in rows if r.upload], ["로봇에 없습니다"])
        await studio.push(c, hub, rows, built)
        s.check("하나만 올라갔습니다", hub.uploaded, ["t_up_m"])
        s.check("음성은 안 만들었습니다", made, [])

        # 그리고 기억만 보면 그걸 못 봅니다 — 그래서 로봇에 묻는 것입니다
        del hub.files["t_up_m"]
        blind, _b = studio.survey(c)          # on_robot 없이
        s.check("기억만 보면 사라진 줄 모릅니다",
                sum(r.upload for r in blind), 0)

        # ★ 안 물어봤으면 '없다' 고 하면 안 됩니다 ★
        #   --offline 은 로봇을 안 본 것입니다. 그런데 처음에는 그 자리에
        #   "로봇에 없습니다" 라고 단정했습니다. 근거가 없는 말이고,
        #   16분짜리 일을 하라고 시키는 말입니다.
        coursefile.save_built("t_up", {"version": 1, "keys": {}})
        (audio / "texts.json").write_text(_json.dumps(
            {k: scenario.for_tts(v)
             for k, v in coursefile.spoken_texts(c).items()},
            ensure_ascii=False), encoding="utf-8")
        blind, _b = studio.survey(c)
        s.check("안 물어봤으면 '모른다' 고 합니다",
                sorted({r.why for r in blind}), ["로봇에 물어봐야 압니다"])
        s.check("모르면 로봇 칸이 '?' 입니다",
                sorted({r.robot_known for r in blind}), [False])
        s.check("모를 때도 올릴 것으로는 셉니다 (안전한 쪽)",
                sum(r.upload for r in blind), 3)
        # 물어보면 딱 잘라 말합니다
        asked, _b = studio.survey(c, on_robot={"t_up_a"})
        s.check("물어보면 있는 것과 없는 것을 가립니다",
                [(r.key, r.upload) for r in asked],
                [("t_up_a", False), ("t_up_b", True), ("t_up_m", True)])
        (audio / "texts.json").unlink()

        # ── 5. 끊겼다 이어서 ────────────────────────────────
        print()
        print("─" * 70)
        print(" 절반쯤에서 끊고, 다시 돌립니다")
        print("─" * 70)
        hub2 = FakeHub()
        coursefile.save_built("t_up", {"version": 1, "keys": {}})
        for f in audio.glob("*"):
            f.unlink()
        rows, built = studio.survey(c, on_robot=set())

        # 두 개만 올리고 멈춘 것처럼 만듭니다
        await studio.push(c, hub2, rows[:2], built)
        s.check("둘까지 올라갔습니다", len(hub2.uploaded), 2)

        hub2.uploaded.clear()
        rows, built = studio.survey(c, on_robot=set(hub2.files))
        s.check("남은 하나만 할 일로 잡힙니다",
                [r.key for r in rows if r.upload], ["t_up_m"])
        await studio.push(c, hub2, rows, built)
        s.check("남은 하나만 올렸습니다", hub2.uploaded, ["t_up_m"])

        # ── 6. 하나가 터져도 ────────────────────────────────
        print()
        print("─" * 70)
        print(" 가운데 하나가 터집니다")
        print("─" * 70)
        #
        #   19분짜리 일이 8분째에 하나 때문에 통째로 멈추면, 다시 8분을
        #   기다려야 합니다. 넘어진 것만 남기고 나머지는 갑니다.
        #
        hub3 = FakeHub()
        hub3.blow_up_on = {"t_up_b"}
        coursefile.save_built("t_up", {"version": 1, "keys": {}})
        rows, built = studio.survey(c, on_robot=set())
        await studio.push(c, hub3, rows, built)
        s.check("터진 것 빼고 다 올라갔습니다", sorted(hub3.uploaded),
                ["t_up_a", "t_up_m"])

        rows, built = studio.survey(c, on_robot=set(hub3.files))
        s.check("다음에 터진 것만 다시 잡힙니다",
                [r.key for r in rows if r.upload], ["t_up_b"])

    finally:
        common.make_tts = real_tts
        common.prepare_wav = real_prepare
        voices.wav_seconds = real_secs
        studio._audio_dir = old_dir
        coursefile.COURSES_DIR = old_courses
        tmp.cleanup()

    return 0 if s.report() else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
