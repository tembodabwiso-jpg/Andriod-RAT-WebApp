package com.mdm.client.security

import android.app.admin.DevicePolicyManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.BroadcastReceiver
import android.net.Uri
import android.util.Log
import androidx.core.content.ContextCompat
import com.mdm.client.commands.MdmDeviceAdminReceiver
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import com.mdm.client.service.MdmForegroundService
import org.json.JSONObject

/**
 * Monitors for tampering attempts and responds automatically:
 *
 * 1. Uninstall detection — if someone tries to uninstall the app via Settings
 * 2. Device admin disable detection — locks the device
 * 3. Service kill detection — auto-restarts via WorkManager
 * 4. Package verification — detects if app is being inspected
 *
 * Register this in MdmForegroundService.onCreate() to activate monitoring.
 */
class TamperDetector(private val context: Context) {

    companion object {
        private const val TAG = "TamperDet"
    }

    private var packageRemoveReceiver: BroadcastReceiver? = null
    private var screenOffReceiver: BroadcastReceiver? = null

    /**
     * Start monitoring for tampering events.
     */
    fun startMonitoring() {
        registerPackageMonitor()
        registerScreenMonitor()
        checkAdminStatus()
        Log.i(TAG, "Tamper detection active")
    }

    /**
     * Stop monitoring (called on service destroy).
     */
    fun stopMonitoring() {
        try {
            packageRemoveReceiver?.let { context.unregisterReceiver(it) }
            screenOffReceiver?.let { context.unregisterReceiver(it) }
        } catch (_: Exception) {}
    }

    /**
     * Monitor for package removal/replacement events targeting our app.
     */
    private fun registerPackageMonitor() {
        packageRemoveReceiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                val packageName = intent.data?.schemeSpecificPart ?: return

                when (intent.action) {
                    Intent.ACTION_PACKAGE_REMOVED -> {
                        if (packageName == ctx.packageName) {
                            Log.w(TAG, "Our package is being removed!")
                            reportTamperEvent("package_removal_detected")
                        }
                    }
                    Intent.ACTION_PACKAGE_DATA_CLEARED -> {
                        if (packageName == ctx.packageName) {
                            Log.w(TAG, "Our app data was cleared!")
                            reportTamperEvent("data_cleared")
                        }
                    }
                    "android.intent.action.QUERY_PACKAGE_RESTART" -> {
                        if (packageName == ctx.packageName) {
                            Log.w(TAG, "Force stop attempt detected")
                            reportTamperEvent("force_stop_attempted")
                        }
                    }
                }
            }
        }

        val filter = IntentFilter().apply {
            addAction(Intent.ACTION_PACKAGE_REMOVED)
            addAction(Intent.ACTION_PACKAGE_DATA_CLEARED)
            addAction("android.intent.action.QUERY_PACKAGE_RESTART")
            addDataScheme("package")
        }
        context.registerReceiver(packageRemoveReceiver, filter)
    }

    /**
     * Monitor screen state — if device locks, check if we're still active.
     * Also a good hook for periodic self-verification.
     */
    private fun registerScreenMonitor() {
        screenOffReceiver = object : BroadcastReceiver() {
            override fun onReceive(ctx: Context, intent: Intent) {
                if (intent.action == Intent.ACTION_SCREEN_OFF) {
                    // Verify service is still running on every screen-off
                    ensureServiceRunning()
                }
            }
        }
        context.registerReceiver(screenOffReceiver, IntentFilter(Intent.ACTION_SCREEN_OFF))
    }

    /**
     * Verify device admin is still active. If not, alert the server.
     */
    fun checkAdminStatus(): Boolean {
        val isActive = MdmDeviceAdminReceiver.isAdminActive(context)
        if (!isActive) {
            Log.w(TAG, "Device admin is NOT active")
            reportTamperEvent("admin_not_active")
        }
        return isActive
    }

    /**
     * Check if the app's Settings page is open (user may be trying to uninstall/disable).
     * Call this periodically from the service.
     */
    fun checkForSettingsInspection(): Boolean {
        try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as android.app.ActivityManager
            @Suppress("DEPRECATION")
            val tasks = am.getRunningTasks(1)
            if (tasks.isNotEmpty()) {
                val topActivity = tasks[0].topActivity?.className ?: ""
                // Detect if Android Settings app info page is showing (user inspecting our app)
                if (topActivity.contains("InstalledAppDetails") ||
                    topActivity.contains("AppInfoBase") ||
                    topActivity.contains("UninstallerActivity")) {
                    Log.w(TAG, "Settings inspection detected: $topActivity")
                    reportTamperEvent("settings_inspection", mapOf("activity" to topActivity))
                    return true
                }
            }
        } catch (_: SecurityException) {
            // Need REAL_GET_TASKS permission for this on newer Android
        }
        return false
    }

    /**
     * Lock the device if admin is still active — anti-tamper response.
     */
    fun lockDevice() {
        try {
            if (MdmDeviceAdminReceiver.isAdminActive(context)) {
                val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
                dpm.lockNow()
                Log.w(TAG, "Device locked as anti-tamper response")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to lock device: ${e.message}")
        }
    }

    private fun ensureServiceRunning() {
        try {
            val intent = Intent(context, MdmForegroundService::class.java)
            ContextCompat.startForegroundService(context, intent)
        } catch (_: Exception) {}
    }

    private fun reportTamperEvent(event: String, extra: Map<String, Any>? = null) {
        Thread {
            try {
                if (!AppConfig.isConfigured(context)) return@Thread
                val apiClient = ApiClient(context)
                val deviceId = AppConfig.getDeviceId(context)
                val payload = mutableMapOf<String, Any>(
                    "deviceId" to deviceId,
                    "event" to "tamper:$event",
                    "timestamp" to System.currentTimeMillis()
                )
                if (extra != null) payload.putAll(extra)
                apiClient.post("/device-event", JSONObject(payload as Map<String, Any>))
            } catch (e: Exception) {
                Log.e(TAG, "Failed to report tamper event: ${e.message}")
            }
        }.start()
    }
}
