# -*- coding: utf-8 -*-
"""
AES 키 받기 (한국어 Windows 대응판).

왜 이 파일이 필요한가
─────────────────────
라이브러리에 딸려오는 `unitree-fetch-aes-key` 명령은 한국어 Windows에서
아래 오류를 내며 죽습니다.

    UnicodeEncodeError: 'latin-1' codec can't encode characters in position 0-3

원인은 unitree_cloud.py 의 이 줄입니다.

    "AppTimezone": time.strftime("%Z") or "UTC",

한국어 Windows에서 이 값이 "대한민국 표준시" 로 나오는데,
HTTP 헤더는 latin-1 만 허용하므로 인코딩에서 터집니다.
(영어 환경이면 "Korea Standard Time" 이라 문제가 없어서, 이 버그는
 한국어·중국어·일본어 로케일에서만 나타납니다.)

여기서는 헤더 값 중 latin-1 로 인코딩되지 않는 것을 안전한 값으로
바꿔치기해서 우회합니다. 라이브러리 파일은 건드리지 않습니다.

사용법
──────
    .\\.venv\\Scripts\\python.exe get_aes_key.py

비밀번호는 프롬프트로 물어봅니다. 명령줄에 적지 마세요.
"""

import getpass
import sys

import unitree_webrtc_connect.unitree_cloud as uc

import config


# ─────────────────────────────────────────────────────────────
# 우회 패치: 헤더 값을 latin-1 안전하게 만든다
# ─────────────────────────────────────────────────────────────

_original_headers = uc.UnitreeCloud._headers


def _ascii_safe_headers(self):
    headers = _original_headers(self)
    for name, value in list(headers.items()):
        if not isinstance(value, str):
            continue
        try:
            value.encode("latin-1")
        except UnicodeEncodeError:
            # 시간대 이름이 한글일 때가 대부분입니다.
            replacement = "UTC" if name == "AppTimezone" else ""
            print(f"[우회] 헤더 {name}: 비ASCII 값을 '{replacement}' 로 대체 "
                  f"(원래 값: {value})")
            headers[name] = replacement
    return headers


uc.UnitreeCloud._headers = _ascii_safe_headers


# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print(" Go2 AES 키 받기")
    print("=" * 60)

    email = config.UNITREE_EMAIL or input("유니트리 계정 이메일: ").strip()
    password = config.UNITREE_PASSWORD or getpass.getpass("비밀번호(화면에 안 보입니다): ")
    region = config.UNITREE_REGION

    print(f"\n[로그인] {region} 클라우드에 접속 중...")
    cloud = uc.UnitreeCloud(region=region, device_type="Go2")
    cloud.login_email(email, password)
    print("[로그인] 성공\n")

    devices = cloud.list_devices()
    if not devices:
        print("이 계정에 바인딩된 로봇이 없습니다.")
        print("  → 앱에서 먼저 기기를 바인딩했는지 확인하세요.")
        print("  → 공용 장비라면 다른 계정에 묶여 있을 수 있습니다.")
        print("  → 계정이 중국 가입이면 config.py 의 UNITREE_REGION 을 'cn' 으로.")
        return

    print("=" * 60)
    print(f" 바인딩된 로봇 {len(devices)}대")
    print("=" * 60)
    for d in devices:
        print(f"\n  이름   : {d.alias}")
        print(f"  SN     : {d.sn}")
        print(f"  모델   : {d.model}")
        print(f"  온라인 : {d.online}")
        if d.key:
            print(f"  AES 키 : {d.key}")
        else:
            print("  AES 키 : (비어 있음 — 펌웨어가 1.1.15 미만이면 키가 필요 없습니다)")

    keyed = [d for d in devices if d.key]
    if keyed:
        import common
        d = keyed[0]
        common.save_settings(aes_key=d.key, robot_sn=d.sn)
        print("\n" + "=" * 60)
        print(" 저장 완료 — 이제 환경변수를 입력할 필요가 없습니다")
        print("=" * 60)
        print(" settings.local.json 에 저장했습니다.")
        print(f"   SN     : {d.sn}")
        print(f"   AES 키 : {d.key[:8]}...")
        print()
        print(" IP 는 실행할 때 자동으로 찾습니다.")
        print(" 그냥 바로 시작하세요:   .\\run 01_connect_test.py")
        print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단됨")
        sys.exit(0)
    except Exception as e:
        print(f"\n[오류] {type(e).__name__}: {e}")
        print("\n  · 이메일/비밀번호를 확인하세요.")
        print("  · 계정이 중국 가입이면 config.py 의 UNITREE_REGION 을 'cn' 으로 바꾸세요.")
        print("  · 기체가 이 계정에 바인딩되어 있어야 키가 나옵니다.")
        sys.exit(1)
