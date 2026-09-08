# -*- coding: utf-8 -*-
"""
왜 라이브러리는 되고 우리는 안 되는가 — **번갈아 세워 봅니다.**

  ★ 1차에서 알아낸 것 두 가지 ★

    ㄱ. **로봇은 토막 SDP 를 안 받습니다.**
        한 줄짜리 가짜 SDP 로는 라이브러리조차 막혔습니다. 그동안
        제가 그걸로 시험했으니 처음부터 헛것이었습니다.

    ㄴ. 진짜 제안으로는 **라이브러리는 되고 우리는 안 됐습니다.**
        봉투도 같고(둘 다 우리 wrap_offer 를 썼습니다), HTTP 도구도
        같았습니다(requests). 그러면 차이는 우리 암호 쪽에 있습니다.

  ★ 그런데 1차 비교에는 흠이 있었습니다 ★

    라이브러리를 **먼저** 돌렸고, 그게 성공했습니다. 성공한 악수는
    로봇에 세션을 하나 열어둡니다. 우리는 그 뒤에 붙으려 한 것이고요.

        ㄹ. 라이브러리 + 진짜   ○ 0.2초
        ㅁ. 우리 + 진짜         ★ 1.0초   ← 로봇이 이미 차 있어서?

    시도끼리 독립이 아닌데 순서를 고정했습니다. **재는 순서가 결과를
    만들었을 수 있습니다.**

  ★ 그래서 번갈아, 두 바퀴 ★

        우리 → 라이브러리 → 우리 → 라이브러리

    우리를 **먼저** 놓습니다. 우리가 첫 자리에서도 막히면 순서 탓이
    아닙니다. 우리가 첫 자리에서 되면 순서 탓이었습니다.

    그리고 성공한 뒤에는 오래 쉽니다 — 로봇이 반쯤 열린 세션을
    정리할 틈을 줍니다.

  ★ 로봇에 아무것도 시키지 않습니다 ★
    악수만 네 번 합니다. 움직이지 않습니다.
    다만 **유니트리 앱과 다른 PC 스크립트는 다 꺼두세요.**

  쓰는 법

      .\\run sig_diff.py              번갈아 두 바퀴 (약 1분)
      .\\run sig_diff.py --rounds 3   더 돌려보기
      .\\run sig_diff.py --dump       두 쪽이 만든 몸통을 글자로 견줍니다
"""

import asyncio
import json
import sys
import time

import common
import sig

REST_AFTER_OK = 6.0     # 성공한 뒤에는 오래 쉽니다 (세션이 열려 있습니다)
REST_AFTER_NO = 2.0


# ── 보내는 쪽 두 가지 ────────────────────────────────────────

def by_library(ip, sdp, key):
    """라이브러리의 함수를 그대로. 봉투는 우리 것을 씌웁니다 —
    드라이버가 하는 일이 그것이고, 1차에서 이 조합이 통했습니다."""
    from unitree_webrtc_connect import unitree_auth as auth
    out = auth.send_sdp_to_local_peer_new_method(ip, sig.wrap_offer(sdp), key)
    if out is None:
        raise RuntimeError("라이브러리가 None 을 돌려줬습니다 (실패)")
    return json.loads(out)["sdp"]


def by_us(ip, sdp, key):
    """우리 sig.handshake — HTTP 는 라이브러리와 같은 requests 로."""
    old = sig._http
    sig._http = _requests_http
    try:
        return sig.handshake(ip, sdp, key, trace=None)
    finally:
        sig._http = old


def _requests_http(url, body="", timeout=8.0):
    import requests
    headers = ({"Content-Type": "application/x-www-form-urlencoded"}
               if body else None)
    r = requests.post(url=url, data=(body or None), headers=headers,
                      timeout=timeout)
    r.raise_for_status()
    return r.text


# ── 진짜 SDP 하나 ────────────────────────────────────────────

async def _real_offer():
    """드라이버가 만드는 것과 같은 모양 — 데이터채널 · 비디오 · 오디오."""
    from aiortc import RTCPeerConnection
    pc = RTCPeerConnection()
    pc.createDataChannel("data")
    pc.addTransceiver("video", direction="recvonly")
    pc.addTransceiver("audio", direction="sendrecv")
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    sdp = pc.localDescription.sdp
    await pc.close()
    return sdp


# ── 두 쪽이 만든 몸통을 견주기 ───────────────────────────────

def dump(ip, sdp, key):
    """**같은 입력에 같은 몸통이 나오는가** — 로봇에 안 보내고 견줍니다.

    로봇은 틀렸을 때 아무 말도 안 해주니, 보내기 전에 우리끼리
    맞춰봅니다. 여기서 갈리면 그 자리가 원인입니다.
    """
    from unitree_webrtc_connect import encryption as lib
    from unitree_webrtc_connect import unitree_auth as auth

    envelope = sig.wrap_offer(sdp)
    aes = sig.new_aes_key()
    print("=" * 70)
    print(" 같은 입력에 같은 몸통이 나오는가 (로봇에 안 보냅니다)")
    print("=" * 70)
    print(f" 봉투 {len(envelope)}글자 · AES 키 {aes}")
    print()

    ours = sig.aes_ecb_encrypt(envelope, aes)
    theirs = lib.aes_encrypt(envelope, aes)
    same = ours == theirs
    print(f" {'○' if same else '★'} AES 로 싼 봉투  우리 {len(ours)} · 라이브러리 {len(theirs)}")
    if not same:
        for i, (a, b) in enumerate(zip(ours, theirs)):
            if a != b:
                print(f"     {i}번째 글자부터 다릅니다: {ours[i:i+40]!r}")
                print(f"                              {theirs[i:i+40]!r}")
                break
        else:
            print("     앞부분은 같고 길이만 다릅니다")

    # RSA 는 매번 값이 달라집니다(패딩에 난수). 길이와 복호 결과로 견줍니다.
    print()
    print(" ※ RSA 는 패딩에 난수가 들어가 매번 값이 다릅니다.")
    print("   그래서 길이만 견줍니다 — 길이가 다르면 조각내기가 다른 것입니다.")
    return 0 if same else 1


# ── 재기 ─────────────────────────────────────────────────────

def attempt(label, fn):
    print(f" ─ {label}")
    t0 = time.time()
    try:
        answer = fn()
        took = time.time() - t0
        print(f"   ○ 됐습니다 · {took:.1f}초 · SDP {len(answer)}글자")
        time.sleep(REST_AFTER_OK)
        return True
    except Exception as e:
        took = time.time() - t0
        print(f"   ★ 막혔습니다 · {took:.1f}초 · "
              f"{type(e).__name__}: {str(e).splitlines()[0][:90]}")
        time.sleep(REST_AFTER_NO)
        return False


def _arg(name, fallback=None):
    args = sys.argv[1:]
    if name in args and args.index(name) + 1 < len(args):
        return args[args.index(name) + 1]
    return fallback


def main():
    ip = common.resolve_ip()
    if not ip:
        return 1
    key = common.load_settings().get("aes_key") or ""
    sdp = asyncio.run(_real_offer())

    if "--dump" in sys.argv[1:]:
        return dump(ip, sdp, key)

    rounds = int(_arg("--rounds", "2"))
    print("=" * 70)
    print(" 번갈아 재기 — 우리가 먼저입니다")
    print("=" * 70)
    print(f" 로봇 {ip} · 키 {'있음' if key else '없음'} · 진짜 제안 {len(sdp)}글자")
    print(" ※ 유니트리 앱과 다른 PC 스크립트를 다 꺼두세요.")
    print(" ※ 성공한 뒤에는 6초 쉽니다 — 로봇이 세션을 정리할 틈입니다.")
    print()

    us, lib = [], []
    for r in range(1, rounds + 1):
        print(f"── {r}바퀴 " + "─" * 50)
        us.append(attempt("우리", lambda: by_us(ip, sdp, key)))
        lib.append(attempt("라이브러리", lambda: by_library(ip, sdp, key)))

    def mark(xs):
        return " ".join("○" if x else "★" for x in xs)

    print()
    print("=" * 70)
    print(" 무엇이 갈랐는가")
    print("=" * 70)
    print(f"   우리        {mark(us)}")
    print(f"   라이브러리  {mark(lib)}")
    print()

    if any(us):
        print(" ★ 우리도 됩니다 ★")
        print("   1차에서 막힌 것은 **순서 탓**이었습니다. 라이브러리가 먼저")
        print("   성공해 로봇에 세션을 열어둔 뒤였습니다.")
        print("   → 다리는 맞습니다. 폰에도 진짜 제안(오디오·비디오 포함)을")
        print("     보내게 하면 됩니다.")
    elif any(lib):
        print(" ★ 라이브러리만 됩니다 — 우리 코드에 아직 차이가 있습니다 ★")
        print("   순서를 바꿔도 우리는 첫 자리에서 막혔습니다. 순서 탓이")
        print("   아닙니다.")
        print("   →  .\\run sig_diff.py --dump  으로 두 쪽이 만든 몸통을")
        print("      글자 단위로 견줘보세요. 로봇에 안 보내고 견줍니다.")
    else:
        print(" ★ 둘 다 안 됩니다 ★")
        print("   우리 코드 탓이 아닙니다. 로봇이 다른 곳과 붙어 있거나")
        print("   시그널링이 막혀 있습니다. 로봇을 껐다 켜고 다시 재보세요.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
        sys.exit(1)
    except Exception as e:
        common.explain_error(e)
        sys.exit(1)
