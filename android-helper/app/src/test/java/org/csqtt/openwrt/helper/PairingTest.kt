package org.csqtt.openwrt.helper

import org.junit.Assert.*
import org.junit.Test

class PairingTest {
    private val link = "csqtt-helper://pair?host=192.168.1.1&port=9443&grant=${"a".repeat(64)}&pin=${"b".repeat(64)}&id=test-1"
    @Test fun valid() { assertEquals("192.168.1.1", Pairing.parse(link).host) }
    @Test fun rejectUntrustedEndpoints() {
        for (bad in listOf(link.replace("192.168.1.1", "example.com"), link.replace("192.168.1.1", "8.8.8.8"), link + "&host=10.0.0.1", link.replace("9443", "22"), link.replace("csqtt-helper", "https"))) {
            assertTrue(runCatching { Pairing.parse(bad) }.isFailure)
        }
    }
    @Test fun vkOrigins() { assertTrue(allowedVk("https://id.vk.com/captcha")); assertFalse(allowedVk("https://id.vk.com.evil.test/")); assertFalse(allowedVk("http://vk.com/")) }
}
