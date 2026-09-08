# -*- coding: utf-8 -*-
"""
시그널링 다리 — 브라우저가 못 하는 두 번의 HTTP.  ★ Kotlin 의 명세입니다 ★

  ★ 왜 이것만 따로 떼는가 ★

    휴대폰이 두뇌가 되려면 폰이 로봇에 직접 붙어야 합니다. 재봤더니
    (web_probe.py) 브라우저가 막히는 곳은 **딱 두 군데**였습니다.

        GET  http://<로봇>:9991/con_notify        ← 막힘 (CORS)
        POST http://<로봇>:9991/con_ing_<토큰>    ← 막힘 (CORS)

        그 뒤의 WebRTC · 데이터채널 · 오디오 · 안내 로직은 전부
        브라우저가 그냥 합니다.

    게다가 이 두 요청에 쓰는 암호를 브라우저 표준으로는 못 합니다.

        AES-ECB + PKCS5 패딩     WebCrypto 에 ECB 가 없습니다
        RSA PKCS1 v1.5           WebCrypto 는 OAEP 만 합니다

    그래서 이 파일이 존재합니다. **앱에서 네이티브로 가야 하는 것은
    이 파일이 하는 일 전부이고, 그게 전부입니다.**

  ★ 계약 — 함수 하나 ★

        handshake(ip, offer_sdp, aes_128_key) -> answer_sdp

    부르는 쪽은 SDP 제안을 주고 SDP 응답을 받습니다. 그 사이의
    암호와 토큰 계산은 여기서 다 합니다. 이 모양이면 파이썬이든
    Kotlin 이든 갈아 끼울 수 있습니다.

  ★ Kotlin 으로 옮길 때 ★

    안드로이드 표준 라이브러리에 그대로 있습니다. 이름까지 같습니다.

        aes_ecb_encrypt / decrypt   Cipher "AES/ECB/PKCS5Padding"
        rsa_encrypt                 Cipher "RSA/ECB/PKCS1Padding"
        decrypt_data1               Cipher "AES/GCM/NoPadding"  (아래 ※)
        HTTP                        OkHttp

    ※ GCM 의 조각 배치가 흔한 순서와 다릅니다. 이걸 놓치면 태그 검사에서
      떨어지는데, 왜인지는 안 알려줍니다.

          [ 암호문 ... ][ nonce 12바이트 ][ 태그 16바이트 ]
                         ~~~~~~~~~~~~~~~   ~~~~~~~~~~~~~~
                         뒤에서 28~16      맨 뒤 16

      보통은 nonce 가 앞에 옵니다. 여기서는 뒤에 있습니다.

    ※ 패딩은 **바이트에** 합니다. 라이브러리는 글자 수로 세는데,
      아스키에서는 둘이 같은 값을 냅니다. SDP 는 아스키라 문제가 없고,
      Kotlin 의 PKCS5Padding 도 바이트에 하므로 그대로 맞습니다.

      다만 아스키가 아니면 라이브러리 쪽은 **틀립니다.** 재봤습니다.

          "가" × 15   라이브러리 46바이트 ← 16의 배수가 아닙니다
                      우리       48바이트

          46바이트로는 AES 가 아예 못 돌아갑니다. 여기 SDP 말고
          다른 것을 넣게 되면 그때 드러날 자리입니다.

  ★ 이 파일을 어떻게 믿는가 ★

    라이브러리를 베낀 것이라 "잘 베꼈는지" 가 문제입니다. 그래서
    두 가지로 확인합니다 (sig_test.py).

      1. 라이브러리가 있으면 **같은 입력에 같은 답**을 내는지 대조
      2. 라이브러리가 없어도, **가짜 로봇과 실제로 악수**가 되는지

    2번이 더 중요합니다. 로봇 쪽 절반을 명세대로 만들어놓고 우리
    다리가 통과하는지 보는 것이라, 베낀 것이 아니라 **맞는 것**인지를
    봅니다.

  쓰는 법

      .\\run sig.py            무엇을 하는지 단계별로 보여줍니다 (연결 안 함)
      .\\run sig_test.py       가짜 로봇과 악수해 봅니다 (로봇 불필요)
"""

import base64
import binascii
import json
import urllib.error
import urllib.request
import uuid

SIGNAL_PORTS = (9991, 8081)

# data2 == 2 인 로봇(구형 펌웨어)이 쓰는 고정 키.
# 유니트리 앱의 AESGCMUtil.keyBytes 와 같습니다.
LEGACY_GCM_KEY = bytes(
    [232, 86, 130, 189, 22, 84, 155, 0, 142, 4, 166, 104, 43, 179, 235, 227]
)

# con_ing_<토큰> 을 만들 때 쓰는 글자표
PATH_ALPHABET = "ABCDEFGHIJ"


class SignalError(RuntimeError):
    """악수가 안 된 이유를 사람 말로 담습니다."""


# ── 암호 ─────────────────────────────────────────────────────

def _pad(data: bytes) -> bytes:
    """PKCS#5/7 — 16의 배수로 채웁니다. 딱 맞으면 16바이트를 더 붙입니다."""
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def _unpad(data: bytes) -> bytes:
    if not data:
        raise SignalError("빈 응답을 받았습니다.")
    n = data[-1]
    if n < 1 or n > 16 or len(data) < n:
        raise SignalError("패딩이 이상합니다 — 키가 다르거나 응답이 깨졌습니다.")
    return data[:-n]


def aes_ecb_encrypt(text: str, key: str) -> str:
    """AES-ECB + PKCS5. 키는 32글자 hex 문자열을 **그대로 바이트로** 씁니다.

    ※ hex 를 디코드하지 않습니다. 32글자 → 32바이트 → AES-256 입니다.
      (앱이 그렇게 하고, 로봇이 그렇게 기대합니다)
    """
    from Crypto.Cipher import AES
    cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
    return base64.b64encode(
        cipher.encrypt(_pad(text.encode("utf-8")))).decode("utf-8")


def aes_ecb_decrypt(b64: str, key: str) -> str:
    from Crypto.Cipher import AES
    cipher = AES.new(key.encode("utf-8"), AES.MODE_ECB)
    raw = base64.b64decode(b64)
    if len(raw) % 16:
        raise SignalError("응답 길이가 블록 크기에 안 맞습니다.")
    return _unpad(cipher.decrypt(raw)).decode("utf-8")


def new_aes_key() -> str:
    """이번 악수에만 쓰는 키 — uuid4 를 hex 32글자로."""
    return binascii.hexlify(uuid.uuid4().bytes).decode("utf-8")


def rsa_encrypt(text: str, pem_b64: str) -> str:
    """RSA PKCS1 v1.5. 키 크기보다 길면 나눠서 붙입니다.

    ※ pem_b64 는 base64 로 감싼 DER 입니다 (PEM 머리말이 없습니다).
    """
    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.PublicKey import RSA
    key = RSA.import_key(base64.b64decode(pem_b64))
    cipher = PKCS1_v1_5.new(key)
    chunk = key.size_in_bytes() - 11
    data = text.encode("utf-8")
    out = bytearray()
    for i in range(0, len(data), chunk):
        out.extend(cipher.encrypt(data[i:i + chunk]))
    return base64.b64encode(bytes(out)).decode("utf-8")


def decrypt_data1(data1_b64: str, data2, aes_128_key=None) -> str:
    """con_notify 가 준 data1 을 풉니다.

        data2 == 1 (또는 없음)   이미 평문
        data2 == 2               고정 키로 GCM 복호
        data2 == 3               이 로봇만의 AES-128 키로 GCM 복호

    ★ 조각 배치가 뒤쪽입니다 ★
      [암호문][nonce 12][태그 16] — nonce 가 앞이 아니라 뒤에 있습니다.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if data2 in (None, 1, "1"):
        return data1_b64
    raw = base64.b64decode(data1_b64)
    if len(raw) < 28:
        raise SignalError("data1 이 너무 짧습니다 (28바이트 미만).")
    tag, nonce, body = raw[-16:], raw[-28:-16], raw[:-28]

    if data2 in (2, "2"):
        key = LEGACY_GCM_KEY
    elif data2 in (3, "3"):
        if not aes_128_key:
            raise SignalError(
                "이 로봇은 자기만의 AES-128 키를 요구합니다 (data2=3).\n"
                "  →  .\\run get_aes_key.py  로 발급받으세요.")
        try:
            key = bytes.fromhex(aes_128_key.strip().lower())
        except ValueError:
            raise SignalError("AES 키가 hex 가 아닙니다 (32글자여야 합니다).")
        if len(key) != 16:
            raise SignalError(
                f"AES 키는 16바이트(32글자)여야 하는데 {len(key)}바이트입니다.")
    else:
        raise SignalError(f"모르는 data2 값입니다: {data2!r}")

    try:
        return AESGCM(key).decrypt(nonce, body + tag, None).decode("utf-8")
    except Exception:
        raise SignalError(
            "AES 키를 로봇이 거부했습니다 (태그 검사 실패).\n"
            "  → 이 로봇의 SN 으로 받은 키가 맞는지 확인하세요.")


def path_ending(data1: str) -> str:
    """con_ing_<여기> 를 계산합니다.

    마지막 10글자를 두 글자씩 끊고, **뒷글자**를 A=0 … J=9 로 바꿔
    이어 붙입니다. 앱이 하는 그대로입니다.
    """
    tail = data1[-10:]
    out = []
    for i in range(0, len(tail), 2):
        pair = tail[i:i + 2]
        if len(pair) > 1 and pair[1] in PATH_ALPHABET:
            out.append(str(PATH_ALPHABET.index(pair[1])))
    return "".join(out)


def public_key_of(data1: str) -> str:
    """data1 에서 공개키만 떼어냅니다 — 앞뒤 10글자가 껍데기입니다."""
    if len(data1) <= 20:
        raise SignalError("data1 이 짧아서 공개키를 못 꺼냅니다.")
    return data1[10:len(data1) - 10]


# ── HTTP ─────────────────────────────────────────────────────

def _http(url, body=None, timeout=8.0):
    """랜 안의 로봇에게 보냅니다. **프록시를 거치지 않습니다.**

    학교 망처럼 프록시가 잡혀 있으면 urllib 이 랜 주소를 바깥으로
    보내려다 조용히 시간만 끕니다.
    """
    data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data,
                                 method="POST" if data else "GET")
    if data:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raise SignalError(f"{url} 이 {e.code} 을 돌려줬습니다.")
    except Exception as e:
        raise SignalError(f"{url} 에 닿지 못했습니다: {type(e).__name__}: {e}")


# ── 계약 ─────────────────────────────────────────────────────

def handshake(ip, offer_sdp, aes_128_key=None, port=9991, timeout=8.0,
              trace=None):
    """SDP 제안을 주면 SDP 응답을 돌려줍니다. **이것이 다리의 전부입니다.**

    trace 에 함수를 주면 단계마다 불러줍니다 (무엇이 어디서 막혔는지
    보려고). 로봇에 아무것도 시키지 않습니다 — 연결을 맺는 첫 악수일
    뿐입니다.
    """
    def step(name, detail=""):
        if trace:
            trace(name, detail)

    base = f"http://{ip}:{port}"

    step("1. con_notify", f"{base}/con_notify")
    raw = _http(f"{base}/con_notify", timeout=timeout)
    try:
        info = json.loads(base64.b64decode(raw).decode("utf-8"))
    except Exception as e:
        raise SignalError(f"con_notify 응답을 못 읽었습니다: {type(e).__name__}")

    data1 = decrypt_data1(info.get("data1", ""), info.get("data2"),
                          aes_128_key)
    step("2. data1 풀기", f"data2={info.get('data2')} · {len(data1)}글자")

    pem = public_key_of(data1)
    token = path_ending(data1)
    step("3. 공개키와 토큰", f"토큰 {token!r}")

    key = new_aes_key()
    body = json.dumps({
        "data1": aes_ecb_encrypt(offer_sdp, key),
        "data2": rsa_encrypt(key, pem),
    })
    step("4. con_ing", f"{base}/con_ing_{token}")
    answer_raw = _http(f"{base}/con_ing_{token}", body=body, timeout=timeout)

    answer = aes_ecb_decrypt(answer_raw, key)
    step("5. 응답 풀기", f"{len(answer)}글자")
    return answer


def show():
    """무엇을 하는지 말로 풀어 보여줍니다. 로봇에 연결하지 않습니다."""
    print("=" * 70)
    print(" 시그널링 다리 — 앱에서 네이티브로 가야 하는 것 전부")
    print("=" * 70)
    print()
    print(" 계약:  handshake(ip, offer_sdp, aes_128_key) -> answer_sdp")
    print()
    for n, line in enumerate([
        "GET  con_notify           →  base64 안에 {data1, data2}",
        "data1 풀기                →  data2 가 1·2·3 중 무엇이냐로 갈립니다",
        "data1[10:-10] = 공개키    ·  마지막 10글자 = con_ing 토큰",
        "AES 키를 새로 만들어      →  SDP 는 AES-ECB, 그 키는 RSA 로",
        "POST con_ing_<토큰>       →  돌아온 것을 AES 로 풀면 SDP 응답",
    ], 1):
        print(f"   {n}. {line}")
    print()
    print(" 브라우저가 못 하는 이유")
    print("   · CORS — 로봇이 Access-Control-Allow-Origin 을 안 줍니다")
    print("   · AES-ECB 와 RSA PKCS1v1.5 는 WebCrypto 에 없습니다")
    print()
    print(" 안드로이드에서는")
    print('   · Cipher "AES/ECB/PKCS5Padding"   · Cipher "RSA/ECB/PKCS1Padding"')
    print('   · Cipher "AES/GCM/NoPadding"      · OkHttp')
    print()
    print(" ※ GCM 조각 배치: [암호문][nonce 12][태그 16] — nonce 가 뒤입니다.")
    print()
    print(" 맞는지 확인:   .\\run sig_test.py   (가짜 로봇과 악수해 봅니다)")


if __name__ == "__main__":
    show()
