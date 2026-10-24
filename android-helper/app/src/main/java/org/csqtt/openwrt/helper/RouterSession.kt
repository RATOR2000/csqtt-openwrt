package org.csqtt.openwrt.helper

import org.json.JSONObject
import java.io.Closeable
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.security.cert.CertificateException
import java.security.cert.X509Certificate
import java.util.concurrent.Executors
import java.util.concurrent.Semaphore
import java.util.concurrent.TimeUnit
import javax.net.ssl.*

class RouterSession(val pairing: Pairing) : Closeable {
    private val context = SSLContext.getInstance("TLS").apply {
        init(null, arrayOf(object : X509TrustManager {
            override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
            override fun checkClientTrusted(chain: Array<X509Certificate>, auth: String) {
                throw CertificateException("Client certificate not expected")
            }
            override fun checkServerTrusted(chain: Array<X509Certificate>, auth: String) {
                if (chain.isEmpty()) throw CertificateException("Missing router certificate")
                chain[0].checkValidity()
                if (pin(chain[0]) != pairing.pin) throw CertificateException("Router certificate changed")
            }
        }), SecureRandom())
    }
    private val lifecycle = Any()
    private val pool = Executors.newFixedThreadPool(18)
    private val timer = Executors.newSingleThreadScheduledExecutor()
    private val slots = Semaphore(8)
    private val sockets = mutableSetOf<Socket>()
    private val requests = mutableSetOf<HttpsURLConnection>()
    private var listener: ServerSocket? = null
    @Volatile private var closed = false
    @Volatile private var session = ""
    @Volatile var expires: Long = 0; private set

    private fun pin(cert: X509Certificate) = MessageDigest.getInstance("SHA-256")
        .digest(cert.encoded).joinToString("") { "%02x".format(it.toInt() and 255) }

    private fun track(socket: Socket) = synchronized(lifecycle) {
        if (closed) { socket.close(); error("Session closed") }
        sockets.add(socket)
    }

    private fun closeSocket(socket: Socket) {
        runCatching { socket.close() }
        synchronized(lifecycle) { sockets.remove(socket) }
    }

    private fun checkActive() {
        check(!closed && session.isNotEmpty() && System.currentTimeMillis() / 1000 < expires)
    }

    private fun request(path: String, body: JSONObject? = null, credential: String = session): JSONObject {
        check(!closed)
        val conn = URL("https://${pairing.host}:${pairing.port}$path").openConnection() as HttpsURLConnection
        conn.sslSocketFactory = context.socketFactory
        conn.hostnameVerifier = HostnameVerifier { host, ssl ->
            host == pairing.host && runCatching { pin(ssl.peerCertificates[0] as X509Certificate) == pairing.pin }.getOrDefault(false)
        }
        conn.instanceFollowRedirects = false
        conn.connectTimeout = 10000; conn.readTimeout = 15000
        conn.setRequestProperty("Authorization", "Bearer $credential")
        conn.setRequestProperty("Accept", "application/json")
        synchronized(lifecycle) {
            if (closed) { conn.disconnect(); error("Session closed") }
            requests.add(conn)
        }
        try {
            if (body != null) {
                conn.requestMethod = "POST"; conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json")
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
            }
            require(conn.responseCode == 200) { "Router request rejected" }
            val bytes = conn.inputStream.use { readBounded(it, 65536) }
            check(!closed)
            return JSONObject(String(bytes, Charsets.UTF_8))
        } finally {
            conn.disconnect()
            synchronized(lifecycle) { requests.remove(conn) }
        }
    }

    fun claim(): String {
        val data = request("/v1/challenge", credential = pairing.grant)
        require(data.getString("id") == pairing.id)
        val redirect = data.getString("redirect_uri"); require(allowedVk(redirect))
        val credential = data.getString("session"); require(credential.matches(Regex("[a-f0-9]{64}")))
        val deadline = data.getLong("expires_at")
        val secondsLeft = deadline - System.currentTimeMillis() / 1000
        require(secondsLeft in 1..600)
        synchronized(lifecycle) {
            check(!closed && session.isEmpty())
            session = credential; expires = deadline
            timer.schedule(Runnable { close() }, (deadline * 1000 - System.currentTimeMillis()).coerceAtLeast(1), TimeUnit.MILLISECONDS)
        }
        return redirect
    }

    fun submit(token: String) {
        require(validCaptchaToken(token)); checkActive()
        require(request("/v1/result", JSONObject().put("id", pairing.id).put("token", token)).optBoolean("ok"))
    }

    fun cancel() {
        if (session.isNotEmpty()) runCatching { request("/v1/cancel", JSONObject()) }
    }

    // WebView talks only to loopback. Native code adds router authentication and TLS pinning.
    fun startRelay(): Int = synchronized(lifecycle) {
        checkActive(); check(listener == null)
        val server = ServerSocket(0, 8, InetAddress.getByName("127.0.0.1"))
        listener = server
        try {
            pool.execute {
                while (!closed) {
                    val browser = try { server.accept() } catch (_: Exception) { break }
                    try { track(browser) } catch (_: Exception) { break }
                    if (!slots.tryAcquire()) { closeSocket(browser); continue }
                    try { pool.execute { relay(browser) } }
                    catch (_: Exception) { closeSocket(browser); slots.release() }
                }
            }
        } catch (error: Exception) {
            listener = null; server.close(); throw error
        }
        server.localPort
    }

    private fun relay(browser: Socket) {
        var router: SSLSocket? = null
        var established = false
        try {
            browser.soTimeout = 15000
            val head = readHttpHeader(browser.inputStream)
            val fields = head.lineSequence().first().split(' ')
            require(fields.size == 3 && fields[0] == "CONNECT" && fields[2] == "HTTP/1.1")
            val destination = fields[1]; require(allowedRelayDestination(destination)); checkActive()
            val remote = context.socketFactory.createSocket() as SSLSocket
            router = remote
            track(remote)
            remote.soTimeout = 15000
            remote.connect(InetSocketAddress(pairing.host, pairing.port), 10000)
            remote.startHandshake(); checkActive()
            remote.outputStream.write(("CONNECT $destination HTTP/1.1\r\nHost: $destination\r\nAuthorization: Bearer $session\r\n\r\n").toByteArray(Charsets.US_ASCII))
            require(readHttpHeader(remote.inputStream).startsWith("HTTP/1.1 200 "))
            checkActive()
            browser.outputStream.write("HTTP/1.1 200 Connection Established\r\n\r\n".toByteArray(Charsets.US_ASCII))
            established = true
            val timeout = ((expires - System.currentTimeMillis() / 1000).coerceIn(1, 300) * 1000).toInt()
            browser.soTimeout = timeout; remote.soTimeout = timeout
            pool.execute {
                try { remote.inputStream.copyTo(browser.outputStream) } catch (_: Exception) {}
                finally { closeSocket(browser); closeSocket(remote) }
            }
            browser.inputStream.copyTo(remote.outputStream)
        } catch (_: Exception) {
            if (!established) runCatching {
                browser.outputStream.write("HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n".toByteArray(Charsets.US_ASCII))
            }
        } finally {
            closeSocket(browser); router?.let { closeSocket(it) }; slots.release()
        }
    }

    override fun close() {
        val resources = synchronized(lifecycle) {
            if (closed) return
            closed = true; session = ""
            val snapshot = Triple(listener, sockets.toList(), requests.toList())
            listener = null; sockets.clear(); requests.clear()
            snapshot
        }
        runCatching { resources.first?.close() }
        resources.second.forEach { runCatching { it.close() } }
        resources.third.forEach { runCatching { it.disconnect() } }
        timer.shutdownNow(); pool.shutdownNow()
    }
}
