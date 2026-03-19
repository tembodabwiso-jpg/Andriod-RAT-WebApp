package com.mdm.client.util

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Formats epoch-millisecond timestamps into the string format the Python server
 * expects in its strptime call:  "%a %b %d %H:%M:%S %Z%z %Y"
 * Example output: "Sat Apr 05 12:50:47 GMT+05:30 2025"
 */
object DateFormatter {
    private val SERVER_FORMAT = SimpleDateFormat("EEE MMM dd HH:mm:ss zzz yyyy", Locale.US)

    fun format(epochMs: Long): String = SERVER_FORMAT.format(Date(epochMs))
}
