package kr.raraavis.guideremote

import android.util.Base64
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.Proxy
import java.net.URL
import java.nio.ByteBuffer
import java.security.KeyFactory
import java.security.interfaces.RSAPublicKey
import java.security.spec.X509EncodedKeySpec
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * 악수가 안 된 이유를 사람 말로 담습니다.
 *
 * 이 다리에서 나는 오류는 거의 다 "어디까지 갔다가 무엇 때문에 막혔다"
 * 로 말할 수 있습니다. 자바 예외 이름만 던지면 폰 화면에서 아무 쓸모가
 * 없습니다.
 */
class SignalError(message: String) : RuntimeException(message)

/**
 * 시그널링 다리 — 브라우저가 못 하는 두 번의 HTTP.
 *
 * ★ 이 파일은 sig.py 를 옮긴 것입니다 ★
 *   원본은 저장소 뿌리의 sig.py 이고, 그 명세를 지키는 시험이
 *   sig_test.py 입니다 (가짜 로봇과 실제로 악수합니다). 여기를 고치면
 *   저기도 같이 고쳐야 합니다. 둘이 갈라지면 시험이 거짓말을 합니다.
 *
 * ★ 왜 네이티브로 와야 했는가 ★
 *   web_probe.py 로 재봤더니 브라우저가 막히는 곳은 딱 두 군데였습니다.
 *
 *       GET  http://<로봇>:9991/con_notify        CORS 로 막힘
 *       POST http://<로봇>:9991/con_ing_<토큰>    CORS 로 막힘
 *
 *   그 뒤의 WebRTC · 데이터채널 · 오디오 · 안내 로직은 전부 브라우저가
 *   그냥 합니다. 게다가 이 두 요청에 쓰는 암호를 브라우저 표준으로는
 *   못 합니다 — WebCrypto 에 ECB 가 없고, RSA 는 OAEP 만 합니다.
 *
 *   그래서 **앱이 해야 하는 일은 이 파일이 하는 일 전부이고, 그게
 *   전부입니다.**
 *
 * ★ 옮기면서 조심한 곳 셋 ★
 *
 *   1. AES 키는 hex 를 **디코드하지 않습니다.**
 *      32글자 hex 문자열을 그대로 32바이트로 씁니다 → AES-256.
 *      디코드하면 16바이트가 되어 AES-128 이 되고, 로봇이 거절합니다.
 *
 *   2. GCM 조각 배치가 흔한 순서와 반대입니다.
 *
 *          [ 암호문 ... ][ nonce 12바이트 ][ 태그 16바이트 ]
 *
 *      보통은 nonce 가 앞에 옵니다. 여기서는 뒤입니다. 놓치면 태그
 *      검사에서 떨어지는데, 왜인지는 안 알려줍니다.
 *
 *   3. base64 에 줄바꿈을 넣으면 안 됩니다 (NO_WRAP).
 *      안드로이드의 Base64 는 기본값이 줄을 접습니다. 파이썬 쪽은 안
 *      접습니다. 접힌 채로 보내면 로봇이 못 읽습니다.
 */
object Sig {

    /** data2 == 2 인 로봇(구형 펌웨어)이 쓰는 고정 키. */
    val LEGACY_GCM_KEY = byteArrayOf(
        232.toByte(), 86.toByte(), 130.toByte(), 189.toByte(),
        22.toByte(), 84.toByte(), 155.toByte(), 0.toByte(),
        142.toByte(), 4.toByte(), 166.toByte(), 104.toByte(),
        43.toByte(), 179.toByte(), 235.toByte(), 227.toByte()
    )

    /** con_ing_<토큰> 을 만들 때 쓰는 글자표. */
    private const val PATH_ALPHABET = "ABCDEFGHIJ"

    // ── 암호 ─────────────────────────────────────────────────

    private fun b64(data: ByteArray): String =
        Base64.encodeToString(data, Base64.NO_WRAP)   // ★ 줄을 접지 않습니다

    private fun unb64(text: String): ByteArray =
        Base64.decode(text, Base64.DEFAULT)

    /**
     * AES-ECB + PKCS5. 키는 32글자 hex 문자열을 **그대로 바이트로** 씁니다.
     * (hex 디코드가 아닙니다 — 32글자 → 32바이트 → AES-256)
     */
    fun aesEcbEncrypt(text: String, key: String): String {
        val c = Cipher.getInstance("AES/ECB/PKCS5Padding")
        c.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key.toByteArray(Charsets.UTF_8), "AES"))
        return b64(c.doFinal(text.toByteArray(Charsets.UTF_8)))
    }

    fun aesEcbDecrypt(b64Text: String, key: String): String {
        val raw = unb64(b64Text)
        if (raw.isEmpty()) throw SignalError("빈 응답을 받았습니다.")
        if (raw.size % 16 != 0) throw SignalError("응답 길이가 블록 크기에 안 맞습니다.")
        return try {
            val c = Cipher.getInstance("AES/ECB/PKCS5Padding")
            c.init(Cipher.DECRYPT_MODE, SecretKeySpec(key.toByteArray(Charsets.UTF_8), "AES"))
            String(c.doFinal(raw), Charsets.UTF_8)
        } catch (e: Exception) {
            throw SignalError("응답을 못 풀었습니다 — 키가 다르거나 깨졌습니다.")
        }
    }

    /** 이번 악수에만 쓰는 키 — uuid4 를 hex 32글자로. */
    fun newAesKey(): String {
        val u = UUID.randomUUID()
        val bytes = ByteBuffer.allocate(16)
            .putLong(u.mostSignificantBits)
            .putLong(u.leastSignificantBits)
            .array()
        val sb = StringBuilder(32)
        for (b in bytes) sb.append(String.format("%02x", b))
        return sb.toString()
    }

    /**
     * RSA PKCS1 v1.5. 키 크기보다 길면 나눠서 붙입니다.
     * pemB64 는 base64 로 감싼 DER 입니다 (PEM 머리말이 없습니다).
     */
    fun rsaEncrypt(text: String, pemB64: String): String {
        val pub = try {
            KeyFactory.getInstance("RSA")
                .generatePublic(X509EncodedKeySpec(unb64(pemB64))) as RSAPublicKey
        } catch (e: Exception) {
            throw SignalError("로봇이 준 공개키를 못 읽었습니다 (${e.javaClass.simpleName}).")
        }
        val size = (pub.modulus.bitLength() + 7) / 8
        val chunk = size - 11
        if (chunk <= 0) throw SignalError("공개키가 너무 작습니다.")
        val c = Cipher.getInstance("RSA/ECB/PKCS1Padding")
        c.init(Cipher.ENCRYPT_MODE, pub)
        val data = text.toByteArray(Charsets.UTF_8)
        val out = ByteArrayOutputStream()
        var i = 0
        while (i < data.size) {
            val end = if (i + chunk < data.size) i + chunk else data.size
            out.write(c.doFinal(data, i, end - i))
            i = end
        }
        return b64(out.toByteArray())
    }

    private fun hexToBytes(hex: String): ByteArray {
        if (hex.length % 2 != 0) throw SignalError("AES 키가 hex 가 아닙니다 (32글자여야 합니다).")
        val out = ByteArray(hex.length / 2)
        for (i in out.indices) {
            val v = hex.substring(i * 2, i * 2 + 2).toIntOrNull(16)
                ?: throw SignalError("AES 키가 hex 가 아닙니다 (32글자여야 합니다).")
            out[i] = v.toByte()
        }
        return out
    }

    /**
     * con_notify 가 준 data1 을 풉니다.
     *
     *     data2 == 1 (또는 없음)   이미 평문
     *     data2 == 2               고정 키로 GCM 복호
     *     data2 == 3               이 로봇만의 AES-128 키로 GCM 복호
     */
    fun decryptData1(data1B64: String, data2: String?, aes128Key: String?): String {
        if (data2 == null || data2 == "1" || data2 == "null") return data1B64
        val raw = unb64(data1B64)
        if (raw.size < 28) throw SignalError("data1 이 너무 짧습니다 (28바이트 미만).")

        // ★ nonce 가 뒤에 있습니다 ★  [암호문][nonce 12][태그 16]
        val tag = raw.copyOfRange(raw.size - 16, raw.size)
        val nonce = raw.copyOfRange(raw.size - 28, raw.size - 16)
        val body = raw.copyOfRange(0, raw.size - 28)

        val key: ByteArray = when (data2) {
            "2" -> LEGACY_GCM_KEY
            "3" -> {
                val hex = (aes128Key ?: "").trim().lowercase()
                if (hex.isEmpty()) throw SignalError(
                    "이 로봇은 자기만의 AES-128 키를 요구합니다 (data2=3).\n" +
                        "  →  PC 에서  .\\run get_aes_key.py  로 발급받아 넣으세요."
                )
                val k = hexToBytes(hex)
                if (k.size != 16) throw SignalError(
                    "AES 키는 16바이트(32글자)여야 하는데 ${k.size}바이트입니다."
                )
                k
            }
            else -> throw SignalError("모르는 data2 값입니다: $data2")
        }

        return try {
            val c = Cipher.getInstance("AES/GCM/NoPadding")
            c.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
            String(c.doFinal(body + tag), Charsets.UTF_8)
        } catch (e: Exception) {
            throw SignalError(
                "AES 키를 로봇이 거부했습니다 (태그 검사 실패).\n" +
                    "  → 이 로봇의 SN 으로 받은 키가 맞는지 확인하세요."
            )
        }
    }

    /**
     * con_ing_<여기> 를 계산합니다.
     * 마지막 10글자를 두 글자씩 끊고, **뒷글자**를 A=0 … J=9 로 바꿔 이어 붙입니다.
     */
    fun pathEnding(data1: String): String {
        val tail = if (data1.length >= 10) data1.substring(data1.length - 10) else data1
        val sb = StringBuilder()
        var i = 0
        while (i + 1 < tail.length) {
            val idx = PATH_ALPHABET.indexOf(tail[i + 1])
            if (idx >= 0) sb.append(idx)
            i += 2
        }
        return sb.toString()
    }

    /** data1 에서 공개키만 떼어냅니다 — 앞뒤 10글자가 껍데기입니다. */
    fun publicKeyOf(data1: String): String {
        if (data1.length <= 20) throw SignalError("data1 이 짧아서 공개키를 못 꺼냅니다.")
        return data1.substring(10, data1.length - 10)
    }

    // ── HTTP ─────────────────────────────────────────────────

    /**
     * 랜 안의 로봇에게 보냅니다. 한 번 실패하면 한 번만 다시 겁니다.
     *
     * ★ 왜 다시 거는가 — 실제로 여기서 막혔습니다 ★
     *
     *   진짜 로봇에 처음 붙였을 때 이렇게 났습니다.
     *
     *       con_ing_70219 에 닿지 못했습니다:
     *       IOException: unexpected end of stream
     *
     *   암호는 다 맞았습니다 (그 토큰이 나왔다는 게 증거입니다).
     *   끊긴 건 **소켓을 아껴 쓰다가** 생긴 일입니다. 안드로이드의
     *   HTTP 는 con_notify 에 썼던 연결을 con_ing 에 다시 씁니다.
     *   그런데 로봇은 답을 주고 나서 그 연결을 닫아버립니다. 닫힌
     *   줄 모르고 두 번째 요청을 밀어 넣으면 저 오류가 납니다.
     *
     *   아래 아래에서 Connection: close 를 붙여 애초에 안 아끼게
     *   했지만, 그래도 한 번은 더 걸어봅니다. 랜에서 한 번 끊기는
     *   일은 흔하고, 다시 거는 값이 시연 중에 멈춰 서는 값보다
     *   훨씬 쌉니다.
     */
    private fun http(url: String, body: String?, timeoutMs: Int): String {
        return try {
            httpOnce(url, body, timeoutMs)
        } catch (first: SignalError) {
            if (!first.message.orEmpty().contains("닿지 못했습니다")) throw first
            try {
                Thread.sleep(300)
            } catch (e: InterruptedException) {
                Thread.currentThread().interrupt()
            }
            try {
                httpOnce(url, body, timeoutMs)
            } catch (second: SignalError) {
                throw SignalError("${second.message}\n  (두 번 걸어봤습니다)")
            }
        }
    }

    /**
     * ★ 두 요청 다 POST 입니다 — con_notify 도요 ★
     *
     *   처음에는 con_notify 를 GET 으로 물었습니다. 답은 옵니다. data1 도
     *   오고, 풀리고, 토큰도 나옵니다. 그런데 뒤이은 con_ing 에서 로봇이
     *   답 없이 연결을 끊었습니다.
     *
     *       con_ing_45330 에 닿지 못했습니다:
     *       IOException: unexpected end of stream   (두 번 걸어봤습니다)
     *
     *   PC 라이브러리를 읽어보니 **몸통 없는 POST** 를 씁니다.
     *
     *       def make_local_request(path, body=None, headers=None):
     *           response = requests.post(url=path, data=body, headers=headers)
     *
     *       make_local_request(f"http://{ip}:9991/con_notify", None, None)
     *
     *   나머지는 우리와 똑같습니다 — con_ing 의 헤더도, 몸통의 모양도,
     *   순서도. 그래서 남은 차이가 이것뿐이었습니다. 아마 로봇이 GET
     *   에는 답만 해주고 **세션을 열어두지는 않는** 모양입니다.
     *
     *   짐작으로 고치지 않고 **되는 코드를 읽어서** 맞췄습니다. 앞의 두
     *   번은 짐작이었고, 둘 다 틀렸습니다.
     */
    private const val NO_BODY = ""       // 몸통 없는 POST (Content-Length: 0)

    /** 랜으로 붙을 때 봉투에 적는 이름. */
    const val ENVELOPE_ID = "STA_localNetwork"

    /**
     * 보내기 전에 제안이 말이 되는지 봅니다.
     *
     * ★ 로봇은 어설픈 제안에 아무 말도 안 해줍니다 ★
     *
     *   데이터채널만 든 566글자 제안을 보냈더니 로봇이 **응답 없이
     *   연결을 끊었습니다.** 오류도, 상태 코드도, 거절 메시지도
     *   없습니다. 그 침묵을 보고 네 번 헛짚었습니다 — 소켓 재사용,
     *   오디오 줄, GET 대 POST, 봉투.
     *
     *   PC 에서 라이브러리와 나란히 세워보고서야 갈렸습니다.
     *
     *       토막 SDP (41글자)     라이브러리도 막힘
     *       진짜 제안 (3860글자)   둘 다 통과
     *
     *   그러니 **보내기 전에 우리가 봅니다.** 로봇의 침묵을 문장으로
     *   바꾸는 것이 이 함수의 전부입니다.
     */
    fun checkOffer(sdp: String) {
        if (sdp.isEmpty() || !sdp.contains("v=0")) {
            throw SignalError("SDP 가 아닙니다 ('v=0' 이 없습니다).")
        }
        val media = sdp.lines().count { it.startsWith("m=") }
        if (media == 0) throw SignalError(
            "제안에 미디어 줄(m=)이 하나도 없습니다.\n" +
                "  로봇은 이런 제안에 말없이 연결을 끊습니다.\n" +
                "  데이터채널·비디오·오디오를 갖춘 제안을 만들어 주세요."
        )
        if (sdp.length < 500) throw SignalError(
            "제안이 너무 짧습니다 (${sdp.length}글자, m= 줄 ${media}개).\n" +
                "  로봇이 받는 진짜 제안은 3천 글자 남짓입니다.\n" +
                "  이대로 보내면 로봇이 말없이 끊습니다."
        )
    }

    /**
     * SDP 를 로봇이 기다리는 봉투에 담습니다.
     *
     * ★ 여기서 세 번 헛짚었습니다 ★
     *
     *   맨 SDP 를 암호화해 보냈더니 로봇이 **말없이 연결을 끊었습니다.**
     *   오류도, 상태 코드도 없이 그냥 끊깁니다. 그 침묵을 보고 저는
     *   차례로 이렇게 짐작했습니다.
     *
     *       1. 소켓을 아껴 쓰다 닫힌 것을 다시 썼다   → 아니었습니다
     *       2. 로봇이 SDP 에 오디오 줄을 요구한다      → 아니었습니다
     *       3. con_notify 를 GET 으로 물어서다        → 아니었습니다
     *                                                  (POST 가 맞긴 합니다)
     *
     *   셋 다 오류 문구만 보고 세운 짐작이었습니다. **되는 코드를 열어
     *   보니** 답이 거기 있었습니다 — 라이브러리는 SDP 를 그냥 안 보내고
     *   JSON 봉투에 담습니다. 로봇은 푼 것을 JSON 으로 읽으니, 맨 SDP 는
     *   파싱에서 넘어지고 연결이 그대로 닫힙니다.
     *
     *   token 은 클라우드 로그인을 했을 때만 값이 있습니다. 랜으로만
     *   붙는 우리는 빈 문자열입니다.
     */
    fun wrapOffer(sdp: String, token: String = ""): String =
        JSONObject()
            .put("id", ENVELOPE_ID)
            .put("sdp", sdp)
            .put("type", "offer")
            .put("token", token)
            .toString()

    /** 돌아온 봉투에서 SDP 를 꺼냅니다. */
    fun unwrapAnswer(text: String): String {
        val got = try {
            JSONObject(text)
        } catch (e: Exception) {
            throw SignalError(
                "응답이 JSON 이 아닙니다 — 봉투 모양이 바뀌었을 수 있습니다.\n" +
                    "  받은 것 앞부분: ${text.take(80)}"
            )
        }
        val sdp = got.optString("sdp", "")
        if (sdp == "reject") throw SignalError(
            "로봇이 거절했습니다 — 이미 다른 곳과 연결돼 있습니다.\n" +
                "  → 유니트리 앱이나 PC 스크립트를 먼저 끊으세요."
        )
        if (sdp.isEmpty()) throw SignalError("응답에 sdp 가 없습니다.")
        return sdp
    }

    /**
     * 한 번 보냅니다. **프록시를 거치지 않습니다.**
     *
     * 학교 망처럼 프록시가 잡혀 있으면 랜 주소를 바깥으로 보내려다
     * 조용히 시간만 끕니다. 파이썬 쪽에서 실제로 겪은 자리라 여기도
     * 똑같이 막아둡니다.
     */
    private fun httpOnce(url: String, body: String?, timeoutMs: Int): String {
        val conn = try {
            URL(url).openConnection(Proxy.NO_PROXY) as HttpURLConnection
        } catch (e: Exception) {
            throw SignalError("$url 을 열지 못했습니다: ${e.javaClass.simpleName}")
        }
        try {
            conn.connectTimeout = timeoutMs
            conn.readTimeout = timeoutMs
            conn.useCaches = false
            // ★ 연결을 아껴 쓰지 않습니다 ★
            //   로봇은 답을 주고 연결을 닫습니다. 그런데 그렇다고 말은
            //   안 해줍니다. 우리가 먼저 "쓰고 버리겠다" 고 하면, 다음
            //   요청은 새 연결로 갑니다.
            conn.setRequestProperty("Connection", "close")
            // gzip 을 달라고 하지 않습니다 — 파이썬 쪽과 같은 모양으로
            // 보내야, 파이썬에서 되는 것이 여기서도 됩니다.
            conn.setRequestProperty("Accept-Encoding", "identity")
            // 둘 다 POST 입니다 (위 NO_BODY 설명 참고). con_notify 는 몸통이
            // 비었고 Content-Type 도 안 붙입니다 — 라이브러리가 그렇게 합니다.
            conn.requestMethod = "POST"
            conn.doOutput = true
            val bytes = (body ?: "").toByteArray(Charsets.UTF_8)
            if (bytes.isNotEmpty()) {
                conn.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
            }
            conn.setFixedLengthStreamingMode(bytes.size)
            conn.outputStream.use { if (bytes.isNotEmpty()) it.write(bytes) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader(Charsets.UTF_8)?.use { it.readText() } ?: ""
            if (code !in 200..299) {
                throw SignalError("$url 이 $code 을 돌려줬습니다: ${text.take(200)}")
            }
            return text
        } catch (e: SignalError) {
            throw e
        } catch (e: Exception) {
            throw SignalError("$url 에 닿지 못했습니다: ${e.javaClass.simpleName}: ${e.message}")
        } finally {
            try {
                conn.disconnect()
            } catch (e: Exception) {
                // 끊는 데 실패한 것은 알릴 것이 없습니다
            }
        }
    }

    // ── 계약 ─────────────────────────────────────────────────

    /**
     * SDP 제안을 주면 SDP 응답을 돌려줍니다. **이것이 다리의 전부입니다.**
     *
     * 로봇에 아무것도 시키지 않습니다 — 연결을 맺는 첫 악수일 뿐입니다.
     * trace 를 주면 단계마다 불러줍니다 (어디서 막혔는지 보려고).
     *
     * ※ 네트워크를 씁니다. 반드시 배경 스레드에서 부르세요.
     */
    fun handshake(
        ip: String,
        offerSdp: String,
        aes128Key: String? = null,
        port: Int = 9991,
        timeoutMs: Int = 8000,
        cloudToken: String = "",
        trace: ((String, String) -> Unit)? = null
    ): String {
        checkOffer(offerSdp)        // 로봇의 침묵을 문장으로 바꿉니다
        val base = "http://$ip:$port"

        trace?.invoke("1. con_notify", "$base/con_notify")
        val raw = http("$base/con_notify", NO_BODY, timeoutMs)

        val info = try {
            JSONObject(String(unb64(raw), Charsets.UTF_8))
        } catch (e: Exception) {
            throw SignalError("con_notify 응답을 못 읽었습니다: ${e.javaClass.simpleName}")
        }
        val data2 = if (info.isNull("data2")) null else info.get("data2").toString()

        val data1 = decryptData1(info.optString("data1", ""), data2, aes128Key)
        trace?.invoke("2. data1 풀기", "data2=$data2 · ${data1.length}글자")

        val pem = publicKeyOf(data1)
        // ★ 이름을 token 으로 두면 안 됩니다 ★
        //   봉투에 들어가는 token 은 클라우드 로그인 토큰이고, 이건 주소에
        //   붙는 경로입니다. 뜻이 다른데 글자만 같습니다.
        val path = pathEnding(data1)
        trace?.invoke("3. 공개키와 경로", "경로 '$path'")

        val key = newAesKey()
        val envelope = wrapOffer(offerSdp, cloudToken)
        val bodyJson = JSONObject()
            .put("data1", aesEcbEncrypt(envelope, key))
            .put("data2", rsaEncrypt(key, pem))
            .toString()

        trace?.invoke("4. con_ing", "$base/con_ing_$path · 봉투 ${envelope.length}글자")
        val answerRaw = http("$base/con_ing_$path", bodyJson, timeoutMs)

        val answer = unwrapAnswer(aesEcbDecrypt(answerRaw, key))
        trace?.invoke("5. 응답 풀기", "SDP ${answer.length}글자")
        return answer
    }
}
