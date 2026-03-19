package com.mdm.client.collectors

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.os.BatteryManager
import android.os.Build
import android.provider.Settings
import android.telephony.TelephonyManager

class DeviceInfoCollector(private val context: Context) {

    fun getDeviceInfo(): Map<String, Any> = mapOf(
        "manufacturer" to Build.MANUFACTURER,
        "model" to Build.MODEL,
        "brand" to Build.BRAND,
        "device" to Build.DEVICE,
        "hardware" to Build.HARDWARE,
        "product" to Build.PRODUCT,
        "fingerprint" to Build.FINGERPRINT,
        "android_id" to (Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: ""),
        "board" to Build.BOARD,
        "bootloader" to Build.BOOTLOADER
    )

    fun getBatteryInfo(): Map<String, Any> {
        val intent = context.registerReceiver(
            null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)
        )
        val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = intent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val plugged = intent?.getIntExtra(BatteryManager.EXTRA_PLUGGED, -1) ?: -1
        val health = intent?.getIntExtra(BatteryManager.EXTRA_HEALTH, -1) ?: -1
        val temperature = intent?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, 0) ?: 0
        val voltage = intent?.getIntExtra(BatteryManager.EXTRA_VOLTAGE, 0) ?: 0

        val percentage = if (scale > 0) level * 100 / scale else -1
        val statusStr = when (status) {
            BatteryManager.BATTERY_STATUS_CHARGING    -> "charging"
            BatteryManager.BATTERY_STATUS_DISCHARGING -> "discharging"
            BatteryManager.BATTERY_STATUS_FULL        -> "full"
            BatteryManager.BATTERY_STATUS_NOT_CHARGING -> "not_charging"
            else -> "unknown"
        }
        val pluggedStr = when (plugged) {
            BatteryManager.BATTERY_PLUGGED_AC    -> "AC"
            BatteryManager.BATTERY_PLUGGED_USB   -> "USB"
            BatteryManager.BATTERY_PLUGGED_WIRELESS -> "wireless"
            else -> "none"
        }
        val healthStr = when (health) {
            BatteryManager.BATTERY_HEALTH_GOOD     -> "good"
            BatteryManager.BATTERY_HEALTH_OVERHEAT -> "overheat"
            BatteryManager.BATTERY_HEALTH_DEAD      -> "dead"
            else -> "unknown"
        }
        return mapOf(
            "level" to percentage,
            "status" to statusStr,
            "plugged" to pluggedStr,
            "health" to healthStr,
            "temperature_celsius" to temperature / 10.0,
            "voltage_mv" to voltage
        )
    }

    fun getSimInfo(): Map<String, Any> {
        return try {
            val tm = context.getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            mapOf(
                "operator_name" to (tm.networkOperatorName ?: ""),
                "operator_code" to (tm.networkOperator ?: ""),
                "country_iso" to (tm.networkCountryIso ?: ""),
                "sim_state" to tm.simState,
                "sim_operator" to (tm.simOperatorName ?: ""),
                "phone_type" to tm.phoneType,
                "data_state" to tm.dataState
            )
        } catch (e: Exception) {
            mapOf("error" to (e.message ?: "permission denied"))
        }
    }

    fun getOsInfo(): Map<String, Any> = mapOf(
        "version" to Build.VERSION.RELEASE,
        "sdk_int" to Build.VERSION.SDK_INT,
        "security_patch" to Build.VERSION.SECURITY_PATCH,
        "build_id" to Build.ID,
        "incremental" to Build.VERSION.INCREMENTAL,
        "codename" to Build.VERSION.CODENAME,
        "build_type" to Build.TYPE,
        "build_tags" to Build.TAGS
    )
}
