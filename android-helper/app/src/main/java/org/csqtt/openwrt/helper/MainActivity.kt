package org.csqtt.openwrt.helper

import android.app.Activity
import android.content.Intent
import android.net.http.SslError
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.*
import android.widget.*
import androidx.webkit.*
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class MainActivity : Activity() {
    private enum class ProxyState { NONE, INSTALLING, INSTALLED, CLEARING }
    private class Attempt(val id: Long, val client: RouterSession) {
        val submitted = AtomicBoolean(false)
        var ending = false
        var proxy = ProxyState.NONE
        var web: WebView? = null
        var expiry: Runnable? = null
    }

    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private var active: Attempt? = null
    private lateinit var status: TextView
    private lateinit var layout: LinearLayout
    private lateinit var entry: EditText

    override fun onCreate(state: Bundle?) {
        super.onCreate(state)
        layout = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(20, 32, 20, 20) }
        status = TextView(this).apply { text = "CSQTT CAPTCHA\nОткройте ссылку из панели роутера или вставьте её ниже."; textSize = 17f }
        entry = EditText(this).apply { hint = "csqtt-helper://pair?…"; isSingleLine = true; isSaveEnabled = false; setText(intent?.dataString ?: "") }
        val begin = Button(this).apply { text = "Открыть проверку VK"; setOnClickListener { start(entry.text.toString()) } }
        val cancel = Button(this).apply { text = "Отмена"; setOnClickListener { cancelAttempt() } }
        layout.addView(status); layout.addView(entry); layout.addView(begin); layout.addView(cancel); setContentView(layout)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        if (active == null) entry.setText(intent.dataString ?: "")
    }

    private fun isActive(attempt: Attempt): Boolean =
        active === attempt && !attempt.ending && attempts.owns(attempt.id) && !isFinishing && !isDestroyed

    private fun start(raw: String) {
        if (active != null || isFinishing || isDestroyed) return
        if (!listOf(WebViewFeature.PROXY_OVERRIDE, WebViewFeature.DOCUMENT_START_SCRIPT, WebViewFeature.WEB_MESSAGE_LISTENER).all { WebViewFeature.isFeatureSupported(it) }) {
            status.text = "Обновите Android System WebView: нужны защищённый мост и настройка прокси."; return
        }
        val pair = runCatching { Pairing.parse(raw) }.getOrElse { status.text = "Неверная ссылка подключения."; return }
        val id = attempts.begin() ?: run { status.text = "Дождитесь завершения предыдущей проверки."; return }
        val client = runCatching { RouterSession(pair) }.getOrElse {
            attempts.finish(id); status.text = "Не удалось подготовить защищённое подключение."; return
        }
        // Reserve ownership before dispatching network work, so a second tap cannot consume the grant.
        val attempt = Attempt(id, client)
        active = attempt
        status.text = "Подключение к роутеру…"
        executor.execute {
            try {
                val redirect = client.claim()
                val port = client.startRelay()
                main.post {
                    if (!isActive(attempt)) { cleanup(attempt); return@post }
                    installProxy(attempt, port, redirect)
                }
            } catch (_: Exception) {
                client.close()
                main.post { fail(attempt, "Не удалось получить проверку. Создайте новую ссылку в LuCI и проверьте подключение к Wi-Fi роутера.") }
            }
        }
    }

    private fun installProxy(attempt: Attempt, port: Int, redirect: String) {
        attempt.proxy = ProxyState.INSTALLING
        try {
            val config = ProxyConfig.Builder().addProxyRule("http://127.0.0.1:$port").removeImplicitRules().build()
            ProxyController.getInstance().setProxyOverride(config, mainExecutor) {
                attempt.proxy = ProxyState.INSTALLED
                if (!isActive(attempt)) { cleanup(attempt); return@setProxyOverride }
                try { showCaptcha(redirect, attempt) }
                catch (_: Exception) { fail(attempt, "Не удалось открыть проверку. Обновите Android System WebView и создайте новую ссылку в LuCI.") }
            }
        } catch (_: Exception) {
            attempt.proxy = ProxyState.INSTALLED
            fail(attempt, "Не удалось настроить защищённое подключение WebView.")
        }
    }

    private fun showCaptcha(redirect: String, attempt: Attempt) {
        status.text = "Пройдите проверку VK. Пароли роутера и VPN не требуются."
        val view = WebView(this)
        attempt.web = view
        view.settings.apply {
            javaScriptEnabled = true; domStorageEnabled = true
            allowFileAccess = false; allowContentAccess = false
            mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
        }
        view.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean =
                !isActive(attempt) || !allowedVk(request.url.toString())

            override fun onReceivedSslError(view: WebView, handler: SslErrorHandler, error: SslError) {
                handler.cancel()
                fail(attempt, "Ошибка сертификата VK. Создайте новую ссылку в LuCI.")
            }

            override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
                if (request.isForMainFrame) fail(attempt, "Проверка недоступна. Создайте новую ссылку в LuCI и проверьте подключение к Wi-Fi роутера.")
            }
        }
        WebViewCompat.addWebMessageListener(view, "CsqttCaptcha", vkOrigins) { _, message, origin, _, _ ->
            val token = message.data ?: return@addWebMessageListener
            if (!isActive(attempt) || !allowedVk(origin.toString()) || !validCaptchaToken(token) ||
                !attempt.submitted.compareAndSet(false, true)) return@addWebMessageListener
            status.text = "Отправка результата роутеру…"
            executor.execute {
                try {
                    attempt.client.submit(token)
                    main.post {
                        if (isActive(attempt)) status.text = "Проверка пройдена. Роутер продолжает подключение."
                        cleanup(attempt)
                    }
                } catch (_: Exception) {
                    main.post { fail(attempt, "Проверка устарела или отклонена. Получите новую ссылку в LuCI.") }
                }
            }
        }
        WebViewCompat.addDocumentStartJavaScript(view, INTERCEPTOR, vkOrigins)
        layout.addView(view, LinearLayout.LayoutParams(-1, 0, 1f))
        val expiry = Runnable {
            if (isActive(attempt)) fail(attempt, "Срок проверки истёк. Создайте новую ссылку в LuCI.")
        }
        attempt.expiry = expiry
        main.postDelayed(expiry, (attempt.client.expires * 1000 - System.currentTimeMillis()).coerceAtLeast(1))
        view.loadUrl(redirect)
    }

    private fun cancelAttempt() {
        val attempt = active ?: run { finish(); return }
        if (attempt.ending) return
        attempt.ending = true
        status.text = "Отмена проверки…"
        destroyWeb(attempt)
        executor.execute {
            attempt.client.cancel()
            main.post { cleanup(attempt); finish() }
        }
    }

    private fun fail(attempt: Attempt, message: String) {
        if (isActive(attempt)) status.text = message
        cleanup(attempt)
    }

    private fun destroyWeb(attempt: Attempt) {
        attempt.expiry?.let { main.removeCallbacks(it) }; attempt.expiry = null
        val view = attempt.web ?: return
        attempt.web = null
        layout.removeView(view)
        runCatching { view.stopLoading() }
        runCatching { WebViewCompat.removeWebMessageListener(view, "CsqttCaptcha") }
        view.destroy()
    }

    private fun cleanup(attempt: Attempt) {
        if (active === attempt) active = null
        attempt.ending = true
        destroyWeb(attempt)
        attempt.client.close()
        when (attempt.proxy) {
            ProxyState.NONE -> attempts.finish(attempt.id)
            ProxyState.INSTALLING, ProxyState.CLEARING -> Unit // Callback finishes cleanup.
            ProxyState.INSTALLED -> {
                attempt.proxy = ProxyState.CLEARING
                try {
                    ProxyController.getInstance().clearProxyOverride(mainExecutor) {
                        attempt.proxy = ProxyState.NONE
                        attempts.finish(attempt.id)
                    }
                } catch (_: Exception) {
                    // Keep process-wide ownership if cleanup failed; no new WebView may start.
                    attempt.proxy = ProxyState.INSTALLED
                    if (!isFinishing && !isDestroyed) status.text = "Не удалось очистить настройку WebView. Перезапустите помощник."
                }
            }
        }
    }

    override fun onDestroy() {
        main.removeCallbacksAndMessages(null)
        active?.let { cleanup(it) }
        executor.shutdownNow()
        super.onDestroy()
    }

    companion object {
        private val attempts = AttemptGate()
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
