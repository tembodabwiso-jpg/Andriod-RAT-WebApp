package com.mdm.client.workers

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import com.mdm.client.network.OfflineDataQueue
import com.mdm.client.util.NetworkUtils
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject

/**
 * Worker that drains the offline data queue when connectivity returns.
 *
 * Triggered by:
 * 1. ConnectivityManager callback in MdmForegroundService (immediate)
 * 2. Periodic WorkManager schedule (every 15 min, requires network)
 *
 * Processes queued payloads in FIFO order, removing successfully delivered
 * entries and incrementing retry count on failures.
 */
class OfflineSyncWorker(context: Context, params: WorkerParameters) :
    CoroutineWorker(context, params) {

    companion object {
        private const val TAG = "OffSync"
        const val WORK_NAME = "offline_sync"
    }

    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val ctx = applicationContext

        if (!AppConfig.isConfigured(ctx)) {
            return@withContext Result.success()
        }

        val queue = OfflineDataQueue(ctx)
        val pendingCount = queue.count()

        if (pendingCount == 0) {
            Log.d(TAG, "No offline data to sync")
            return@withContext Result.success()
        }

        Log.i(TAG, "Starting offline sync — $pendingCount queued requests")

        // Purge entries that have exceeded max retries
        queue.purgeExpired()

        val apiClient = ApiClient(ctx)
        var successCount = 0
        var failCount = 0

        // Process in batches of 50 to avoid holding the DB connection too long
        while (true) {
            val batch = queue.peekBatch(50)
            if (batch.isEmpty()) break

            for (request in batch) {
                try {
                    val body = JSONObject(request.body)
                    val delivered = apiClient.postDirect(request.path, body)

                    if (delivered) {
                        queue.remove(request.id)
                        successCount++
                    } else {
                        queue.markRetry(request.id)
                        failCount++
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to deliver ${request.dataType}: ${e.message}")
                    queue.markRetry(request.id)
                    failCount++
                }
            }
        }

        val remaining = queue.count()
        Log.i(TAG, "Offline sync complete — delivered=$successCount, failed=$failCount, remaining=$remaining")

        if (remaining > 0) {
            Result.retry()
        } else {
            Result.success()
        }
    }
}
