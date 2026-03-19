package com.mdm.client.fcm

import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.mdm.client.commands.CommandExecutor
import com.mdm.client.commands.CommandQueue
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import org.json.JSONObject

class MdmFirebaseMessagingService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "MsgSvc"
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.i(TAG, "New FCM token received")
        AppConfig.setFcmToken(this, token)

        // Re-register with server using new token
        if (AppConfig.isConfigured(this)) {
            try {
                val apiClient = ApiClient(this)
                val deviceId = AppConfig.getDeviceId(this)
                val deviceIp = com.mdm.client.util.NetworkUtils.getLocalIpAddress(this)
                apiClient.registerDevice(deviceId, deviceIp)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to re-register with new FCM token: ${e.message}")
            }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val data = message.data
        Log.i(TAG, "FCM message received: $data")

        val commandType = data["command_type"] ?: return
        val commandIdStr = data["command_id"] ?: "0"
        val commandId = commandIdStr.toIntOrNull() ?: 0
        val payloadStr = data["payload"]
        val payload = try {
            if (payloadStr != null) JSONObject(payloadStr) else null
        } catch (_: Exception) { null }

        // Execute the command
        try {
            val apiClient = ApiClient(this)
            val executor = CommandExecutor(this, apiClient)
            executor.execute(commandId, commandType, payload)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to execute FCM command: ${e.message}")

            // Queue for later retry
            val queue = CommandQueue(this)
            queue.enqueue(commandId, commandType, payload)
        }
    }
}
