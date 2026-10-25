package org.csqtt.openwrt.helper

import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import org.junit.Assert.*
import org.junit.Test

class AttemptGateTest {
    @Test fun concurrentStartsReserveOneAttempt() {
        val gate = AttemptGate()
        val pool = Executors.newFixedThreadPool(12)
        val start = CountDownLatch(1)
        try {
            val attempts = (1..12).map { pool.submit<Long?> { start.await(); gate.begin() } }
            start.countDown()
            val owners = attempts.mapNotNull { it.get(5, TimeUnit.SECONDS) }
            assertEquals(1, owners.size)
            assertTrue(gate.owns(owners.single()))
            assertNull(gate.begin())
        } finally { pool.shutdownNow() }
    }

    @Test fun staleCleanupCannotReleaseLaterAttempt() {
        val gate = AttemptGate()
        val first = requireNotNull(gate.begin())
        gate.finish(first)
        val second = requireNotNull(gate.begin())
        gate.finish(first)
        assertFalse(gate.owns(first))
        assertTrue(gate.owns(second))
        assertNull(gate.begin())
        gate.finish(second)
        assertNotNull(gate.begin())
    }
}
