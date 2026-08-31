# -*- coding: utf-8 -*-
"""
로봇 IP 찾기 + 네트워크 진단.

로봇을 움직이지 않습니다. 안전합니다.

  1. 이 PC 의 네트워크 어댑터와 IP 를 보여줍니다
  2. 멀티캐스트로 Go2 를 찾습니다 (앱이 쓰는 것과 같은 방식)
  3. 못 찾으면 같은 대역 전체를 훑어 신호 포트(9991, 8081)가
     열린 기기를 직접 찾아냅니다
  4. 찾으면 그대로 붙여넣을 설정 줄을 출력합니다

사용법:
    .\\run find_robot.py
"""

import socket
import sys
from concurrent.futures import ThreadPoolExecutor

import config

SIGNALING_PORTS = (9991, 8081)


# ─────────────────────────────────────────────────────────────
# 1. 이 PC 의 네트워크
# ─────────────────────────────────────────────────────────────

def show_interfaces():
    print("=" * 64)
    print(" 이 PC 의 네트워크")
    print("=" * 64)

    subnets = []
    try:
        import ifaddr
        adapters = ifaddr.get_adapters()
    except ImportError:
        adapters = None

    if adapters:
        for adapter in adapters:
            shown = [
                ip for ip in adapter.ips
                if isinstance(ip.ip, str) and not ip.ip.startswith("127.")
            ]
            if not shown:
                continue
            print(f"\n  {adapter.nice_name}")
            for ip in shown:
                print(f"      {ip.ip}/{ip.network_prefix}")
                parts = ip.ip.split(".")
                if len(parts) == 4 and parts[0] != "169":   # 169.254 = 링크로컬
                    subnets.append(".".join(parts[:3]))
    else:
        host = socket.gethostbyname(socket.gethostname())
        print(f"  {host}")
        subnets.append(".".join(host.split(".")[:3]))

    print()
    return sorted(set(subnets))


# ─────────────────────────────────────────────────────────────
# 2. 멀티캐스트 탐색
# ─────────────────────────────────────────────────────────────

def multicast_scan():
    print("=" * 64)
    print(" 1단계 — 멀티캐스트 탐색 (231.1.1.1)")
    print("=" * 64)
    try:
        from unitree_webrtc_connect import discover_ip_sn
        found = discover_ip_sn(timeout=5, device_type="Go2",
                               sn=config.ROBOT_SN or None)
        return found or {}
    except Exception as e:
        print(f"  탐색 실패: {type(e).__name__}: {e}")
        return {}


# ─────────────────────────────────────────────────────────────
# 3. 포트 스캔 (멀티캐스트가 막혔을 때)
# ─────────────────────────────────────────────────────────────

def check_host(ip):
    """신호 포트가 열려 있으면 포트 번호를, 아니면 None 을 돌려줍니다."""
    for port in SIGNALING_PORTS:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.4)
        try:
            if s.connect_ex((ip, port)) == 0:
                return port
        except OSError:
            pass
        finally:
            s.close()
    return None


def port_scan(subnets):
    print("=" * 64)
    print(f" 2단계 — 포트 스캔 (신호 포트 {SIGNALING_PORTS})")
    print("=" * 64)

    hits = []
    for subnet in subnets:
        targets = [f"{subnet}.{i}" for i in range(1, 255)]
        print(f"\n  {subnet}.1 ~ {subnet}.254 훑는 중...", end="", flush=True)
        with ThreadPoolExecutor(max_workers=128) as pool:
            for ip, port in zip(targets, pool.map(check_host, targets)):
                if port:
                    hits.append((ip, port))
        print(f"  ({len(hits)}대 발견)")
    return hits


# ─────────────────────────────────────────────────────────────

def report_success(ip, extra=""):
    print("\n" + "=" * 64)
    print(" 아래를 PowerShell 에 붙여넣으세요")
    print("=" * 64)
    print(f'$env:GO2_IP = "{ip}"')
    print("=" * 64)
    if extra:
        print(extra)
    print("\n그다음:  .\\run 01_connect_test.py")


def main():
    subnets = show_interfaces()

    found = multicast_scan()
    if found:
        print("\n" + "=" * 64)
        print(f" 찾았습니다 — {len(found)}대")
        print("=" * 64)
        for serial, ip in found.items():
            print(f"\n  SN : {serial}")
            print(f"  IP : {ip}")
        report_success(list(found.values())[0])
        return

    print("\n  멀티캐스트로는 못 찾았습니다.")
    print("  (방화벽이나 AP 격리로 막혔을 수 있으니 직접 훑어보겠습니다)\n")

    if not subnets:
        print("  이 PC 의 IP 대역을 알 수 없어 스캔할 수 없습니다.")
        return

    hits = port_scan(subnets)

    if hits:
        print("\n" + "=" * 64)
        print(f" 신호 포트가 열린 기기 {len(hits)}대")
        print("=" * 64)
        for ip, port in hits:
            print(f"    {ip}  (포트 {port} 열림)")
        if len(hits) == 1:
            report_success(hits[0][0])
        else:
            print("\n  여러 대가 나왔습니다. 하나씩 시도해 보세요:")
            for ip, _ in hits:
                print(f'    $env:GO2_IP = "{ip}"  ;  .\\run 01_connect_test.py')
        return

    # ── 아무것도 못 찾음 ──────────────────────────────────────
    print("\n" + "=" * 64)
    print(" 로봇을 찾지 못했습니다")
    print("=" * 64)
    print(f"\n 훑어본 대역: {', '.join(s + '.x' for s in subnets)}")
    print("\n 원인 후보")
    print(" ─────────────────────────────────────────────────────────")
    print(" 1. AP 격리(클라이언트 격리)  ★ 사무실·게스트 Wi-Fi 에서 흔합니다 ★")
    print("    같은 Wi-Fi 에 붙어도 단말끼리 못 보게 막는 설정입니다.")
    print("    관리자가 풀어주지 않으면 그 망에서는 방법이 없습니다.")
    print()
    print(" 2. Windows 방화벽 / 네트워크 프로필")
    print("    설정 → 네트워크 → 해당 Wi-Fi → 네트워크 프로필 을")
    print("    '공용' 에서 '개인' 으로 바꾸고 다시 시도하세요.")
    print()
    print(" 3. 로봇이 그 Wi-Fi 에 실제로 안 붙어 있음")
    print("    앱의 로봇 목록에서 'On-line' 인지 확인하세요.")
    print("    'Off-line' 이면 로봇이 아직 그 망에 없습니다.")
    print()
    print(" 확실한 우회 (둘 다 5분이면 됩니다)")
    print(" ─────────────────────────────────────────────────────────")
    print(" A. 폰 핫스팟")
    print("    로봇과 PC 를 모두 폰 핫스팟에 붙입니다.")
    print("    핫스팟은 클라이언트 격리를 하지 않습니다.")
    print()
    print(" B. 로봇 AP 모드  ★ 네트워크 관리자 없이 가능 ★")
    print("    1) 앱에서  Device → Robot Dog Settings")
    print("       → 'Change another connection' 으로 AP 모드 전환")
    print("    2) PC 의 Wi-Fi 를 로봇 핫스팟 GO2-XXXXXX 에 연결")
    print("       (유선 랜선은 꽂아두면 인터넷도 그대로 씁니다)")
    print("    3) config.py 에서  CONNECTION_MODE = \"ap\"")
    print("    4) .\\run 01_connect_test.py")
    print("    IP 도 인터넷도 필요 없습니다.")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n중단됨")
        sys.exit(0)
    except Exception as e:
        print(f"\n[오류] {type(e).__name__}: {e}")
        sys.exit(1)
