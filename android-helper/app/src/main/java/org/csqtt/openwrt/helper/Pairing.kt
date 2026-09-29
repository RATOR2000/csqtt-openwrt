package org.csqtt.openwrt.helper

import java.net.URI
import java.net.URLDecoder
import java.net.InetAddress

data class Pairing(val host: String, val port: Int, val grant: String, val pin: String, val id: String) {
    companion object {
        fun parse(raw: String): Pairing {
            require(raw.length <= 4096)
            val uri = URI(raw)
            require(uri.scheme == "csqtt-helper" && uri.host == "pair" && uri.userInfo == null && uri.fragment == null)
            val fields = mutableMapOf<String, String>()
            for (part in (uri.rawQuery ?: "").split('&')) {
                val pair = part.split('=', limit = 2)
                require(pair.size == 2)
                val key = URLDecoder.decode(pair[0], "UTF-8")
                require(!fields.containsKey(key))
                fields[key] = URLDecoder.decode(pair[1], "UTF-8")
            }
            require(fields.keys == setOf("host", "port", "grant", "pin", "id"))
            val host = fields.getValue("host")
            require(host.matches(Regex("(?:[0-9]{1,3}\\.){3}[0-9]{1,3}")))
            require(host.split('.').all { it.toInt() in 0..255 } && InetAddress.getByName(host).isSiteLocalAddress)
            val port = fields.getValue("port").toInt()
            require(port == 9443)
            for (key in listOf("grant", "pin")) require(fields.getValue(key).matches(Regex("[a-f0-9]{64}")))
            val id = fields.getValue("id")
            require(id.matches(Regex("[A-Za-z0-9_-]{1,128}")))
            return Pairing(host, port, fields.getValue("grant"), fields.getValue("pin"), id)
        }
    }
}

internal val vkOrigins = setOf("https://vk.com", "https://*.vk.com", "https://vk.ru", "https://*.vk.ru", "https://ok.ru", "https://*.ok.ru", "https://okcdn.ru", "https://*.okcdn.ru")
internal fun allowedVk(raw: String): Boolean = runCatching {
    val u = URI(raw)
    val host = u.host?.lowercase() ?: return false
    u.scheme == "https" && u.userInfo == null && (u.port == -1 || u.port == 443) &&
        listOf("vk.com", "vk.ru", "ok.ru", "okcdn.ru").any { host == it || host.endsWith(".$it") }
}.getOrDefault(false)
