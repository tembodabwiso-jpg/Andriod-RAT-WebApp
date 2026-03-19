package com.mdm.client.media

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import com.mdm.client.util.NetworkUtils
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

class ScreenshotManager(
    private val context: Context,
    private val screenCaptureManager: ScreenCaptureManager
) {
    companion object {
        private const val TAG = "CaptureMgr"
        private val TIMESTAMP_FORMAT = SimpleDateFormat("yyyyMMdd_HHmmss_SSS", Locale.US)
    }

    fun captureScreenshot(): Map<String, Any> {
        val bitmap = screenCaptureManager.captureFrame()
            ?: return mapOf(
                "status" to "error",
                "message" to "Screen capture unavailable — grant MediaProjection permission in the app"
            )

        return try {
            val filename = "screenshot_${TIMESTAMP_FORMAT.format(Date())}.jpg"
            val outputDir = context.getExternalFilesDir("screenshots") ?: context.filesDir
            val file = File(outputDir, filename)

            file.outputStream().use { out ->
                bitmap.compress(Bitmap.CompressFormat.JPEG, 80, out)
            }

            val deviceIp = NetworkUtils.getLocalIpAddress(context)
            val fileUrl = "http://$deviceIp:8080/screenshot/file/$filename"

            Log.i(TAG, "Screenshot saved: $filename")
            mapOf(
                "filename" to filename,
                "file_url" to fileUrl
            )
        } catch (e: Exception) {
            Log.e(TAG, "Screenshot failed: ${e.message}")
            mapOf("status" to "error", "message" to (e.message ?: "Screenshot failed"))
        }
    }
}
