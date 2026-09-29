package org.csqtt.openwrt.helper

// WebView proxy overrides are process-wide. Keep ownership until the asynchronous
// proxy cleanup completes, including when an Activity is recreated.
internal class AttemptGate {
    private var next = 0L
    private var owner: Long? = null

    @Synchronized fun begin(): Long? {
        if (owner != null) return null
        return (++next).also { owner = it }
    }

    @Synchronized fun owns(id: Long): Boolean = owner == id

    @Synchronized fun finish(id: Long) {
        if (owner == id) owner = null
    }
}
