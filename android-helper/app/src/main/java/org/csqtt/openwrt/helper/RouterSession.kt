package org.csqtt.openwrt.helper

import org.json.JSONObject
import java.io.Closeable
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import java.util.concurrent.ConcurrentHashMap
import javax.net.ssl.*

class RouterSession(val pairing: Pairing) : Closeable {
    private val context = SSLContext.getInstance("TLS").apply {
        init(null, arrayOf(object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, auth: String) { throw java.security.cert.CertificateException("Client certificate not expected") }
            override fun checkServerTrusted(chain: Array<X509Certificate>, auth: String) {
                require(chain.isNotEmpty())
                chain[0].checkValidity()
                require(pin(chain[0]) == pairing.pin) { "Router certificate changed" }
            }
        }), SecureRandom())
    }
    private val pool = Executors.newFixedThreadPool(18)
    private val slots = Semaphore(8)
    private val sockets = ConcurrentHashMap.newKeySet<Socket>()
    private var listener: ServerSocket? = null
    @Volatile private var closed = false
    @Volatile private var session = ""
    var expires: Long = 0; private set
    private fun pin(cert: X509Certificate) = MessageDigest.getInstance("SHA-256").digest(cert.encoded).joinToString("") { "%02x".format(it.toInt() and 255) }

    fun request(path: String, body: JSONObject? = null, credential: String = session): JSONObject {
        check(!closed)
        val conn = URL("https://${pairing.host}:${pairing.port}$path").openConnection() as HttpsURLConnection
        conn.sslSocketFactory = context.socketFactory
        conn.hostnameVerifier = HostnameVerifier { host, ssl -> host == pairing.host && runCatching { pin(ssl.peerCertificates[0] as X509Certificate) == pairing.pin }.getOrDefault(false) }
        conn.connectTimeout = 10000; conn.readTimeout = 15000
        conn.setRequestProperty("Authorization", "Bearer $credential")
        conn.setRequestProperty("Accept", "application/json")
        try {
            if (body != null) { conn.requestMethod = "POST"; conn.doOutput = true; conn.setRequestProperty("Content-Type", "application/json"); conn.outputStream.use { it.write(body.toString().toByteArray()) } }
            require(conn.responseCode == 200) { "Роутер отклонил запрос (${conn.responseCode})" }
            val bytes = conn.inputStream.use { it.readNBytes(32769) }
            require(bytes.size <= 32768)
            return JSONObject(String(bytes, Charsets.UTF_8))
        } finally { conn.disconnect() }
    }
    fun claim(): String {
        val data = request("/v1/challenge", credential = pairing.grant)
        require(data.getString("id") == pairing.id)
        val redirect = data.getString("redirect_uri"); require(allowedVk(redirect))
        session = data.getString("session"); require(session.matches(Regex("[a-f0-9]{64}")))
        expires = data.getLong("expires_at"); require(expires > System.currentTimeMillis() / 1000)
        return redirect
    }
    fun submit(token: String) { require(token.length in 1..16384 && !token.contains('\n') && !token.contains('\r')); request("/v1/result", JSONObject().put("id", pairing.id).put("token", token)) }
    fun cancel() { if (session.isNotEmpty()) runCatching { request("/v1/cancel", JSONObject()) } }

    // WebView talks only to loopback. Native code adds router authentication and TLS pinning.
    fun startRelay(): Int {
        check(session.isNotEmpty())
        val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1")); listener = server
        pool.execute {
            while (!closed) {
                val browser = try { server.accept() } catch (_: Exception) { break }
                if (!slots.tryAcquire()) { browser.close(); continue }
                sockets.add(browser)
                pool.execute {
                    var router: SSLSocket? = null
                    try {
                        browser.soTimeout = 15000
                        val head = readHeader(browser)
                        val fields = head.lineSequence().first().split(' ')
                        require(fields.size == 3 && fields[0] == "CONNECT" && fields[2] == "HTTP/1.1")
                        val destination = fields[1]
                        require(destination.endsWith(":443") && allowedVk("https://${destination.removeSuffix(":443")}/"))
                        require(System.currentTimeMillis() / 1000 < expires)
                        router = context.socketFactory.createSocket(pairing.host, pairing.port) as SSLSocket
                        sockets.add(router)
                        router.soTimeout = 15000; router.startHandshake()
                        router.outputStream.write(("CONNECT $destination HTTP/1.1\r\nHost: $destination\r\nAuthorization: Bearer $session\r\n\r\n").toByteArray(Charsets.US_ASCII))
                        require(readHeader(router).startsWith("HTTP/1.1 200 "))
                        browser.outputStream.write("HTTP/1.1 200 Connection Established\r\n\r\n".toByteArray())
                        val timeout = ((expires - System.currentTimeMillis() / 1000).coerceIn(1, 300) * 1000).toInt()
                        browser.soTimeout = timeout; router.soTimeout = timeout
                        val remote = router
                        pool.execute { try { remote.inputStream.copyTo(browser.outputStream) } catch (_: Exception) {} finally { runCatching { browser.close() }; runCatching { remote.close() } } }
                        browser.inputStream.copyTo(router.outputStream)
                    } catch (_: Exception) {
                        runCatching { browser.outputStream.write("HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n".toByteArray()) }
                    } finally {
                        runCatching { browser.close() }; sockets.remove(browser)
                        router?.let { runCatching { it.close() }; sockets.remove(it) }; slots.release()
                    }
                }
            }
        }
        return server.localPort
    }
    private fun readHeader(socket: Socket): String {
        val out = java.io.ByteArrayOutputStream()
        while (out.size() < 8192) { val byte = socket.inputStream.read(); require(byte >= 0); out.write(byte); if (byte == 10 && out.toString("US-ASCII").endsWith("\r\n\r\n")) return out.toString("US-ASCII") }
        error("HTTP header too large")
    }
    override fun close() { closed = true; runCatching { listener?.close() }; sockets.forEach { runCatching { it.close() } }; sockets.clear(); pool.shutdownNow() }
}
