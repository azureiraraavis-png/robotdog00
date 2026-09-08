# -*- coding: utf-8 -*-
"""
시그널링 다리가 맞는가 — **가짜 로봇과 실제로 악수해 봅니다.**

  ★ 왜 '베꼈다' 로는 모자란가 ★

    sig.py 는 라이브러리를 보고 다시 쓴 것입니다. 그러면 "잘 베꼈나"
    가 문제가 되는데, 그건 눈으로 봐서는 알 수 없습니다. 이 프로젝트에서
    눈으로 봐서 넘어갔다가 틀린 것이 여러 번입니다.

    그래서 **로봇 쪽 절반을 명세대로 만들어놓고** 우리 다리가 통과하는지
    봅니다. 로봇 역을 맡은 쪽은 자기가 받은 것을 실제로 풀어보고,
    안 풀리면 거절합니다. 통과하면 '베낀 것' 이 아니라 '맞는 것' 입니다.

    ★ 이 시험이 곧 Kotlin 의 채점표입니다 ★
      나중에 안드로이드로 옮기고 나면, 같은 가짜 로봇에 붙여보면 됩니다.
      로봇 앞에 갈 필요가 없습니다.

  ★ 무엇을 보는가 ★

      1. data2=1 (평문)      악수가 끝까지 갑니다
      2. data2=2 (고정 키)   〃
      3. data2=3 (전용 키)   〃
      4. 키가 틀리면         거절당하고, 왜인지 말해줍니다
      5. 토큰 계산           앱이 하는 것과 같은 값
      6. 라이브러리 대조     있으면 같은 답을 내는지 (없으면 건너뜁니다)

  ※ 로봇에 연결하지 않습니다. 켜져 있지 않아도 됩니다.

  쓰는 법

      .\\run sig_test.py                    파이썬 다리를 채점합니다
      .\\run sig_test.py --serve            ★ 폰이 붙을 수 있게 랜에 세웁니다 ★
      .\\run sig_test.py --serve --data2 1  평문 로봇으로 (제일 단순한 길)
      .\\run sig_test.py --serve --data2 3 --key <hex32>

  ★ --serve 가 Kotlin 의 채점표입니다 ★
    폰 앱의 Sig.kt 는 빌드해 볼 수 없는 코드라, 진짜 로봇 앞에서 처음
    재면 "안 됩니다" 만 알고 돌아오게 됩니다. 여기 선 상대는 **왜**
    안 되는지 말해줍니다. 그게 폰 화면에 그대로 뜹니다.
"""

import asyncio
import base64
import json
import os
import sys

import sig

PORT = 8772


# ── 로봇 역 ──────────────────────────────────────────────────

class FakeRobot:
    """con_notify 와 con_ing 을 **명세대로** 흉내 냅니다.

    받은 것을 진짜로 풀어봅니다. 우리 다리가 조금이라도 어긋나면
    여기서 떨어집니다 — 그게 이 시험의 값어치입니다.
    """

    def __init__(self, data2=1, aes_128_key=None):
        from Crypto.PublicKey import RSA
        self.data2 = data2
        self.aes_128_key = aes_128_key
        self.rsa = RSA.generate(2048)
        # 앞뒤 10글자는 껍데기, 가운데가 공개키, 마지막 10글자가 토큰 재료
        pub = base64.b64encode(
            self.rsa.publickey().export_key("DER")).decode()
        self.tail = "1A2C3E4G5I"          # → 토큰 "02468"
        self.data1 = "0123456789" + pub + self.tail
        self.answer_sdp = "v=0\r\no=- 1 1 IN IP4 0.0.0.0\r\ns=fake answer\r\n"
        self.busy = False        # True 면 "reject" 를 돌려줍니다
        self.seen = {}

    def con_notify(self):
        if self.data2 == 1:
            payload = self.data1
        else:
            key = (sig.LEGACY_GCM_KEY if self.data2 == 2
                   else bytes.fromhex(self.aes_128_key))
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = os.urandom(12)
            sealed = AESGCM(key).encrypt(nonce, self.data1.encode(), None)
            body, tag = sealed[:-16], sealed[-16:]
            # ★ 조각 배치 — nonce 가 뒤입니다 ★
            payload = base64.b64encode(body + nonce + tag).decode()
        return base64.b64encode(json.dumps(
            {"data1": payload, "data2": self.data2}).encode()).decode()

    def con_ing(self, token, body_text):
        """받은 것을 실제로 풀어봅니다. 못 풀면 거절합니다."""
        from Crypto.Cipher import PKCS1_v1_5
        want = sig.path_ending(self.data1)
        if token != want:
            raise ValueError(f"토큰이 다릅니다: 받은 {token!r}, 기대 {want!r}")
        got = json.loads(body_text)
        # RSA 로 감싼 AES 키를 풉니다
        cipher = PKCS1_v1_5.new(self.rsa)
        blob = base64.b64decode(got["data2"])
        size = self.rsa.size_in_bytes()
        key = b""
        for i in range(0, len(blob), size):
            piece = cipher.decrypt(blob[i:i + size], None)
            if piece is None:
                raise ValueError("RSA 를 못 풀었습니다 (패딩이 다릅니다)")
            key += piece
        key = key.decode()
        if len(key) != 32:
            raise ValueError(f"AES 키가 32글자가 아닙니다: {len(key)}")
        # 그 키로 봉투를 풉니다
        inner = sig.aes_ecb_decrypt(got["data1"], key)

        # ★ 봉투를 요구합니다 — 진짜 로봇이 그러니까요 ★
        #   전에는 여기서 맨 SDP 를 그냥 받아줬습니다. 그래서 우리 다리가
        #   맨 SDP 를 보내도 통과했고, **진짜 로봇 앞에서만 막혔습니다.**
        #   진짜는 파싱에 실패하면 말없이 연결을 끊습니다 — 아무 단서도
        #   안 주고요. 시험하는 상대가 목표한 상대보다 관대하면 시험이
        #   거짓말을 합니다. 이 저장소에서 세 번째로 적는 문장입니다.
        try:
            envelope = json.loads(inner)
        except Exception:
            raise ValueError("봉투가 JSON 이 아닙니다 (맨 SDP 를 보냈나요?)")
        for need in ("id", "sdp", "type", "token"):
            if need not in envelope:
                raise ValueError(f"봉투에 {need!r} 가 없습니다")
        if envelope["type"] != "offer":
            raise ValueError(f"type 이 offer 가 아닙니다: {envelope['type']!r}")

        offer = envelope["sdp"]
        self.seen = {"key": key, "offer": offer, "envelope": envelope}
        answer = json.dumps({"sdp": "reject" if self.busy else self.answer_sdp,
                             "type": "answer"})
        return sig.aes_ecb_encrypt(answer, key)


async def serve(robot, port, host="127.0.0.1", log=None, polite=False):
    """가짜 로봇 서버.

    ★ polite 를 왜 껐는가 ★

      처음에는 응답마다 'Connection: close' 를 붙였습니다. 그러면
      클라이언트가 그 소켓을 재사용하지 않습니다. 그런데 **진짜 로봇은
      그 말을 안 해줍니다.** 답을 주고 그냥 닫습니다.

      그 차이 때문에 폰이 진짜 로봇 앞에서 처음 막혔습니다.

          con_ing_70219 에 닿지 못했습니다:
          IOException: unexpected end of stream

      안드로이드의 HTTP 가 con_notify 에 썼던 연결을 아껴뒀다가
      con_ing 에 다시 썼는데, 로봇은 이미 닫아둔 뒤였습니다.

      **시험하는 상대가 목표한 상대보다 예의바르면 시험이 거짓말을
      합니다.** 그래서 이제 기본값은 무례한 쪽입니다 — 말없이 닫습니다.
      polite=True 로 하면 옛날처럼 붙여줍니다 (견줘볼 때 씁니다).
    """
    async def handle(reader, writer):
        try:
            first = await reader.readline()
            if not first:
                return
            method, path = first.decode("latin-1").split()[:2]
            length = 0
            while True:
                h = await reader.readline()
                if h in (b"\r\n", b"\n", b""):
                    break
                if h.lower().startswith(b"content-length:"):
                    length = int(h.split(b":")[1].strip())
            body = (await reader.readexactly(length)) if length else b""
            try:
                if path == "/con_notify":
                    out, code = robot.con_notify(), "200 OK"
                elif path.startswith("/con_ing_"):
                    out = robot.con_ing(path[len("/con_ing_"):],
                                        body.decode("utf-8"))
                    code = "200 OK"
                else:
                    out, code = "?", "404 Not Found"
            except Exception as e:
                out, code = f"{type(e).__name__}: {e}", "400 Bad Request"
            if log:
                who = writer.get_extra_info("peername")
                log(who[0] if who else "?", method, path, code, out)
            data = out.encode("utf-8")
            head = (f"HTTP/1.1 {code}\r\nContent-Type: text/plain\r\n"
                    f"Content-Length: {len(data)}\r\n")
            if polite:
                head += "Connection: close\r\n"    # 진짜 로봇은 이 말을 안 합니다
            writer.write((head + "\r\n").encode() + data)
            await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass
    return await asyncio.start_server(handle, host, port)


# ── 폰이 붙을 수 있게 랜에 내놓기 ────────────────────────────

def lan_ip():
    """이 PC 가 랜에서 갖는 주소. 폰에 입력할 값입니다.

    ※ 소켓을 열어보되 보내지는 않습니다. hostname 으로 찾으면 가상
      어댑터 주소가 나오는 일이 잦아서, 실제로 랜을 향하는 것을
      물어봅니다.
    """
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))       # 실제로 보내지 않습니다
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


async def serve_forever(data2, key, port):
    """가짜 로봇을 랜에 세워둡니다 — **폰의 다리를 여기다 대고 잽니다.**

    ★ 왜 진짜 로봇 앞에서 처음 재지 않는가 ★

      Kotlin 쪽 Sig.kt 는 제가(작성한 AI가) 빌드해 볼 수 없는 코드입니다.
      틀렸다면 진짜 로봇은 그냥 거절할 뿐, 어디가 틀렸는지 안 알려줍니다.
      복도까지 걸어가서 "안 됩니다" 만 확인하고 오게 됩니다.

      여기 선 상대는 명세대로 만들어져 있고, **받은 것을 실제로
      풀어보고 못 풀면 이유를 말해줍니다.** 토큰이 다르면 다르다고,
      RSA 패딩이 다르면 다르다고 합니다. 그게 폰 화면에 그대로 뜹니다.
    """
    robot = FakeRobot(data2=data2, aes_128_key=key)
    ip = lan_ip()

    def log(who, method, path, code, out):
        mark = "○" if code.startswith("2") else "★"
        short = path if len(path) < 40 else path[:37] + "…"
        print(f" {mark} {who}  {method} {short}  → {code}")
        if not code.startswith("2"):
            print(f"     {out}")

    srv = await serve(robot, port, host="0.0.0.0", log=log)
    print("=" * 70)
    print(" 가짜 로봇이 서 있습니다 — 폰을 여기에 대보세요")
    print("=" * 70)
    print(f"   주소   {ip}")
    print(f"   포트   {port}")
    print(f"   data2  {data2}" + (f"  ·  키 {key}" if key else ""))
    print()
    print(" 폰 앱의 '시그널링 다리' 칸에 위 주소와 포트를 넣고")
    print(" '악수해 보기' 를 누르세요. 오가는 것이 여기 찍힙니다.")
    print()
    print(" ※ 폰과 PC 가 **같은 와이파이**에 있어야 합니다.")
    print("   윈도 방화벽이 물어보면 '허용' 하세요. 물어보지도 않고")
    print("   막는 일이 있는데, 그러면 폰에는 '닿지 못했습니다' 로 뜹니다.")
    print()
    print(" 멈추려면 Ctrl+C")
    print("─" * 70)
    try:
        async with srv:
            await srv.serve_forever()
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass


# ── 채점 ─────────────────────────────────────────────────────

class Score:
    def __init__(self):
        self.rows = []

    def check(self, name, got, want=True):
        ok = (got == want)
        self.rows.append((ok, name, got, want))
        print(f" {'○' if ok else '★'} {name}")
        if not ok:
            print(f"     받은 것: {got!r}   바라던 것: {want!r}")
        return ok

    def report(self):
        bad = [r for r in self.rows if not r[0]]
        print()
        print("=" * 70)
        if not bad:
            print(f" 모두 통과했습니다 ({len(self.rows)}가지)")
            print(" 다리가 맞습니다. 이제 Kotlin 은 이것과 같은 답만 내면 됩니다.")
            return True
        print(f" ★ {len(bad)}가지가 어긋납니다 ★")
        for _o, name, got, want in bad:
            print(f"   · {name}: {got!r} (바라던 것 {want!r})")
        return False


# ★ 진짜 제안 모양이어야 합니다 ★
#   전에는 "v=0 … a=filler:x" 만 늘어놓은 토막이었습니다. 가짜 로봇은
#   그걸 받아줬고, **진짜 로봇은 말없이 연결을 끊었습니다.** 로봇이
#   받는 제안은 데이터채널·비디오·오디오 줄을 갖춘 3천 글자짜리입니다.
#   그래서 여기도 m= 줄을 갖춘 모양으로 두고, sig.check_offer 가
#   지키게 합니다.
STUB = "v=0\r\no=- 1 2 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0\r\n"   # 로봇이 안 받는 것

OFFER = (
    "v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\n"
    "s=-\r\nt=0 0\r\na=group:BUNDLE 0 1 2\r\n"
    "m=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n"
    "c=IN IP4 0.0.0.0\r\na=mid:0\r\na=sctp-port:5000\r\n"
    + "a=candidate:filler 1 udp 100 10.0.0.1 5000 typ host\r\n" * 12 +
    "m=video 9 UDP/TLS/RTP/SAVPF 96\r\nc=IN IP4 0.0.0.0\r\n"
    "a=mid:1\r\na=recvonly\r\na=rtpmap:96 VP8/90000\r\n"
    + "a=candidate:filler 1 udp 100 10.0.0.1 5001 typ host\r\n" * 12 +
    "m=audio 9 UDP/TLS/RTP/SAVPF 111\r\nc=IN IP4 0.0.0.0\r\n"
    "a=mid:2\r\na=sendrecv\r\na=rtpmap:111 opus/48000/2\r\n"
    + "a=candidate:filler 1 udp 100 10.0.0.1 5002 typ host\r\n" * 12
)


async def one(s, label, data2, key=None, give=None, port=PORT):
    robot = FakeRobot(data2=data2, aes_128_key=key)
    srv = await serve(robot, port)
    try:
        steps = []
        answer = await asyncio.to_thread(
            sig.handshake, "127.0.0.1", OFFER,
            give if give is not None else key, port, 5.0,
            lambda n, d: steps.append(n))
        s.check(f"{label} — 악수가 끝까지 갑니다", answer, robot.answer_sdp)
        s.check(f"{label} — 로봇이 받은 SDP 가 우리가 보낸 것", robot.seen.get("offer"), OFFER)
        s.check(f"{label} — 단계 다섯을 다 지납니다", len(steps), 5)
        env = robot.seen.get("envelope", {})
        s.check(f"{label} — 봉투에 담아 보냅니다", env.get("id"), sig.ENVELOPE_ID)
        s.check(f"{label} — 봉투의 type 은 offer", env.get("type"), "offer")
    finally:
        srv.close()
        await srv.wait_closed()


async def main():
    print("=" * 70)
    print(" 시그널링 다리가 맞는가 — 가짜 로봇과 악수")
    print("=" * 70)
    print(" 로봇에 연결하지 않습니다. 명세대로 만든 상대와 맞춰봅니다.")
    print()
    s = Score()

    print("─" * 70)
    print(" 세 가지 로봇 (data2 = 1 · 2 · 3)")
    print("─" * 70)
    await one(s, "평문(1)", 1, port=8781)
    await one(s, "고정 키(2)", 2, port=8782)
    await one(s, "전용 키(3)", 3, key="0f1e2d3c4b5a69788796a5b4c3d2e1f0", port=8783)

    print()
    print("─" * 70)
    print(" 키가 틀렸을 때 — 조용히 실패하면 안 됩니다")
    print("─" * 70)
    robot = FakeRobot(data2=3, aes_128_key="0f1e2d3c4b5a69788796a5b4c3d2e1f0")
    srv = await serve(robot, 8784)
    try:
        for label, give, want in (
                ("키를 안 주면", None, "자기만의 AES-128 키를 요구"),
                ("키가 hex 가 아니면", "이건hex가아닙니다", "hex 가 아닙니다"),
                ("길이가 모자라면", "0f1e2d", "16바이트"),
                ("다른 키를 주면", "ffffffffffffffffffffffffffffffff", "거부했습니다")):
            try:
                await asyncio.to_thread(sig.handshake, "127.0.0.1", OFFER,
                                        give, 8784, 5.0, None)
                s.check(f"{label} → 막습니다", "통과해버림", "막힘")
            except sig.SignalError as e:
                s.check(f"{label} → 이유를 말해줍니다", want in str(e))
    finally:
        srv.close()
        await srv.wait_closed()

    print()
    print("─" * 70)
    print(" 봉투 — 여기서 진짜 로봇 앞에서만 막혔습니다")
    print("─" * 70)
    #
    # ★ 왜 이걸 따로 지키는가 ★
    #   맨 SDP 를 보냈더니 진짜 로봇이 **말없이 연결을 끊었습니다.**
    #   오류도 상태 코드도 없이요. 그 침묵을 보고 세 번 헛짚었습니다
    #   (소켓 재사용 · 오디오 줄 · GET 대 POST). 답은 라이브러리 코드에
    #   있었습니다 — SDP 를 JSON 봉투에 담아 보냅니다.
    #   침묵으로 대답하는 상대와는 눈으로 씨름해 봐야 집니다.
    #
    robot = FakeRobot(data2=1)
    srv = await serve(robot, 8785)
    try:
        s.check("봉투의 모양", json.loads(sig.wrap_offer("SDP")),
                {"id": "STA_localNetwork", "sdp": "SDP",
                 "type": "offer", "token": ""})
        s.check("답에서 sdp 만 꺼냅니다",
                sig.unwrap_answer('{"sdp":"답","type":"answer"}'), "답")

        # ★ 얄팍한 제안을 보내기 전에 잡는가 ★
        #   진짜 로봇은 이런 제안에 말없이 끊습니다. 그 침묵을 문장으로
        #   바꾸는 것이 check_offer 의 일입니다.
        for label, bad, want in (
                ("빈 것", "", "SDP 가 아닙니다"),
                ("m= 줄이 없으면", STUB, "미디어 줄"),
                ("너무 짧으면", "v=0\r\nm=audio 9 x\r\n", "너무 짧습니다")):
            try:
                sig.check_offer(bad)
                s.check(f"{label} → 막습니다", "통과해버림", "막힘")
            except sig.SignalError as e:
                s.check(f"{label} → 이유를 말해줍니다", want in str(e), True)
        s.check("갖춘 제안은 통과합니다", sig.check_offer(OFFER), None)

        # 봉투를 안 씌우면 로봇이 거절해야 합니다 — 시험이 무른지 봅니다
        try:
            robot.con_ing(sig.path_ending(robot.data1), json.dumps({
                "data1": sig.aes_ecb_encrypt(OFFER, "0" * 32),
                "data2": "x"}))
            s.check("맨 SDP 는 거절당합니다", "통과해버림", "거절")
        except Exception as e:
            s.check("맨 SDP 는 거절당합니다", isinstance(e, ValueError), True)

        # 로봇이 바쁘면 사람 말로 알려줘야 합니다
        robot.busy = True
        try:
            await asyncio.to_thread(sig.handshake, "127.0.0.1", OFFER,
                                    None, 8785, 5.0, None)
            s.check("바쁠 때 → 막습니다", "통과해버림", "막힘")
        except sig.SignalError as e:
            s.check("바쁠 때 → 이유를 말해줍니다",
                    "이미 다른 곳과 연결" in str(e), True)
        robot.busy = False
    finally:
        srv.close()
        await srv.wait_closed()

    print()
    print("─" * 70)
    print(" 조각들")
    print("─" * 70)
    s.check("토큰 — 뒷글자를 A=0…J=9 로", sig.path_ending("xxxx1A2C3E4G5I"), "02468")
    s.check("공개키 — 앞뒤 10글자를 뗍니다",
            sig.public_key_of("0123456789" + "KEY" + "9876543210"), "KEY")
    k = sig.new_aes_key()
    s.check("새 키는 32글자 hex", len(k) == 32 and all(c in "0123456789abcdef" for c in k))
    s.check("AES 왕복 — 딱 떨어지는 길이",
            sig.aes_ecb_decrypt(sig.aes_ecb_encrypt("가" * 16, k), k), "가" * 16)
    s.check("AES 왕복 — 블록에 딱 맞는 길이(패딩 한 블록 더)",
            sig.aes_ecb_decrypt(sig.aes_ecb_encrypt("A" * 16, k), k), "A" * 16)
    s.check("AES 왕복 — 아주 긴 것",
            sig.aes_ecb_decrypt(sig.aes_ecb_encrypt(OFFER, k), k), OFFER)

    print()
    print("─" * 70)
    print(" 라이브러리와 대조")
    print("─" * 70)
    try:
        from unitree_webrtc_connect import encryption as lib
        from unitree_webrtc_connect import unitree_auth as auth
        s.check("AES 암호가 라이브러리와 같은 값",
                sig.aes_ecb_encrypt(OFFER, k), lib.aes_encrypt(OFFER, k))
        s.check("AES 복호도 같은 값",
                sig.aes_ecb_decrypt(lib.aes_encrypt("시험", k), k), "시험")
        s.check("토큰 계산이 라이브러리와 같은 값",
                sig.path_ending("xxxx1A2C3E4G5I"),
                auth._calc_local_path_ending("xxxx1A2C3E4G5I"))
        s.check("고정 키가 같습니다", sig.LEGACY_GCM_KEY, auth._LEGACY_GCM_KEY)
    except ImportError:
        print("   (라이브러리가 없어서 건너뜁니다 — 가짜 로봇 쪽이 더 중요합니다)")

    return 0 if s.report() else 1


def _arg(name, fallback=None):
    """--이름 값  형태를 하나 꺼냅니다."""
    args = sys.argv[1:]
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return fallback


if __name__ == "__main__":
    try:
        if "--serve" in sys.argv[1:]:
            d2 = int(_arg("--data2", "2"))
            k = _arg("--key")
            if d2 == 3 and not k:
                print("data2=3 은 키가 있어야 합니다:  --data2 3 --key <hex32>")
                sys.exit(1)
            sys.exit(asyncio.run(serve_forever(d2, k, int(_arg("--port", "9991")))) or 0)
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
