/*
  시그널링 다리 — 화면 쪽 절반.

  앱의 app.handshake() 는 답을 바로 안 줍니다. 배경 스레드로 가서
  일하고, 끝나면 window.__sigDone 을 부릅니다 (그래야 악수하는 8초
  동안 화면이 안 멈춥니다). 여기서 그걸 약속(Promise)으로 감싸서,
  부르는 쪽은 그냥 이렇게 쓰면 되게 합니다.

      const answer = await handshake('192.168.0.51', 9991, offer, key);

  ※ 이 파일은 앱 안에서만 뜻이 있습니다. PC 브라우저로 같은 페이지를
    열면 app 이 없으니 곧바로 "앱이 안 붙어 있습니다" 로 거절합니다.
    조용히 아무 일도 안 하는 것보다 낫습니다.
*/

window.__sigWait = {};

/* 앱이 부르는 자리. 이름표로 짝을 찾아 약속을 끝냅니다. */
window.__sigDone = function (id, res) {
  const f = window.__sigWait[id];
  delete window.__sigWait[id];
  if (!f) {
    console.warn('다리: 모르는 이름표의 답이 왔습니다 — ' + id);
    return;
  }
  f(res);
};

function handshake(ip, port, offerSdp, aesKey) {
  return new Promise(function (ok, no) {
    if (typeof app === 'undefined' || !app.handshake) {
      no(new Error('앱이 안 붙어 있습니다 — 브라우저로는 이 두 번의 HTTP 를 못 합니다'));
      return;
    }
    const id = 'h' + Date.now() + '_' + Math.random().toString(36).slice(2);
    window.__sigWait[id] = function (r) {
      if (r.steps) console.log('다리가 지난 단계\n' + r.steps);
      if (r.ok) ok(r.sdp);
      else no(new Error(r.why));
    };
    try {
      app.handshake(ip, port | 0, offerSdp, aesKey || '', id);
    } catch (e) {
      delete window.__sigWait[id];
      no(e);
    }
  });
}

/*
  진짜 SDP 제안 하나를 만듭니다.

  가짜 문자열을 보내면 우리 다리는 통과해도 로봇이 거절합니다. 그러면
  "다리가 틀렸나 SDP 가 틀렸나" 를 구별할 수 없습니다. 그래서 시험에도
  브라우저가 실제로 만든 제안을 씁니다.

  데이터채널을 하나 열어둡니다 — 그게 없으면 m= 줄이 없는 빈 제안이
  나옵니다.
*/
async function makeOffer() {
  const pc = new RTCPeerConnection();

  /* ★ 제안은 로봇이 기대하는 만큼 갖춰져야 합니다 ★

     처음에는 데이터채널 하나만 넣어 566글자짜리 제안을 보냈습니다.
     로봇은 **말없이 연결을 끊었습니다** — 오류도 상태 코드도 없이요.
     그 침묵을 보고 네 번 헛짚었습니다 (소켓 재사용 · 오디오 줄 · GET
     대 POST · 봉투). 앞의 셋은 아니었고 봉투는 맞지만 모자랐습니다.

     PC 에서 라이브러리와 나란히 재보고 나서야 갈렸습니다.

         토막 SDP (41글자)    라이브러리도 막힘   ← 로봇이 안 받습니다
         진짜 제안 (3860글자)  둘 다 통과

     로봇이 붙는 상대는 데이터채널 · 비디오 · 오디오를 다 갖춘
     제안입니다. PC 드라이버가 만드는 것이 그 모양이고, 여기서도
     같은 모양을 만듭니다.

     ※ 트랙 없이 자리만 여는 것이라 마이크·카메라 권한을 묻지
       않습니다. 실제로 쓰게 될 때 그때 묻습니다. */
  pc.createDataChannel('data');
  pc.addTransceiver('video', {direction: 'recvonly'});
  pc.addTransceiver('audio', {direction: 'sendrecv'});

  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  // ICE 후보가 다 모일 때까지 잠깐 기다립니다 (최대 2초).
  await new Promise(function (done) {
    if (pc.iceGatheringState === 'complete') return done();
    const t = setTimeout(done, 2000);
    pc.addEventListener('icegatheringstatechange', function () {
      if (pc.iceGatheringState === 'complete') { clearTimeout(t); done(); }
    });
  });
  const sdp = pc.localDescription.sdp;
  pc.close();
  return sdp;
}
