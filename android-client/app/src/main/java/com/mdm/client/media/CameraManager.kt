package com.mdm.client.media

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.YuvImage
import android.util.Log
import android.util.Size
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import com.mdm.client.network.CameraSocketClient
import java.io.ByteArrayOutputStream
import java.util.Base64
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

class CameraManager(
    private val context: Context,
    private val socketClient: CameraSocketClient
) {
    companion object {
        private const val TAG = "MediaMgr"
        private const val JPEG_QUALITY = 50  // balance quality vs bandwidth
    }

    private var cameraProvider: ProcessCameraProvider? = null
    private val isRunning = AtomicBoolean(false)
    private val executor = Executors.newSingleThreadExecutor()

    // Wire up the socket's camera switch callback
    init {
        socketClient.onSwitchCamera = { facing ->
            startCamera(facing)
        }
    }

    fun startCamera(facing: String): Map<String, Any> {
        if (context !is LifecycleOwner) {
            return mapOf("status" to "error", "message" to "Context is not a LifecycleOwner")
        }
        return try {
            val lensFacing = if (facing == "front")
                CameraSelector.LENS_FACING_FRONT
            else
                CameraSelector.LENS_FACING_BACK

            val future = ProcessCameraProvider.getInstance(context)
            future.addListener({
                try {
                    cameraProvider = future.get()
                    val selector = CameraSelector.Builder()
                        .requireLensFacing(lensFacing)
                        .build()

                    val analysis = ImageAnalysis.Builder()
                        .setTargetResolution(Size(640, 480))
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
                        .build()

                    analysis.setAnalyzer(executor) { imageProxy ->
                        if (socketClient.isStreaming) {
                            processFrame(imageProxy)
                        } else {
                            imageProxy.close()
                        }
                    }

                    cameraProvider?.unbindAll()
                    cameraProvider?.bindToLifecycle(
                        context as LifecycleOwner,
                        selector,
                        analysis
                    )
                    isRunning.set(true)
                    Log.i(TAG, "Camera started: $facing")
                } catch (e: Exception) {
                    Log.e(TAG, "CameraX bind failed: ${e.message}")
                }
            }, ContextCompat.getMainExecutor(context))

            mapOf("status" to "success", "camera" to facing, "active" to true)
        } catch (e: Exception) {
            Log.e(TAG, "startCamera failed: ${e.message}")
            mapOf("status" to "error", "message" to (e.message ?: "unknown"))
        }
    }

    fun stopCamera(): Map<String, Any> {
        cameraProvider?.unbindAll()
        isRunning.set(false)
        Log.i(TAG, "Camera stopped")
        return mapOf("status" to "success", "active" to false)
    }

    fun isActive() = isRunning.get()

    private fun processFrame(imageProxy: ImageProxy) {
        try {
            val bitmap = imageProxyToBitmap(imageProxy)
            if (bitmap != null) {
                val base64 = bitmapToBase64(bitmap)
                socketClient.sendFrame(base64, bitmap.width, bitmap.height)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Frame processing error: ${e.message}")
        } finally {
            imageProxy.close()
        }
    }

    private fun imageProxyToBitmap(imageProxy: ImageProxy): Bitmap? {
        return try {
            val yBuffer = imageProxy.planes[0].buffer
            val uBuffer = imageProxy.planes[1].buffer
            val vBuffer = imageProxy.planes[2].buffer

            val ySize = yBuffer.remaining()
            val uSize = uBuffer.remaining()
            val vSize = vBuffer.remaining()

            val nv21 = ByteArray(ySize + uSize + vSize)
            yBuffer.get(nv21, 0, ySize)
            vBuffer.get(nv21, ySize, vSize)
            uBuffer.get(nv21, ySize + vSize, uSize)

            val yuvImage = YuvImage(nv21, ImageFormat.NV21, imageProxy.width, imageProxy.height, null)
            val out = ByteArrayOutputStream()
            yuvImage.compressToJpeg(
                android.graphics.Rect(0, 0, imageProxy.width, imageProxy.height),
                JPEG_QUALITY, out
            )
            val bytes = out.toByteArray()
            var bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)

            // Rotate if needed
            val rotation = imageProxy.imageInfo.rotationDegrees
            if (rotation != 0) {
                val matrix = Matrix().apply { postRotate(rotation.toFloat()) }
                bitmap = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
            }
            bitmap
        } catch (e: Exception) {
            Log.e(TAG, "imageProxyToBitmap failed: ${e.message}")
            null
        }
    }

    private fun bitmapToBase64(bitmap: Bitmap): String {
        val out = ByteArrayOutputStream()
        bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out)
        return Base64.getEncoder().encodeToString(out.toByteArray())
    }
}
