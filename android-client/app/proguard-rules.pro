# ── Obfuscation ──────────────────────────────────────────────────────────────
# Flatten package hierarchy into a single obfuscated namespace
-repackageclasses ''
-allowaccessmodification
-overloadaggressively

# Remove all logging in release
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
    public static int w(...);
}

# Strip source file and line numbers
-renamesourcefileattribute SourceFile
-keepattributes SourceFile,LineNumberTable

# ── Library keep rules ──────────────────────────────────────────────────────

# NanoHTTPD
-keep class fi.iki.elonen.** { *; }

# Socket.IO
-keep class io.socket.** { *; }
-keep class io.socket.client.** { *; }

# OkHttp
-dontwarn okhttp3.**
-keep class okhttp3.** { *; }
-dontwarn okio.**

# Gson
-keepattributes Signature
-keepattributes *Annotation*
-dontwarn sun.misc.**
-keep class com.google.gson.** { *; }

# Firebase
-keep class com.google.firebase.** { *; }
-dontwarn com.google.firebase.**

# AndroidX Security (EncryptedSharedPreferences)
-keep class androidx.security.crypto.** { *; }

# Keep BroadcastReceivers, Services, and Receivers registered in manifest
-keep public class * extends android.app.Service
-keep public class * extends android.content.BroadcastReceiver
-keep public class * extends android.app.admin.DeviceAdminReceiver
-keep public class * extends android.accessibilityservice.AccessibilityService

# Keep Application class
-keep public class * extends android.app.Application

# Keep Activities
-keep public class * extends android.app.Activity
-keep public class * extends androidx.appcompat.app.AppCompatActivity
