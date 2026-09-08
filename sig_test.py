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

      .\\run sig_test.py
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
        # 그 키로 SDP 를 풉니다
        offer = sig.aes_ecb_decrypt(got["data1"], key)
        self.seen = {"key": key, "offer": offer}
        return sig.aes_ecb_encrypt(self.answer_sdp, key)


async def serve(robot, port):
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
            data = out.encode("utf-8")
            writer.write(f"HTTP/1.1 {code}\r\nContent-Type: text/plain\r\n"
                         f"Content-Length: {len(data)}\r\n"
                         f"Connection: close\r\n\r\n".encode() + data)
            await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass
    return await asyncio.start_server(handle, "127.0.0.1", port)


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


OFFER = ("v=0\r\no=- 4611731400430051336 2 IN IP4 127.0.0.1\r\n"
         "s=-\r\nt=0 0\r\na=group:BUNDLE 0\r\n" + "a=filler:x\r\n" * 40)


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


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
