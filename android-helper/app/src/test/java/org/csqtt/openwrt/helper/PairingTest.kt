package org.csqtt.openwrt.helper

import org.junit.Assert.*
import org.junit.Test

class PairingTest {
    private val link = "csqtt-helper://pair?host=192.168.1.1&port=9443&grant=${"a".repeat(64)}&pin=${"b".repeat(64)}&id=test-1"
    @Test fun valid() { assertEquals("192.168.1.1", Pairing.parse(link).host) }
    @Test fun rejectUntrustedEndpoints() {
        for (bad in listOf(link.replace("192.168.1.1", "example.com"), link.replace("192.168.1.1", "8.8.8.8"), link.replace("192.168.1.1", "192.168.001.1"), link + "&host=10.0.0.1", link.replace("9443", "22"), link.replace("csqtt-helper", "https"), link.replace("//pair?", "//pair:9443?"), link.replace("//pair?", "//pair/path?"), link + "#fragment")) {
            assertTrue(runCatching { Pairing.parse(bad) }.isFailure)
        }
    }
    @Test fun vkOrigins() { assertTrue(allowedVk("https://id.vk.com/captcha")); assertFalse(allowedVk("https://id.vk.com.evil.test/")); assertFalse(allowedVk("http://vk.com/")) }
    @Test fun relayAcceptsOnlyVkHttpsAuthority() {
        assertTrue(allowedRelayDestination("id.vk.com:443"))
        for (bad in listOf("id.vk.com:80", "vk.com.evil.test:443", "vk.com/path:443", "vk.com?query:443", "vk.com#fragment:443", "user@vk.com:443", "127.0.0.1:443", "vk.com:443/path")) {
            assertFalse(allowedRelayDestination(bad))
        }
    }
    @Test fun tokenLimitUsesUtf8BytesAndRejectsControls() {
        assertTrue(validCaptchaToken("x".repeat(16384)))
        assertFalse(validCaptchaToken("x".repeat(16385)))
        assertTrue(validCaptchaToken("я".repeat(8192)))
        assertFalse(validCaptchaToken("я".repeat(8193)))
        for (bad in listOf("", " ", "x\n", "x\r", "x\u0000", "x\u007f", "x\u0085")) assertFalse(validCaptchaToken(bad))
    }
    @Test fun pairingStringDoesNotDiscloseCredentials() {
        val pairing = Pairing.parse(link)
        assertFalse(pairing.toString().contains(pairing.grant))
        assertFalse(pairing.toString().contains(pairing.pin))
    }
}
