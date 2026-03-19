package com.mdm.client.collectors

import android.content.Context
import android.provider.ContactsContract
import android.util.Log

class ContactsCollector(private val context: Context) {

    companion object {
        private const val TAG = "CtSync"
    }

    fun getContacts(): List<Map<String, Any>> {
        val contacts = mutableMapOf<String, MutableList<String>>() // name -> phones
        return try {
            val cursor = context.contentResolver.query(
                ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
                arrayOf(
                    ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                    ContactsContract.CommonDataKinds.Phone.NUMBER
                ),
                null, null,
                "${ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME} ASC"
            )
            cursor?.use {
                val nameIdx = it.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
                val numIdx  = it.getColumnIndexOrThrow(ContactsContract.CommonDataKinds.Phone.NUMBER)
                while (it.moveToNext()) {
                    val name   = it.getString(nameIdx) ?: "Unknown"
                    val number = it.getString(numIdx)  ?: ""
                    contacts.getOrPut(name) { mutableListOf() }.add(number)
                }
            }
            contacts.map { (name, numbers) ->
                mapOf(
                    "name" to name,
                    "number" to numbers.firstOrNull().orEmpty(),
                    "numbers" to numbers
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read contacts: ${e.message}")
            emptyList()
        }
    }
}
