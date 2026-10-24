package org.csqtt.openwrt.helper

import java.io.ByteArrayOutputStream
import java.io.InputStream

// Android API 28 has InputStream.read(), but not readNBytes(). Read one extra byte
// so an oversized response cannot be accepted as a silently truncated document.
internal fun readBounded(input: InputStream, maximum: Int): ByteArray {
    require(maximum in 1..1048576)
    val output = ByteArrayOutputStream()
    val buffer = ByteArray(4096)
    while (output.size() <= maximum) {
        val count = input.read(buffer, 0, minOf(buffer.size, maximum + 1 - output.size()))
        if (count < 0) break
        if (count == 0) {
            val byte = input.read()
            if (byte < 0) break
            output.write(byte)
        } else output.write(buffer, 0, count)
    }
    require(output.size() <= maximum) { "Response too large" }
    return output.toByteArray()
}

// Do not buffer beyond CRLF CRLF: the following bytes belong to the TLS stream.
internal fun readHttpHeader(input: InputStream): String {
    val output = ByteArrayOutputStream()
    var tail = 0
    while (output.size() < 8192) {
        val byte = input.read()
        require(byte >= 0) { "Incomplete HTTP header" }
        output.write(byte)
        tail = (tail shl 8) or byte
        if (tail == 0x0d0a0d0a) return output.toString("US-ASCII")
    }
    error("HTTP header too large")
}
