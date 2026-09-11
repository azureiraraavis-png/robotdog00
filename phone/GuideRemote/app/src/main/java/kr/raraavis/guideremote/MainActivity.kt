package kr.raraavis.guideremote

import android.Manifest
import android.annotation.SuppressLint
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.net.http.SslError
import android.webkit.PermissionRequest
import android.webkit.SslErrorHandler
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import org.json.JSONObject
import java.io.ByteArrayInputStream

/**
 * 안내 리모컨 — 화면 전체가 WebView 하나입니다.
 *
 * ★ 왜 WebView 인가 ★
 *   안내 화면과 로직은 이미 다 만들어져 있고(remote.py 의 PAGE), 브라우저에서
 *   실제로 돌고 있습니다. 그걸 Kotlin 으로 다시 쓸 이유가 없습니다.
 *   앱이 해야 하는 일은 **브라우저가 못 하는 것 하나** 뿐입니다 —
 *   로봇과의 시그널링 (CORS 로 막히고, 쓰는 암호가 WebCrypto 에 없습니다).
 *   자세한 것은 저장소의 web_probe.py 와 sig.py 에 있습니다.
 *
 * ★ 통로는 뚫렸습니다 (1판에서 확인) ★
 *   빌드 → 설치 → 실행 → 화면 → 앱까지 여섯 줄이 다 ○ 였습니다.
 *   출처가 https://guide.local 로 잡히고, 저장소도 WebRTC 도 삽니다.
 *   그래서 이제 다리(Sig.kt)를 얹었습니다.
 *
 *   '만들었다' 와 '보인다' 는 다릅니다 — 이 저장소에서 다섯 번 겪었습니다.
 *   하물며 이건 제가(작성한 AI가) 빌드해 볼 수 없는 코드입니다.
 *   그래서 화면 맨 위에 **판수 딱지**를 답니다. 고쳐 넣었는데 화면이
 *   그대로일 때, '안 들어간 것' 과 '내가 안 내려본 것' 이 똑같이
 *   보이거든요. 실제로 한 번 그랬습니다.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var web: WebView

    companion object {
        /**
         * 페이지가 살 주소.
         *
         * ★ 왜 file:// 이 아니라 이것인가 ★
         *   assets 를 file:// 로 열면 **출처가 없습니다.** 그러면 fetch 도
         *   localStorage 도 막히고, 우리 화면은 둘 다 씁니다.
         *   가짜 https 주소를 하나 정해두고 **나가기 전에 우리가 가로채면**
         *   진짜 출처가 생깁니다. 바깥으로 나가는 일은 없습니다.
         *
         *   그리고 이 자리가 곧 **시그널링 다리가 들어올 자리**입니다.
         *   페이지는 그냥 같은 출처로 fetch 하면 되고, 우리가 그것만
         *   로봇에게 대신 물어봐 주면 됩니다.
         */
        const val ORIGIN = "https://guide.local"

        /** 설정을 담아두는 곳. PC 주소와 인증서 지문이 들어갑니다. */
        const val PREFS = "guide"
        const val KEY_PC = "pc"            // 예: "192.168.0.80:8766"
        const val KEY_FINGER = "finger"    // 그 PC 인증서의 지문
    }

    private lateinit var prefs: SharedPreferences

    /**
     * 지금 떠 있는 주소. **UI 실에서만** 적습니다.
     *
     * ★ web.url 을 그냥 부르면 안 됩니다 ★
     *   @JavascriptInterface 함수는 'JavaBridge' 라는 딴 실에서 돕니다.
     *   WebView 의 메서드는 UI 실에서만 부를 수 있어서, 거기서 web.url 을
     *   읽으면 던집니다.
     *
     *   그런데 **화면에는 아무 일도 안 일어난 것처럼 보입니다.** 단추를
     *   눌러도 조용하고, 오류도 화면에 안 뜹니다. 실제로 그렇게 한 번
     *   막혔습니다 (2026-09-11). Logcat 을 봐야 알 수 있습니다.
     *
     *   그래서 주소가 바뀔 때마다 여기 적어두고, 다리에서는 이것만
     *   읽습니다. 읽는 쪽이 어느 실에 있든 상관없어집니다.
     */
    @Volatile
    private var here: String = ""


    /** 저장된 PC 주소. 없으면 null — 그러면 설정 화면(assets)을 엽니다. */
    private fun pcUrl(): String? =
        prefs.getString(KEY_PC, null)?.takeIf { it.isNotBlank() }?.let { "https://$it/" }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        web = findViewById(R.id.web)

        prefs = getSharedPreferences(PREFS, MODE_PRIVATE)

        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView, request: WebResourceRequest
            ): WebResourceResponse? = serve(request.url)

            /** 여기는 UI 실입니다 — 주소를 적어둘 수 있는 자리. */
            override fun onPageStarted(view: WebView, url: String, favicon: android.graphics.Bitmap?) {
                here = url
                super.onPageStarted(view, url, favicon)
            }

            override fun onPageFinished(view: WebView, url: String) {
                here = url
                super.onPageFinished(view, url)
            }

            /**
             * PC 의 자체 서명 인증서를 어떻게 다룰 것인가.
             *
             * ★ 그냥 proceed() 하면 안 됩니다 ★
             *   한 줄이면 되고 잘 돌아가 보입니다. 그런데 그건 **아무
             *   인증서나 받는다**는 뜻입니다. 같은 공유기에 있는 누구든
             *   우리 앱에게 자기가 PC 인 척할 수 있게 됩니다.
             *
             * ★ 그렇다고 CA 검증을 할 수도 없습니다 ★
             *   인증서는 그 PC 가 자기 IP 앞으로 스스로 만든 것입니다
             *   (web_mic.make_cert). 보증해 줄 기관이 없습니다.
             *
             * ★ 그래서 '처음 본 것을 기억한다' 로 갑니다 ★
             *   처음 붙을 때 지문을 보여주고 사람에게 묻습니다. 그 뒤로는
             *   같은 지문이면 조용히 통과하고, **바뀌면 멈추고 다시
             *   묻습니다.**
             *
             *   브라우저의 '고급 → 계속' 보다 나은 점은 두 가지입니다 —
             *   무엇을 승낙하는지 보여주고, **바뀌면 알아챕니다.**
             *   브라우저는 매번 묻지만 매번 같은 것을 묻지 않습니다.
             *
             *   정직하게 말하면 이건 인증이 아니라 **약속**입니다.
             *   학과 랜 안에서 쓰는 물건이라 이 정도로 둡니다.
             */
            override fun onReceivedSslError(
                view: WebView, handler: SslErrorHandler, error: SslError
            ) {
                val want = prefs.getString(KEY_PC, "")?.substringBefore(":")
                val host = Uri.parse(error.url ?: "").host
                if (want.isNullOrBlank() || host != want) {
                    Log.w("인증서", "우리 PC 가 아닙니다: $host (기다리는 것은 $want)")
                    handler.cancel()
                    return
                }

                val finger = fingerprintOf(error)
                if (finger == null) {
                    // ★ 못 읽으면 통과시키지 않습니다 ★
                    //   지문을 모르면 '기억한다' 가 성립하지 않습니다.
                    //   그 상태로 proceed() 하면 아무 인증서나 받는 것과
                    //   같아집니다. (API 29 밑에서 이럴 수 있습니다)
                    Log.w("인증서", "지문을 못 읽었습니다 — 통과시키지 않습니다")
                    handler.cancel()
                    say("이 안드로이드에서는 인증서 지문을 못 읽습니다.\n" +
                        "앱으로는 못 붙습니다 — 브라우저로 여세요.")
                    return
                }

                val known = prefs.getString(KEY_FINGER, null)
                when (known) {
                    finger -> handler.proceed()        // 아는 PC 입니다
                    null -> askFirstTime(handler, host, finger)
                    else -> {
                        handler.cancel()
                        say("PC 의 인증서가 **바뀌었습니다.**\n\n" +
                            "전: $known\n지금: $finger\n\n" +
                            "PC 주소가 바뀌었거나 인증서를 다시 만들었으면 " +
                            "정상입니다. 설정에서 지운 뒤 다시 붙으세요.\n" +
                            "짐작 가는 일이 없다면 붙지 마세요.")
                    }
                }
            }
        }

        // 페이지가 콘솔에 찍는 것과 **터진 오류**를 로그캣으로 보냅니다.
        // ★ 이게 없으면 화면이 조용히 죽어도 아무 데도 안 보입니다 ★
        //   실제로 그런 적이 있습니다 — 초록 점은 켜져 있고 화면만 비었습니다.
        web.webChromeClient = object : WebChromeClient() {
            /**
             * 화면이 마이크를 달라고 할 때.
             *
             * ★ 안 넣으면 조용히 막힙니다 ★
             *   브라우저에서는 되는데 앱에서만 안 되는 일이 여기서
             *   생깁니다. WebView 는 **기본으로 아무것도 안 줍니다** —
             *   물어보지도 않고 거절합니다. 화면에는 권한 거부처럼
             *   보이고, 사람은 폰 설정을 뒤지게 됩니다.
             *
             *   앱 권한(RECORD_AUDIO)과 이것, **둘 다** 있어야 합니다.
             */
            override fun onPermissionRequest(req: PermissionRequest) {
                val want = req.resources.filter {
                    it == PermissionRequest.RESOURCE_AUDIO_CAPTURE
                }
                val mine = ContextCompat.checkSelfPermission(
                    this@MainActivity, Manifest.permission.RECORD_AUDIO
                ) == PackageManager.PERMISSION_GRANTED
                // ★ 준 것도 적습니다 ★
                //   거절할 때만 적으면, Logcat 에 아무것도 없을 때 그게
                //   "줬다" 인지 "아예 안 물어봤다" 인지 구별이 안 됩니다.
                //   물어봐 놓고 답을 못 읽는 꼴입니다.
                Log.i("마이크", "화면이 달랍니다: ${req.resources.joinToString()}" +
                        "  (온 곳 ${req.origin}, 앱 권한 ${if (mine) "있음" else "없음"})")
                runOnUiThread {
                    if (want.isNotEmpty() && mine) {
                        req.grant(want.toTypedArray())
                        Log.i("마이크", "줬습니다")
                    } else {
                        // 카메라 같은 것은 안 줍니다. 달라고 한 적도 없고,
                        // 쓰지도 않습니다.
                        req.deny()
                        if (want.isNotEmpty()) {
                            Log.w("마이크", "앱 권한이 없어 못 줍니다")
                            askMic()
                        }
                    }
                }
            }

            override fun onConsoleMessage(m: ConsoleMessage): Boolean {
                Log.i("화면", "[${m.messageLevel()}] ${m.message()}" +
                        "  (${m.sourceId()}:${m.lineNumber()})")
                return true
            }
        }

        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true                    // localStorage
            mediaPlaybackRequiresUserGesture = false
            // ★ 페이지는 앱 안에 있으니 캐시할 이유가 없습니다 ★
            //   고쳐 넣었는데 옛 화면이 뜨면, '안 들어갔나' 를 의심하며
            //   엉뚱한 데를 뒤지게 됩니다. 그 몇 밀리초를 아낄 값어치가
            //   없습니다.
            cacheMode = WebSettings.LOAD_NO_CACHE
        }

        // 뒤로 가기로 앱이 툭 꺼지지 않게 — 시연 중에 제일 나쁜 일입니다.
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (web.canGoBack()) web.goBack()
                // 아니면 아무 일도 안 합니다. 끄려면 홈으로 나가면 됩니다.
            }
        })

        web.addJavascriptInterface(Bridge(), "app")

        // ★ 마이크 권한은 **미리** 받아둡니다 ★
        //   화면이 달라고 하는 순간에 받으려 하면, 그때 물음창이 뜨고
        //   사람이 누르는 사이에 getUserMedia 가 이미 거절당합니다.
        //   시연 중에 그러면 "왜 안 되지" 로 몇 분이 갑니다.
        askMic()

        // 저장된 PC 가 있으면 그리로, 없으면 설정 화면으로.
        val first = pcUrl() ?: "$ORIGIN/index.html"
        here = first          // onPageStarted 보다 화면이 먼저 물어볼 수 있습니다
        web.loadUrl(first)
    }

    /** 앱 권한이 없으면 한 번 물어봅니다. 있으면 아무 일도 안 합니다. */
    private fun askMic() {
        val ok = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        if (!ok) {
            requestPermissions(arrayOf(Manifest.permission.RECORD_AUDIO), 1)
        }
    }

    /** 한 줄 알림. 화면이 아니라 앱이 말해야 하는 것들에 씁니다. */
    private fun say(text: String) {
        runOnUiThread {
            AlertDialog.Builder(this)
                .setMessage(text)
                .setPositiveButton("알겠습니다", null)
                .show()
        }
    }

    /**
     * 처음 붙는 PC 의 지문을 보여주고 묻습니다.
     *
     * ※ 사람이 이 지문을 **어디와** 견줄 수 있어야 합니다. remote.py 가
     *   띄울 때 같은 값을 콘솔에 찍습니다 — 그 두 줄이 같으면 맞습니다.
     */
    private fun askFirstTime(handler: SslErrorHandler, host: String?, finger: String) {
        runOnUiThread {
            AlertDialog.Builder(this)
                .setTitle("처음 붙는 PC 입니다")
                .setMessage(
                    "$host\n\n인증서 지문\n$finger\n\n" +
                    "PC 화면에 찍힌 지문과 같습니까?\n" +
                    "같으면 기억해 두고, 다음부터는 안 묻습니다."
                )
                .setCancelable(false)
                .setPositiveButton("같습니다") { _, _ ->
                    prefs.edit().putString(KEY_FINGER, finger).apply()
                    handler.proceed()
                }
                .setNegativeButton("아닙니다") { _, _ -> handler.cancel() }
                .show()
        }
    }

    /**
     * 인증서의 지문 (SHA-256).
     *
     * ★ API 29 아래에서는 못 읽습니다 ★
     *   SslCertificate 에서 진짜 X.509 를 꺼내는 길이 그때 생겼습니다.
     *   minSdk 가 26 이라 이 앱은 더 낮은 기기에도 깔립니다. 그런
     *   기기에서는 **null 을 돌려주고, 부르는 쪽이 통과를 막습니다.**
     *   못 읽는 것을 '괜찮다' 로 치면 검사 자체가 없는 것과 같습니다.
     */
    @SuppressLint("NewApi")
    private fun fingerprintOf(error: SslError): String? {
        // ★ 검사 모양을 lint 가 알아보게 씁니다 ★
        //   `if (낮으면) null else 쓴다` 로 적었더니 lint 가 못 알아보고
        //   빨간 줄을 그었습니다. **먼저 막고 그 다음에 쓰는** 모양이
        //   사람에게도 읽기 쉽습니다.
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) return null
        return try {
            val cert = error.certificate.x509Certificate ?: return null
            java.security.MessageDigest.getInstance("SHA-256")
                .digest(cert.encoded)
                .joinToString(":") { "%02X".format(it) }
        } catch (e: Throwable) {
            Log.w("인증서", "지문을 못 냈습니다: ${e.message}")
            null
        }
    }

    /**
     * 우리 주소로 가는 요청을 **나가기 전에** 가로채 assets 에서 꺼내줍니다.
     *
     * androidx.webkit 의 WebViewAssetLoader 가 같은 일을 하지만, 그 쪽을
     * 쓰려면 의존성 버전을 하나 더 정해야 합니다. 하는 일이 이만큼이라
     * 직접 둡니다 — 나중에 다리를 끼울 자리도 여기입니다.
     */
    private fun serve(url: Uri): WebResourceResponse? {
        if ("${url.scheme}://${url.host}" != ORIGIN) return null   // 우리 것이 아님
        val path = (url.path ?: "/").removePrefix("/").ifEmpty { "index.html" }
        return try {
            WebResourceResponse(mimeOf(path), "utf-8", assets.open(path))
        } catch (e: Exception) {
            Log.w("화면", "assets 에 '$path' 가 없습니다")
            WebResourceResponse(
                "text/plain", "utf-8", 404, "Not Found", emptyMap(),
                ByteArrayInputStream("'$path' 를 못 찾았습니다".toByteArray())
            )
        }
    }

    private fun mimeOf(path: String): String = when {
        path.endsWith(".html") -> "text/html"
        path.endsWith(".js") -> "text/javascript"
        path.endsWith(".css") -> "text/css"
        path.endsWith(".json") -> "application/json"
        path.endsWith(".svg") -> "image/svg+xml"
        path.endsWith(".png") -> "image/png"
        path.endsWith(".wav") -> "audio/wav"
        path.endsWith(".mp3") -> "audio/mpeg"
        else -> "application/octet-stream"
    }

    /**
     * 페이지가 앱에게 물어볼 수 있는 것들.
     *
     * ※ 이름은 영문으로 둡니다. 한글 식별자도 문법상 되지만, 제가 빌드해
     *   볼 수 없는 코드에 굳이 드문 것을 쓰지 않습니다.
     */
    inner class Bridge {

        /**
         * 이 부탁이 **우리 화면**에서 온 것인가.
         *
         * ★ 왜 이게 생겼는가 ★
         *   여태 앱은 assets 안의 페이지만 열었습니다. 그러니 다리를
         *   부를 수 있는 것도 우리 페이지뿐이었습니다.
         *
         *   이제 PC 의 주소를 엽니다. addJavascriptInterface 는 **어느
         *   페이지에나** 붙으므로, 엉뚱한 데로 흘러간 화면이 로봇에게
         *   악수를 걸 수 있게 됩니다. 그래서 부를 때마다 어디인지 봅니다.
         */
        private fun mine(): Boolean {
            // ★ web.url 을 여기서 읽으면 안 됩니다 ★
            //   여기는 JavaBridge 실입니다. 위의 `here` 에 적어둔 값을
            //   씁니다 — 까닭은 그 선언 옆에 적어뒀습니다.
            val url = here
            if (url.isEmpty()) return false
            if (url.startsWith("$ORIGIN/")) return true
            val pc = pcUrl() ?: return false
            return url.startsWith(pc)
        }

        /** 화면이 PC 주소를 정합니다. 다음 실행부터 거기로 엽니다. */
        @JavascriptInterface
        fun savePc(ipPort: String): Boolean {
            if (!mine()) return false
            val clean = ipPort.trim().removePrefix("https://").trimEnd('/')
            // ★ 정규식을 안 씁니다 ★
            //   코틀린 문자열 안의 $ 는 '값 끼워넣기' 시작입니다. 정규식의
            //   '끝' 표시와 부딪히고, 이스케이프로 피하려다 두 번 틀렸습니다
            //   ($ → \$ → \\$ 가 다 다른 뜻입니다).
            //   그냥 풀어 쓰면 헷갈릴 자리가 없습니다. 읽기도 낫습니다.
            val bits = clean.split(":")
            if (bits.size != 2) return false
            val host = bits[0]
            val port = bits[1].toIntOrNull() ?: return false
            if (port !in 1..65535) return false
            if (host.isEmpty() || host.any { it != '.' && !it.isDigit() }) return false
            // ★ 주소가 바뀌면 지문도 버립니다 ★
            //   PC 는 IP 마다 인증서를 새로 만듭니다 (web_mic.make_cert).
            //   옛 지문을 남겨두면 새 PC 에서 "인증서가 바뀌었습니다" 가
            //   뜨는데, 그건 사실이 아니라 **우리가 안 지운 탓**입니다.
            //   거짓 경보가 한 번 울리면 다음 진짜 경보도 무시됩니다.
            val was = prefs.getString(KEY_PC, null)
            // apply {} (코틀린 확장) 와 apply() (Editor 의 메서드) 가
            // 이름이 같습니다. 붙여 쓰면 사람도 헷갈립니다 — 풀어 씁니다.
            val edit = prefs.edit()
            edit.putString(KEY_PC, clean)
            if (was != clean) edit.remove(KEY_FINGER)
            edit.apply()
            return true
        }

        /** 지금 정해진 PC 주소. 없으면 빈 글자. */
        @JavascriptInterface
        fun pc(): String = if (mine()) prefs.getString(KEY_PC, "") ?: "" else ""

        /** 기억한 인증서 지문. 없으면 빈 글자 — 아직 안 붙어본 것입니다. */
        @JavascriptInterface
        fun finger(): String = if (mine()) prefs.getString(KEY_FINGER, "") ?: "" else ""

        /** PC 를 잊습니다. 다음 실행 때 설정 화면이 뜹니다. */
        @JavascriptInterface
        fun forgetPc(): Boolean {
            if (!mine()) return false
            prefs.edit().remove(KEY_PC).remove(KEY_FINGER).apply()
            return true
        }

        /** 지금 바로 그 주소를 엽니다. */
        @JavascriptInterface
        fun openPc(): Boolean {
            if (!mine()) return false
            val url = pcUrl() ?: return false
            runOnUiThread { web.loadUrl(url) }
            return true
        }

        /** 설정 화면으로 돌아갑니다 — PC 화면에서도 부를 수 있어야 합니다. */
        @JavascriptInterface
        fun openSetup(): Boolean {
            if (!mine()) return false
            runOnUiThread { web.loadUrl("$ORIGIN/index.html") }
            return true
        }

        @JavascriptInterface
        fun device(): String = "${Build.MANUFACTURER} ${Build.MODEL}"

        @JavascriptInterface
        fun androidVersion(): String =
            "${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})"

        @JavascriptInterface
        fun appVersion(): String =
            packageManager.getPackageInfo(packageName, 0).versionName ?: "?"

        /**
         * 시그널링 다리 — 화면이 못 하는 두 번의 HTTP 를 대신 해줍니다.
         *
         * ★ 왜 답을 그냥 돌려주지 않는가 ★
         *   여기는 WebView 의 자바브리지 스레드입니다. 네트워크를 써도
         *   되지만, 답이 올 때까지 **화면의 자바스크립트가 통째로
         *   멈춥니다.** 악수는 8초까지 걸릴 수 있습니다. 멈춘 화면은
         *   고장난 화면과 구별이 안 갑니다 — 그 8초 동안 사용자는
         *   앱이 죽었다고 생각합니다.
         *
         *   그래서 배경 스레드로 보내고, 끝나면 화면의 함수를 불러
         *   알려줍니다. 화면 쪽은 sig.js 가 그걸 약속(Promise)으로
         *   감싸주니, 부르는 쪽은 그냥 await 하면 됩니다.
         *
         * @param callId 화면이 만든 이름표. 어느 부탁의 답인지 짝을 맞춥니다.
         */
        @JavascriptInterface
        fun handshake(
            ip: String, port: Int, offerSdp: String, aesKey: String, callId: String
        ) {
            if (!mine()) {
                Log.w("다리", "우리 화면이 아닙니다 — 악수를 안 합니다")
                return
            }
            Thread {
                val steps = StringBuilder()
                val res = JSONObject()
                try {
                    val sdp = Sig.handshake(
                        ip, offerSdp,
                        if (aesKey.isBlank()) null else aesKey,
                        port
                    ) { name, detail ->
                        if (steps.length > 0) steps.append("\n")
                        steps.append("$name — $detail")
                        Log.i("다리", "$name — $detail")
                    }
                    Log.i("다리", "악수 성공 · 응답 ${sdp.length}글자")
                    res.put("ok", true).put("sdp", sdp)
                } catch (e: Throwable) {
                    Log.w("다리", "악수 실패: ${e.message}")
                    res.put("ok", false).put("why", e.message ?: e.toString())
                }
                res.put("steps", steps.toString())
                // ★ evaluateJavascript 는 UI 스레드에서만 됩니다 ★
                val js = "window.__sigDone(${JSONObject.quote(callId)}, $res)"
                runOnUiThread { web.evaluateJavascript(js, null) }
            }.start()
        }
    }
}
