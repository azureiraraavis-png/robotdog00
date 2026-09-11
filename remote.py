# -*- coding: utf-8 -*-
"""
휴대폰 리모컨 — 복도에서 안내를 넘길 수 있게.

  ★ 왜 필요한가 ★

    로봇의 움직임은 사람이 조종하기로 정했습니다. 그러면 "여기서 안내
    시작" 신호를 어디서 주느냐가 남는데, PC 가 **데스크톱**입니다.
    조종하는 사람은 복도에 있고 PC 는 방에 있습니다.

    걸어서 왔다 갔다 하는 것은 답이 아닙니다. 정차 지점이 다섯 개인데
    시연 중에 사람이 사라졌다 돌아오는 것을 방문객이 봅니다.

    그런데 조종하는 사람의 주머니에 이미 화면 달린 물건이 있습니다.

  ★ 조종도 여기서 합니다 ★

    게임패드 버튼은 우리에게 오지 않습니다. keys_test.py 로 확인했습니다 —
    **게임패드로 로봇을 실제로 움직이는 동안에도** 우리가 받는 값은
    0 뿐이었습니다. 버튼은 로봇 안에서만 처리되고 밖으로는 안 실립니다.

    그래서 조종을 이 화면으로 옮겼습니다. drive.py 와 같은 배치입니다.

        Q W E    게걸음← · 앞으로 · 게걸음→
        A S D    좌회전  · 뒤로   · 우회전

    ★ 누르고 있는 동안 '아직 누르고 있다' 를 계속 보냅니다 ★
      버튼은 '누른 순간' 만 알려주는데, 걷기는 '누르고 있는 동안'
      갑니다. 손 뗀 신호 하나를 놓치면 로봇이 계속 갑니다 — 복도에서요.
      그래서 반대로 만듭니다. 계속 말하게 하고, 그 말이 끊기면 멈춥니다.
      화면이 가려져도, 네트워크가 끊겨도, 휴대폰 배터리가 나가도 멈춥니다.

      **놓쳐서 멈추는 것은 안전하고, 놓쳐서 계속 가는 것은 아닙니다.**

    ※ 조종판은 '다음' 버튼과 같은 규칙으로 켜집니다 (기다리는 중에만).
      설명·회전 중에 몰면 로봇이 자기 회전과 우리 조종을 동시에 받습니다.

    ※ 게임패드는 여전히 로봇을 움직입니다 — 우리가 그 버튼을 못 읽을
      뿐입니다. **비상 정지 L2+B 도 그대로 됩니다.** 둘을 동시에 잡고
      몰지는 마세요.

  ★ 이게 '앱' 의 첫 조각입니다 ★

    나중에 한국어 전용 앱을 만들게 되면, 이 화면이 그 안으로 들어가면
    됩니다. 지금은 웹페이지 한 장이지만 하는 일은 같습니다 —
    **다음 순서를 사람이 정하고, 로봇이 그 순서를 수행합니다.**

  ★ 무엇에도 기대지 않습니다 ★

    설치할 것이 없습니다. 파이썬 기본 기능만 씁니다.
    휴대폰에는 앱을 깔 필요가 없습니다. 브라우저면 됩니다.
    인터넷도 필요 없습니다 — PC 와 휴대폰이 같은 공유기에 있으면 됩니다
    (로봇이 이미 그 공유기에 있습니다).

  쓰는 법 — 혼자서도 돌아갑니다

      .\\run remote.py

    주소가 뜹니다. 휴대폰 브라우저에 치면 화면이 나옵니다.
    버튼을 누르면 여기 콘솔에 찍힙니다. 연결만 먼저 확인하고 싶을 때
    이렇게 씁니다.

  안내와 같이 쓸 때는 guide.py 가 알아서 띄웁니다

      .\\run guide.py --manual

  ※ 안내 중에 화면이 꺼지지 않게 해둡니다 (Wake Lock). 안드로이드
    크롬·삼성인터넷에서 됩니다. 안 되는 기기라면 화면 오른쪽 위의
    '화면 유지' 글자가 안 뜹니다 — 그때는 설정에서 화면 자동 꺼짐을
    길게 잡아두세요.

  ※ 시연장 공유기에 아무나 붙을 수 있다면, 이 주소를 아는 사람은
    버튼을 누를 수 있습니다. 학과 내부 네트워크라 자물쇠는 안 걸었습니다.
    걱정되면 --pin 1234 로 네 자리를 걸 수 있습니다.
"""

import asyncio
import json
import socket
import sys
import time
from pathlib import Path

PORT = 8765

# 메뉴에서 시킬 수 있는 것들. 여기 없는 이름은 받지 않습니다 —
# 주소창에 아무 말이나 쳐서 로봇을 움직이게 두지 않으려고요.
JOBS = ("stand", "sit", "lie", "light_on", "light_off", "mic",
        "vol_up", "vol_down")

# ★ 그중 다리를 쓰는 것 ★
#   설명·회전 중에는 받지 않습니다. 로봇은 다리가 한 벌뿐이라, 도는
#   도중에 앉히면 4초짜리 회전이 8.2초가 되고 각도도 흐트러집니다
#   (실제 로그). 말하는 도중이면 방문객 앞에서 말과 몸이 따로 놉니다.
#
#   라이트·음성 인식·프로그램 종료는 여기 없습니다 — 언제든 됩니다.
#   메뉴를 통째로 잠그는 것이 아니라, 다리를 쓰는 셋만 잠급니다.
MOTION_JOBS = ("stand", "sit", "lie")

# ★ 기다리는 중에만 받는 것들 ★
#   위의 셋에 '음성 인식' 이 붙습니다. 이유는 다릅니다 — 다리를 다투는
#   것이 아니라, **로봇이 말하는 동안 켜면 자기 말을 듣습니다.**
#   대본의 "지금부터 … 안내해 드리겠습니다" 에 '안내' 가 들어 있고,
#   그것이 '다음' 으로 번역됩니다. 로봇이 자기 말로 자기 안내를 넘깁니다.
#
#   ※ 켜둔 채로 안내가 시작되는 경우는 이것으로 안 막힙니다. 그때는
#     guide.ear_gate 가 마이크를 잠시 막습니다 (stt.Listener.pause).
#     버튼을 잠그는 것과 귀를 막는 것은 다른 일입니다 — 둘 다 합니다.
WAIT_ONLY_JOBS = MOTION_JOBS + ("mic",)

# ── 조종판 ──
#   drive.py 와 **같은 배치, 같은 뜻**입니다. 두 벌을 따로 두면 언젠가
#   한쪽만 고쳐집니다.
#       키 → (전진, 게걸음, 회전)   부호는 사람 기준
#       전진 +앞  /  게걸음 +오른쪽  /  회전 +좌회전
DRIVE = {
    "w": (+1, 0, 0), "s": (-1, 0, 0),      # 앞으로 / 뒤로
    "q": (0, -1, 0), "e": (0, +1, 0),      # 게걸음 왼쪽 / 오른쪽
    "a": (0, 0, +1), "d": (0, 0, -1),      # 좌회전 / 우회전
}
# 손을 뗀 신호를 못 받아도 이만큼 지나면 멈춥니다.
#   ★ 이게 이 기능의 전부입니다 ★
#   버튼은 '누른 순간' 만 알려주는데 걷기는 '누르고 있는 동안' 갑니다.
#   네트워크가 끊기거나 화면이 가려지면 손 뗀 신호가 안 옵니다.
#   그래서 **누르고 있다는 말을 계속 보내게** 하고, 그 말이 끊기면
#   멈춥니다. 놓쳐서 멈추는 것은 안전하고, 놓쳐서 계속 가는 것은 아닙니다.
DEADMAN = 0.45

# 폰이 보내는 녹음의 상한. 3초에 21 KB 였으니 (29번) 넉넉합니다.
# 이보다 크면 우리 것이 아닙니다 — 그 연결은 버립니다.
MAX_BODY = 4 * 1024 * 1024


def cert_finger(path):
    """인증서의 SHA-256 지문. 못 내면 None.

    앱이 보여주는 값과 **글자 그대로** 같아야 합니다. 그래서 앱과 같은
    모양으로 적습니다 — 대문자 두 자리씩, 콜론으로 이음.
    """
    import hashlib
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization
        cert = x509.load_pem_x509_certificate(Path(path).read_bytes())
        der = cert.public_bytes(serialization.Encoding.DER)
        return ":".join(f"{b:02X}" for b in hashlib.sha256(der).digest())
    except Exception:
        return None


def lan_ip():
    """휴대폰이 칠 수 있는 이 PC 의 주소.

    ★ socket.gethostbyname(hostname) 을 쓰면 안 됩니다 ★
      윈도우에서 127.0.0.1 이나 엉뚱한 가상 어댑터 주소가 나옵니다.
      바깥으로 나가는 소켓을 하나 열어서 **실제로 쓰이는 쪽** 주소를
      물어보는 것이 확실합니다. (보내지는 않습니다)
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))       # 실제 통신은 일어나지 않습니다
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


# ── 화면은 web/remote.html 에 있습니다 ──────────────────────
#
# ★ 왜 파이썬 문자열에서 꺼냈는가 ★
#
#   674줄짜리 HTML 이 이 파일 안 문자열로 들어 있었습니다. PC 에서만
#   쓸 때는 아무 문제가 없었습니다. 그런데 **폰이 두뇌가 되면 이 화면이
#   앱 안으로 들어가야 합니다.** 문자열인 채로는 옮기는 방법이 손으로
#   복사하는 것뿐이고, 그러면 같은 화면이 두 곳에 생깁니다.
#
#   코스가 scenario.py 와 course.json 두 곳에 있어서 겪은 것과 똑같은
#   일입니다. 그건 언젠가 갈라집니다.
#
#   파일로 두면 remote.py 가 읽어서 내주고, 앱은 빌드할 때 같은 파일을
#   assets 로 가져갑니다. **고치는 자리는 한 곳입니다.**
#
#   값이 쌌습니다 — f-string 이 아니고 보간 자리가 하나도 없어서
#   통째로 옮기면 끝이었습니다.

SCREEN = Path(__file__).parent / "web" / "remote.html"

try:
    PAGE = SCREEN.read_text(encoding="utf-8")
except FileNotFoundError:
    # 조용히 빈 화면을 띄우면 안 됩니다. 폰에는 흰 종이가 뜨고,
    # 보는 사람은 서버가 고장난 줄 압니다.
    raise SystemExit(
        f"화면 파일이 없습니다: {SCREEN}\n"
        "      remote.py 는 이 파일을 읽어서 휴대폰에 내줍니다.\n"
        "      web/remote.html 이 remote.py 옆에 있어야 합니다."
    )



def check_page():
    """화면이 실제로 이어져 있는지 봅니다. 문제 목록을 돌려줍니다.

    ★ 왜 이게 있어야 하는가 ★

      오늘 같은 실수를 두 번 했습니다.

        1. '다시' 버튼을 만들고 뜻을 안 붙였습니다 (눌러도 아무 일 없음)
        2. 메뉴를 만들고 **자바스크립트를 안 넣었습니다.** 치환이 조용히
           빗나갔는데, 저는 버튼이 있는지만 확인하고 된다고 했습니다.

      둘 다 "있는가" 는 통과하고 "이어져 있는가" 에서 틀렸습니다.
      그리고 브라우저에서만 드러납니다 — 파이썬은 아무 불평도 안 합니다.
      실제로 2번은 스크립트 전체를 죽여서, 화면의 **모든** 버튼이
      먹통이 됐습니다. 문자열 안에 진짜 줄바꿈이 들어간 탓입니다
      (PAGE 가 보통 문자열이라 \n 이 줄바꿈이 됩니다 — \\\n 로 써야 합니다).

      그래서 세 가지를 봅니다. 브라우저 없이 할 수 있는 것들입니다.
    """
    import re
    body, script = PAGE.split("<script>")[0], PAGE.split("<script>")[1]
    script = script.split("</script>")[0]
    bad = []

    ids = set(re.findall(r"id=([A-Za-z][\w-]*)", body))
    used = set(re.findall(r"\$\('([^']+)'\)", script))

    # 1. 스크립트가 없는 것을 찾고 있지 않은가  (null 이면 그 줄에서 죽습니다)
    for name in sorted(used - ids):
        bad.append(f"스크립트가 $('{name}') 를 찾는데 화면에 없습니다")

    # 2. id 가 붙은 버튼은 눌렀을 때 할 일이 있어야 합니다
    for name in sorted(re.findall(r"<button[^>]*\bid=([A-Za-z][\w-]*)", body)):
        if name not in used:
            bad.append(f"버튼 '{name}' 에 하는 일이 없습니다 (아무도 안 씁니다)")

    # 3. 문자열 안에 진짜 줄바꿈이 들어가면 스크립트가 통째로 죽습니다
    for n, line in enumerate(script.splitlines(), 1):
        plain = re.sub(r"\\.", "", line)
        if plain.count("'") % 2 or plain.count('"') % 2:
            bad.append(f"스크립트 {n}번째 줄에서 따옴표가 안 닫혔습니다: {line.strip()[:50]}")

    # ★ 3-2. 자기가 자기를 덮어쓰는 CSS ★
    #
    #   `#burger{margin-left:auto; … ; margin:0}` 이 있었습니다.
    #   뒤쪽 margin:0 이 앞의 margin-left:auto 를 없앱니다 — 햄버거를
    #   오른쪽 끝으로 밀라는 규칙이 **쓰인 날부터 한 번도 안 들었습니다.**
    #
    #   이런 것은 브라우저가 안 알려줍니다. 화면이 멀쩡해 보이거든요.
    #   "만들었다" 와 "듣는다" 가 다른 또 하나의 예입니다.
    style = PAGE.split("<style>")[1].split("</style>")[0] if "<style>" in PAGE else ""
    SHORTHAND = {"margin": ("margin-left", "margin-right",
                            "margin-top", "margin-bottom"),
                 "padding": ("padding-left", "padding-right",
                             "padding-top", "padding-bottom")}
    for block in re.findall(r"\{([^{}]*)\}", style):
        decls = [d.strip() for d in block.split(";") if ":" in d]
        names = [d.split(":", 1)[0].strip() for d in decls]
        for short, longs in SHORTHAND.items():
            if short not in names:
                continue
            at = names.index(short)
            for long in longs:
                if long in names and names.index(long) < at:
                    bad.append(
                        f"CSS 에서 '{long}' 을 써놓고 뒤에서 '{short}' 로 "
                        f"덮어씁니다 — 앞의 것이 죽습니다: {block.strip()[:60]}")

    # 4. 메뉴 항목은 서버가 받는 이름이어야 합니다
    for job in sorted(set(re.findall(r"data-job=([\w-]+)", body))):
        if job not in JOBS:
            bad.append(f"메뉴의 '{job}' 를 서버가 안 받습니다 (JOBS 에 없음)")

    # 5. 바깥 이름을 함수 안에서 다시 선언하면 안 됩니다
    #
    #    ★ 이것 하나가 화면 갱신을 통째로 죽였습니다 ★
    #      조종판에 `let held = new Map()` 을 만들었는데, poll() 안쪽에
    #      이미 `const held = f.mic==='held'` 가 있었습니다. let/const 는
    #      함수 맨 위로 끌어올려져 선언 전까지 못 쓰는 상태가 되므로,
    #      **아래에 있는 그 한 줄 때문에 위쪽 held 가 전부** 죽었습니다.
    #      코스 목록도 음량도 안 그려졌는데 초록 점은 멀쩡했습니다.
    #
    #    자바스크립트에서 가리기(shadowing)는 문법상 맞습니다. 다만 이
    #    화면은 함수 몇 개가 바깥 이름을 같이 쓰는 구조라, 여기서는
    #    거의 언제나 실수입니다. 그리고 틀렸을 때 조용히 죽습니다.
    #
    #    ※ 바깥(들여쓰기 없는) 선언만 봅니다. 함수 안쪽끼리 b·p·tag 같은
    #      이름을 나눠 쓰는 것은 정상입니다.
    #    ※ 주석과 문자열은 먼저 지웁니다. 안 지웠더니 이 검사를 설명하는
    #      **주석 자체**를 잡았습니다 (거기 `const held` 라고 적혀 있어서).
    #      그리고 `const NAMES={w:'앞으로',s:'뒤로'}` 의 s 를 바깥 이름으로
    #      셌습니다 — 쉼표를 괄호 깊이 없이 잘랐던 탓입니다.
    clean = _js_bare(script)
    lines = clean.splitlines()
    outer = set()
    for line in lines:
        if line[:1] in (" ", "\t"):
            continue
        outer |= _js_declared(line)
    raw = script.splitlines()
    for n, line in enumerate(lines, 1):
        if line[:1] not in (" ", "\t"):
            continue
        for name in sorted(_js_declared(line.lstrip()) & outer):
            bad.append(
                f"스크립트 {n}번째 줄이 바깥 이름 '{name}' 를 함수 안에서 "
                f"다시 선언합니다 — 그 함수에서 바깥 '{name}' 가 통째로 "
                f"죽습니다: {raw[n - 1].strip()[:50]}")
    return bad


def _js_bare(script):
    """주석과 문자열 속을 공백으로 지웁니다. 줄 수는 그대로 둡니다."""
    out = []
    i, n = 0, len(script)
    while i < n:
        two = script[i:i + 2]
        if two == "//":
            while i < n and script[i] != "\n":
                out.append(" ")
                i += 1
        elif two == "/*":
            while i < n and script[i:i + 2] != "*/":
                out.append("\n" if script[i] == "\n" else " ")
                i += 1
            out.append("  ")
            i += 2
        elif script[i] in "'\"`":
            q = script[i]
            out.append(" ")
            i += 1
            while i < n and script[i] != q:
                if script[i] == "\\":
                    out.append(" ")
                    i += 1
                out.append("\n" if script[i:i + 1] == "\n" else " ")
                i += 1
            out.append(" ")
            i += 1
        else:
            out.append(script[i])
            i += 1
    return "".join(out)


def _js_declared(line):
    """이 줄이 let/const/var 로 만드는 이름들.

    `let a=1, b=2;` 는 둘 다. `const N={x:1,y:2}` 는 N 하나 —
    쉼표를 깊이 없이 자르면 x 와 y 까지 이름으로 셉니다.
    """
    import re
    m = re.match(r"\s*(?:let|const|var)\s+(.*)", line)
    if not m:
        return set()
    rest, depth, part, parts = m.group(1), 0, [], []
    for ch in rest:
        if ch in "{[(":
            depth += 1
        elif ch in "}])":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(part))
            part = []
        else:
            part.append(ch)
    parts.append("".join(part))
    out = set()
    for p in parts:
        got = re.match(r"\s*([A-Za-z_$][\w$]*)\s*(?:[=;]|$)", p)
        if got:
            out.add(got.group(1))
    return out


class Remote:
    """휴대폰에서 오는 신호를 받아둡니다.

    guide.py 가 `await remote.wait()` 로 기다리고, 사람이 휴대폰에서
    '다음' 을 누르면 풀립니다. 신호를 주는 길이 나중에 게임패드나
    로봇 마이크로 바뀌어도, 여기 모양만 맞추면 guide.py 는 그대로입니다.
    """

    def __init__(self, port=PORT, pin=None, ears=True):
        self.port = port
        self.pin = pin
        # ★ 음성 인식은 이제 열려 있습니다 ★
        #   한동안 잠가뒀습니다. 마이크가 PC 에 있어서 복도에서 누르면
        #   whisper 가 GPU 를 붙들고도 아무 일이 안 일어나니까요.
        #   그런데 **PC 옆에 사람이 있을 때는 쓸모가 있습니다.** 잠가두면
        #   그 경우까지 막습니다. 아예 못 켜게 하려면 guide.py --no-ears.
        #
        #   대신 켜고 끄는 것은 **기다리는 중에만** 됩니다 —
        #   로봇이 말하는 동안 켜면 자기 말을 듣습니다.
        self.ears = ears
        # ★ 귀가 폰으로 옮겨왔습니다 (29번) ★
        #   ear 는 "소리 덩어리 → (글자, 초)" 를 돌려주는 함수입니다.
        #   guide.py 의 toggle_ears 가 whisper 를 올린 뒤 여기에 꽂고,
        #   끄면 None 으로 되돌립니다. remote.py 는 whisper 를 모릅니다 —
        #   화면을 띄우는 쪽이 음성 인식기를 끌어안으면 무거워집니다.
        self.ear = None
        self.said = asyncio.Queue()   # 들은 글자. ear_loop 가 꺼냅니다
        self.heard_last = ""          # 화면에 되비쳐 보여줄 것
        self.server = None
        self.tls = None               # https 쪽 (없을 수도 있습니다)
        self.event = asyncio.Event()
        self.stop_event = asyncio.Event()   # '멈춤' 은 따로 — 대기 중이 아니어도
        # ★ '멈춤' 과 '종료' 는 다른 일입니다 ★
        #   stop : 지금 하는 설명만 끊고 그 자리에 섭니다 (되돌릴 수 있음)
        #   end  : 안내를 끝냅니다 (되돌릴 수 없음)
        #   하나로 묶여 있을 때는, 방문객이 말을 걸어서 잠깐 끊고 싶어도
        #   안내가 통째로 끝나버렸습니다.
        self.action = None            # go | again | restart | stop | end
        self.stopped = False
        self.hits = 0
        self.ignored = 0              # 기다리는 중에 누른 '멈춤' — 흘려보낸 수
        # 화면에 보여줄 것 — guide.py 가 갱신합니다
        # 고른 코스는 여기 적힙니다. guide.py 가 읽어서 처리합니다.
        self.course_want = None
        self.state = {"sid": "", "place": "준비 중", "detail": "", "button": "다음",
                      "waiting": False, "done": False, "index": 0, "total": 1,
                      # ★ 코스는 안내 중에 바꾸지 않습니다 ★
                      #   중간에 대본을 갈아 끼우면 로봇은 다른 안내의
                      #   3번 구간부터 시작합니다. 준비 화면과 끝 화면에서만
                      #   고를 수 있게 guide.py 가 이 값을 켜고 끕니다.
                      "can_pick": False,
                      "course": None, "courses": [],
                      "flags": {"mic": "off" if ears else "held",
                                "light": False, "posture": "?",
                                # 로봇에서 읽기 전까지는 None 입니다 —
                                # 짐작한 숫자를 화면에 띄우지 않습니다.
                                "volume": None,
                                # 로봇에게 듣기 전까지는 모릅니다.
                                # 0 으로 두면 화면에 "0%" 가 뜨고,
                                # 그건 배터리가 없다는 뜻이 됩니다.
                                "battery": None, "battery_stale": False,
                                "battery_note": ""}}
        # ★ 메뉴에서 누르는 것들은 '다음' 과 성격이 다릅니다 ★
        #   순서를 넘기는 것이 아니라, 지금 당장 하나 시키는 것입니다.
        #   기다리는 자리를 거치지 않고 따로 흘려보냅니다.
        self.jobs = asyncio.Queue()
        # 키 → 마지막으로 '누르고 있다' 를 들은 시각. guide.py 가 읽습니다.
        # ★ 여럿입니다 ★ 앞으로 가면서 도는 것이 되어야 하므로, 눌린
        #   키를 다 담습니다. 한 개만 담던 때는 두 번째 손가락이 첫
        #   번째를 밀어냈습니다.
        self.held = {}

    # ── guide.py 가 쓰는 부분 ───────────────────────────────
    def show(self, **kw):
        self.state.update(kw)

    def holding(self):
        """지금 눌려 있는 키들 (예: "aw"). 없으면 빈 문자열."""
        now = time.time()
        return "".join(sorted(k for k, t in self.held.items()
                              if now - t <= DEADMAN))

    def stick(self):
        """지금 눌려 있는 방향. 손을 뗐거나 소식이 끊기면 None.

        시간을 여기서 봅니다 — 부르는 쪽마다 따로 재면 언젠가 한 곳이
        빠집니다. **멈추는 판단은 한 군데에만 있어야 합니다.**

        ★ 여러 키를 더합니다 ★
          예전에는 키 하나만 담아서, 앞으로 가면서 도는 것이 안 됐습니다.
          축마다 +키와 −키가 하나씩이므로 더한 값은 언제나 -1·0·+1 이고,
          따로 자를 것이 없습니다. w 와 s 를 같이 누르면 0 — 서로
          상쇄되어 멈춥니다. 그것이 맞습니다.
        """
        fx = fy = fz = 0.0
        for k in self.holding():
            a, b, c = DRIVE[k]
            fx += a
            fy += b
            fz += c
        if fx == 0.0 and fy == 0.0 and fz == 0.0:
            return None
        return (fx, fy, fz)

    def flag(self, **kw):
        """메뉴에 보여줄 상태 (음성 인식 켜짐, 라이트, 자세)."""
        self.state["flags"].update(kw)

    async def wait_stop(self):
        """'멈춤' 만 기다립니다.

        ★ 왜 따로 두는가 ★
          wait() 는 '다음을 기다리는 자리' 에서만 돌아갑니다. 그런데
          멘트 하나가 30초입니다. 그동안 빨간 버튼을 눌러도 아무 일도
          일어나지 않았습니다 — **30초 뒤에나 듣는 정지 버튼**이었습니다.
          이제 수행 중에도 이 자리에서 받습니다.
        """
        await self.stop_event.wait()
        return "end" if self.action == "end" else "stop"

    def arm(self):
        """새 구간을 시작하기 전에 묵은 신호를 비웁니다.

        안 비우면, 대기 중에 눌린 '멈춤' 이 다음 구간을 시작하자마자
        터집니다. 누른 사람은 아무것도 안 했다고 생각하는데요.
        """
        self.event.clear()
        self.stop_event.clear()

    async def wait(self, allow=("go", "again", "restart", "end")):
        """신호가 올 때까지 기다립니다. 돌려주는 값: 눌린 것.

        ★ allow 를 좁게 잡아뒀다가 '다시' 를 죽였습니다 ★
          처음에 allow=("go",) 로 두고 어디서도 다른 값을 안 넘겼습니다.
          그래서 화면에는 '다시' 버튼이 있는데 누르면 아무 일도 일어나지
          않았습니다. 신호는 서버까지 잘 왔고, 여기서 조용히 버려졌습니다.
          **버튼을 만들어놓고 뜻을 안 붙인 것입니다.**
          이제 기본으로 받습니다. 부르는 쪽이 좁히고 싶을 때만 좁힙니다.

        ★ '멈춤' 을 여기서 돌려주지 않습니다 ★
          예전에는 `or self.action == "stop"` 이 붙어 있어서, allow 에
          없는데도 '멈춤' 만 빠져나갔습니다. 받은 쪽(guide.py)은 그것을
          '이 구간을 다시' 로 읽고 같은 구간을 처음부터 돌렸습니다 —
          **멈추라고 눌렀는데 되레 다시 시작한 것입니다.**
          이제 _fire 가 아예 받지 않습니다. 여기는 그 결과로 조용합니다.
        """
        self.state["waiting"] = True
        self.stop_event.clear()      # 기다리는 중에는 끊을 것이 없습니다
        try:
            while True:
                self.event.clear()
                await self.event.wait()
                if self.action in allow:
                    return self.action
        finally:
            self.state["waiting"] = False

    # ── HTTP ────────────────────────────────────────────────
    def _fire(self, action):
        """버튼 하나를 받습니다. 받았으면 True, 흘려보냈으면 False.

        ★ '멈춤' 은 지금 하는 것이 있을 때만 뜻이 있습니다 ★
          기다리는 자리에서는 끊을 것이 없습니다. 그런데도 받아서
          넘겼더니, 받은 쪽이 그것을 '이 구간을 다시' 로 읽고
          M1 을 네 번 돌렸습니다 — 180도 회전까지 매번 다시.

          거르는 자리를 부르는 쪽마다 두면 언젠가 한 곳이 빠집니다.
          stick() 에서 배운 것과 같습니다: **거르는 판단은 한 군데에만.**
          여기가 그 한 군데입니다.
        """
        if action == "stop" and self.state["waiting"]:
            self.ignored += 1
            return False
        self.action = action
        self.hits += 1
        if action in ("stop", "end"):
            self.stopped = (action == "end")
            self.stop_event.set()
        self.event.set()
        return True

    async def _client(self, reader, writer):
        """한 연결에서 **여러 요청**을 받습니다 (keep-alive).

        ★ 왜 이게 필요한가 ★
          조종판은 120ms 마다 "아직 누르고 있다" 를 보냅니다. 그런데
          매번 Connection: close 로 끊고 있었습니다 — 초당 여덟 번씩
          TCP 를 새로 맺고 끊은 것입니다. 무선에서 그 값이 흔들리면
          한 번이 0.45초를 넘고, 그러면 DEADMAN 이 정직하게 멈춥니다.

          실제 로그에 ⟨조종⟩ 이 42번 찍혔습니다. 한 번 누른 것을
          42번 시작한 것입니다. 그게 '삐걱' 의 정체입니다.

          연결을 열어두면 그 왕복이 통째로 사라집니다.
        """
        keep = 30
        try:
            while keep > 0:
                keep -= 1
                try:
                    line = await asyncio.wait_for(reader.readline(), 20.0)
                except Exception:
                    break
                if not line:
                    break

                # ★ https 를 http 포트에 대면 이런 꼴이 됩니다 ★
                #   TLS 는 맨 앞에 0x16 을 보냅니다. 그건 요청 줄이
                #   아니니 아래 split 이 실패하고, 우리는 연결을 그냥
                #   끊습니다 — 폰에는 **"연결이 예기치 않게 종료되었
                #   습니다"** 로 뜹니다. 포트를 잘못 쓴 것인데 화면에는
                #   서버가 고장난 것처럼 보입니다.
                #
                #   TLS 로는 되돌려줄 말이 없습니다 (평문을 보내면
                #   브라우저가 또 다른 오류로 읽습니다). 그래서 **PC
                #   화면에 적습니다.** 거기 사람이 있으니까요.
                if line[:1] == b"\x16":
                    print(f"[리모컨] ★ {self.address_of(writer)} 가 "
                          f"**http 포트({self.port})에 https 로** 붙었습니다.")
                    print(f"         https 는 {self.port + 1}번입니다 — "
                          f"주소의 포트를 보세요.")
                    break

                try:
                    method, path, _ = line.decode("latin-1").split(" ", 2)
                except ValueError:
                    break
                # ★ 본문을 반드시 다 읽어야 합니다 ★
                #   여태 헤더를 버리고 본문 없는 요청만 받았습니다.
                #   폰이 녹음을 보내기 시작하면 그러면 안 됩니다 —
                #   본문을 안 읽으면 그 20 KB 가 소켓에 남고, 다음
                #   readline 이 **소리 조각을 요청 줄로 읽습니다.**
                #   그러면 연결이 어긋나고, 조종판이 같은 연결을
                #   쓰고 있으므로 **조종이 통째로 먹통이 됩니다.**
                #   길이를 못 읽으면 그 연결은 버립니다 (아래 break).
                length = 0
                try:
                    while True:
                        h = await asyncio.wait_for(reader.readline(), 5.0)
                        if h in (b"\r\n", b"\n", b""):
                            break
                        name, _, value = h.decode("latin-1").partition(":")
                        if name.strip().lower() == "content-length":
                            length = int(value.strip() or 0)
                except Exception:
                    break

                payload = b""
                if length:
                    if length > MAX_BODY:
                        break                    # 이상한 것은 안 받습니다
                    try:
                        payload = await asyncio.wait_for(
                            reader.readexactly(length), 20.0)
                    except Exception:
                        break                    # 반쯤 읽었으면 연결을 버립니다

                if path.split("?")[0] == "/heard":
                    body, ctype, code = await self._hear(payload)
                else:
                    body, ctype, code = self._answer(path)
                writer.write(
                    f"HTTP/1.1 {code}\r\nContent-Type: {ctype}\r\n"
                    f"Content-Length: {len(body)}\r\nCache-Control: no-store\r\n"
                    f"Connection: keep-alive\r\n"
                    f"Keep-Alive: timeout=20\r\n\r\n".encode("latin-1") + body)
                await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

    @staticmethod
    def address_of(writer):
        try:
            return writer.get_extra_info("peername")[0]
        except Exception:
            return "누군가"

    async def _hear(self, raw):
        """폰이 보낸 녹음 한 덩어리를 글자로 옮깁니다.

        ★ 여기서 움직이지 않습니다 ★
          들은 글자는 `said` 큐에 넣기만 합니다. guide.py 의 ear_loop 가
          꺼내서 **버튼과 똑같은 길**로 흘려보냅니다. 말로 하든 손으로
          하든 한 길을 지나야, 한쪽만 고쳐지는 일이 안 생깁니다.

        ★ 넘어져도 화면에는 답을 줍니다 ★
          여기서 예외가 나가면 위의 _client 가 연결을 끊습니다. 그러면
          폰은 "못 보냈습니다" 로 뜨고, 그건 **소리가 안 닿은 것과
          구별이 안 됩니다.** 닿은 것은 닿았다고 말합니다.
        """
        out = {"bytes": len(raw)}
        try:
            if self.ear is None:
                out["error"] = "마이크가 꺼져 있습니다 — 화면에서 켜세요"
            elif not raw:
                out["error"] = "빈 녹음입니다 — 단추를 좀 더 오래 누르세요"
            else:
                text, secs = await self.ear(raw)
                out["secs"] = round(secs, 1)
                out["text"] = text
                if text:
                    print(f"   ⟨폰⟩ {text}")
                    self.said.put_nowait(text)
                    self.heard_last = text
                else:
                    print(f"   ⟨폰⟩ {secs:.1f}초 — 아무 말도 안 들렸습니다")
        except Exception as e:
            out["error"] = f"{type(e).__name__}: {e}"
            print(f"   ★ 못 알아들었습니다 — {out['error']}")
        return (json.dumps(out, ensure_ascii=False).encode("utf-8"),
                "application/json; charset=utf-8", "200 OK")

    def _answer(self, path):
        """요청 하나에 대한 답. (본문, 형식, 코드)"""
        path, _, query = path.partition("?")
        if self.pin and path not in ("/", "/state") \
                and f"pin={self.pin}" not in query:
            return b"pin", "text/plain; charset=utf-8", "403 Forbidden"

        if path == "/":
            page = PAGE
            if self.pin:
                page = page.replace("fetch('/", f"fetch('?pin={self.pin}&x=/")
            return page.encode("utf-8"), "text/html; charset=utf-8", "200 OK"

        if path == "/state":
            return (json.dumps(self.state, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8", "200 OK")

        if path.startswith("/drive/"):
            # 눌린 키가 다 붙어서 옵니다 ("wa" = 앞으로 + 좌회전).
            # 안 온 키는 뗀 것입니다 — 통째로 갈아치웁니다. 하나씩
            # 지우려 들면 지우는 신호를 놓쳤을 때 눌린 채로 남습니다.
            now = time.time()
            self.held = {c: now for c in path[7:] if c in DRIVE}
            return b"ok", "text/plain", "200 OK"

        if path in ("/go", "/again", "/restart", "/stop", "/end"):
            took = self._fire(path[1:])
            # 흘려보냈으면 그렇다고 말해줍니다. 화면은 이미 '멈춤' 을
            # 잠가두지만, 잠그기 전에 눌린 것이 있을 수 있습니다.
            return ((b"ok", "text/plain", "200 OK") if took else
                    (b"idle", "text/plain", "200 OK"))

        if path.startswith("/course/"):
            cid = path[8:]
            if not self.state.get("can_pick"):
                self.ignored += 1
                return b"idle", "text/plain", "200 OK"
            known = {c.get("id") for c in self.state.get("courses") or []}
            if cid not in known:
                # 주소창에 아무 이름이나 쳐서 고르게 두지 않습니다
                return b"?", "text/plain", "404 Not Found"
            if cid == (self.state.get("course") or {}).get("id"):
                return b"same", "text/plain", "200 OK"
            self.course_want = cid
            self._fire("course")
            return b"ok", "text/plain", "200 OK"

        if path.startswith("/job/"):
            job = path[5:]
            if job == "mic" and not self.ears:
                return b"held", "text/plain", "409 Conflict"
            # 화면이 잠그기 전에 눌린 것이 있을 수 있습니다 (화면은
            # 0.6초마다 갱신됩니다). 거르는 자리는 여기 한 곳입니다.
            if job in WAIT_ONLY_JOBS and self.state["waiting"] is False:
                self.ignored += 1
                return b"idle", "text/plain", "200 OK"
            if job in JOBS:
                self.jobs.put_nowait(job)
                self.hits += 1
                self.action = job
                return b"ok", "text/plain", "200 OK"
            return b"?", "text/plain", "404 Not Found"

        return b"?", "text/plain", "404 Not Found"

    async def start(self, verbose=True):
        for problem in check_page():
            print(f"[리모컨] ★ {problem}")
        try:
            self.server = await asyncio.start_server(self._client, "0.0.0.0", self.port)
        except OSError as e:
            print(f"[리모컨] ★ {self.port}번 포트를 열지 못했습니다: {e}")
            print("         다른 프로그램이 쓰고 있거나 방화벽이 막았습니다.")
            return None
        # ★ https 는 **더하는 것**이지 바꾸는 것이 아닙니다 ★
        #
        #   폰은 안전한 자리(https)가 아니면 마이크를 안 줍니다. 함수를
        #   아예 안 만들어 둡니다 — 그래서 권한 문제처럼 보입니다 (29번).
        #
        #   그렇다고 http 를 걷어내면, 인증서 쪽이 조금이라도 어긋났을 때
        #   **여태 되던 조종 화면까지 같이 죽습니다.** 시연 아침에 그건
        #   안 됩니다. 그래서 둘 다 엽니다. 마이크가 필요하면 https,
        #   아니면 여태 쓰던 http 그대로.
        tls_url = None
        try:
            tls_url = await self._start_tls()
        except Exception as e:
            print(f"[리모컨] ※ https 를 못 열었습니다: {type(e).__name__}: {e}")
            print("         http 는 그대로 됩니다 — 다만 폰 마이크는 못 씁니다.")
        if not tls_url:
            print("[리모컨] ※ https 가 안 열렸습니다 — 폰이 마이크를 안 내줍니다.")
            print("         까닭은 바로 위에 적혀 있습니다.")

        url = f"http://{lan_ip()}:{self.port}/"
        if self.pin:
            url += f"?pin={self.pin}"
        if verbose:
            print()
            print("┌" + "─" * 52 + "┐")
            print("│  휴대폰 브라우저에 이 주소를 치세요" + " " * 15 + "│")
            print("│" + " " * 52 + "│")
            print("│    " + url.ljust(48) + "│")
            print("│" + " " * 52 + "│")
            print("│  ※ 휴대폰이 PC 와 같은 공유기에 있어야 합니다" + " " * 4 + "│")
            print("└" + "─" * 52 + "┘")
            print()
            print("     처음에 윈도우가 방화벽을 물어보면 '허용' 하세요.")
            print("     (사설망 쪽만 허용하면 됩니다)")
            if tls_url:
                print()
                print("  ── 음성으로 시키려면 이쪽입니다 ──────────────")
                print(f"    {tls_url}")
                print("    ※ '안전하지 않습니다' 경고가 뜹니다. 스스로 만든")
                print("      인증서라 그렇습니다. 고급 → 계속 을 누르세요.")
                print("      http 로는 폰이 마이크를 아예 안 내줍니다.")
                print()
        return url

    async def _start_tls(self):
        """같은 화면을 https 로도 엽니다. 안 되면 None 을 돌려줍니다.

        인증서 만드는 부분은 web_mic.py 에 있습니다 — 거기서 폰으로
        확인한 그대로입니다 (IP 를 subjectAltName 에 넣어야 크롬이
        받아줍니다). 두 벌로 갈라두면 한쪽만 고쳐집니다.
        """
        import ssl
        # ★ 여기서 조용히 돌아가면 안 됩니다 ★
        #   처음에 `except Exception: return None` 이라고 썼습니다.
        #   그래서 https 가 안 열렸는데 **화면에 아무 말도 안 나왔고**,
        #   사이안 님은 주소가 왜 하나뿐인지 알 길이 없었습니다.
        #   안 되는 것은 안 된다고 말해야 합니다. 27번·29번과 같은
        #   실수를 제가 제 코드 안에서 또 했습니다.
        try:
            import web_mic
        except Exception as e:
            print(f"[리모컨] ※ web_mic.py 를 못 읽었습니다: "
                  f"{type(e).__name__}: {e}")
            print("         그 파일이 remote.py 옆에 있어야 https 가 열립니다.")
            return None
        ip = lan_ip()
        if not web_mic.cert_ok_for(ip):
            print(f"[리모컨] 인증서를 만듭니다 ({ip} 앞으로, 30일)…")
            web_mic.make_cert(ip)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(web_mic.CERT, web_mic.KEY)
        self.tls = await asyncio.start_server(
            self._client, "0.0.0.0", self.port + 1, ssl=ctx)
        # ★ 지문을 찍어둡니다 ★
        #   앱이 처음 붙을 때 "이 지문이 맞습니까" 를 묻습니다. 사람이
        #   그것을 **무언가와** 견줄 수 있어야 물음에 뜻이 생깁니다.
        #   견줄 것이 없으면 사람은 그냥 '같습니다' 를 누르고, 그러면
        #   묻는 절차가 장식이 됩니다.
        self.finger = cert_finger(web_mic.CERT)
        if self.finger:
            print(f"[리모컨] 인증서 지문 (SHA-256)")
            print(f"         {self.finger}")
            print("         앱이 처음 붙을 때 이 값을 보여줍니다. 같으면 맞습니다.")

        url = f"https://{ip}:{self.port + 1}/"
        if self.pin:
            url += f"?pin={self.pin}"
        return url

    async def close(self):
        for srv in (self.server, self.tls):
            if not srv:
                continue
            srv.close()
            try:
                await srv.wait_closed()
            except Exception:
                pass


async def main():
    pin = None
    args = sys.argv[1:]
    if "--pin" in args:
        try:
            pin = args[args.index("--pin") + 1]
        except IndexError:
            print("--pin 뒤에 숫자를 적어주세요.  예: --pin 1234")
            return

    print("=" * 62)
    print(" 휴대폰 리모컨 — 연결 확인")
    print("=" * 62)
    problems = check_page()
    if problems:
        for x in problems:
            print(f" ★ {x}")
        print()
    else:
        print(" 화면 점검: 이상 없음 (버튼과 하는 일이 다 이어져 있습니다)")
    print(" 로봇에 연결하지 않습니다. 버튼이 여기까지 오는지만 봅니다.")

    r = Remote(pin=pin)
    if not await r.start():
        return
    r.show(sid="시험", place="버튼을 눌러보세요",
           detail="여기 눌린 것이 PC 콘솔에 찍히면 연결된 것입니다. "
                  "버튼 넷을 다 눌러보세요.",
           waiting=True, index=0, total=3)

    # ★ 코스 목록도 진짜를 채웁니다 ★
    #   여기서 안 채웠더니 메뉴의 코스 칸이 비어 있었습니다. 화면을
    #   확인하려고 이걸 띄우는 건데, 정작 확인하려던 자리가 빈 채로
    #   나왔습니다. 로봇 없이 볼 수 있는 것은 로봇 없이 다 보여야
    #   합니다 — 그게 이 파일이 혼자 돌아가는 이유입니다.
    picker = None
    try:
        import courses as picker
        for note in picker.report():
            print(f" ※ {note}")
        now = picker.default()
        r.show(courses=[c.brief() for c in picker.all_courses()],
               course={"id": now.id, "name": now.name},
               can_pick=True)
        print(f" 코스 {len(picker.all_courses())}개를 메뉴에 올렸습니다"
              f" — 눌러서 골라볼 수 있습니다.")
        print(" ※ 여기서 고르는 것은 화면 동작만 봅니다."
              " 로봇에 멘트를 올리지는 않습니다.")
    except Exception as e:
        print(f" ※ 코스를 못 읽었습니다: {type(e).__name__}: {e}")

    print(" Ctrl+C 로 끝냅니다.")
    print(" (음성 인식은 guide.py 에서만 실제로 돕니다 — 여기서는 화면만)\n")
    seen = 0
    try:
        while True:
            await asyncio.sleep(0.2)
            if r.hits > seen:
                seen = r.hits
                stamp = time.strftime("%H:%M:%S")
                print(f" [{stamp}] '{r.action}' 눌림   (모두 {seen}번)")
                # 코스를 골랐으면 화면의 '지금 이것' 도 옮겨줍니다.
                # 안 옮기면 눌러도 아무 일 없는 것처럼 보입니다.
                if r.action == "course" and picker is not None:
                    got = picker.get(r.course_want)
                    if got:
                        print(f"          → 코스를 '{got.name}' 로 바꿨습니다"
                              f" (화면만)")
                        r.show(course={"id": got.id, "name": got.name})
                    continue
                r.show(detail=f"{seen}번 눌렸습니다. 잘 오고 있습니다.")
    except KeyboardInterrupt:
        pass
    finally:
        await r.close()
        print()
        if seen:
            print(f" 버튼 {seen}번을 받았습니다. 이 길은 됩니다.")
            print(" 다음:  .\\run guide.py --manual")
        else:
            print(" 한 번도 안 눌렸습니다.")
            print(" · 휴대폰이 같은 공유기에 붙어 있는지")
            print(" · 윈도우 방화벽에서 python 을 허용했는지")
            print(" 두 가지를 확인해 보세요.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
