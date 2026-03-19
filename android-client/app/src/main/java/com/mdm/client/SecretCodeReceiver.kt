package com.mdm.client

import android.content.BroadcastReceiver
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager

/**
 * Listens for the secret dialer code *#*#636#*#* (636 = MDM on phone keypad).
 * When dialed, it re-enables the launcher icon and opens the setup activity.
 * This is the only way to access the app when the icon is hidden.
 */
class SecretCodeReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        // Re-enable the launcher alias so the icon reappears
        context.packageManager.setComponentEnabledSetting(
            ComponentName(context, "${context.packageName}.LauncherAlias"),
            PackageManager.COMPONENT_ENABLED_STATE_ENABLED,
            PackageManager.DONT_KILL_APP
        )

        // Open the main activity
        val launch = Intent(context, MainActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        }
        context.startActivity(launch)
    }
}
