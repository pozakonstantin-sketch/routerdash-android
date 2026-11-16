package ru.routerdash.android

import org.junit.Assert.assertEquals
import org.junit.Test

class DashboardParsingTest {
    @Test
    fun loadAverageUsesOpenWrtFixedPointScale() {
        assertEquals("0.09", formatLoadAverage(5952L))
        assertEquals("0.16", formatLoadAverage(10752L))
        assertEquals("0.17", formatLoadAverage(11296L))
    }

    @Test
    fun dhcpLeaseSecondsAreHumanReadable() {
        assertEquals("10ч 56м", formatLeaseExpiry("39378"))
        assertEquals("—", formatLeaseExpiry("—"))
        assertEquals("Истекла", formatLeaseExpiry("0"))
    }

    @Test
    fun syslogFacilitySeverityIsRecognized() {
        assertEquals("error", parseLogPriority("cron.err: job failed"))
        assertEquals("error", parseLogPriority("daemon.crit kernel failure"))
        assertEquals("warning", parseLogPriority("dnsmasq.warn: slow response"))
        assertEquals("info", parseLogPriority("daemon.info: service started"))
    }
}
