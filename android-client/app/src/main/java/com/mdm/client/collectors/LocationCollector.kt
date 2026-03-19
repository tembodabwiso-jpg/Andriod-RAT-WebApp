package com.mdm.client.collectors

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.os.Looper
import android.util.Log
import androidx.core.content.ContextCompat
import com.google.android.gms.location.*
import com.mdm.client.config.AppConfig
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume

class LocationCollector(private val context: Context) {

    companion object {
        private const val TAG = "LocSync"
    }

    private val fusedClient = LocationServices.getFusedLocationProviderClient(context)

    @Volatile private var lastLocation: Location? = null

    fun getLastLocation(): Map<String, Any> {
        val loc = lastLocation ?: return mapOf("status" to "error", "message" to "No location yet")
        return locationToMap(loc)
    }

    suspend fun getFreshLocation(): Map<String, Any> {
        if (!hasPermission()) return mapOf("status" to "error", "message" to "Permission denied")
        return suspendCancellableCoroutine { cont ->
            val request = LocationRequest.Builder(Priority.PRIORITY_HIGH_ACCURACY, 0)
                .setMaxUpdates(1)
                .setWaitForAccurateLocation(false)
                .build()
            val callback = object : LocationCallback() {
                override fun onLocationResult(result: LocationResult) {
                    fusedClient.removeLocationUpdates(this)
                    val loc = result.lastLocation
                    if (loc != null) {
                        lastLocation = loc
                        cont.resume(locationToMap(loc))
                    } else {
                        cont.resume(mapOf("status" to "error", "message" to "Null location"))
                    }
                }
            }
            try {
                fusedClient.requestLocationUpdates(request, callback, Looper.getMainLooper())
                cont.invokeOnCancellation { fusedClient.removeLocationUpdates(callback) }
            } catch (e: SecurityException) {
                cont.resume(mapOf("status" to "error", "message" to "SecurityException"))
            }
        }
    }

    private fun locationToMap(loc: Location): Map<String, Any> = mapOf(
        "status" to "success",
        "deviceId" to AppConfig.getDeviceId(context),
        "latitude" to loc.latitude,
        "longitude" to loc.longitude,
        "accuracy" to loc.accuracy,
        "altitude" to loc.altitude,
        "speed" to loc.speed,
        "bearing" to loc.bearing,
        "provider" to (loc.provider ?: "unknown"),
        "timestamp" to loc.time
    )

    fun updateLastKnown(location: Location) {
        lastLocation = location
    }

    private fun hasPermission() = ContextCompat.checkSelfPermission(
        context, Manifest.permission.ACCESS_FINE_LOCATION
    ) == PackageManager.PERMISSION_GRANTED
}
