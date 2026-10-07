# robotdog00 — Go2 PRO 한국어 안내 로봇

Unitree Go2 PRO가 **한국어로 말하면서 방문객을 안내하도록** 만드는 프로젝트입니다.

앱에 딸린 음성 비서(벤벤)는 한국어를 알아듣지 못하고 손댈 수도 없습니다.
그래서 앱을 거치지 않고 **PC에서 로봇에 직접 붙어**, 한국어 음성을 만들어
로봇 스피커로 내보내고, 한국어 명령으로 움직이게 합니다.

> A Korean-language voice guide built on the Unitree Go2 PRO.
> The stock BenBen assistant is a closed loop to Unitree's servers with no way to add
> Korean, so this controls the robot directly over the same WebRTC path the app uses —
> local Whisper for Korean speech recognition, edge-tts for synthesis, played through
> the robot's own speaker. Documentation is in Korean; the findings section below may
> be useful to anyone working with a Go2, especially on a non-English Windows locale.

<a id="toc"></a>

## 문서 안내

이 저장소의 기록은 두 갈래입니다.

| | 문서 | 무엇이 들어 있나 |
|---|---|---|
| **1부** | [로봇개 조종](docs/1_control.md) | 진짜 로봇(Go2 PRO)을 PC 로 조종해 한국어 안내를 시키는 일 — 준비물 · 실행 순서 · 리모컨 · 주의 · 삽질 기록 1~29 · 30~32장 |
| **2부** | [가상 로봇개 훈련](docs/2_training.md) | 시뮬레이터(Isaac Sim · Isaac Lab) 속 로봇개에게 계단을 가르치는 일 — 33~56장 |

장 번호(30, 41, 53-4 …)는 코드 주석과 커밋 메시지가 가리키는 번호라 **바꾸지 않습니다.** "README 40-12" 처럼 적힌 곳은 번호로 찾으면 됩니다 — **32장까지는 1부, 33장부터는 2부**입니다.

| 바로 가기 | |
|---|---|
| 지금 안내를 하려면 | [지금 안내를 하려면](docs/1_control.md#a10) |
| 실기체의 현재 상태 | [현재 상태](#a01) |
| 가상 로봇개가 지금 서 있는 곳 | [56-2. 결과 — 0.15 도 지키고, 단은 같다 (10/07 · 45판)](docs/2_training.md#c56-2) |
| 파일이 무엇을 하는가 | [파일 구성](#a51) |

### 1부. 로봇개 조종 (실기체 Go2 PRO)

- **시작하기**
  - [왜 앱으로는 안 되는가](docs/1_control.md#a03)
  - [준비물](docs/1_control.md#a04)
  - [네트워크 구성](docs/1_control.md#a07)
  - [AES 키 받기](docs/1_control.md#a08)
  - [실행 순서](docs/1_control.md#a09)
- **쓰기**
  - [안내 코스 — 하나 더 만들기](docs/1_control.md#a13)
  - [휴대폰 리모컨](docs/1_control.md#a17)
  - [조종 장치가 **두 개**입니다](docs/1_control.md#a19)
  - [동반 리모컨 (작은 막대형)](docs/1_control.md#a21)
  - [게임패드 (큰 것)](docs/1_control.md#a25)
- **주의와 문제 해결**
  - [⚠ 전원을 켤 때 발버둥치는 문제](docs/1_control.md#a32)
  - [문제 해결](docs/1_control.md#a39)
  - [⚠ 운영상 주의](docs/1_control.md#a40)
- **방향**
  - [앞으로의 방향](docs/1_control.md#a41)
- **기록**
  - [삽질 기록 — 이 프로젝트에서 알아낸 것들](docs/1_control.md#a43)
    - [오디오](docs/1_control.md#a44)
    - [연결](docs/1_control.md#a45)
    - [안전](docs/1_control.md#a46)
    - [환경](docs/1_control.md#a47)
    - [회피와 이동 거리](docs/1_control.md#a48)
    - [안내와 화면](docs/1_control.md#a49)
  - [30. 복도에서 실제로 어땠는가 (2026-09-11 외빈 안내)](docs/1_control.md#c30)
  - [31. 앱이 PC 화면을 엽니다 — 그리고 조용히 막히는 것 둘 (2026-09-11)](docs/1_control.md#c31)
  - [32. 로봇에게 눈이 있었습니다 — 그리고 왼쪽으로 휩니다 (2026-09-14)](docs/1_control.md#c32)

### 2부. 가상 로봇개 훈련 (Isaac Sim · Isaac Lab)

- [33. 시뮬레이터에서 Go2 를 세우는 데 이틀 걸렸습니다 (2026-09-14~15)](docs/2_training.md#c33)
- [34. 정책을 직접 학습시켰습니다 — 3분 반이면 한 판입니다 (2026-09-15 오후)](docs/2_training.md#c34)
- [35. 문턱 앞에서 넘어집니다 — 그리고 제 시험대를 여덟 번 고쳤습니다 (2026-09-16)](docs/2_training.md#c35)
- [36. 거친 지형으로 옮겼더니, 이번엔 기어갑니다 (2026-09-16 저녁)](docs/2_training.md#c36)
- [37. std 가 음수가 된 게 아니었습니다 — NaN 이었습니다 (2026-09-17 아침)](docs/2_training.md#c37)
- [38. 시험대가 개를 떨어뜨리고 있었습니다 (2026-09-17 오후)](docs/2_training.md#c38)
- [39. 커리큘럼은 "얼마나 잘 올랐나"가 아니라 "얼마나 멀리 갔나"를 잽니다 (2026-09-17 저녁)](docs/2_training.md#c39)
- [40. 답은 이틀 전에 이미 손에 있었습니다 (2026-09-18)](docs/2_training.md#c40)
- [41. 다리를 풀었더니 몸이 폈습니다 (2026-09-21)](docs/2_training.md#c41)
- [42. 연속 계단 (2026-10-02)](docs/2_training.md#c42)
- [43. 이어 학습 — 높은 계단을 만나게 (2026-10-02)](docs/2_training.md#c43)
- [44. 승급선 고치기 — 처음부터 한 번에 (2026-10-02)](docs/2_training.md#c44)
- [45. 내려가기 (2026-10-02)](docs/2_training.md#c45)
- [46. 다른 씨앗으로 한 번 더 — 18 cm 는 운이었는가 (2026-10-02)](docs/2_training.md#c46)
- [47. 숙임 고치기 — 수평 벌을 켜고 이어 학습 (2026-10-06)](docs/2_training.md#c47)
- [48. 정책에 눈을 줍니다 — 높이 스캔 (2026-10-06)](docs/2_training.md#c48)
- [49. 참에서 주저앉기 — 넷이 같은 일이 아니었습니다 (2026-10-06)](docs/2_training.md#c49)
- [50. 가장 나은 정책을 새 자로 마저 잽니다 — 내려가기와 15 cm (2026-10-06)](docs/2_training.md#c50)
- [51. 헛발질을 세는 자 (2026-10-07)](docs/2_training.md#c51)
- [52. 발을 들라고 말해 준다 — `feet_air_time` (2026-10-07)](docs/2_training.md#c52)
- [53. 끄는 발을 직접 벌한다 — `feet_slide` (2026-10-07)](docs/2_training.md#c53)
- [54. 흠 26 을 고침 — 옆 밀림을 세계 좌표로 (2026-10-07)](docs/2_training.md#c54)
- [55. 계단 위 쏠림 — 학습 없이, 바깥 고리로 잡히는가 (2026-10-07)](docs/2_training.md#c55)
- [56. 새 정책을 0.15 계단과 단에서 잰다 (2026-10-07)](docs/2_training.md#c56)

# robotdog00 — Go2 PRO 한국어 안내 로봇

Unitree Go2 PRO가 **한국어로 말하면서 방문객을 안내하도록** 만드는 프로젝트입니다.

앱에 딸린 음성 비서(벤벤)는 한국어를 알아듣지 못하고 손댈 수도 없습니다.
그래서 앱을 거치지 않고 **PC에서 로봇에 직접 붙어**, 한국어 음성을 만들어
로봇 스피커로 내보내고, 한국어 명령으로 움직이게 합니다.

> A Korean-language voice guide built on the Unitree Go2 PRO.
> The stock BenBen assistant is a closed loop to Unitree's servers with no way to add
> Korean, so this controls the robot directly over the same WebRTC path the app uses —
> local Whisper for Korean speech recognition, edge-tts for synthesis, played through
> the robot's own speaker. Documentation is in Korean; the findings section below may
> be useful to anyone working with a Go2, especially on a non-English Windows locale.

<a id="a01"></a>

## 현재 상태

[↑ 문서 안내](#toc)

| | 상태 |
|---|---|
| PC → 로봇 제어 연결 (WebRTC, AES 인증) | ✅ 실기 확인 |
| 한국어 음성 → 로봇 스피커 재생 | ✅ 실기 확인 |
| 연속 재생 (여러 문장을 이어서) | ✅ 실기 확인 |
| 안전하게 눕히기 / 들어 올리기 / 넘어짐 복구 | ✅ 실기 확인 |
| 자세 감시 (기울기 읽기) | ✅ 실기 확인 |
| 한국어 음성 인식 (whisper) | ✅ 실기 확인 — GPU(RTX 4070) 로 medium 모델 |
| 음성 명령 → 제자리 동작 (`05`) | ✅ 실기 확인 |
| 보행·회전 (`02_move_test.py`) | ✅ 실기 확인 |
| 키보드 조종 (`drive.py`) | ✅ 실기 확인 — 전진 0.5 m/s, 회전 1.4 rad/s |
| 자세 전환 뒤에도 계속 걷기 | ✅ 해결 — 일어선 뒤 `StopMove` (13-11-7) |
| 음성 명령 → 보행 | ✅ 실기 확인 — 전진·후진·좌우 회전 |
| 음성 명령: 자세 전환 뒤 회전 | ✅ 실기 확인 (앉기·엎드리기 후에도 정상) |
| 라이다·카메라로 주변 보기 | ✅ 실기 확인 — 지도가 사진과 일치 (9-3~9-7) |
| 안내 한 판 통째로 (`guide.py --manual`) | ✅ 실기 확인 — 멘트 21개·동작·라이트·회전 |
| 휴대폰 리모컨 (`remote.py`) | ✅ 실기 확인 — 조종판·메뉴·코스 고르기 |
| 닫은 각도로 회전 (`common.turn_by`) | ✅ 실기 확인 — 명령 대비 ±2도, 관성 5도 |
| 안내 코스 여러 벌 (`courses.py`) | ✅ 화면·등록 확인 (둘째 코스 대본은 아직) |

<a id="a02"></a>

### 닫힌 문 — 알아보고 안 되는 것으로 판정한 것들

여기 적힌 것은 "아직 안 해봤다" 가 아니라 **재보고 아니라고 결론 낸 것**입니다.
다시 열어보지 않아도 됩니다.

| | 결과 |
|---|---|
| 로봇의 장애물 회피 (`SwitchAvoidMode`) | ❌ 코드 0 을 주지만 거동이 안 바뀝니다 (18) |
| 게임패드 버튼 읽기 (`keys_test.py`) | ❌ 실제로 몰면서 봐도 값은 0 뿐 (19) |
| 로봇 마이크로 듣기 (`mic_test.py`) | ❌ 프레임은 오는데 소리가 안 담깁니다 (20) |
| 천천히 엎드리기 (`settle_test.py`) | ❌ MCF 에 `BodyHeight` 가 없고 `StandDown` 은 거부 (21) |
| 완전 자동 주행 | ❌ 회전 오차 ±5도가 바닥 — 사람이 몹니다 (`DECISION.md`) |
| 브라우저만으로 로봇에 붙기 (`web_probe.py`) | ❌ CORS 도 막고 AES-ECB·RSA PKCS1v1.5 가 WebCrypto 에 없습니다 → 앱 + 네이티브 다리 (28) |

**기체**: Unitree Go2 **PRO** (오디오 재생은 PRO/EDU 전용), 펌웨어 MCF 모드

---

<a id="a50"></a>

## 참고

[↑ 문서 안내](#toc)

- [go2_webrtc_connect](https://github.com/legion1581/go2_webrtc_connect) — 이 프로젝트가 쓰는 라이브러리 (AIR/PRO/EDU 지원)
- [go2_ros2_sdk](https://github.com/abizovnuralem/go2_ros2_sdk) — ROS2가 필요해지면
- [Go2 AIR / PRO 사용 설명서](https://static1.squarespace.com/static/5e76e0c52a318c0c1a850442/t/6670b3b47b72423f1b3b0e5b/1718662095370/GO2+User+Manual.pdf)

<a id="a51"></a>

## 파일 구성

[↑ 문서 안내](#toc)

```
robotdog00/
├── README.md              첫 화면 — 소개 · 현재 상태 · 두 문서로 가는 목차
├── docs/1_control.md      ★ 1부. 로봇개 조종 (실기체) — 삽질 기록 1~29 · 30~32장
├── docs/2_training.md     ★ 2부. 가상 로봇개 훈련 (시뮬레이터) — 33~56장
├── DECISION.md            ★ 왜 로봇이 스스로 걷지 않기로 했는가
├── MEASURE.md             복도를 줄자로 재는 법
├── ISAACLAB.md            ★ Isaac Lab 에 고친 곳 (남의 저장소라 git 이 안 봅니다)
├── requirements.txt
├── run.cmd                ★ 가상환경을 알아서 씁니다 — .\run <파일>
│
├── sim_world.py           실측 3층을 USD 로 씁니다
├── sim_check.py           Isaac Sim 이 스크립트로 열리는가
├── sim_open.py            그 세계를 실제로 엽니다
├── sim_source.py          NVIDIA 원본 코드를 꺼내 봅니다
├── sim_joints.py          관절 차례·무게·이득 (걷게 하지 않습니다)
├── sim_go2.py             ★ 시뮬레이터의 개를 걷게 하고 잽니다
├── feet_read.py           발 자취(sim\feet\*.csv)에서 헛발질을 셉니다 (시뮬레이터 불필요)
├── scan_check.py          학습 환경의 높이 스캔과 시험대의 식이 같은지 잽니다
├── curve.py               학습 곡선 보기 (tensorboard 없이 tfevents 직독)
├── isaaclab_edits/go2/    ★ Isaac Lab 에 덮어쓰는 과제 설정 원본
│
│  ── 안내 (지금 쓰는 것) ──
├── guide.py               ★ 안내 실행기 — .\run guide.py --manual
├── scenario.py            ★ 대본과 건물의 사실 (문패·거리·회전 모델)
├── courses.py             안내 코스 등록소 (course_*.py 를 스스로 찾습니다)
├── course_example.py      코스 본보기 — 복사해서 새 코스를 만듭니다
├── course_short.py        짧은 코스 (대본 작성 중 — DRAFT)
├── remote.py              휴대폰 리모컨 (조종판·메뉴·코스)
├── voices.py              멘트 mp3 만들고 길이 재기 (로봇 불필요)
├── measure.py             복도 실측 기록
│
│  ── 바탕 ──
├── config.py              ★ IP, AES 키, 목소리, 안전 한계값
├── common.py              연결·이동·회전·음성 헬퍼 (모든 스크립트가 사용)
├── safety.py              자세 감시, 자동 복구 제어
├── perception.py          라이다로 주변 보기
├── stt.py                 한국어 음성 인식 (로컬 whisper)
├── brain.py               명령어 판단 + 자유 질의응답
├── cuda_dlls.py           윈도우 CUDA DLL 경로 등록 (stt 가 자동 사용)
├── get_aes_key.py         AES 키 발급 (한국어 Windows 대응판)
├── sig.py                 시그널링 절차 — 코틀린으로 옮길 원본
├── find_robot.py          로봇 IP 찾기 + 네트워크 진단
│
│  ── 시험 (대부분 로봇 없이 됩니다) ──
├── stop_test.py           ★ 화면과 버튼 — 로봇 없이 88가지
├── turn_test.py           회전 각도 실측
├── lie_test.py            엎드리기가 왜 자리마다 다른가 (인사 뒤 철푸덕)
├── settle_test.py         천천히 엎드릴 수 있는가 (결론: 못 합니다)
├── mic_test.py            로봇에게 귀가 있는가 (결론: 없습니다 — 세 번 확인)
├── keys_test.py           게임패드 버튼이 오는가 (결론: 안 옵니다)
├── light_test.py          전방 라이트를 켜는 api_id 찾기
├── avoid_test.py          로봇의 장애물 회피가 실제로 도는가 (결론: 안 돕니다)
├── gait_test.py           걸음 통로 비교 실험
├── mode_test.py           조종이 안 먹을 때 원인 찾기
├── sit_test.py            앉기 후 못 걷는 문제
├── web_probe.py           브라우저가 로봇 손잡이를 잡을 수 있는가 (결론: 못 잡습니다)
├── web_mic.py             폰 브라우저가 마이크를 여는가 (결론: https 면 열립니다)
├── sig_test.py            시그널링 절차가 맞는가 — 가짜 로봇 상대로 33가지
├── sig_diff.py            ★ 라이브러리와 우리를 같은 로봇에 나란히 세웁니다
├── dump_state.py          로봇이 보내는 상태 그대로 보기
├── gpu_check.py           음성 인식 GPU 사용 가능 여부 진단
├── test_listen.py         마이크가 잡히는지만 확인 (로봇 불필요)
│
│  ── 손도구 ──
├── drive.py               키보드 조종
├── look.py                로봇의 눈 — 카메라 사진 + 라이다 지도
├── speak.py               대화형 말하기 콘솔
├── audio_check.py         안내 음성 재생 점검
├── hush.py                로봇이 계속 떠들 때 멈추기
├── park.py                전원 끄기 전 안전 자세
├── recover.py             넘어짐 복구 / 자동 복구 끄기
├── carry.py               들어 올리기 전 안전 조치
│
│  ── 처음 붙일 때 ──
├── 01_connect_test.py     연결 확인          (안 움직임)
├── 02_move_test.py        동작 확인          (움직임)
├── 03_speak_korean.py     한국어 음성 시험    (소리만)
├── 04_guide_demo.py       옛 안내 데모        (움직임 — guide.py 로 대체)
├── 05_voice_control.py    한국어 음성 제어    (움직임)
│
└── audio/                 생성된 mp3·wav 와 실측 길이 (자동 생성)
```
