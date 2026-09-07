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


PAGE = """<!doctype html><html lang=ko><head>
<meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name=theme-color content="#14181d">
<title>안내 리모컨</title>
<style>
:root{color-scheme:dark;--bg:#14181d;--card:#1d232a;--line:#2c343d;--ink:#e8edf1;
      --dim:#8d979f;--go:#2f7d5f;--go2:#256549;--again:#39444e;--stop:#8f2f26}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent;
   -webkit-user-select:none;user-select:none;touch-action:manipulation}
body{margin:0;background:var(--bg);color:var(--ink);
     font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo","Malgun Gothic",sans-serif;
     display:flex;flex-direction:column;min-height:100dvh;padding:env(safe-area-inset-top) 14px env(safe-area-inset-bottom)}
header{padding:16px 4px 12px;display:flex;align-items:center;gap:10px}
#burger{margin-left:auto;background:transparent;border:0;color:var(--ink);
        font-size:22px;line-height:1;padding:6px 10px;width:auto;margin:0;border-radius:10px}
#burger:active{background:var(--card)}
#veil{position:fixed;inset:0;background:rgba(0,0,0,.55);opacity:0;pointer-events:none;
      transition:opacity .18s;z-index:9}
#veil.on{opacity:1;pointer-events:auto}
#menu{position:fixed;left:0;right:0;bottom:0;z-index:10;background:var(--card);
      border-top:1px solid var(--line);border-radius:18px 18px 0 0;
      padding:10px 14px calc(18px + env(safe-area-inset-bottom));
      transform:translateY(102%);transition:transform .22s ease;max-height:88dvh;overflow:auto}
#menu.on{transform:none}
#grip{width:38px;height:4px;border-radius:2px;background:var(--line);margin:6px auto 12px}
.mh{font-size:11px;letter-spacing:.12em;color:var(--dim);text-transform:uppercase;
    margin:14px 4px 8px}
.mrow{display:flex;gap:8px}
.mrow button,.mfull{background:var(--again);font-size:16px;padding:16px 6px;margin-bottom:8px;
                    width:100%;border:0;border-radius:12px;color:#fff;font-weight:600;
                    font-family:inherit}
.mfull{text-align:left;padding-left:18px}
.mfull .st{float:right;font-weight:400;color:var(--dim);font-size:14px}
.mfull.on{background:var(--go)}
.mfull.on .st{color:#cfe9de}
.danger{background:var(--stop)!important}
/* 코스 목록 — 한 줄이 아니라 한 칸입니다. 고르는 데 쓰는 것을 다 적습니다 */
.course{display:block;width:100%;text-align:left;background:var(--again);border:0;
        border-radius:12px;padding:14px 16px;margin-bottom:8px;color:#fff;
        font-family:inherit;font-size:15px;line-height:1.5}
.course.on{background:var(--go)}
.course:disabled{opacity:1}                 /* 지금 코스는 흐려지지 않습니다 */
.course.on:disabled{opacity:1}
.course:disabled:not(.on){opacity:.4}       /* 안내 중이라 못 고르는 것만 흐리게 */
.cname{font-weight:600;font-size:16px}
.ctag{float:right;font-weight:400;font-size:12px;color:var(--dim)}
.course.on .ctag{color:#cfe9de}
.cfacts{font-size:13px;color:#cbd5db;margin-top:5px;font-variant-numeric:tabular-nums}
.course.on .cfacts{color:#dff0e8}
.croute{font-size:12px;color:var(--dim);margin-top:3px}
.csub{font-size:12px;color:var(--dim);margin-top:5px;line-height:1.5}
.course.on .croute,.course.on .csub{color:#a9cfbf}
/* 음량 — 가운데는 버튼이 아니라 지금 값을 보여주는 자리입니다 */
.vol{display:flex;align-items:center;justify-content:center;background:var(--bg);
     border-radius:12px;min-width:96px;margin-bottom:8px;font-weight:600;
     font-size:15px;letter-spacing:.02em}
.vol b{font-size:22px;margin-right:3px}
.hint{font-size:12px;color:var(--dim);line-height:1.55;margin:2px 4px 10px}
.hint code{background:var(--bg);padding:1px 5px;border-radius:4px;font-size:11px}
h1{font-size:15px;margin:0;font-weight:600;letter-spacing:-.01em}
#dot{width:9px;height:9px;border-radius:50%;background:var(--dim);flex:none}
#dot.on{background:#43c98a}
#dot.off{background:#c9584b}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:12px}
.k{font-size:11px;letter-spacing:.12em;color:var(--dim);text-transform:uppercase;margin-bottom:8px}
#sid{font-size:13px;color:var(--dim);font-variant-numeric:tabular-nums}
#place{font-size:26px;font-weight:600;margin:2px 0 0;line-height:1.3}
#detail{font-size:14px;color:var(--dim);margin-top:10px;line-height:1.55}
#prog{display:flex;gap:5px;margin-top:16px}
#prog i{flex:1;height:4px;border-radius:2px;background:var(--line)}
#prog i.done{background:var(--go)}
#prog i.now{background:var(--ink)}
.spacer{flex:1}

/* ── 조종판 ──
   drive.py 의 키 배치를 그대로 땄습니다. QWE / ASD 가 마침 키보드에서도
   그 모양이라, 화면과 키보드와 문서가 전부 같은 그림이 됩니다.
       Q W E    게걸음← · 앞으로 · 게걸음→
       A S D    좌회전  · 뒤로   · 우회전
       Space    즉시 정지
   지금은 껍데기입니다. 눌러도 아무 일도 일어나지 않습니다 — 그렇게
   보이도록 흐리게 두었습니다. 되는 것처럼 보이는 버튼이 제일 나쁩니다. */
#pad{margin:6px 0 4px}
#pad.off{opacity:.35}
.pk{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-bottom:7px}
.key{background:var(--card);border:1px solid var(--line);border-radius:11px;
     padding:12px 4px 9px;text-align:center;color:var(--ink);width:100%;
     font-family:inherit;margin:0;font-size:inherit;font-weight:400;
     display:flex;flex-direction:column;align-items:center;gap:3px;
     transition:background .08s}
.key:disabled{opacity:.45}
.key.hot{background:var(--go);border-color:var(--go)}
.key.hot .n,.key.hot .c{color:#d9efe6}
.key .g{font-size:21px;line-height:1}
.key .n{font-size:10.5px;color:var(--dim);letter-spacing:.02em}
.key .c{position:absolute;margin:-10px 0 0 -34px;font-size:9px;color:var(--dim);
        opacity:.75;font-weight:600}
.key.wide{grid-column:1/-1;flex-direction:row;justify-content:center;gap:8px;padding:11px}
.key.wide .g{font-size:14px}
#padnote{font-size:11.5px;color:var(--dim);text-align:center;margin:2px 0 12px}
button{width:100%;border:0;border-radius:14px;color:#fff;font-size:19px;font-weight:600;
       font-family:inherit;padding:22px;margin-bottom:10px;transition:transform .06s,background .15s}
button:active{transform:scale(.985)}
button:disabled{opacity:.4}
#go{background:var(--go);font-size:24px;padding:30px}
#go:active{background:var(--go2)}
#go.busy{background:var(--again)}
.row{display:flex;gap:8px}
.row button{margin-bottom:10px;font-size:15px;padding:16px 6px}
#again,#restart{background:var(--again)}
#stop{background:var(--stop)}
#end{background:transparent;border:1px solid var(--line);color:var(--dim);
     font-size:14px;font-weight:500;padding:13px;margin-bottom:4px}
#msg{text-align:center;font-size:13px;color:var(--dim);min-height:20px;padding-bottom:10px}
#lock{font-size:11px;color:var(--dim);opacity:.7}
@media(prefers-reduced-motion:reduce){button{transition:none}}
</style></head><body>
<header><span id=dot></span><h1>안내 리모컨</h1><span id=lock></span>
  <button id=burger aria-label=메뉴>☰</button></header>

<div id=veil></div>
<div id=menu>
  <div id=grip></div>

  <div class=mh>안내 코스</div>
  <div id=courses></div>
  <p class=hint id=coursehint></p>

  <div class=mh>자세</div>
  <div class=mrow>
    <button class=legs data-job=stand>일어서기</button>
    <button class=legs data-job=sit>앉기</button>
    <button class=legs data-job=lie>엎드리기</button>
  </div>
  <p class=hint id=legshint></p>

  <div class=mh>안내 음량</div>
  <div class=mrow>
    <button data-job=vol_down>줄이기 −</button>
    <div class=vol id=volst>—</div>
    <button data-job=vol_up>키우기 +</button>
  </div>
  <p class=hint>로봇 스피커의 음량입니다. 설명 도중에도 바꿉니다 —
     복도가 울리거나 방문객이 많을 때 바로 고칠 수 있어야 합니다.</p>

  <div class=mh>전방 라이트</div>
  <div class=mrow>
    <button data-job=light_on>켜기</button>
    <button data-job=light_off>끄기</button>
  </div>
  <p class=hint>라이트는 설명 중에도 됩니다 — 다리를 쓰지 않습니다.</p>

  <div class=mh>음성 인식</div>
  <button class=mfull id=mic data-job=mic><span class=st id=micst>꺼짐</span>음성 인식</button>
  <p class=hint id=michint></p>

  <div class=mh>끝내기</div>
  <button class="mfull danger" id=endm>프로그램 종료</button>
  <p class=hint>로봇을 정리하고 PC 의 프로그램이 끝납니다.
     다시 하려면 PC 에서 실행해야 합니다.</p>
</div>

<div class=card>
  <div class=k>지금</div>
  <div id=sid>연결 중…</div>
  <div id=place>—</div>
  <div id=detail></div>
  <div id=prog></div>
</div>

<div class=spacer></div>

<div id=pad>
  <div class=pk>
    <button class=key data-k=q><span class=c>Q</span><span class=g>⇦</span><span class=n>게걸음 왼쪽</span></button>
    <button class=key data-k=w><span class=c>W</span><span class=g>▲</span><span class=n>앞으로</span></button>
    <button class=key data-k=e><span class=c>E</span><span class=g>⇨</span><span class=n>게걸음 오른쪽</span></button>
  </div>
  <div class=pk>
    <button class=key data-k=a><span class=c>A</span><span class=g>↺</span><span class=n>좌회전</span></button>
    <button class=key data-k=s><span class=c>S</span><span class=g>▼</span><span class=n>뒤로</span></button>
    <button class=key data-k=d><span class=c>D</span><span class=g>↻</span><span class=n>우회전</span></button>
  </div>
  <p id=padnote>누르고 있는 동안 갑니다. 손을 떼면 멈춥니다.</p>
</div>

<button id=go disabled>다음</button>
<div class=row>
  <button id=again disabled>다시</button>
  <button id=restart disabled>처음부터</button>
  <button id=stop>멈춤</button>
</div>

<div id=msg></div>

<script>
const $=i=>document.getElementById(i);
let miss=0;

/* ★ 화면이 꺼지면 안내가 멈춥니다 ★
   정차 지점 하나가 30초, 이동까지 하면 1분이 넘습니다. 그 사이에
   화면이 꺼지면 다음 지점에서 잠금을 풀고 다시 켜야 합니다 —
   방문객 앞에서요. 화면 꺼짐 막기를 요청해 둡니다.
   (안 되는 기기도 있습니다. 그러면 조용히 넘어가고, 대신 설정에서
    화면 자동 꺼짐을 길게 해두시면 됩니다) */
let wake=null;
async function hold(){
  try{
    if('wakeLock' in navigator && (!wake || wake.released)){
      wake = await navigator.wakeLock.request('screen');
      wake.addEventListener('release',()=>{ $('lock').textContent=''; });
      $('lock').textContent='화면 유지';
    }
  }catch(e){ $('lock').textContent=''; }
}
/* 다른 앱에 갔다 돌아오면 잠금이 풀려 있습니다 — 다시 잡습니다 */
document.addEventListener('visibilitychange',()=>{ if(!document.hidden) hold(); });
document.addEventListener('click',hold,{once:false});
hold();
async function hit(p){
  try{ await fetch(p,{method:'POST'}); $('msg').textContent=''; }
  catch(e){ $('msg').textContent='PC 에 닿지 않습니다'; }
  poll();
}
/* ★ 버튼 하나에 뜻 하나 ★
   '다시' 가 안내 중에는 '이 설명 한 번 더', 끝에서는 '마지막 인사 한 번 더'
   였고, '처음부터' 는 큰 버튼이 끝에서만 바뀌는 형태였습니다. 복도에서
   한 손으로 누르는 사람에게 그건 외울 것이 늘어나는 일입니다.
   이제 자리가 고정입니다 — 같은 버튼은 언제나 같은 뜻입니다. */
$('go').onclick     =()=>hit('/go');
$('again').onclick  =()=>hit('/again');
$('restart').onclick=()=>{ if(confirm('처음부터 다시 안내합니까?')) hit('/restart'); };
/* ★ '멈춤' 에는 확인을 붙이지 않습니다 ★
   방문객이 말을 걸었거나 누가 지나갈 때 누르는 버튼입니다. 확인창이
   곧 지연입니다 — 물어보는 동안 설명이 계속 나옵니다. 되돌릴 수 있는
   일이라 확인이 필요 없기도 합니다. 확인은 되돌릴 수 없는 쪽에만. */

/* ── 메뉴 ── */
const menu=$('menu'), veil=$('veil');
function sheet(on){ menu.classList.toggle('on',on); veil.classList.toggle('on',on); }
$('burger').onclick=()=>sheet(!menu.classList.contains('on'));
veil.onclick=()=>sheet(false);
/* ── 조종판 ──
   ★ 누르고 있는 동안 '아직 누르고 있다' 를 계속 보냅니다 ★
     한 번만 보내면, 손 뗀 신호를 놓쳤을 때 로봇이 계속 갑니다.
     계속 보내면, 무엇이 끊기든 로봇은 멈춥니다. 놓쳐서 멈추는 것은
     안전하고 놓쳐서 계속 가는 것은 아닙니다. */
/* ★ 손가락은 버튼 밖으로 나갑니다 ★
     touchstart 를 버튼에 걸고 touchend 도 버튼에 걸었더니, 누른 채로
     손가락을 밖으로 빼면 **눌린 채로 남았습니다.** 터치는 처음 닿은
     요소가 계속 붙잡고 있어서 mouseleave 같은 것이 안 옵니다.
     그래서 **놓는 것은 창 전체**에서 받습니다. 손가락이 어디서 떨어지든
     창은 그것을 봅니다. 누르는 것만 버튼에서 받습니다.

   ★ 그리고 심장박동이 겹치면 안 됩니다 ★
     120ms 마다 보내는데 한 번이 그보다 오래 걸리면 요청이 쌓입니다.
     쌓이면 느려지고, 느려지면 더 쌓입니다. 앞의 것이 안 끝났으면
     이번 것은 거릅니다 — 거른 것이 쌓이면 DEADMAN 이 알아서 멈춥니다. */
/* ★ 손가락 하나가 아니라 여럿입니다 ★
     예전에는 눌린 키를 holding 하나에 담았습니다. 그래서 앞으로
     가면서 도는 것이 안 됐습니다 — 두 번째 손가락이 첫 번째를
     밀어냈습니다. 진짜 컨트롤러는 그렇지 않습니다.

     이제 **손가락(pointerId)마다** 어느 키를 짚고 있는지 적어둡니다.
     한 손가락이 떨어져도 다른 손가락은 그대로입니다. 보낼 때는
     눌린 키를 다 붙여서 보냅니다 ("wa" = 앞으로 + 좌회전).

   ★ 놓친 손가락에 대비합니다 ★
     떼는 신호를 놓치면 로봇이 계속 갑니다. 심장박동은 화면이
     보내는 것이라 DEADMAN 도 안 도와줍니다. 그래서 한 키를
     30초 넘게 붙들고 있으면 화면이 스스로 놓습니다. 이 복도에서
     제일 긴 구간이 3.6 m 니까, 30초는 정상적인 주행이 아닙니다. */
const NAMES={w:'앞으로',s:'뒤로',q:'게걸음 왼쪽',e:'게걸음 오른쪽',
             a:'좌회전',d:'우회전'};
let held=new Map();        /* 손가락 → 키 */
let since=new Map();       /* 키 → 처음 눌린 시각 */
let beat=null, inflight=false, sent=0, lost=0, rtt=0;
const HOLD_MAX=30000;

function combo(){ return [...new Set(held.values())].sort().join(''); }

function send(){
  if(inflight) return;                    /* 앞의 것이 아직 안 끝났습니다 */
  inflight=true; const t0=performance.now();
  fetch('/drive/'+(combo()||'-'),{method:'POST'})
    .then(()=>{ sent++; rtt=Math.round(performance.now()-t0); })
    .catch(()=>{ lost++; })
    .finally(()=>{ inflight=false; });
}
function paint(){
  const on=new Set(held.values());
  document.querySelectorAll('[data-k]').forEach(b=>{
    b.classList.toggle('hot', on.has(b.dataset.k));
  });
}
function grab(id,k){
  if(held.get(id)===k) return;
  if(held.size===0){ sent=0; lost=0; }
  held.set(id,k);
  if(!since.has(k)) since.set(k,performance.now());
  paint();
  send();
  if(!beat) beat=setInterval(()=>{
    /* 너무 오래 붙들고 있는 키는 놓습니다 */
    const now=performance.now();
    for(const [i,k2] of [...held]){
      if(now-(since.get(k2)||now) > HOLD_MAX) held.delete(i);
    }
    if(held.size===0){ release(); return; }
    send();
  },120);
}
function drop(id){
  if(!held.has(id)) return;
  const k=held.get(id);
  held.delete(id);
  if(![...held.values()].includes(k)) since.delete(k);
  paint();
  if(held.size===0) release(); else send();
}
function release(){
  if(beat){ clearInterval(beat); beat=null; }
  held.clear(); since.clear();
  inflight=false;
  paint();
  fetch('/drive/-',{method:'POST'}).catch(()=>{});
}
document.querySelectorAll('[data-k]').forEach(b=>{
  b.addEventListener('pointerdown', e=>{
    if(b.disabled) return;
    e.preventDefault();
    try{ b.setPointerCapture(e.pointerId); }catch(_){}   /* 이 손가락을 끝까지 */
    grab(e.pointerId,b.dataset.k);
  });
  b.addEventListener('lostpointercapture', e=>drop(e.pointerId));
});
/* 놓는 것은 창 전체에서 — 버튼 밖에서 떨어져도, 전화가 와도.
   손가락마다 따로 놓습니다: 한 손가락이 떨어져도 나머지는 그대로. */
['pointerup','pointercancel'].forEach(ev=>
  window.addEventListener(ev, e=>drop(e.pointerId)));
/* 화면을 벗어나는 일은 통째로 놓습니다 — 어느 손가락인지 알 수 없습니다 */
document.addEventListener('visibilitychange',()=>{ if(document.hidden) release(); });
window.addEventListener('blur',release);
window.addEventListener('pagehide',release);

document.querySelectorAll('[data-job]').forEach(b=>{
  /* 메뉴를 닫지 않는 것들 — 잇달아 누르는 버튼입니다 */
  const STAY=['mic','vol_up','vol_down'];
  b.onclick=()=>{ hit('/job/'+b.dataset.job);
                  if(!STAY.includes(b.dataset.job)) sheet(false); };
});
$('endm').onclick=()=>{
  if(confirm('프로그램을 종료합니까? 로봇을 정리하고 PC 의 프로그램이 끝납니다.')){
    sheet(false); hit('/end');
  }
};
/* ★ '멈춤' 에는 확인을 붙이지 않습니다 ★
   방문객이 말을 걸었거나 누가 지나갈 때 누르는 버튼입니다. 지금 하는
   설명만 끊고 그 자리에 섭니다. 한 번 더 물어보면 그 사이에 설명이
   계속 나옵니다 — 확인창이 곧 지연입니다.
   되돌릴 수 있는 일이라 확인이 필요 없기도 합니다 ('다음' 이나 '다시'
   를 누르면 이어집니다). 확인은 되돌릴 수 없는 쪽에만 붙입니다. */
$('stop').onclick   =()=>hit('/stop');
/* ★ 코스 목록은 PC 가 정합니다 ★
   화면에 코스를 적어두면 courses.py 와 두 벌이 되고, 언젠가 한쪽만
   고쳐집니다. 여기는 온 대로 그립니다.
   ※ 0.6초마다 다시 그리면 누르는 순간 버튼이 갈립니다. 달라졌을
     때만 그립니다. */
/* ★ 목록은 접어둡니다 — 평소에는 지금 코스 한 칸만 ★
   코스가 넷만 되어도 메뉴 아래쪽 절반이 코스로 덮입니다. 자세도,
   음량도, 라이트도 화면 밖으로 밀려납니다. 복도에서 한 손으로
   쓰는 화면에서 스크롤이 늘어나는 것은 그 자체로 비용입니다.

   그래서 평소에는 **지금 하는 코스 한 칸**만 둡니다. 그것을 누르면
   저장된 것이 모두 펼쳐집니다. 하나를 고르면 다시 접힙니다.

   ※ 코스가 하나뿐이거나 안내 중일 때는 펼칠 것도, 고를 것도
     없으므로 누르는 시늉을 하지 않습니다. 눌러보고 아는 것보다
     안 눌리는 편이 낫습니다. */
let courseSig='', courseOpen=false, lastState=null;

function toggleCourses(){
  courseOpen = !courseOpen;
  courseSig = '';                     /* 다시 그리게 합니다 */
  if(lastState) drawCourses(lastState);
}

function courseCard(c, cur, lock, expandable){
  const me = c.id===cur;
  const b=document.createElement('button');
  b.className='course'+(me?' on':'');
  /* 지금 코스는 '펼치기' 로 눌립니다. 나머지는 '고르기' 로. */
  b.disabled = me ? !expandable : lock;

  const head=document.createElement('div');
  head.className='cname';
  head.textContent=c.name;
  const tag=document.createElement('span');
  tag.className='ctag';
  if(me) tag.textContent = expandable ? (courseOpen?'접기 ▴':'바꾸기 ▾') : '지금 이것';
  else   tag.textContent = lock ? '' : '고르기';
  head.appendChild(tag);
  b.appendChild(head);

  [['cfacts',c.facts],['croute',c.route],['csub',c.subtitle]].forEach(([k,v])=>{
    if(!v) return;
    const d=document.createElement('div'); d.className=k; d.textContent=v;
    b.appendChild(d);
  });

  b.onclick = me ? toggleCourses
                 : ()=>{ courseOpen=false; hit('/course/'+c.id); sheet(false); };
  return b;
}

function drawCourses(s){
  lastState = s;
  const list=s.courses||[], cur=(s.course||{}).id||'', lock=!s.can_pick;
  const others = list.filter(c=>c.id!==cur);
  const expandable = !lock && others.length>0;
  if(!expandable) courseOpen=false;       /* 펼쳐둔 채로 잠기면 접습니다 */

  const sig=JSON.stringify([list,cur,lock,courseOpen]);
  if(sig===courseSig) return;
  courseSig=sig;

  const box=$('courses');
  box.innerHTML='';
  /* ★ 한 칸에 고를 만큼을 적습니다 ★
     이름만 적혀 있으면 "이 무리에겐 어느 코스?" 를 못 정합니다.
     정하는 데 쓰는 것은 몇 분 걸리고 어디를 도는지입니다. */
  const now = list.filter(c=>c.id===cur);
  /* 지금 코스를 모르는 동안(올리는 중)에는 있는 대로 다 보여줍니다 */
  (now.length ? now : list).forEach(c=>
    box.appendChild(courseCard(c, cur, lock, expandable)));
  if(courseOpen) others.forEach(c=>
    box.appendChild(courseCard(c, cur, lock, expandable)));

  $('coursehint').textContent = lock
    ? '안내 중에는 코스를 바꾸지 않습니다. 준비 화면이나 끝 화면에서 고르세요.'
    : (!others.length
        ? '아직 코스가 하나입니다. course_example.py 를 복사해서 만듭니다.'
        : courseOpen
          ? '시간은 멘트와 쉼만 더한 것입니다 — 걷는 시간은 사람에게 달렸으니 '
            + '빠졌습니다. 고르면 그 코스의 멘트를 로봇에 올립니다.'
          : '누르면 저장된 코스 ' + list.length + '개가 모두 뜹니다.');
}
/* ★ '못 닿았다' 와 '그리다 터졌다' 를 갈라놓습니다 ★
   둘을 한 catch 로 묶어놨다가 하루를 날렸습니다. 화면을 그리는 코드가
   첫 줄에서 터졌는데, 잡아서 '못 닿았다' 로 셌습니다. 초록 점은 멀쩡히
   켜져 있고, 코스 목록도 음량도 그냥 비어 있었습니다 — 아무 데도
   오류가 안 보였습니다.

   가져오는 것과 그리는 것은 다른 일입니다. 다르게 잡습니다. */
async function poll(){
  let s;
  try{
    const r=await fetch('/state',{cache:'no-store'});
    s=await r.json();
  }catch(e){
    if(++miss>2){ $('dot').className='off'; $('msg').textContent='PC 에 닿지 않습니다'; }
    return;
  }
  miss=0; $('dot').className='on';
  try{
    $('sid').textContent = s.done ? '끝' : (s.sid||'—');
    $('place').textContent = s.place||'—';
    $('detail').textContent = s.detail||'';
    /* 설명·동작 중에는 눌러도 소용이 없습니다. 눌러봐야 아는 것보다
       눌리지 않는 편이 낫습니다. '멈춤' 만 언제나 살아 있습니다. */
    $('go').disabled = !s.waiting;
    $('again').disabled = !s.waiting;
    $('restart').disabled = !s.waiting;
    /* ★ '멈춤' 은 반대입니다 — 하는 것이 있을 때만 삽니다 ★
       기다리는 자리에서는 끊을 것이 없습니다. 그런데 눌리기는 했고,
       PC 는 그것을 '이 구간을 다시' 로 읽어 180도를 다시 돌았습니다.
       PC 쪽에서 막았고, 여기서도 눌리지 않게 합니다 — 눌러보고 아는
       것보다 안 눌리는 편이 낫습니다. ('안내 종료' 는 메뉴 안에
       언제나 살아 있습니다) */
    $('stop').disabled = !!s.waiting;
    /* ★ 다리를 쓰는 메뉴는 설명 중에 잠급니다 ★
       메뉴 자체는 그대로 열립니다 — 라이트도, 음성 인식도, 만일을
       위한 '프로그램 종료' 도 언제든 됩니다. 잠그는 것은 **다리를
       쓰는 세 개**뿐입니다. 설명하고 있는데 옆에서 앉혀버리면
       방문객 앞에서 말과 몸이 따로 놉니다. */
    document.querySelectorAll('.legs').forEach(b=>{ b.disabled = !s.waiting; });
    $('legshint').textContent = s.waiting
      ? '지금은 됩니다.'
      : '설명·회전 중에는 잠급니다. 먼저 멈춤을 누르세요.';
    /* 조종판은 버튼과 같은 규칙입니다 — 설명·동작 중에는 못 몹니다.
       그때 몰면 로봇이 자기 회전과 우리 조종을 동시에 받습니다. */
    $('pad').classList.toggle('off', !s.waiting);
    if(!s.waiting && held.size) release();
    /* ★ 누르고 있는 버튼은 건드리지 않습니다 ★
       disabled 를 다시 매기면 브라우저가 그 손가락을 놓아버립니다.
       그러면 한 번 보내고 끝나는 것처럼 보입니다.
       (이제 손가락이 여럿이라 눌린 키가 여럿일 수 있습니다) */
    const on=new Set(held.values());
    document.querySelectorAll('[data-k]').forEach(b=>{
      if(on.has(b.dataset.k)) return;
      b.disabled = !s.waiting;
    });
    $('padnote').textContent = !s.waiting
      ? '설명 중에는 못 몹니다. 몰려면 먼저 멈춤.'
      : (held.size
          ? [...on].map(k=>NAMES[k]||k).join(' + ')
            + ' · 신호 '+sent+'회 · 왕복 '+rtt+'ms'+(lost?' · 놓침 '+lost:'')
          : '누르고 있는 동안 갑니다. 두 개를 같이 눌러도 됩니다.');
    $('go').className = s.waiting ? '' : 'busy';
    $('go').textContent = s.waiting ? (s.button||'다음') : '진행 중…';
    const p=$('prog');
    if(p.children.length!==s.total){
      p.innerHTML=''; for(let i=0;i<s.total;i++) p.appendChild(document.createElement('i'));
    }
    [...p.children].forEach((el,i)=>{ el.className = i<s.index?'done':(i===s.index?'now':''); });
    drawCourses(s);
    const f=s.flags||{};
    /* 음량 — 아직 못 읽었으면 '—' 입니다. 짐작해서 숫자를 쓰지 않습니다 */
    $('volst').innerHTML = (f.volume===null||f.volume===undefined)
      ? '—' : '<b>'+f.volume+'</b>/10';
    /* ★ 이름을 조종판의 held 와 겹치지 않게 씁니다 ★
       여기 있던 `const held` 하나가 poll() 전체를 죽였습니다.
       let/const 는 함수 맨 위로 끌어올려져 그때까지 못 쓰는 상태가
       되므로, **아래에 있는 이 한 줄 때문에 위쪽의 held 가 전부**
       "Cannot access 'held' before initialization" 이 됐습니다.
       코스 목록도 음량도 그래서 안 그려졌습니다. 화면에는 초록 점만
       멀쩡히 켜져 있었고요 — catch 가 삼켰습니다. */
    const micHeld = f.mic==='held';
    /* ★ 음성 인식도 다리 쓰는 것과 같은 규칙입니다 ★
       로봇이 말하는 동안 켜면 자기 말을 듣습니다. 그래서 기다릴
       때만 켜고 끕니다. 켜둔 채로 안내가 시작되면 PC 쪽에서
       마이크를 잠시 막습니다 — 그때 '잠깐 멈춤' 으로 뜹니다. */
    $('mic').disabled = micHeld || !s.waiting;
    $('micst').textContent = micHeld ? '보류'
      : ({on:'켜짐', deaf:'잠깐 멈춤', loading:'모델 읽는 중…',
          off:'꺼짐'}[f.mic]||'꺼짐');
    $('mic').classList.toggle('on', f.mic==='on'||f.mic==='deaf');
    $('michint').innerHTML = micHeld
      ? 'PC 에서 <code>--no-ears</code> 로 잠가뒀습니다. 그 옵션을 빼면 열립니다.'
      : (f.mic==='deaf'
          ? '지금은 <b>귀를 막고</b> 있습니다 — 로봇이 말하거나 도는 동안에는 '
            + '자기 목소리를 듣게 되어서요. 기다리는 자리로 오면 다시 듣습니다.'
          : '★ 마이크는 <b>PC</b> 에 있습니다 ★ 복도에서 말해도 안 들립니다. '
            + 'PC 옆에 사람이 있을 때 쓰세요. 켜면 "앉아 · 일어서 · 불 켜" 같은 '
            + '말을 듣고, <b>"다음"</b> 이라고 하면 안내를 넘깁니다. '
            + '설명 중에는 켜고 끄지 못합니다.');
  }catch(e){
    /* 여기까지 왔다는 것은 PC 와는 잘 통했다는 뜻입니다. 그리는
       코드가 터진 것이고, 그건 우리 잘못입니다. 숨기지 않습니다. */
    $('dot').className='off';
    $('msg').textContent='화면 오류 — '+e;
  }
}
poll(); setInterval(poll,600);
</script></body></html>"""


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
        self.server = None
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
                                "volume": None}}
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
                try:
                    method, path, _ = line.decode("latin-1").split(" ", 2)
                except ValueError:
                    break
                # 헤더는 버립니다 (본문 없는 요청만 받습니다)
                try:
                    while True:
                        h = await asyncio.wait_for(reader.readline(), 5.0)
                        if h in (b"\r\n", b"\n", b""):
                            break
                except Exception:
                    break

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
        return url

    async def close(self):
        if self.server:
            self.server.close()
            try:
                await self.server.wait_closed()
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
