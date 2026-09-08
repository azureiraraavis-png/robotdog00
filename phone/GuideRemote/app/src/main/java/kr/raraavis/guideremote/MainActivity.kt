package kr.raraavis.guideremote

import android.annotation.SuppressLint
import android.net.Uri
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
import androidx.appcompat.app.AppCompatActivity
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
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        web = findViewById(R.id.web)

        web.webViewClient = object : WebViewClient() {
            override fun shouldInterceptRequest(
                view: WebView, request: WebResourceRequest
            ): WebResourceResponse? = serve(request.url)
        }

        // 페이지가 콘솔에 찍는 것과 **터진 오류**를 로그캣으로 보냅니다.
        // ★ 이게 없으면 화면이 조용히 죽어도 아무 데도 안 보입니다 ★
        //   실제로 그런 적이 있습니다 — 초록 점은 켜져 있고 화면만 비었습니다.
        web.webChromeClient = object : WebChromeClient() {
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
        web.loadUrl("$ORIGIN/index.html")
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
