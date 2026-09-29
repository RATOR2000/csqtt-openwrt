package org.csqtt.openwrt.helper

import android.app.Activity
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.widget.*
import androidx.webkit.*
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private var session: RouterSession? = null
    private var web: WebView? = null
    private lateinit var status: TextView
    private lateinit var layout: LinearLayout
    private val submitted = AtomicBoolean(false)
    private var proxyInstalled = false
    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(20, 32, 20, 20) }
        status = TextView(this).apply { text = "CSQTT CAPTCHA\nОткройте ссылку из панели роутера или вставьте её ниже."; textSize = 17f }
        val entry = EditText(this).apply { hint = "csqtt-helper://pair?…"; isSingleLine = true; setText(intent?.dataString ?: "") }
        val begin = Button(this).apply { text = "Открыть проверку VK"; setOnClickListener { start(entry.text.toString()) } }
        val cancel = Button(this).apply { text = "Отмена"; setOnClickListener { executor.execute { session?.cancel(); main.post { finish() } } } }
        layout.addView(status); layout.addView(entry); layout.addView(begin); layout.addView(cancel); setContentView(layout)
    }
    private fun start(raw: String) {
        if (session != null) return
        if (!listOf(WebViewFeature.PROXY_OVERRIDE, WebViewFeature.DOCUMENT_START_SCRIPT, WebViewFeature.WEB_MESSAGE_LISTENER).all { WebViewFeature.isFeatureSupported(it) }) {
            status.text = "Обновите Android System WebView: нужны защищённый мост и настройка прокси."; return
        }
        val pair = runCatching { Pairing.parse(raw) }.getOrElse { status.text = "Неверная ссылка подключения."; return }
        status.text = "Подключение к роутеру…"
        executor.execute {
            val client = RouterSession(pair); session = client
            try {
                val redirect = client.claim(); val port = client.startRelay()
                main.post {
                    if (isFinishing || isDestroyed) { client.close(); return@post }
                    ProxyController.getInstance().setProxyOverride(ProxyConfig.Builder().addProxyRule("http://127.0.0.1:$port").build(), mainExecutor) {
                        proxyInstalled = true
                        if (!isFinishing && !isDestroyed) showCaptcha(redirect, client)
                    }
                }
            } catch (_: Exception) { client.close(); session = null; main.post { status.text = "Не удалось получить проверку. Создайте новую ссылку в LuCI и проверьте подключение к Wi-Fi роутера." } }
        }
    }
    private fun showCaptcha(redirect: String, client: RouterSession) {
        status.text = "Пройдите проверку VK. Пароли роутера и VPN не требуются."
        val view = WebView(this); web = view
        view.settings.apply { javaScriptEnabled = true; domStorageEnabled = true; allowFileAccess = false; allowContentAccess = false; mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW }
        view.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean = !allowedVk(request.url.toString())
        }
        WebViewCompat.addWebMessageListener(view, "CsqttCaptcha", vkOrigins) { _, message, origin, _, _ ->
            val token = message.data ?: return@addWebMessageListener
            if (!allowedVk(origin.toString()) || token.length !in 1..16384 || !submitted.compareAndSet(false, true)) return@addWebMessageListener
            status.text = "Отправка результата роутеру…"
            executor.execute { try { client.submit(token); main.post { status.text = "Проверка пройдена. Роутер продолжает подключение."; releaseWeb() } } catch (_: Exception) { main.post { status.text = "Проверка устарела или отклонена. Получите новую ссылку в LuCI."; releaseWeb() } } }
        }
        WebViewCompat.addDocumentStartJavaScript(view, INTERCEPTOR, vkOrigins)
        layout.addView(view, LinearLayout.LayoutParams(-1, 0, 1f)); view.loadUrl(redirect)
        main.postDelayed({ if (!submitted.get()) { status.text = "Срок проверки истёк. Создайте новую ссылку в LuCI."; releaseWeb() } }, ((client.expires * 1000 - System.currentTimeMillis()).coerceAtLeast(1)))
    }
    private fun releaseWeb() {
        web?.let { layout.removeView(it); it.stopLoading(); WebViewCompat.removeWebMessageListener(it, "CsqttCaptcha"); it.destroy() }; web = null
        if (proxyInstalled) { ProxyController.getInstance().clearProxyOverride(mainExecutor) {}; proxyInstalled = false }
        session?.close(); session = null
    }
    override fun onDestroy() { main.removeCallbacksAndMessages(null); releaseWeb(); executor.shutdownNow(); super.onDestroy() }
    companion object {
        // Adapted from upstream ManlCaptchaActivity (amurcanov, PolyForm Noncommercial).
        private val INTERCEPTOR = """
            (() => {
              if (window.__csqtt_helper) return;
              window.__csqtt_helper = true;
              const isCheck = u => { try { return new URL(u, location.href).pathname.endsWith('/captchaNotRobot.check'); } catch (_) { return false; } };
              const report = data => { const t = data && data.response && data.response.success_token; if (typeof t === 'string') window.CsqttCaptcha.postMessage(t); };
              const originalFetch = window.fetch;
              window.fetch = async function(...args) {
                const response = await originalFetch.apply(this, args);
                if (isCheck(typeof args[0] === 'string' ? args[0] : args[0]?.url)) response.clone().json().then(report).catch(() => {});
                return response;
              };
              const open = XMLHttpRequest.prototype.open, send = XMLHttpRequest.prototype.send;
              XMLHttpRequest.prototype.open = function(method, url, ...rest) { this.__csqtt_check = isCheck(url); return open.call(this, method, url, ...rest); };
              XMLHttpRequest.prototype.send = function(...args) { if (this.__csqtt_check) this.addEventListener('load', () => { try { report(JSON.parse(this.responseText)); } catch (_) {} }); return send.apply(this, args); };
            })();
        """.trimIndent()
    }
}
