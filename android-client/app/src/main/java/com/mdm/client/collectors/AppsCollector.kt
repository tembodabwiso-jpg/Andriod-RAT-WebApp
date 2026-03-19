package com.mdm.client.collectors

import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log

class AppsCollector(private val context: Context) {

    companion object {
        private const val TAG = "AppSync"
    }

    fun getApps(): List<Map<String, Any>> {
        return try {
            val pm = context.packageManager
            val packages = pm.getInstalledPackages(PackageManager.GET_META_DATA)
            val usageMap = getUsageStats()

            packages.map { pkg ->
                val usage = usageMap[pkg.packageName]
                mapOf(
                    "package_name" to pkg.packageName,
                    "app_name" to (pm.getApplicationLabel(pkg.applicationInfo).toString()),
                    "app_version" to (pkg.versionName ?: ""),
                    "install_time" to pkg.firstInstallTime,
                    "last_used_time" to (usage?.lastTimeUsed ?: pkg.lastUpdateTime),
                    "is_system_app" to ((pkg.applicationInfo.flags and
                            android.content.pm.ApplicationInfo.FLAG_SYSTEM) != 0),
                    "is_enabled" to pkg.applicationInfo.enabled,
                    "total_time_in_foreground" to (usage?.totalTimeInForeground ?: 0L)
                )
            }.sortedBy { it["app_name"] as String }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to read apps: ${e.message}")
            emptyList()
        }
    }

    private fun getUsageStats(): Map<String, android.app.usage.UsageStats> {
        return try {
            val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
            val end = System.currentTimeMillis()
            val start = end - 30L * 24 * 60 * 60 * 1000 // 30 days
            usm.queryUsageStats(UsageStatsManager.INTERVAL_MONTHLY, start, end)
                ?.associateBy { it.packageName } ?: emptyMap()
        } catch (e: Exception) {
            Log.w(TAG, "Usage stats unavailable (need PACKAGE_USAGE_STATS): ${e.message}")
            emptyMap()
        }
    }
}
