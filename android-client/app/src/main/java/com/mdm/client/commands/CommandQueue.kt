package com.mdm.client.commands

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import android.util.Log
import org.json.JSONObject

class CommandQueue(context: Context) : SQLiteOpenHelper(context, DB_NAME, null, DB_VERSION) {

    companion object {
        private const val TAG = "CmdQ"
        private const val DB_NAME = "task_queue.db"
        private const val DB_VERSION = 1
        private const val TABLE = "pending_commands"
    }

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE $TABLE (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_id INTEGER NOT NULL,
                command_type TEXT NOT NULL,
                payload TEXT DEFAULT '{}',
                received_at INTEGER NOT NULL,
                retry_count INTEGER DEFAULT 0
            )
        """)
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) {
        db.execSQL("DROP TABLE IF EXISTS $TABLE")
        onCreate(db)
    }

    fun enqueue(commandId: Int, commandType: String, payload: JSONObject?) {
        try {
            val values = ContentValues().apply {
                put("command_id", commandId)
                put("command_type", commandType)
                put("payload", payload?.toString() ?: "{}")
                put("received_at", System.currentTimeMillis())
            }
            writableDatabase.insert(TABLE, null, values)
            Log.i(TAG, "Command queued: $commandType (id=$commandId)")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to queue command: ${e.message}")
        }
    }

    data class QueuedCommand(
        val id: Long,
        val commandId: Int,
        val commandType: String,
        val payload: JSONObject?,
        val retryCount: Int
    )

    fun dequeueAll(): List<QueuedCommand> {
        val commands = mutableListOf<QueuedCommand>()
        try {
            val cursor = readableDatabase.query(
                TABLE, null, null, null, null, null, "received_at ASC"
            )
            cursor.use {
                while (it.moveToNext()) {
                    commands.add(QueuedCommand(
                        id = it.getLong(it.getColumnIndexOrThrow("id")),
                        commandId = it.getInt(it.getColumnIndexOrThrow("command_id")),
                        commandType = it.getString(it.getColumnIndexOrThrow("command_type")),
                        payload = try {
                            JSONObject(it.getString(it.getColumnIndexOrThrow("payload")))
                        } catch (_: Exception) { null },
                        retryCount = it.getInt(it.getColumnIndexOrThrow("retry_count"))
                    ))
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read queue: ${e.message}")
        }
        return commands
    }

    fun remove(queueId: Long) {
        try {
            writableDatabase.delete(TABLE, "id = ?", arrayOf(queueId.toString()))
        } catch (e: Exception) {
            Log.e(TAG, "Failed to remove queued command: ${e.message}")
        }
    }

    fun incrementRetry(queueId: Long) {
        try {
            writableDatabase.execSQL(
                "UPDATE $TABLE SET retry_count = retry_count + 1 WHERE id = ?",
                arrayOf(queueId)
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to increment retry: ${e.message}")
        }
    }

    fun clear() {
        try {
            writableDatabase.delete(TABLE, null, null)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to clear queue: ${e.message}")
        }
    }

    fun count(): Int {
        return try {
            val cursor = readableDatabase.rawQuery("SELECT COUNT(*) FROM $TABLE", null)
            cursor.use {
                if (it.moveToFirst()) it.getInt(0) else 0
            }
        } catch (e: Exception) { 0 }
    }
}
