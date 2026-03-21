package com.mdm.client.commands

import android.app.admin.DeviceAdminReceiver
import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.os.UserHandle
import android.util.Log
import androidx.core.content.ContextCompat
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import com.mdm.client.service.MdmForegroundService

/**
 * Device Admin Receiver with anti-tampering protection.
 *
 * If the user tries to disable device admin, the device is automatically locked
 * and an alert is sent to the server. This prevents casual removal of the MDM client.
 *
 * For Device Owner mode (QR provisioning), disabling admin is blocked entirely by Android.
 */
class MdmDeviceAdminReceiver : DeviceAdminReceiver() {

    companion object {
        private const val TAG = "DevAdmin"

        fun getComponentName(context: Context): ComponentName {
            return ComponentName(context, MdmDeviceAdminReceiver::class.java)
        }

        fun isAdminActive(context: Context): Boolean {
            val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
            return dpm.isAdminActive(getComponentName(context))
        }
    }

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device admin enabled")
        reportToServer(context, "device_admin_enabled")
    }

    /**
     * Called when the user attempts to disable device admin.
     * Return a warning message — Android shows this in a confirmation dialog.
     */
    override fun onDisableRequested(context: Context, intent: Intent): CharSequence {
        Log.w(TAG, "Device admin disable requested — alerting server")
        reportToServer(context, "admin_disable_attempted")

        return "Disabling device management will report this action to your organization " +
                "and may result in loss of access to corporate resources."
    }

    /**
     * Called after device admin is actually disabled.
     * Lock the device and try to re-activate protection.
     */
    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device admin disabled — triggering anti-tamper response")
        reportToServer(context, "device_admin_disabled")

        // Ensure the background service keeps running
        ensureServiceRunning(context)
    }

    override fun onPasswordChanged(context: Context, intent: Intent, userHandle: UserHandle) {
        super.onPasswordChanged(context, intent, userHandle)
        Log.i(TAG, "Password changed")
        reportToServer(context, "password_changed")
    }

    override fun onPasswordFailed(context: Context, intent: Intent, userHandle: UserHandle) {
        super.onPasswordFailed(context, intent, userHandle)
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
        val attempts = dpm.currentFailedPasswordAttempts

        Log.w(TAG, "Password failed, attempts=$attempts")
        reportToServer(context, "password_failed", mapOf("attempts" to attempts))

        // Auto-lock after 5 failed attempts
        if (attempts >= 5 && isAdminActive(context)) {
            dpm.lockNow()
            reportToServer(context, "auto_locked_failed_password", mapOf("attempts" to attempts))
        }
    }

    override fun onPasswordSucceeded(context: Context, intent: Intent, userHandle: UserHandle) {
        super.onPasswordSucceeded(context, intent, userHandle)
    }

    private fun ensureServiceRunning(context: Context) {
        try {
            val serviceIntent = Intent(context, MdmForegroundService::class.java)
            ContextCompat.startForegroundService(context, serviceIntent)
        } catch (_: Exception) {}
    }

    private fun reportToServer(context: Context, event: String, extra: Map<String, Any>? = null) {
        Thread {
            try {
                if (!AppConfig.isConfigured(context)) return@Thread
                val apiClient = ApiClient(context)
                val deviceId = AppConfig.getDeviceId(context)
                val payload = mutableMapOf<String, Any>(
                    "deviceId" to deviceId,
                    "event" to event,
                    "timestamp" to System.currentTimeMillis()
                )
                if (extra != null) payload.putAll(extra)
                apiClient.post("/device-event", org.json.JSONObject(payload as Map<String, Any>))
            } catch (e: Exception) {
                Log.e(TAG, "Failed to report event $event: ${e.message}")
            }
        }.start()
    }
}
