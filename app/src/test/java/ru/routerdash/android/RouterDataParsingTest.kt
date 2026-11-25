package ru.routerdash.android

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class RouterDataParsingTest {
    @Test fun parsesKernelLoadAverageWithoutFixedPointConversion() {
        assertEquals("0.55 / 0.33 / 0.44", parseLoadAverage("0.55 0.33 0.44 1/120 1234"))
    }
    @Test fun rejectsInvalidLoadAverage() {
        assertNull(parseLoadAverage("not available"))
        assertNull(parseLoadAverage("0.1 0.2"))
    }
    @Test fun parsesThermalValuesInMillidegreesAndDegrees() {
        assertEquals(54.25, parseTemperatureC("54250")!!, 0.001)
        assertEquals(54.25, parseTemperatureC("54.25")!!, 0.001)
        assertNull(parseTemperatureC("999999"))
    }
    @Test fun unwrapsNestedServiceInventoryAndKeepsAllServices() {
        val rc = JSONObject("""{"result":{"dnsmasq":{"running":true,"enabled":true},"rpcd":{"running":true},"aria2":{"running":false}}}""")
        val init = JSONObject("""{"services":{"avahi-daemon":{"enabled":true},"dnsmasq":{"enabled":true}}}""")
        val merged = normalizeServiceInventory(rc, init)
        assertEquals(4, merged.length())
        assertEquals(true, merged.getJSONObject("dnsmasq").getBoolean("running"))
        assertEquals(true, merged.getJSONObject("avahi-daemon").getBoolean("enabled"))
    }
}
