package org.csqtt.openwrt.helper

import java.io.ByteArrayInputStream
import java.io.InputStream
import org.junit.Assert.*
import org.junit.Test

class TransportIOTest {
    @Test fun boundedReadAllowsExactLimit() {
        val bytes = ByteArray(65536) { (it % 251).toByte() }
        assertArrayEquals(bytes, readBounded(ByteArrayInputStream(bytes), 65536))
    }

    @Test fun oversizedResponseStopsAfterOneExtraByte() {
        val input = ByteArrayInputStream(ByteArray(70000))
        assertTrue(runCatching { readBounded(input, 65536) }.isFailure)
        assertEquals(70000 - 65537, input.available())
    }

    @Test fun zeroLengthReadCannotLoopForever() {
        val input = object : InputStream() {
            private var count = 0
            override fun read(buffer: ByteArray, offset: Int, length: Int) = 0
            override fun read(): Int = if (count++ == 0) 42 else -1
        }
        assertArrayEquals(byteArrayOf(42), readBounded(input, 8))
    }

    @Test fun httpHeaderPreservesFollowingTlsBytes() {
        val header = "HTTP/1.1 200 Connection Established\r\n\r\n"
        val tls = byteArrayOf(0x16, 0x03, 0x03, 0x00, 0x07)
        val input = ByteArrayInputStream(header.toByteArray(Charsets.US_ASCII) + tls)
        assertEquals(header, readHttpHeader(input))
        assertArrayEquals(tls, input.readBytes())
    }

    @Test fun httpHeaderRejectsTruncatedAndOversizedInput() {
        for (bytes in listOf("HTTP/1.1 200 OK\r\n".toByteArray(), ByteArray(8192) { 65 })) {
            assertTrue(runCatching { readHttpHeader(ByteArrayInputStream(bytes)) }.isFailure)
        }
    }
}
