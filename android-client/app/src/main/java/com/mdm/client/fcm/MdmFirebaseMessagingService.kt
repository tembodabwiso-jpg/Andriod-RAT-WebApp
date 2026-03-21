package com.mdm.client.fcm

import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.mdm.client.commands.CommandExecutor
import com.mdm.client.commands.CommandQueue
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import com.mdm.client.service.MdmForegroundService
import org.json.JSONObject

/**
 * Primary command delivery channel via Firebase Cloud Messaging.
 * Commands arrive instantly with zero polling — truly invisible network activity.
 *
 * Payload format (data-only message, no notification):
 * {
 *   "command_id": "123",
 *   "command_type": "LOCK_DEVICE",
 *   "payload": "{\"key\": \"value\"}"
 * }
 *
 * Special control messages:
 *   command_type = "WAKE_SERVICE"  → ensures foreground service is running
 *   command_type = "SYNC_NOW"     → triggers immediate data sync
 */
class MdmFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "MsgSvc"
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.i(TAG, "New FCM token")
        AppConfig.setFcmToken(this, token)

        // Re-register with server using new token
        if (AppConfig.isConfigured(this)) {
            Thread {
                try {
                    val apiClient = ApiClient(this)
                    val deviceId = AppConfig.getDeviceId(this)
                    val deviceIp = com.mdm.client.util.NetworkUtils.getLocalIpAddress(this)
                    apiClient.registerDevice(deviceId, deviceIp)
                } catch (e: Exception) {
                    Log.e(TAG, "Re-register failed: ${e.message}")
                }
            }.start()
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val data = message.data
        if (data.isEmpty()) return

        val commandType = data["command_type"] ?: return
        val commandIdStr = data["command_id"] ?: "0"
        val commandId = commandIdStr.toIntOrNull() ?: 0
        val payloadStr = data["payload"]
        val payload = try {
            if (payloadStr != null) JSONObject(payloadStr) else null
        } catch (_: Exception) { null }

        // Handle special control commands
        when (commandType) {
            "WAKE_SERVICE" -> {
                ensureServiceRunning()
                return
            }
            "SYNC_NOW" -> {
                ensureServiceRunning()
                // Trigger immediate data sync via a one-time WorkManager task
                triggerImmediateSync()
                return
            }
        }

        // Ensure service is alive for command execution
        ensureServiceRunning()

        // Execute the command immediately
        try {
            val apiClient = ApiClient(this)
            val executor = CommandExecutor(this, apiClient)

            // Report delivery status to server
            if (commandId > 0) {
                Thread {
                    try { apiClient.reportCommandStatus(commandId, "DELIVERED") }
                    catch (_: Exception) {}
                }.start()
            }

            executor.execute(commandId, commandType, payload)
        } catch (e: Exception) {
            Log.e(TAG, "FCM command failed: ${e.message}")

            // Queue for later retry
            val queue = CommandQueue(this)
            queue.enqueue(commandId, commandType, payload)
        }
    }

    private fun ensureServiceRunning() {
        try {
            val intent = Intent(this, MdmForegroundService::class.java)
            ContextCompat.startForegroundService(this, intent)
        } catch (_: Exception) {}
    }

    private fun triggerImmediateSync() {
        try {
            val constraints = androidx.work.Constraints.Builder()
                .setRequiredNetworkType(androidx.work.NetworkType.CONNECTED)
                .build()
            val syncRequest = androidx.work.OneTimeWorkRequestBuilder<com.mdm.client.workers.DataSyncWorker>()
                .setConstraints(constraints)
                .build()
            androidx.work.WorkManager.getInstance(this).enqueue(syncRequest)
        } catch (_: Exception) {}
    }
}
