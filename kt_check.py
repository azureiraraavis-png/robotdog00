# -*- coding: utf-8 -*-
"""코틀린 파일을 컴파일 없이 훑어봅니다 — 제가 자꾸 내는 실수만.

  ★ 왜 이게 있어야 하는가 ★

    이 저장소의 화면(remote.py)에는 check_page() 가 있습니다. 그 3번
    규칙이 **"문자열 안에 진짜 줄바꿈이 들어가면 스크립트가 통째로
    죽는다"** 입니다. 실제로 그것 때문에 화면의 모든 버튼이 먹통이 된
    적이 있습니다.

    그런데 **코틀린에는 그 검사기가 없었습니다.** 그래서 같은 실수를
    또 했습니다 (2026-09-11). 파이썬 스크립트로 Kotlin 파일을 고치면서
    `\\n` 을 진짜 줄바꿈으로 써 넣었고, 문자열 넷이 줄 중간에서
    끊겼습니다. 오류 14개가 한꺼번에 났습니다.

        Syntax error: Expecting "".        :265
        Unresolved reference '인증서'.      :267   ← 글자가 코드가 됐습니다
        Unresolved reference '지문'.        :267

    안드로이드 스튜디오가 잡아주기는 합니다. 다만 그건 **사이안 님
    화면에서** 잡힙니다. 제 쪽에서 먼저 걸러야 할 것들입니다.

  ★ 무엇을 보는가 ★

    컴파일러 흉내를 내지 않습니다. 그건 안드로이드 스튜디오가 합니다.
    **제가 실제로 낸 실수**만 봅니다.

      1. 문자열 안의 진짜 줄바꿈      (오늘 낸 것)
      2. 문자열 안의 홀로 선 $         ($ 는 값 끼워넣기 시작입니다)
      3. 중괄호가 안 맞는가
      4. @JavascriptInterface 없이 브리지에 넣은 함수

  쓰는 법

      .\\run kt_check.py                     phone/ 아래 전부
      .\\run kt_check.py 어떤파일.kt          하나만
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent


def scan(text):
    """글자를 하나씩 따라가며 어디가 문자열이고 어디가 주석인지 가립니다.

    ★ 처음에는 정규식으로 지웠습니다. 그게 틀렸습니다 ★

      주석을 먼저 지웠더니 **문자열 안의 // 까지 지웠습니다.**
      "https://guide.local" 이 "https: 가 되어 따옴표가 홀로 남고,
      멀쩡한 줄 넷이 빨갛게 떴습니다. Sig.kt 는 몇 주째 잘 컴파일되던
      파일인데요.

      늑대를 부르는 검사기는 없느니만 못합니다. 한 번 헛울리면 다음
      진짜 경고도 무시하게 됩니다 — 이 저장소에 이미 적어둔 말입니다.

      순서를 바꾸는 것으로는 안 됩니다. 주석 안에 따옴표가 있고 문자열
      안에 //가 있으니, **어느 쪽을 먼저 지워도 다른 쪽이 망가집니다.**
      한 번에 같이 봐야 합니다.

    돌려주는 것: (줄번호, 그 줄의 상태) 목록과, 문자열 밖의 글자만 남긴 글.
    """
    out = []            # 문자열·주석을 뺀 글자들 (중괄호 세는 데 씁니다)
    unclosed = []       # 문자열이 줄 끝까지 안 닫힌 줄
    lone = []           # 홀로 선 $ 가 있는 줄

    i, n, line = 0, len(text), 1
    state = "code"      # code · line · block · str · raw · chr
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""

        if c == "\n":
            if state == "str":
                unclosed.append(line)
                state = "code"          # 다음 줄은 새로 봅니다
            elif state == "line":
                state = "code"
            line += 1
            out.append("\n")
            i += 1
            continue

        if state == "code":
            if c == "/" and nxt == "/":
                state = "line"; i += 2; continue
            if c == "/" and nxt == "*":
                state = "block"; i += 2; continue
            if text.startswith('"""', i):
                state = "raw"; i += 3; continue
            if c == '"':
                state = "str"; i += 1; continue
            if c == "'":
                state = "chr"; i += 1; continue
            out.append(c); i += 1; continue

        if state == "line":
            i += 1; continue

        if state == "block":
            if c == "*" and nxt == "/":
                state = "code"; i += 2
            else:
                i += 1
            continue

        if state == "raw":
            if text.startswith('"""', i):
                state = "code"; i += 3
            else:
                i += 1
            continue

        if state == "chr":
            if c == "\\":
                i += 2
            elif c == "'":
                state = "code"; i += 1
            else:
                i += 1
            continue

        # state == "str"
        if c == "\\":
            i += 2; continue
        if c == '"':
            state = "code"; i += 1; continue
        if c == "$":
            after = nxt
            if not (after.isalpha() or after == "_" or after == "{"):
                lone.append(line)
        i += 1

    if state == "str":
        unclosed.append(line)
    return "".join(out), sorted(set(unclosed)), sorted(set(lone))


def look(path):
    raw = path.read_text(encoding="utf-8")
    code, unclosed, lone = scan(raw)
    bad = []

    # ── 1. 문자열 안의 진짜 줄바꿈 ────────────────────────────
    #
    #   코틀린의 보통 문자열("…")은 줄을 넘을 수 없습니다. 넘으면 그
    #   줄에서 문법이 깨지고 **그 뒤의 글자들이 코드로 읽힙니다.**
    #   오류가 엉뚱한 곳에서 무더기로 납니다 — 진짜 원인은 맨 위
    #   한 줄인데요. 실제로 이것 하나로 14개가 났습니다.
    for n in unclosed:
        bad.append((n, "따옴표가 이 줄에서 안 닫혔습니다 — "
                       "코틀린 문자열은 줄을 못 넘습니다"))

    # ── 2. 홀로 선 $ ─────────────────────────────────────────
    #
    #   문자열 안의 $ 는 값 끼워넣기 시작입니다. 뒤에 이름이나 { 가
    #   와야 합니다. 정규식의 '끝' 표시를 그냥 쓰다가 두 번 틀렸습니다.
    for n in lone:
        bad.append((n, "문자열 안에 홀로 선 $ 가 있습니다 — "
                       r"값을 넣는 게 아니면 \$ 로 적으세요"))

    # ── 3. 중괄호 ────────────────────────────────────────────
    depth = 0
    for n, ln in enumerate(code.splitlines(), 1):
        depth += ln.count("{") - ln.count("}")
        if depth < 0:
            bad.append((n, "닫는 중괄호가 하나 많습니다"))
            depth = 0
    if depth:
        bad.append((0, f"중괄호가 {depth}개 안 닫혔습니다"))

    # ── 4. 브리지에 넣고 이름표를 안 붙인 함수 ────────────────
    #
    #   @JavascriptInterface 가 없으면 화면에서 **안 보입니다.**
    #   그런데 컴파일은 됩니다. 화면 쪽에서는 "함수가 없다" 로만 뜨고,
    #   왜 없는지는 안 알려줍니다.
    if "inner class Bridge" in raw:
        body = raw.split("inner class Bridge", 1)[1]
        for m in re.finditer(r"\n\s*(private\s+)?fun\s+(\w+)", body):
            if m.group(1):
                continue                      # private 은 화면이 안 씁니다
            if "@JavascriptInterface" not in body[max(0, m.start() - 160):m.start()]:
                bad.append((0, f"Bridge 의 '{m.group(2)}' 에 "
                               "@JavascriptInterface 가 없습니다 — "
                               "화면에서 안 보입니다"))
    # ── 5. 다리에서 WebView 를 직접 만지는가 ─────────────────
    #
    #   ★ 컴파일은 됩니다. 화면도 멀쩡해 보입니다 ★
    #
    #     @JavascriptInterface 함수는 'JavaBridge' 라는 딴 실에서 돕니다.
    #     WebView 의 메서드(web.url, web.loadUrl …)는 **UI 실에서만**
    #     부를 수 있어서, 거기서 부르면 던집니다.
    #
    #     그런데 화면에는 **아무 일도 안 일어난 것처럼** 보입니다.
    #     단추를 눌러도 조용하고 오류도 안 뜹니다. 2026-09-11 에
    #     `val url = web.url` 한 줄로 그렇게 막혔습니다 — 화면에 뜬
    #     "아직 안 정했습니다" 는 HTML 에 원래 적혀 있던 글자였습니다.
    #
    #     runOnUiThread { } 안에 있으면 괜찮습니다.
    if "inner class Bridge" in raw:
        body = raw.split("inner class Bridge", 1)[1]
        start = raw.index("inner class Bridge")
        line0 = raw[:start].count("\n") + 1
        depth, ui = 0, []          # ui: runOnUiThread 가 열린 깊이들
        for k, ln in enumerate(strip_for_braces(body).splitlines()):
            if "runOnUiThread" in ln or "Thread {" in ln:
                ui.append(depth + ln.count("{"))
            hit = re.search(r"\bweb\.(\w+)", ln)
            if hit and not ui:
                bad.append((line0 + k,
                            f"다리 안에서 web.{hit.group(1)} 를 직접 만집니다 — "
                            "JavaBridge 실입니다. runOnUiThread 로 감싸거나 "
                            "미리 적어둔 값을 쓰세요"))
            depth += ln.count("{") - ln.count("}")
            while ui and depth < ui[-1]:
                ui.pop()
    return bad


def strip_for_braces(text):
    """중괄호만 세려고 문자열·주석을 지웁니다 (줄 수는 지킵니다)."""
    code, _u, _l = scan(text)
    return code


# 화면이 이것을 부르면 ─────→ 매니페스트에 이 줄들이 다 있어야 합니다
NEEDS = {
    "getUserMedia": ("RECORD_AUDIO", "MODIFY_AUDIO_SETTINGS"),
}


def look_manifest():
    """화면이 달라는 것과 매니페스트가 적어둔 것이 맞는지 봅니다.

    ★ 왜 이게 있어야 하는가 (2026-09-11) ★

      RECORD_AUDIO 는 적었는데 MODIFY_AUDIO_SETTINGS 를 빠뜨렸습니다.
      WebView 의 Chromium 은 **둘을 같이** 봅니다. 하나만 있으면 장치
      목록에는 마이크가 보이는데 여는 데서 막힙니다.

      막히는 꼴이 고약합니다 —

        · 화면에 올라오는 것은 NotReadableError 하나뿐입니다.
          그 이름은 '누가 쓰고 있다' 로도, '권한이 없다' 로도 읽힙니다.
          저는 그 둘을 차례로 짐작했고 **둘 다 틀렸습니다.**
        · 설정의 권한 화면에는 '마이크 — 허용됨, 거부된 권한 없음' 으로
          나옵니다. MODIFY_AUDIO_SETTINGS 는 물어보는 권한이 아니라서
          거기 아예 안 나옵니다. **보고 있어도 안 보입니다.**
        · 같은 폰의 브라우저에서는 됩니다 (크롬은 둘 다 선언합니다).
          그래서 '앱이 뭔가 잘못했다' 까지는 알아도 무엇인지는 모릅니다.

      진짜 이름은 Logcat 의 cr_media 한 줄에만 있었습니다. 거기까지
      가는 데 짐작 세 번이 걸렸습니다. 한 번 걸렸으면 그만입니다.
    """
    man = HERE / "phone" / "GuideRemote" / "app" / "src" / "main" / "AndroidManifest.xml"
    if not man.exists():
        return []
    said = man.read_text(encoding="utf-8")

    screens = [HERE / "web" / "remote.html",
               HERE / "phone" / "GuideRemote" / "app" / "src" / "main"
               / "assets" / "index.html"]
    asked = ""
    for s in screens:
        if s.exists():
            asked += s.read_text(encoding="utf-8")

    bad = []
    for call, perms in NEEDS.items():
        if call not in asked:
            continue
        for p in perms:
            if f"android.permission.{p}" not in said:
                bad.append((0, f"화면이 {call} 을 부르는데 매니페스트에 "
                               f"{p} 가 없습니다 — 화면에는 "
                               "NotReadableError 로만 보입니다"))
    return bad


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = ([Path(a) for a in args] if args
             else sorted((HERE / "phone").rglob("*.kt")))
    files = [f for f in files if "build" not in f.parts]
    if not files:
        print(" 볼 파일이 없습니다.")
        return 1

    print("=" * 70)
    print(" 코틀린 훑어보기 — 컴파일 전에 걸러낼 것들")
    print("=" * 70)
    print(" ※ 컴파일러 흉내가 아닙니다. 안드로이드 스튜디오가 할 일은")
    print("   거기서 합니다. 여기서는 제가 자꾸 내는 실수만 봅니다.")
    print()

    total = 0
    for f in files:
        bad = look(f)
        total += len(bad)
        mark = "★" if bad else "○"
        print(f" {mark} {f.relative_to(HERE) if HERE in f.parents else f}"
              f"   ({sum(1 for _ in f.read_text(encoding='utf-8').splitlines())}줄)")
        for n, why in bad:
            where = f"{n:>5}번째 줄" if n else "      파일 전체"
            print(f"     {where}  {why}")

    # 매니페스트는 파일 하나가 아니라 **화면과의 짝**을 봅니다.
    # 파일을 하나만 찍어서 부를 때는 건너뜁니다.
    if not args:
        mbad = look_manifest()
        total += len(mbad)
        print(f" {'★' if mbad else '○'} phone/…/AndroidManifest.xml"
              f"   (화면이 달라는 것과 맞는가)")
        for n, why in mbad:
            print(f"           {why}")

    print()
    print("=" * 70)
    if total:
        print(f" {total}가지가 걸립니다. 고치고 빌드하세요.")
        return 1
    print(" 걸리는 것이 없습니다. 이제 안드로이드 스튜디오에 물어보세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
