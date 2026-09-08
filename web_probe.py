# -*- coding: utf-8 -*-
"""
휴대폰 브라우저가 로봇에 **직접** 붙을 수 있는가 — 앱의 길을 정하는 시험.

  ★ 왜 이것부터 재는가 ★

    휴대폰이 두뇌가 되려면 폰이 로봇에 직접 붙어야 합니다. 그런데
    '어떻게 붙느냐' 에 따라 만들 것의 크기가 **열 배쯤 차이납니다.**

        ㄱ. 브라우저가 그냥 붙는다      네이티브 코드 0 줄 (PWA)
        ㄴ. 시그널링만 막힌다           작은 다리 하나 (~200줄 Kotlin)
        ㄷ. 아무것도 안 된다            연결 계층 재작성 (~1,800줄)

    셋 중 어느 것인지는 **로봇에게 물어봐야** 알 수 있습니다. 문서에
    없고, 짐작할 수도 없습니다. 그래서 먼저 잽니다.

  ★ 무엇이 갈림길인가 — CORS ★

    로봇에 붙는 첫 단계는 평범한 HTTP 입니다.

        GET  http://<로봇>:9991/con_notify        ← 세션 공개키를 받음
        POST http://<로봇>:9991/con_ing_<토큰>    ← 암호화한 SDP 를 보냄

    파이썬은 이걸 그냥 합니다. 그런데 **브라우저는 다릅니다.**
    다른 출처(우리 화면은 PC 에서 옵니다)로 보낸 요청의 **응답을 읽으려면**
    서버가 `Access-Control-Allow-Origin` 을 붙여줘야 합니다.

    안 붙여주면 요청은 나가는데 답을 못 읽습니다. 그러면 공개키를
    못 받고, 거기서 끝입니다.

    ※ 다행히 이 두 요청은 '단순 요청' 이라 사전 확인(preflight OPTIONS)이
      없습니다. Content-Type 이 application/x-www-form-urlencoded 이고
      특별한 헤더를 안 붙이거든요. 그래서 오직 그 헤더 하나가 문제입니다.

  ★ 두 군데서 잽니다 ★

    1. PC 에서   — 응답 헤더에 그 값이 실제로 있는가
    2. 휴대폰에서 — 브라우저가 정말로 읽어내는가

    1번만으로는 모자랍니다. 헤더가 있어도 값이 안 맞을 수 있고, 없어도
    브라우저 종류에 따라 다를 수 있습니다. **재는 것은 브라우저입니다.**
    2번이 진짜 답이고, 1번은 그 이유를 알려줍니다.

  ★ 로봇을 움직이지 않습니다 ★

    연결을 맺지도 않습니다. 첫 인사만 건네고 헤더를 봅니다.
    로봇은 엎드려 있어도 되고, 다른 프로그램이 붙어 있어도 됩니다.
    (con_notify 는 세션을 잡지 않습니다)

  쓰는 법

      .\\run web_probe.py                    로봇은 알아서 찾습니다
      .\\run web_probe.py 192.168.0.51       주소를 직접 줄 때

    주소가 뜹니다. 휴대폰 브라우저로 열고 버튼을 누르세요.
    결과가 이 콘솔에 찍힙니다.
"""

import asyncio
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import config

PORT = 8770
SIGNAL_PORTS = (9991, 8081)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def port_open(ip, port, timeout=1.5):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, port)) == 0
    finally:
        s.close()


# ── 1. PC 에서 재기 ──────────────────────────────────────────

def ask_from_pc(ip, port):
    """con_notify 를 불러 응답 헤더를 그대로 봅니다."""
    url = f"http://{ip}:{port}/con_notify"
    out = {"url": url}
    req = urllib.request.Request(url, method="GET")
    # 브라우저가 보내는 것과 같은 Origin 을 붙여봅니다 — 서버가 이것을
    # 보고 헤더를 붙이는 구현도 흔합니다.
    req.add_header("Origin", f"http://{lan_ip()}:{PORT}")
    # ★ 프록시를 거치지 않습니다 ★
    #   로봇은 같은 공유기 안에 있습니다. 그런데 urllib 는 환경변수의
    #   http_proxy 를 그냥 씁니다. 학교 망처럼 프록시가 잡혀 있으면
    #   랜 주소를 바깥으로 보내려다 조용히 시간만 끕니다.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=5) as r:
            out["code"] = r.status
            out["headers"] = dict(r.headers)
            body = r.read()
            out["bytes"] = len(body)
    except urllib.error.HTTPError as e:
        out["code"] = e.code
        out["headers"] = dict(e.headers)
        out["bytes"] = 0
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def show_pc(res):
    print("─" * 70)
    print(" 1. PC 에서 — 응답 헤더에 무엇이 붙어 오는가")
    print("─" * 70)
    print(f"   {res['url']}")
    if "error" in res:
        print(f"   ★ 닿지 못했습니다: {res['error']}")
        return None
    print(f"   응답 {res['code']} · 본문 {res['bytes']} 바이트")
    print()
    for k, v in sorted(res["headers"].items()):
        mark = "★" if k.lower().startswith("access-control") else " "
        print(f"   {mark} {k}: {v}")
    acao = None
    for k, v in res["headers"].items():
        if k.lower() == "access-control-allow-origin":
            acao = v
    print()
    if acao:
        print(f"   ★ Access-Control-Allow-Origin: {acao}")
        print("     브라우저가 응답을 읽을 수 있다는 뜻입니다.")
    else:
        print("   ※ Access-Control-Allow-Origin 이 없습니다.")
        print("     브라우저는 응답을 못 읽습니다 — 요청은 나가지만 답이 막힙니다.")
    return acao


# ── 2. 휴대폰에서 재기 ───────────────────────────────────────

PAGE = """<!doctype html><html lang=ko><head>
<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>로봇에 직접 붙을 수 있는가</title>
<style>
body{margin:0;padding:18px;background:#14181d;color:#e8edf1;
     font-family:-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
     line-height:1.6}
h1{font-size:17px;margin:0 0 6px}
p.sub{color:#8d979f;font-size:13px;margin:0 0 18px}
button{width:100%;padding:18px;font-size:17px;font-weight:600;border:0;
       border-radius:12px;background:#2f7d5f;color:#fff;font-family:inherit}
button:disabled{opacity:.5}
.box{background:#1d232a;border:1px solid #2c343d;border-radius:12px;
     padding:14px;margin-top:14px;font-size:14px;white-space:pre-wrap;
     word-break:break-all}
.ok{color:#7fe0b0}.no{color:#ff9c8f}.dim{color:#8d979f;font-size:12px}
</style></head><body>
<h1>휴대폰이 로봇에 직접 붙을 수 있는가</h1>
<p class=sub>로봇 __IP__:__PORT__ 에 첫 인사만 건네봅니다.
로봇은 움직이지 않고, 연결도 맺지 않습니다.</p>
<button id=go>재보기</button>
<div class=box id=out>아직 안 눌렀습니다.</div>
<p class=dim>결과는 PC 콘솔에도 함께 찍힙니다.</p>
<script>
const $=i=>document.getElementById(i);
function say(html){ $('out').innerHTML = html; }
async function tell(result){
  try{ await fetch('/result',{method:'POST',
       headers:{'Content-Type':'text/plain'},
       body:JSON.stringify(result)}); }catch(e){}
}
$('go').onclick = async ()=>{
  $('go').disabled = true;
  say('보내는 중…');
  const url = 'http://__IP__:__PORT__/con_notify';
  const t0 = performance.now();
  const r = {ua: navigator.userAgent};
  try{
    const res = await fetch(url, {method:'GET', cache:'no-store'});
    r.ms = Math.round(performance.now()-t0);
    r.status = res.status;
    const body = await res.text();
    r.bytes = body.length;
    r.ok = true;
    say('<span class=ok>★ 읽었습니다 ★</span>\\n\\n'
        + '응답 ' + res.status + ' · ' + body.length + ' 글자 · '
        + r.ms + 'ms\\n\\n'
        + '브라우저가 로봇의 답을 읽어냈습니다.\\n'
        + '네이티브 코드 없이 붙을 수 있다는 뜻입니다.');
  }catch(e){
    r.ms = Math.round(performance.now()-t0);
    r.ok = false;
    r.error = String(e);
    say('<span class=no>막혔습니다</span>\\n\\n' + e + '\\n\\n'
        + '요청은 나갔을 수 있지만 <b>답을 읽지 못했습니다.</b>\\n'
        + '브라우저만으로는 로봇에 못 붙습니다 — 시그널링을 대신 해줄\\n'
        + '작은 다리가 필요합니다.\\n\\n'
        + '<span class=dim>※ 로봇이 꺼져 있거나 다른 공유기에 있어도\\n'
        + '같은 모양으로 실패합니다. PC 쪽 결과와 같이 보세요.</span>');
  }
  await tell(r);
  $('go').disabled = false;
};
</script></body></html>"""


class Probe:
    def __init__(self, robot_ip, port):
        self.robot_ip = robot_ip
        self.port = port
        self.said = []

    async def _client(self, reader, writer):
        try:
            line = await asyncio.wait_for(reader.readline(), 10)
            if not line:
                return
            parts = line.decode("latin-1").split()
            if len(parts) < 2:
                return
            method, path = parts[0], parts[1]
            length = 0
            while True:
                h = await asyncio.wait_for(reader.readline(), 10)
                if h in (b"\r\n", b"\n", b""):
                    break
                if h.lower().startswith(b"content-length:"):
                    length = int(h.split(b":")[1].strip())
            body = await reader.readexactly(length) if length else b""

            if path == "/result" and method == "POST":
                try:
                    self.said.append(json.loads(body.decode("utf-8")))
                except Exception:
                    pass
                out, ctype = b"ok", "text/plain"
            else:
                page = (PAGE.replace("__IP__", self.robot_ip)
                            .replace("__PORT__", str(self.port)))
                out, ctype = page.encode("utf-8"), "text/html; charset=utf-8"
            writer.write(b"HTTP/1.1 200 OK\r\n"
                         + f"Content-Type: {ctype}\r\n".encode()
                         + f"Content-Length: {len(out)}\r\n".encode()
                         + b"Connection: close\r\n\r\n" + out)
            await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass


def verdict(acao, phone):
    print()
    print("=" * 70)
    print(" 그래서 어느 길인가")
    print("=" * 70)
    if phone is None:
        print(" 휴대폰에서 아직 안 눌렀습니다. 그게 진짜 답입니다 — 눌러주세요.")
        if acao:
            print(" (PC 쪽만 보면 좋아 보입니다. 그래도 브라우저로 확인하세요)")
        return None

    if phone.get("ok"):
        print(" ★ ㄱ. 브라우저가 그냥 붙습니다 ★")
        print()
        print("   휴대폰 브라우저가 로봇의 답을 읽어냈습니다.")
        print("   네이티브 코드 없이 **웹앱(PWA)** 으로 갈 수 있습니다.")
        print("   지금 만들어둔 화면이 그대로 앱이 됩니다.")
        print()
        print("   다음: 시그널링 두 단계를 브라우저 WebCrypto 로 옮기기")
        print("         (RSA-OAEP · AES-GCM — 둘 다 브라우저에 있습니다)")
        return "pwa"

    print(" ㄴ/ㄷ. 브라우저만으로는 못 붙습니다")
    print()
    print(f"   막힌 모양: {phone.get('error')}")
    print()
    if acao:
        print("   ※ PC 에서는 헤더가 보였는데 브라우저는 막혔습니다.")
        print("     값이 우리 출처와 안 맞거나, 사전 확인에서 걸린 것입니다.")
    else:
        print("   PC 쪽에서도 Access-Control-Allow-Origin 이 없었습니다.")
        print("   로봇은 브라우저에서 부를 것을 염두에 두고 만들어지지 않았습니다.")
    print()
    print("   → 그래도 통째로 다시 만들 일은 아닙니다.")
    print("     막힌 것은 **시그널링 두 번의 HTTP 요청뿐**입니다.")
    print("     WebRTC 자체와 데이터채널·오디오는 브라우저가 다 합니다.")
    print()
    print("     그러니 WebView 앱 + 그 두 요청만 대신 해주는 작은 다리로")
    print("     충분합니다. 화면과 안내 로직은 지금 것을 그대로 씁니다.")
    return "bridge"


def find_robot_ip(verbose=True):
    """로봇 IP — **다른 스크립트와 같은 방법으로** 찾습니다.

    ★ 여기만 다르게 굴면 안 됩니다 ★
      처음에 config.ROBOT_IP 만 봤다가 "로봇 IP 를 모르겠습니다" 로
      끝났습니다. 그 칸은 원래 비어 있는 것이 정상입니다 — 이 저장소는
      **찾아서 저장해 두고 그다음부터는 그냥 씁니다.**
      (환경변수/config → settings.local.json → 자동 탐색)

      쓰는 사람 입장에서는 다른 스크립트가 다 알아서 찾는데 이것만
      물어보는 셈입니다. 같은 길을 지나게 합니다.
    """
    try:
        import common
        return common.resolve_ip(verbose=verbose)
    except Exception as e:
        # common 은 로봇 라이브러리를 불러옵니다. 그게 없어도 저장된
        # 값만은 읽을 수 있으니 거기까지는 해봅니다.
        if verbose:
            print(f" ※ common 을 못 불러왔습니다 ({type(e).__name__}). "
                  f"저장된 값만 봅니다.")
        try:
            saved = json.loads(
                (config.HERE if hasattr(config, "HERE") else Path("."))
                .joinpath("settings.local.json").read_text(encoding="utf-8"))
            return saved.get("robot_ip", "")
        except Exception:
            return ""


async def main():
    ip = ""
    for a in sys.argv[1:]:
        if a.count(".") == 3:
            ip = a
    if not ip:
        ip = (getattr(config, "ROBOT_IP", "") or "").strip()
    if not ip:
        ip = find_robot_ip()
    if not ip:
        print("로봇을 찾지 못했습니다.")
        print("  → 로봇이 켜져 있고 같은 공유기에 있는지:  .\\run find_robot.py")
        print("  → 아니면 주소를 직접:  .\\run web_probe.py 192.168.0.51")
        return 1

    print("=" * 70)
    print(" 휴대폰이 로봇에 직접 붙을 수 있는가")
    print("=" * 70)
    print(" 로봇을 움직이지 않습니다. 연결도 맺지 않습니다.")
    print(" 첫 인사(con_notify)만 건네고 응답 헤더를 봅니다.")
    print()

    port = None
    for p in SIGNAL_PORTS:
        if port_open(ip, p):
            port = p
            print(f" 시그널링 포트: {ip}:{p} 열려 있습니다")
            break
    if port is None:
        print(f" ★ {ip} 의 {SIGNAL_PORTS} 가 다 닫혀 있습니다.")
        print("   로봇이 켜져 있고 같은 공유기에 있는지 보세요 "
              "(.\\run find_robot.py)")
        return 1
    print()

    acao = show_pc(ask_from_pc(ip, port))

    probe = Probe(ip, port)
    server = await asyncio.start_server(probe._client, "0.0.0.0", PORT)
    here = lan_ip()
    print()
    print("─" * 70)
    print(" 2. 휴대폰에서 — 브라우저가 정말로 읽어내는가")
    print("─" * 70)
    print(f"   휴대폰 브라우저로 여세요:   http://{here}:{PORT}")
    print("   '재보기' 를 누르면 결과가 여기 찍힙니다.")
    print("   (Ctrl+C 로 끝냅니다)")
    print()

    try:
        seen = 0
        while True:
            await asyncio.sleep(0.3)
            if len(probe.said) > seen:
                got = probe.said[-1]
                seen = len(probe.said)
                stamp = time.strftime("%H:%M:%S")
                mark = "읽었습니다" if got.get("ok") else "막혔습니다"
                print(f" [{stamp}] 휴대폰: {mark}"
                      + (f" (응답 {got.get('status')}, "
                         f"{got.get('bytes')}글자, {got.get('ms')}ms)"
                         if got.get("ok") else f" — {got.get('error')}"))
                verdict(acao, got)
                print()
                print(" 다시 눌러도 됩니다. 끝내려면 Ctrl+C.")
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        server.close()
        if not probe.said:
            verdict(acao, None)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()) or 0)
    except KeyboardInterrupt:
        print("\n멈췄습니다.")
