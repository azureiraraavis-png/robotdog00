# -*- coding: utf-8 -*-
"""MainActivity.kt 에 '마이크를 줬다' 는 기록을 넣습니다. 그것만 합니다.

  ★ 왜 이것부터인가 ★

    지금 코드는 **거절할 때만** Log 를 남깁니다. 그래서 Logcat 에
    '마이크' 줄이 하나도 안 보이면, 그게

        (가) 줬는데 안 적어서 안 보이는 것인지
        (나) 화면이 아예 안 물어봐서 안 보이는 것인지

    구별이 안 됩니다. 물어봐 놓고 답을 못 읽는 꼴입니다.

    NotReadableError 의 원인을 짐작으로 두 번 틀렸으니(딴 앱이 쥐고
    있다 / 앱 권한이 없다), 이번에는 짐작을 더 얹지 않고 **읽을 수
    있게만** 만듭니다. 동작은 한 글자도 안 바꿉니다.

  쓰는 법

      .\\run patch_mic_log.py        고칩니다 (두 번 돌려도 안전합니다)
      .\\run kt_check.py             고친 뒤 훑어봅니다
"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
KT = (HERE / "phone" / "GuideRemote" / "app" / "src" / "main" / "java"
      / "kr" / "raraavis" / "guideremote" / "MainActivity.kt")

# ── 1. 들어올 때 적기 ──────────────────────────────────────────
BEFORE_1 = """                ) == PackageManager.PERMISSION_GRANTED
                runOnUiThread {"""

AFTER_1 = """                ) == PackageManager.PERMISSION_GRANTED
                // ★ 준 것도 적습니다 ★
                //   거절할 때만 적으면, Logcat 에 아무것도 없을 때 그게
                //   "줬다" 인지 "아예 안 물어봤다" 인지 구별이 안 됩니다.
                //   물어봐 놓고 답을 못 읽는 꼴입니다.
                Log.i("마이크", "화면이 달랍니다: ${req.resources.joinToString()}" +
                        "  (온 곳 ${req.origin}, 앱 권한 ${if (mine) "있음" else "없음"})")
                runOnUiThread {"""

# ── 2. 줄 때 적기 ─────────────────────────────────────────────
BEFORE_2 = """                        req.grant(want.toTypedArray())
                    } else {"""

AFTER_2 = """                        req.grant(want.toTypedArray())
                        Log.i("마이크", "줬습니다")
                    } else {"""


def main():
    if not KT.exists():
        print(f" ✖ {KT} 가 없습니다.")
        return 1

    text = KT.read_text(encoding="utf-8")

    if "줬습니다" in text and "화면이 달랍니다" in text:
        print(" ○ 이미 들어 있습니다. 아무것도 안 했습니다.")
        return 0

    for before, after, what in ((BEFORE_1, AFTER_1, "들어올 때"),
                                (BEFORE_2, AFTER_2, "줄 때")):
        if text.count(before) != 1:
            print(f" ✖ '{what}' 를 넣을 자리를 {text.count(before)}군데 "
                  "찾았습니다 (하나여야 합니다).")
            print("   파일이 그 사이에 바뀐 것 같습니다 — 그대로 두겠습니다.")
            return 1
        text = text.replace(before, after)

    KT.write_text(text, encoding="utf-8")
    print(" ○ 넣었습니다. 동작은 그대로입니다 — 기록만 늘었습니다.")
    print()
    print("   다음으로")
    print("     .\\run kt_check.py        훑어보기")
    print("     안드로이드 스튜디오에서 다시 빌드 → 설치")
    return 0


if __name__ == "__main__":
    sys.exit(main())
