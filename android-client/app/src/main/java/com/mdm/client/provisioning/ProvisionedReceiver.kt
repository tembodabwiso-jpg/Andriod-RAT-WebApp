package com.mdm.client.provisioning

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import com.mdm.client.config.AppConfig
import com.mdm.client.service.MdmForegroundService

/**
 * Receives the PROVISIONING_SUCCESSFUL broadcast after QR or Zero-Touch enrollment.
 * Automatically starts the headless agent without any user interaction.
 */
class ProvisionedReceiver : BroadcastReceiver() {

    companion object {
        private const val TAG = "ProvRcv"
    }

    override fun onReceive(context: Context, intent: Intent) {
        Log.i(TAG, "Provisioning complete, action=${intent.action}")

        // Extract server IP from provisioning extras if available
        val serverIp = intent.getStringExtra("server_ip")
        if (!serverIp.isNullOrBlank()) {
            AppConfig.setServerIp(context, serverIp)
        }

        // Mark setup as complete — skip the enrollment UI entirely
        if (AppConfig.isConfigured(context)) {
            AppConfig.setSetupComplete(context, true)

            // Start the headless background service
            try {
                val serviceIntent = Intent(context, MdmForegroundService::class.java)
                ContextCompat.startForegroundService(context, serviceIntent)
                Log.i(TAG, "Headless service started after provisioning")
            } catch (e: Exception) {
                Log.e(TAG, "Service start failed: ${e.message}")
            }
        }
    }
}
