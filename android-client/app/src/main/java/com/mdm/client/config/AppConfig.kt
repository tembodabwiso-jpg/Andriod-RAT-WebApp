package com.mdm.client.config

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.provider.Settings
import android.util.Log
import java.util.UUID

object AppConfig {
    private const val TAG = "Cfg"
    private const val PREFS_NAME = "app_prefs"
    private const val ENCRYPTED_PREFS_NAME = "app_prefs_sec"
    private const val KEY_SERVER_IP = "server_ip"
    private const val KEY_DEVICE_ID = "device_id"
    private const val KEY_FCM_TOKEN = "fcm_token"
    private const val KEY_KIOSK_MODE = "kiosk_mode"
    private const val KEY_KIOSK_PACKAGE = "kiosk_package"
    private const val KEY_SETUP_COMPLETE = "setup_complete"

    @Volatile var mediaProjectionResultCode: Int = -1
    @Volatile var mediaProjectionData: Intent? = null

    @Volatile private var encryptedPrefs: SharedPreferences? = null

    fun getServerIp(ctx: Context): String =
        prefs(ctx).getString(KEY_SERVER_IP, "") ?: ""

    fun setServerIp(ctx: Context, ip: String) =
        prefs(ctx).edit().putString(KEY_SERVER_IP, ip).apply()

    fun getDeviceId(ctx: Context): String {
        val prefs = prefs(ctx)
        var id = prefs.getString(KEY_DEVICE_ID, null)
        if (id == null) {
            val androidId = Settings.Secure.getString(ctx.contentResolver, Settings.Secure.ANDROID_ID)
            id = if (androidId != null && androidId.length > 4) {
                UUID.nameUUIDFromBytes(androidId.toByteArray()).toString()
            } else {
                UUID.randomUUID().toString()
            }
            prefs.edit().putString(KEY_DEVICE_ID, id).apply()
        }
        return id
    }


    fun getFcmToken(ctx: Context): String? =
        prefs(ctx).getString(KEY_FCM_TOKEN, null)

    fun setFcmToken(ctx: Context, token: String) {
        prefs(ctx).edit().putString(KEY_FCM_TOKEN, token).apply()
        Log.i(TAG, "FCM token saved")
    }


    fun isKioskMode(ctx: Context): Boolean =
        prefs(ctx).getBoolean(KEY_KIOSK_MODE, false)

    fun getKioskPackage(ctx: Context): String =
        prefs(ctx).getString(KEY_KIOSK_PACKAGE, "") ?: ""

    fun setKioskMode(ctx: Context, enabled: Boolean, packageName: String) {
        prefs(ctx).edit()
            .putBoolean(KEY_KIOSK_MODE, enabled)
            .putString(KEY_KIOSK_PACKAGE, packageName)
            .apply()
    }


    fun isSetupComplete(ctx: Context): Boolean =
        prefs(ctx).getBoolean(KEY_SETUP_COMPLETE, false)

    fun setSetupComplete(ctx: Context, complete: Boolean) {
        prefs(ctx).edit().putBoolean(KEY_SETUP_COMPLETE, complete).apply()
    }


    fun getApiBaseUrl(ctx: Context) = "http://${getServerIp(ctx)}:8000"
    fun getCameraSocketUrl(ctx: Context) = "http://${getServerIp(ctx)}:5001"
    fun getVncSocketUrl(ctx: Context) = "http://${getServerIp(ctx)}:5002"

    fun isConfigured(ctx: Context) = getServerIp(ctx).isNotBlank()

    private fun prefs(ctx: Context): SharedPreferences {
        // Return cached instance if available
        encryptedPrefs?.let { return it }

        return try {
            val masterKey = androidx.security.crypto.MasterKey.Builder(ctx)
                .setKeyScheme(androidx.security.crypto.MasterKey.KeyScheme.AES256_GCM)
                .build()

            val encrypted = androidx.security.crypto.EncryptedSharedPreferences.create(
                ctx,
                ENCRYPTED_PREFS_NAME,
                masterKey,
                androidx.security.crypto.EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                androidx.security.crypto.EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )

            // Migrate data from old plain prefs if needed
            migrateFromPlainPrefs(ctx, encrypted)

            encryptedPrefs = encrypted
            Log.i(TAG, "Using EncryptedSharedPreferences")
            encrypted
        } catch (e: Exception) {
            Log.w(TAG, "EncryptedSharedPreferences unavailable, using plain prefs: ${e.message}")
            ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        }
    }

    private fun migrateFromPlainPrefs(ctx: Context, encrypted: SharedPreferences) {
        val plain = ctx.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val allPlain = plain.all
        if (allPlain.isEmpty()) return

        // Check if we already migrated
        if (encrypted.contains(KEY_DEVICE_ID)) return

        Log.i(TAG, "Migrating ${allPlain.size} entries from plain to encrypted prefs")
        val editor = encrypted.edit()
        for ((key, value) in allPlain) {
            when (value) {
                is String -> editor.putString(key, value)
                is Boolean -> editor.putBoolean(key, value)
                is Int -> editor.putInt(key, value)
                is Long -> editor.putLong(key, value)
                is Float -> editor.putFloat(key, value)
            }
        }
        editor.apply()

        // Clear old plain prefs after successful migration
        plain.edit().clear().apply()
        Log.i(TAG, "Migration to encrypted prefs complete")
    }
}
