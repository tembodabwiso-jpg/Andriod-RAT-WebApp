package com.mdm.client.util

import android.content.Context
import android.net.wifi.WifiManager
import java.net.NetworkInterface

object NetworkUtils {

    fun getLocalIpAddress(ctx: Context): String {
        // Try WifiManager first (most reliable on WiFi)
        try {
            val wifiMgr = ctx.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
            val wifiInfo = wifiMgr.connectionInfo
            val ipInt = wifiInfo.ipAddress
            if (ipInt != 0) {
                return intToIp(ipInt)
            }
        } catch (_: Exception) {}

        // Fall back to iterating network interfaces
        try {
            val interfaces = NetworkInterface.getNetworkInterfaces()
            while (interfaces.hasMoreElements()) {
                val iface = interfaces.nextElement()
                val addresses = iface.inetAddresses
                while (addresses.hasMoreElements()) {
                    val addr = addresses.nextElement()
                    if (!addr.isLoopbackAddress && addr.hostAddress?.contains(':') == false) {
                        return addr.hostAddress ?: ""
                    }
                }
            }
        } catch (_: Exception) {}

        return "127.0.0.1"
    }

    private fun intToIp(ip: Int): String {
        return "${ip and 0xff}.${ip shr 8 and 0xff}.${ip shr 16 and 0xff}.${ip shr 24 and 0xff}"
    }
}
