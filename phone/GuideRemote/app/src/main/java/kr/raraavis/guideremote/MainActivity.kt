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
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
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
 * ★ 지금은 그 하나가 아직 없습니다 ★
 *   이 파일은 **통로가 뚫리는지만** 봅니다. 빌드되고, 폰에 깔리고,
 *   WebView 가 뜨고, 우리 페이지가 보이는지. 그것부터 확인하고 나서
 *   다리를 놓습니다.
 *
 *   '만들었다' 와 '보인다' 는 다릅니다 — 이 저장소에서 네 번 겪었습니다.
 *   하물며 이건 제가(작성한 AI가) 빌드해 볼 수 없는 첫 코드입니다.
 *   그래서 처음 것을 최대한 작게 만듭니다. 틀렸을 때 어디가 틀렸는지
 *   바로 보이도록요.
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
    }
}
