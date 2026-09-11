# -*- coding: utf-8 -*-
"""화면(HTML)이 실제로 이어져 있는지 봅니다 — 브라우저 없이.

  ★ 왜 이게 따로 생겼는가 ★

    remote.py 안에 check_page() 가 있었습니다. 좋은 검사기고, 여러 번
    저를 잡았습니다. 그런데 **그 화면 하나만** 봤습니다.

    앱에도 화면이 있습니다 (phone/…/assets/index.html). 거기에는 검사기가
    없었고, 그래서 2026-09-11 에 이런 일이 났습니다 —

      · 자바스크립트는 들어갔는데 HTML 칸이 안 들어갔습니다
      · PC.go 가 null 이 되고, 거기서 스크립트가 터졌습니다
      · **그 아래가 통째로 죽었습니다** — 상관없는 '악수해 보기' 버튼까지
      · 화면은 멀쩡해 보였습니다. 목록도 나오고 초록 칸도 떴습니다

    check_page() 의 1번 규칙이 바로 이것을 잡습니다. 있는 규칙을 딴 화면에
    안 걸어둔 탓입니다.

  ★ 두 방향을 다 봅니다 ★

    스크립트가 찾는데 화면에 없는 것   → 그 줄에서 죽습니다
    화면에 있는데 아무도 안 쓰는 것    → 죽은 자리입니다

    첫째가 위험하고 둘째는 지저분한 것인데, 둘 다 말해줍니다.

  ★ 두 가지 말투를 다 압니다 ★

    web/remote.html 은  $('아이디')          로 씁니다
    앱의 index.html 은  getElementById('…')  로 씁니다

    한쪽만 알면 다른 쪽에서 "아무도 안 쓴다" 고 헛울립니다. 검사기가
    늑대를 부르면 다음 진짜 경고도 무시하게 됩니다.

  쓰는 법

      .\\run web_check.py              저장소의 화면 전부
      .\\run web_check.py 어떤파일.html  하나만
"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent

# 화면 파일들. 새로 생기면 여기 적습니다 — 자동으로 찾으면 build/ 안의
# 남은 것들까지 걸려서 헛울립니다.
SCREENS = [
    HERE / "web" / "remote.html",
    HERE / "phone" / "GuideRemote" / "app" / "src" / "main" / "assets" / "index.html",
]


def split_page(html):
    """몸통과 스크립트로 가릅니다.

    ★ 처음에 틀린 자리 ★
      `html.split("<script>")[0]` 을 몸통으로 삼았습니다. <script> 가
      둘이면 **그 사이의 화면이 통째로 스크립트로 분류됩니다.** 그래서
      멀쩡히 있는 칸 여섯이 "화면에 없다" 고 빨갛게 떴습니다.
      검사기가 늑대를 부르면 다음 진짜 경고도 무시하게 됩니다.
    """
    scripts, body = [], []
    rest = html
    while True:
        i = rest.find("<script")
        if i < 0:
            body.append(rest)
            break
        body.append(rest[:i])
        j = rest.find("</script>", i)
        if j < 0:                       # 안 닫혔으면 나머지는 다 스크립트
            scripts.append(rest[i:])
            break
        head = rest.find(">", i)
        scripts.append(rest[head + 1:j])
        rest = rest[j + len("</script>"):]
    return "".join(body), "\n".join(scripts)


def strip_comments(script):
    """자바스크립트 주석을 지웁니다. 줄 수는 지킵니다.

    주석 안의 따옴표까지 세면 헛울립니다 — 실제로 그랬습니다.
    이 저장소의 주석에는 «"다리가 틀렸나"» 같은 따옴표가 흔합니다.
    """
    def blank(m):
        return "\n" * m.group(0).count("\n")
    script = re.sub(r"/\*(?:.|\n)*?\*/", blank, script)
    return re.sub(r"(?<![:\w])//[^\n]*", "", script)


def style_of(html):
    """<style> 안의 글. 여럿이면 이어붙입니다."""
    return "\n".join(p.split("</style>")[0] for p in html.split("<style>")[1:])


def ids_used(script):
    """스크립트가 실제로 찾는 아이디들. 두 말투를 다 봅니다."""
    got = set(re.findall(r"\$\('([^']+)'\)", script))
    got |= set(re.findall(r"getElementById\('([^']+)'\)", script))
    return got


def look(path):
    html = path.read_text(encoding="utf-8")
    body, raw_script = split_page(html)
    script = strip_comments(raw_script)
    bad = []

    have = set(re.findall(r"\bid=([A-Za-z][\w-]*)", body))
    used = ids_used(script)

    # ── 1. 스크립트가 없는 것을 찾는가 ────────────────────────
    #
    #   이게 제일 위험합니다. null 에 점을 찍는 순간 그 줄에서 터지고,
    #   **그 아래 전부가 안 돕니다.** 상관없어 보이는 버튼들이 같이
    #   먹통이 되니, 원인을 엉뚱한 데서 찾게 됩니다.
    for name in sorted(used - have):
        bad.append(f"★ 스크립트가 '{name}' 을 찾는데 화면에 없습니다 "
                   "— 여기서 터지면 아래가 다 죽습니다")

    # ── 2. 화면에 있는데 아무도 안 쓰는가 ─────────────────────
    #
    #   ★ 자바스크립트만 쓰는 게 아닙니다 ★
    #     CSS 가 #아이디 로 쓰는 자리도 있습니다 (메뉴의 손잡이 같은 것).
    #     그건 죽은 자리가 아니라 **모양만 있는 자리**입니다. 안 빼면
    #     고칠 수 없는 잔소리가 영영 뜨고, 그러면 사람이 이 검사기의
    #     출력을 통째로 안 읽게 됩니다.
    grouped = set(re.findall(r"<[^>]*\bdata-(?:job|k)=[^>]*\bid=([A-Za-z][\w-]*)", body))
    styled = set(re.findall(r"#([A-Za-z][\w-]*)", style_of(html)))
    for name in sorted(have - used - grouped - styled):
        bad.append(f"· 화면의 '{name}' 를 스크립트도 CSS 도 안 씁니다 (죽은 자리)")

    # ── 3. 뜻이 안 붙은 버튼 ─────────────────────────────────
    #
    #   ★ 뜻을 붙이는 방법이 여럿입니다 ★
    #     .onclick = · addEventListener · data-job 목록에 실려 한꺼번에.
    #     한 가지만 알면 나머지 둘을 "죽었다" 고 헛울립니다 — 실제로
    #     remote.html 의 '음량' 과 '누르고 말하기' 를 그렇게 물었습니다.
    #   ※ 태그를 통째로 봅니다. 처음에는 id= **앞쪽**만 봤는데,
    #     `<button class=mfull id=mic data-job=mic>` 처럼 data-job 이
    #     뒤에 오면 못 봅니다. 그래서 멀쩡한 '음량' 버튼을 물었습니다.
    for m in re.finditer(r"<button\b([^>]*)>", body):
        attrs = m.group(1)
        got = re.search(r"\bid=([A-Za-z][\w-]*)", attrs)
        if not got:
            continue
        name = got.group(1)
        wired = (
            f"$('{name}').onclick" in script
            or re.search(rf"\$\('{name}'\)\.addEventListener", script)
            or re.search(rf"getElementById\('{name}'\)", script)
            or "data-job=" in attrs          # [data-job] 을 한꺼번에 거는 곳이 있습니다
            or "data-k=" in attrs
        )
        if not wired:
            bad.append(f"★ '{name}' 버튼에 하는 일이 없습니다")

    # ── 4. 문자열 안의 진짜 줄바꿈 ────────────────────────────
    #
    #   이것 하나로 화면의 **모든** 버튼이 먹통이 된 적이 있습니다.
    for n, line in enumerate(script.splitlines(), 1):
        plain = re.sub(r"\\.", "", line)
        if plain.count("'") % 2 or plain.count('"') % 2:
            bad.append(f"★ 스크립트 {n}번째 줄에서 따옴표가 안 닫혔습니다: "
                       f"{line.strip()[:50]}")

    # ── 5. 자기가 자기를 덮어쓰는 CSS ─────────────────────────
    style = style_of(html)
    SHORT = {"margin": ("margin-left", "margin-right", "margin-top", "margin-bottom"),
             "padding": ("padding-left", "padding-right", "padding-top", "padding-bottom")}
    for block in re.findall(r"\{([^{}]*)\}", style):
        names = [d.split(":", 1)[0].strip()
                 for d in block.split(";") if ":" in d]
        for short, longs in SHORT.items():
            if short not in names:
                continue
            at = names.index(short)
            for long in longs:
                if long in names and names.index(long) < at:
                    bad.append(f"· CSS 에서 '{long}' 을 뒤의 '{short}' 가 "
                               f"덮어씁니다: {block.strip()[:50]}")
    return bad


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = [Path(a) for a in args] if args else [p for p in SCREENS if p.exists()]
    if not files:
        print(" 볼 화면이 없습니다.")
        return 1

    print("=" * 70)
    print(" 화면이 이어져 있는가")
    print("=" * 70)
    print(" ★ 는 고쳐야 하는 것, · 는 지저분한 것입니다.")
    print()

    worst = 0
    for f in files:
        bad = look(f)
        hard = [b for b in bad if b.startswith("★")]
        worst = max(worst, 2 if hard else (1 if bad else 0))
        mark = "★" if hard else ("·" if bad else "○")
        try:
            name = f.relative_to(HERE)
        except ValueError:
            name = f
        print(f" {mark} {name}")
        for b in bad:
            print(f"     {b}")

    print()
    print("=" * 70)
    if worst == 2:
        print(" 고쳐야 하는 것이 있습니다.")
        return 1
    if worst == 1:
        print(" 돌기는 합니다. 지저분한 자리가 있습니다.")
        return 0
    print(" 두 화면 다 이어져 있습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
