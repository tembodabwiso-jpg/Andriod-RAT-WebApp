package com.mdm.client.network

import android.content.Context
import android.util.Log
import com.mdm.client.config.AppConfig
import io.socket.client.IO
import io.socket.client.Socket
import org.json.JSONObject
import java.net.URISyntaxException

class CameraSocketClient(private val context: Context) {

    companion object {
        private const val TAG = "MediaSock"
    }

    private var socket: Socket? = null

    @Volatile var isStreaming = false
        private set

    /** Callback invoked when the server requests a camera switch */
    var onSwitchCamera: ((String) -> Unit)? = null

    fun connect() {
        val url = AppConfig.getCameraSocketUrl(context)
        if (url.contains(":5001")) {
            try {
                val opts = IO.Options().apply {
                    transports = arrayOf("websocket")
                    reconnection = true
                    reconnectionDelay = 2000
                    reconnectionAttempts = Int.MAX_VALUE
                }
                socket = IO.socket(url, opts)
                socket?.apply {
                    on(Socket.EVENT_CONNECT) { Log.i(TAG, "Connected to camera server") }
                    on(Socket.EVENT_DISCONNECT) {
                        Log.i(TAG, "Disconnected from camera server")
                        isStreaming = false
                    }
                    on("start_camera") { args ->
                        val facing = (args.getOrNull(0) as? JSONObject)?.optString("camera", "back") ?: "back"
                        Log.i(TAG, "start_camera received: $facing")
                        isStreaming = true
                        onSwitchCamera?.invoke(facing)
                    }
                    on("stop_camera") {
                        Log.i(TAG, "stop_camera received")
                        isStreaming = false
                    }
                    on("switch_camera") { args ->
                        val facing = (args.getOrNull(0) as? JSONObject)?.optString("camera", "back") ?: "back"
                        onSwitchCamera?.invoke(facing)
                    }
                    connect()
                }
            } catch (e: URISyntaxException) {
                Log.e(TAG, "Bad URL: $url — ${e.message}")
            }
        }
    }

    /** Emit a camera frame (base64 JPEG) to the streaming server. */
    fun sendFrame(base64Jpeg: String, width: Int, height: Int) {
        socket?.emit("camera_data", JSONObject().apply {
            put("image", base64Jpeg)
            put("width", width)
            put("height", height)
        })
    }

    fun disconnect() {
        isStreaming = false
        socket?.disconnect()
        socket = null
    }
}
