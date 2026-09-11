#!/usr/bin/env python3
"""폰 브라우저가 마이크를 쓸 수 있는가 — 그것만 재는 자리.

`web_probe.py` 의 동생입니다. 그쪽은 "폰이 로봇에 붙을 수 있는가" 를
쟀고, 이쪽은 "폰이 **귀**를 쓸 수 있는가" 를 잽니다.

★ 이름을 조심하세요 ★

  이 파일은 처음에 mic_test.py 라는 이름으로 만들었습니다. 그런데
  그 이름은 **이미 쓰이고 있었습니다** — 로봇에게 귀가 있는지 재는
  스크립트입니다. 하마터면 덮어쓸 뻔했습니다.

  둘은 묻는 것이 다릅니다.

      mic_test.py   로봇에게 귀가 있는가   → 없습니다 (두 번 확인)
      web_mic.py    폰에게 귀를 빌릴 수 있는가

★ 왜 만들었나 ★

  로봇에게 귀가 없다는 것이 확인됐습니다. mic_test.py 를 두 번
  돌려서, 말할 때와 조용할 때가 **-0.1 dB / +0.1 dB** 로 같았습니다.
  프레임은 초당 50개씩 오는데 소리가 안 담겨 있습니다.

  그러면 귀는 폰에서 빌려와야 합니다. 그런데 "웹앱으로 음성 인식이
  되느냐" 에 답하려면 세 가지를 알아야 하는데, 셋 다 제가
  **확실히 모릅니다.**

    ㄱ. http://192.168.0.x 가 폰 브라우저에서 '안전한 자리' 인가
    ㄴ. 안드로이드 크롬의 한국어 인식이 인터넷 없이 되는가
    ㄷ. WebView (=우리 앱) 안에서도 같은 것이 되는가

  세 가지를 **읽어서** 답하면 또 틀립니다. 이 프로젝트에서 그렇게
  네 번 틀렸습니다 (삽질 기록 28번). 그래서 재는 것을 먼저 만듭니다.

★ 무엇이 걸림돌이라고 짐작하는가 ★

  브라우저는 마이크를 아무에게나 안 줍니다. **'안전한 자리'**
  (secure context) 에서만 줍니다 — https 이거나 localhost 일 때만요.
  그런데 remote.py 는 http://192.168.0.x:8765 로 뜹니다. 폰이 보기에
  그건 안전한 자리가 아닙니다.

  걸림돌이 **인식기가 아니라 자물쇠**라는 뜻입니다. 자물쇠만 풀면
  인식하는 길은 두 갈래로 열립니다.

    ㄱ. 브라우저가 직접 알아듣기   (Web Speech API)
    ㄴ. 폰이 녹음해서 PC 로 보내기 (PC 의 whisper 가 알아듣기)

  ㄴ 이 더 마음에 듭니다. **마이크는 복도에, 인식기는 PC 에** 두는
  것이고, whisper 는 이미 돌고 있으며 인터넷도 안 씁니다.

  다만 둘 다 마이크를 잡아야 합니다. 그래서 자물쇠가 먼저입니다.

★ 이 스크립트가 하는 일 ★

  같은 페이지를 **두 가지 자리에서** 띄웁니다.

      .\\run web_mic.py            https (스스로 만든 인증서)
      .\\run web_mic.py --plain    http  (remote.py 와 같은 조건)

  폰으로 둘 다 열어보고 견주면, 자물쇠가 진짜 원인인지 한눈에
  드러납니다. 한쪽만 되면 원인이 맞고, 둘 다 안 되면 딴 데 있습니다.

  ※ https 쪽은 폰이 "이 사이트는 안전하지 않습니다" 라고 겁을 줍니다.
    스스로 만든 인증서라 그렇습니다. 고급 → 계속 을 누르세요.
    그러고도 마이크를 안 주면, 인증서를 폰에 심어야 합니다 —
    그 이야기는 아래 CERT_NOTE 에 적어뒀습니다.
"""

import argparse
import datetime
import http.server
import json
import socket
import ssl
import sys
from pathlib import Path

HERE = Path(__file__).parent
CERT = HERE / "webmic_cert.local.pem"      # .gitignore 에 있습니다
KEY = HERE / "webmic_key.local.pem"
PORT_HTTPS = 8767
PORT_PLAIN = 8766

CERT_NOTE = """
 인증서를 폰에 심는 법 (경고 화면을 눌러도 마이크를 안 줄 때)

   1. 폰 브라우저로  http://{ip}:{plain}/cert  를 엽니다 (내려받아집니다)
   2. 설정 → 보안 → 기타 보안 설정 → 인증서 설치 → CA 인증서
   3. 내려받은 webmic_cert.local.pem 을 고릅니다

 ※ 삼성 폰은 여기서도 한 번 더 겁을 줍니다. 이 인증서는 이 PC 가
   방금 만든 것이고 유효기간이 30일입니다. 시연이 끝나면 지우세요
   (설정 → 보안 → 신뢰할 수 있는 자격증명 → 사용자).
"""


def lan_ip():
    """휴대폰이 칠 수 있는 이 PC 의 주소.

    remote.py 의 것과 같은 방법입니다. 바깥으로 나가는 소켓을 하나
    열어서 실제로 쓰이는 쪽 주소를 물어봅니다 (보내지는 않습니다).
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def make_cert(ip):
    """스스로 서명한 인증서를 만듭니다.

    ★ 주소를 인증서 안에 넣어야 합니다 ★
      크롬은 이름(CN)만 보지 않고 subjectAltName 을 봅니다. IP 로
      접속하면 SAN 에 그 **IP** 가 들어 있어야 합니다 — DNS 이름으로
      넣으면 안 맞습니다. 이걸 빼먹으면 '계속' 을 눌러도 자물쇠가
      안 풀립니다.

    새 의존성은 없습니다. cryptography 는 aiortc 가 이미 끌고 옵니다.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    import ipaddress

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ip),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "robotdog00 mic test"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)                     # 스스로 서명합니다
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=30))
        .add_extension(x509.SubjectAlternativeName([
            x509.IPAddress(ipaddress.ip_address(ip)),
            x509.DNSName("localhost"),
        ]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None),
                       critical=True)
        .sign(key, hashes.SHA256())
    )
    CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    KEY.write_bytes(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()))
    return cert


def cert_ok_for(ip):
    """이미 있는 인증서가 이 주소에 맞는가.

    주소가 바뀌면 (다른 공유기, 다른 랜) 옛 인증서는 못 씁니다.
    말없이 옛것을 쓰면 '계속' 을 눌러도 안 되는 이유를 알 수 없습니다.
    """
    if not (CERT.exists() and KEY.exists()):
        return False
    try:
        from cryptography import x509
        import ipaddress
        c = x509.load_pem_x509_certificate(CERT.read_bytes())
        now = datetime.datetime.now(datetime.timezone.utc)
        if c.not_valid_after_utc < now:
            return False
        san = c.extensions.get_extension_for_class(
            x509.SubjectAlternativeName).value
        return ipaddress.ip_address(ip) in san.get_values_for_type(
            x509.IPAddress)
    except Exception:
        return False


PAGE = """<!doctype html><html lang=ko><head>
<meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>마이크가 열리는가</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;padding:18px calc(16px + env(safe-area-inset-left)) 40px;
     background:#14181d;color:#e8edf1;line-height:1.6;
     font-family:-apple-system,"Apple SD Gothic Neo","Malgun Gothic",sans-serif}
h1{font-size:18px;margin:0 0 4px}
.ver{font-size:11px;font-weight:400;color:#14181d;border-radius:6px;
     padding:2px 7px;vertical-align:middle;margin-left:6px}
.ver.s{background:#7fe0b0}.ver.p{background:#ffb37a}
p.sub{color:#8d979f;font-size:13px;margin:0 0 18px}
h2{font-size:12px;letter-spacing:.12em;color:#8d979f;text-transform:uppercase;
   margin:24px 4px 10px}
.row{display:flex;gap:10px;align-items:flex-start;background:#1d232a;
     border:1px solid #2c343d;border-radius:12px;padding:12px 14px;margin-bottom:8px}
.mark{flex:none;width:22px;font-size:16px;text-align:center}
.what{font-weight:600;font-size:15px}
.why{color:#8d979f;font-size:12.5px;margin-top:2px;word-break:break-word}
.ok .mark{color:#7fe0b0}.no .mark{color:#ff9c8f}.hm .mark{color:#ffd27a}
button{width:100%;margin-top:10px;padding:14px;border-radius:12px;border:0;
       background:#2f6d8f;color:#fff;font-size:15px;font-weight:600;
       font-family:inherit}
button:disabled{background:#2c343d;color:#6d767e}
button.rec{background:#8f2f26}
.box{margin-top:12px;padding:14px;border-radius:12px;font-size:14px;
     background:#1d232a;border:1px solid #2c343d;word-break:break-word}
.box.good{background:#215843;border-color:#2f7d5f}
.box.bad{background:#5b241d;border-color:#8f2f26}
.heard{font-size:17px;color:#fff;margin-top:8px;min-height:24px}
b{color:#fff}
</style></head><body>

<h1>마이크가 열리는가 <span class="ver __CLS__">__MODE__</span></h1>
<p class=sub>폰 브라우저가 <b>마이크를 내주는지</b>, 그리고 내준다면
한국어를 알아듣는지 — 그것만 봅니다. 로봇은 상관 없습니다.
<b>http 와 https 를 둘 다 열어 견주세요.</b></p>

<h2>자리</h2>
<div id=where></div>

<h2>1 · 마이크를 달라고 해보기</h2>
<button id=ask>마이크 권한 받기</button>
<div class=box id=askr>아직 안 해봤습니다.</div>

<h2>2 · 브라우저가 직접 알아듣기</h2>
<p class=sub style="margin:0 0 8px">Web Speech API. 되면 제일 간단합니다.
<b>다만 인터넷을 쓸 수 있습니다</b> — 그건 아래에서 갈립니다.</p>
<button id=talk disabled>한국어로 말해보기</button>
<div class=box id=talkr>1번을 먼저 하세요.</div>
<div class=heard id=heard></div>

<h2>3 · 녹음해서 PC 로 보내기</h2>
<p class=sub style="margin:0 0 8px">이쪽이 낫습니다 — <b>마이크는 복도에,
인식기는 PC 에.</b> whisper 는 이미 돌고 있고 인터넷을 안 씁니다.
여기서는 <b>소리가 PC 까지 닿는지</b>만 봅니다.</p>
<button id=rec disabled>3초 녹음해서 보내기</button>
<div class=box id=recr>1번을 먼저 하세요.</div>
<div class=heard id=heard2></div>

<script>
function $(id){return document.getElementById(id);}
function row(what, mark, why){
  var cls = mark === '○' ? 'ok' : (mark === '★' ? 'hm' : 'no');
  return '<div class="row ' + cls + '"><div class=mark>' + mark +
         '</div><div><div class=what>' + what +
         '</div><div class=why>' + why + '</div></div></div>';
}
/* ★ 이름표가 아니라 자리를 받습니다 ★
   처음에는 say($('askr'), …) 로 이름표를 넘겼습니다. 그랬더니
   check_page() 가 askr·talkr·recr 을 "죽은 자리" 로 잡았습니다 —
   화면에는 있는데 스크립트가 $('askr') 로 안 부르니까요.
   검사기를 넓히는 대신 부르는 쪽을 맞췄습니다. 규칙이 하나면
   검사기가 계속 쓸모 있습니다. */
function say(e, cls, html){
  e.className = 'box' + (cls ? ' ' + cls : '');
  e.innerHTML = html;
}

/* ── 자리부터 ────────────────────────────────────────────
   여기가 이 페이지의 핵심입니다. isSecureContext 가 false 면
   아래 셋은 볼 것도 없이 다 막힙니다 — 그리고 브라우저는 그 까닭을
   안 알려줍니다. 그냥 "권한 거부" 처럼 보입니다.                */
var secure = window.isSecureContext;
var hasMedia = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
var hasRec = !!SR;
var isWV = / wv\\b/.test(navigator.userAgent) ||
           /; wv\\)/.test(navigator.userAgent);

var w = '';
w += row('안전한 자리인가', secure ? '○' : '×',
         'window.isSecureContext = <b>' + secure + '</b>' +
         (secure ? '' : ' — 여기서 막히면 마이크는 아예 안 열립니다') +
         '<br>' + location.origin);
w += row('마이크를 잡는 길이 있는가', hasMedia ? '○' : '×',
         'navigator.mediaDevices.getUserMedia');
w += row('브라우저에 인식기가 있는가', hasRec ? '○' : '×',
         'SpeechRecognition / webkitSpeechRecognition');
w += row(isWV ? '앱 안(WebView)입니다' : '진짜 브라우저입니다',
         isWV ? '★' : '○',
         (isWV ? 'WebView 는 인식기가 없을 수 있습니다. 그러면 2번이 ' +
                 '아니라 3번(또는 안드로이드 STT)으로 갑니다.'
               : '앱 안에서도 열어보고 견주세요.') +
         '<br>' + navigator.userAgent);
$('where').innerHTML = w;

/* ── 1. 마이크 권한 ─────────────────────────────────── */
var stream = null;
$('ask').onclick = function(){
  if (!hasMedia){
    say($('askr'),'bad','<b>잡는 길이 아예 없습니다.</b> 위의 "안전한 자리" ' +
        '칸을 보세요. http 로 열었다면 그게 까닭입니다.');
    return;
  }
  say($('askr'),'','묻는 중…');
  navigator.mediaDevices.getUserMedia({audio:true}).then(function(s){
    stream = s;
    var t = s.getAudioTracks()[0];
    say($('askr'),'good','<b>마이크가 열렸습니다.</b><br>' +
        (t ? t.label || '(이름 없음)' : ''));
    $('talk').disabled = !hasRec;
    $('rec').disabled = false;
    if (!hasRec) say($('talkr'),'bad','이 브라우저에는 인식기가 없습니다. 3번으로 가세요.');
    else say($('talkr'),'','눌러서 말해보세요.');
    say($('recr'),'','눌러서 3초 녹음해보세요.');
  }).catch(function(e){
    say($('askr'),'bad','<b>' + e.name + '</b><br>' + e.message +
        (secure ? '' : '<br><br>안전한 자리가 아니라서일 가능성이 큽니다. ' +
                       'https 쪽으로 열어 견주세요.'));
  });
};

/* ── 2. 브라우저가 직접 ─────────────────────────────── */
$('talk').onclick = function(){
  var r = new SR();
  r.lang = 'ko-KR';
  r.interimResults = true;
  r.continuous = false;
  var got = '';
  var online = navigator.onLine;
  say($('talkr'),'','듣는 중… 말해보세요.');
  $('heard').textContent = '';
  r.onresult = function(ev){
    got = '';
    for (var i = 0; i < ev.results.length; i++) got += ev.results[i][0].transcript;
    $('heard').textContent = got;
  };
  r.onerror = function(ev){
    say($('talkr'),'bad','<b>' + ev.error + '</b>' +
        (ev.error === 'network'
          ? '<br>인터넷이 필요한 인식기입니다. <b>전시장에서 못 씁니다.</b> 3번으로 가세요.'
          : ''));
  };
  r.onend = function(){
    if (got) say($('talkr'),'good','<b>알아들었습니다.</b><br>' +
                 '접속 상태: ' + (online ? '온라인' : '오프라인') +
                 ' — 오프라인에서도 됐다면 폰 안에서 한 것입니다.');
  };
  try { r.start(); } catch(e){ say($('talkr'),'bad', e.message); }
};

/* ── 3. 녹음해서 PC 로 ──────────────────────────────
   여기서는 **PC 까지 닿는지**만 봅니다. 알아듣는 것은 whisper 의
   일이고, 그건 이미 돌고 있습니다. 소리가 안 닿으면 알아들 것도
   없으니 순서가 이렇습니다.                                    */
$('rec').onclick = function(){
  if (!window.MediaRecorder){
    say($('recr'),'bad','MediaRecorder 가 없습니다.');
    return;
  }
  var mr, bits = [];
  try { mr = new MediaRecorder(stream); }
  catch(e){ say($('recr'),'bad', e.message); return; }
  mr.ondataavailable = function(e){ if (e.data.size) bits.push(e.data); };
  mr.onstop = function(){
    var blob = new Blob(bits, {type: mr.mimeType});
    say($('recr'),'','보내는 중… ' + Math.round(blob.size/1024) + ' KB');
    fetch('/heard', {method:'POST', body: blob,
                     headers:{'Content-Type': mr.mimeType || 'application/octet-stream'}})
      .then(function(r){ return r.json(); })
      .then(function(j){
        var head = '<b>PC 가 받았습니다.</b><br>' + j.bytes + ' 바이트 · ' + j.kind;
        if (j.error){
          say($('recr'),'bad', head + '<br><b>그런데 못 알아들었습니다.</b><br>' + j.error);
        } else if (typeof j.text === 'string'){
          /* 빈 문자열도 답입니다 — 닿았는데 아무 말도 안 들린 것.
             '못 보냈습니다' 와 섞이면 안 됩니다. */
          say($('recr'), j.text ? 'good' : 'bad',
              head + ' · ' + j.secs + '초');
          $('heard2').textContent = j.text || '(아무 말도 안 들렸습니다)';
        } else {
          say($('recr'),'good', head +
              '<br>알아듣는 것은 whisper 가 합니다 — 지금은 --whisper 없이 띄웠습니다.');
        }
      })
      .catch(function(e){ say($('recr'),'bad','못 보냈습니다 — ' + e.message); });
  };
  $('rec').className = 'rec';
  $('rec').textContent = '녹음 중… (3초)';
  mr.start();
  setTimeout(function(){
    mr.stop();
    $('rec').className = '';
    $('rec').textContent = '3초 녹음해서 보내기';
  }, 3000);
};
</script>
</body></html>
"""


def check_page():
    """화면이 이어져 있는지 봅니다 — 브라우저 없이.

    remote.py 의 check_page() 와 같은 뜻입니다. 거기서 두 번 당했습니다:
    버튼을 만들고 뜻을 안 붙였고, 스크립트를 통째로 안 넣었습니다.
    둘 다 "있는가" 는 통과하고 "이어져 있는가" 에서 틀렸습니다.
    """
    import re
    body = PAGE.split("<script>")[0]
    script = PAGE.split("<script>")[1].split("</script>")[0]
    bad = []

    ids = set(re.findall(r"id=([A-Za-z][\w-]*)", body))
    used = set(re.findall(r"\$\('([^']+)'\)", script))
    for u in sorted(used - ids):
        bad.append(f"스크립트가 찾는 '{u}' 가 화면에 없습니다")
    for b in sorted(ids - used):
        bad.append(f"화면의 '{b}' 를 스크립트가 안 씁니다 — 죽은 자리입니다")

    for btn in re.findall(r"<button[^>]*id=(\w+)", body):
        if f"$('{btn}').onclick" not in script:
            bad.append(f"'{btn}' 버튼에 뜻이 안 붙었습니다")

    for token in ("__MODE__", "__CLS__"):
        if token not in body:
            bad.append(f"{token} 자리가 없습니다 — 판수 딱지가 안 뜹니다")
    return bad


def decode_to_16k(raw):
    """폰이 보낸 소리 덩어리를 whisper 가 먹는 모양으로 바꿉니다.

    폰은 webm/opus 로 보냅니다 (측정: 3초에 24,804 바이트). whisper 는
    **16 kHz · 한 채널 · float32** 를 받습니다. 그 사이를 잇습니다.

    ★ 새 의존성은 없습니다 ★
      av (PyAV) 는 aiortc 가 이미 끌고 옵니다. ffmpeg 를 따로 부르지
      않는 이유는 윈도우에서 그게 있으리라는 보장이 없어서입니다.

    ★ 왜 함수로 떼어놨는가 ★
      whisper 없이도 이 부분만 시험할 수 있어야 합니다. 소리가 안
      들릴 때 "옮기다 틀렸나 알아듣다 틀렸나" 를 갈라야 하는데,
      한 덩어리로 붙어 있으면 못 가립니다. --selftest 가 이것만 봅니다.
    """
    import io
    import av
    import numpy as np

    with av.open(io.BytesIO(raw)) as box:
        if not box.streams.audio:
            raise ValueError("소리 갈래가 없습니다 — 빈 녹음이거나 딴 파일입니다")
        rs = av.audio.resampler.AudioResampler(
            format="flt", layout="mono", rate=16000)
        bits = []
        for frame in box.decode(audio=0):
            for out in rs.resample(frame):
                bits.append(out.to_ndarray().reshape(-1))
        for out in rs.resample(None):           # 남은 것을 마저 뱉게 합니다
            bits.append(out.to_ndarray().reshape(-1))
    if not bits:
        raise ValueError("소리가 한 조각도 안 나왔습니다")
    return np.concatenate(bits).astype("float32")


def selftest():
    """whisper 없이, 옮기는 부분만 봅니다.

    av 로 1초짜리 440 Hz 소리를 webm/opus 로 만들어서 (폰이 보내는
    것과 같은 모양), 도로 풀어보고 길이와 세기를 잽니다.
    """
    import io
    import math
    import av
    import numpy as np

    ok, bad = 0, []

    def check(what, got, want):
        nonlocal ok
        if got == want:
            print(f" ○ {what}")
            ok += 1
        else:
            print(f" ★ {what}\n   받은 것: {got}\n   바란 것: {want}")
            bad.append(what)

    # ── 폰이 보내는 것과 같은 모양을 하나 만듭니다 ──────────
    buf = io.BytesIO()
    with av.open(buf, mode="w", format="webm") as box:
        st = box.add_stream("libopus", rate=48000)
        st.layout = "mono"
        n, rate = 48000, 48000
        tone = np.array(
            [math.sin(2 * math.pi * 440 * i / rate) * 0.5 for i in range(n)],
            dtype="float32").reshape(1, -1)
        frame = av.AudioFrame.from_ndarray(tone, format="flt", layout="mono")
        frame.sample_rate = rate
        for pkt in st.encode(frame):
            box.mux(pkt)
        for pkt in st.encode(None):
            box.mux(pkt)
    raw = buf.getvalue()
    print(f" (시험용 소리 {len(raw)} 바이트를 만들었습니다)")

    got = decode_to_16k(raw)
    check("16 kHz 로 나옵니다", round(len(got) / 16000), 1)
    check("한 채널입니다", got.ndim, 1)
    check("소리가 담겨 있습니다", bool(float(np.abs(got).mean()) > 0.01), True)

    # ★ 빈 것과 쓰레기를 말없이 삼키면 안 됩니다 ★
    #   mic_test.py 가 "프레임은 오는데 소리가 안 담겨 있습니다" 를
    #   잡아낸 것과 같은 이유입니다. 0을 0으로 넘기면 whisper 는
    #   빈 문자열을 돌려주고, 우리는 왜인지 모릅니다.
    for what, blob in (("쓰레기", b"not audio at all"), ("빈 것", b"")):
        try:
            decode_to_16k(blob)
            check(f"{what}은 거절합니다" if what == "빈 것" else f"{what}를 거절합니다", "삼켰습니다", "거절합니다")
        except Exception:
            check(f"{what}은 거절합니다" if what == "빈 것" else f"{what}를 거절합니다", "거절합니다", "거절합니다")

    print()
    if bad:
        print("=" * 70)
        print(f" {len(bad)}가지가 틀렸습니다")
        return 1
    print("=" * 70)
    print(f" 모두 통과했습니다 ({ok}가지)")
    print(" 폰이 보내는 모양을 whisper 가 먹는 모양으로 옮길 수 있습니다.")
    return 0


class Ears:
    """whisper 를 게으르게 붙듭니다.

    모델을 올리는 데 몇십 초 듭니다. --whisper 로 띄웠을 때만, 그리고
    **첫 소리가 닿았을 때** 올립니다. 서버가 뜨자마자 올리면 폰을
    집어들기도 전에 기다리게 됩니다.
    """

    def __init__(self):
        self.listener = None

    def hear(self, raw):
        import stt
        if self.listener is None:
            print(" whisper 를 올립니다 (처음 한 번, 좀 걸립니다)…")
            self.listener = stt.Listener(verbose=False)
            self.listener.load_model()
            print(" 올렸습니다.")
        audio = decode_to_16k(raw)
        secs = len(audio) / 16000
        return self.listener.transcribe(audio), secs


class Handler(http.server.BaseHTTPRequestHandler):
    mode = "https"
    ears = None

    def log_message(self, fmt, *a):
        print(f" · {self.address_string()} {fmt % a}")

    def _send(self, code, kind, body):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/cert"):
            if not CERT.exists():
                self._send(404, "text/plain; charset=utf-8",
                           "인증서가 없습니다".encode())
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/x-pem-file")
            self.send_header("Content-Disposition",
                             'attachment; filename="webmic_cert.local.pem"')
            body = CERT.read_bytes()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        cls, label = ("s", "https · 안전한 자리") if self.mode == "https" \
            else ("p", "http · remote.py 와 같은 조건")
        page = PAGE.replace("__MODE__", label).replace("__CLS__", cls)
        self._send(200, "text/html; charset=utf-8", page.encode("utf-8"))

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        kind = self.headers.get("Content-Type") or "(모름)"
        print(f" ★ 소리가 닿았습니다 — {len(raw)} 바이트 · {kind}")
        out = {"bytes": len(raw), "kind": kind}

        if self.ears is not None:
            # ★ 여기서 넘어져도 폰에는 답을 줍니다 ★
            #   whisper 가 터졌을 때 폰 화면이 "못 보냈습니다" 로 뜨면,
            #   소리가 안 닿은 것과 구별이 안 됩니다. 닿은 것은 닿았다고
            #   말하고, 못 알아들은 것은 따로 말합니다.
            try:
                text, secs = self.ears.hear(raw)
                out["secs"] = round(secs, 1)
                out["text"] = text
                print(f"   {secs:.1f}초 → {text!r}")
            except Exception as e:
                out["error"] = f"{type(e).__name__}: {e}"
                print(f"   ★ 못 알아들었습니다 — {out['error']}")

        self._send(200, "application/json",
                   json.dumps(out, ensure_ascii=False).encode("utf-8"))


def main():
    ap = argparse.ArgumentParser(description="폰 브라우저가 마이크를 여는가")
    ap.add_argument("--plain", action="store_true",
                    help="http 로 띄웁니다 (remote.py 와 같은 조건)")
    ap.add_argument("--check", action="store_true",
                    help="화면이 이어져 있는지만 보고 끝냅니다")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--whisper", action="store_true",
                    help="닿은 소리를 whisper 로 옮겨 폰에 돌려줍니다")
    ap.add_argument("--selftest", action="store_true",
                    help="whisper 없이 옮기는 부분만 시험합니다")
    args = ap.parse_args()

    if args.selftest:
        print("=" * 70)
        print(" 폰이 보낸 모양을 whisper 가 먹는 모양으로 옮기는가")
        print("=" * 70)
        return selftest()

    bad = check_page()
    if bad:
        print("=" * 70)
        print(" 화면이 이어져 있지 않습니다")
        print("=" * 70)
        for b in bad:
            print(f" ★ {b}")
        return 1
    if args.check:
        print(" ○ 화면은 이어져 있습니다. 버튼마다 뜻이 붙어 있습니다.")
        return 0

    ip = lan_ip()
    mode = "plain" if args.plain else "https"
    port = args.port or (PORT_PLAIN if args.plain else PORT_HTTPS)
    Handler.mode = mode
    if args.whisper:
        Handler.ears = Ears()

    srv = http.server.ThreadingHTTPServer(("0.0.0.0", port), Handler)
    scheme = "http"
    if mode == "https":
        if not cert_ok_for(ip):
            print(f" 인증서를 만듭니다 ({ip} 앞으로, 30일)…")
            make_cert(ip)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        scheme = "https"

    print("=" * 70)
    print(" 마이크가 열리는가")
    print("=" * 70)
    print(f"  폰으로 여세요 →  {scheme}://{ip}:{port}/")
    print()
    if mode == "https":
        print("  ※ '안전하지 않습니다' 경고가 뜹니다. 스스로 만든 인증서라")
        print("    그렇습니다. 고급 → 계속 을 누르세요.")
        print(CERT_NOTE.format(ip=ip, plain=PORT_PLAIN))
    else:
        print("  ※ 이쪽은 http 입니다 — remote.py 와 같은 조건입니다.")
        print("    '안전한 자리' 칸이 false 로 나오면, 그게 답입니다.")
    print()
    if args.whisper:
        print("  ★ 3번으로 보낸 소리를 whisper 가 옮겨 폰 화면에 돌려줍니다.")
        print("    모델은 첫 소리가 닿을 때 올립니다 — 그때 한 번 오래 걸립니다.")
        print()
    print("  두 쪽을 다 열어 견주세요. 끝내려면 Ctrl+C.")
    print()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n 닫습니다.")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
