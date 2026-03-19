package com.mdm.client.media

import android.content.Context
import android.media.MediaRecorder
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.mdm.client.util.NetworkUtils
import java.io.File

class MicrophoneManager(private val context: Context) {

    companion object {
        private const val TAG = "AudioMgr"
    }

    private var recorder: MediaRecorder? = null
    private var currentFile: File? = null
    private var recordingStartTime = 0L
    @Volatile private var isRecording = false

    private val recordings = mutableListOf<Map<String, Any>>()
    private val handler = Handler(Looper.getMainLooper())

    fun startRecording(duration: Int = 30): Map<String, Any> {
        if (isRecording) {
            return mapOf("status" to "error", "message" to "Already recording")
        }
        val outputDir = context.getExternalFilesDir("recordings")
            ?: context.filesDir
        currentFile = File(outputDir, "mic_${System.currentTimeMillis()}.m4a")

        return try {
            recorder = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                MediaRecorder(context)
            } else {
                @Suppress("DEPRECATION")
                MediaRecorder()
            }
            recorder!!.apply {
                setAudioSource(MediaRecorder.AudioSource.MIC)
                setOutputFormat(MediaRecorder.OutputFormat.MPEG_4)
                setAudioEncoder(MediaRecorder.AudioEncoder.AAC)
                setAudioSamplingRate(44100)
                setAudioEncodingBitRate(128000)
                setOutputFile(currentFile!!.absolutePath)
                prepare()
                start()
            }
            recordingStartTime = System.currentTimeMillis()
            isRecording = true

            // Auto-stop after requested duration
            handler.postDelayed({
                if (isRecording) {
                    Log.i(TAG, "Auto-stopping recording after ${duration}s")
                    stopRecording()
                }
            }, duration * 1000L)

            Log.i(TAG, "Recording started: ${currentFile!!.name}")
            mapOf("status" to "success", "message" to "Recording started", "duration" to duration)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start recording: ${e.message}")
            isRecording = false
            recorder?.release()
            recorder = null
            mapOf("status" to "error", "message" to (e.message ?: "Unknown error"))
        }
    }

    fun stopRecording(): Map<String, Any> {
        if (!isRecording) {
            return mapOf("status" to "error", "message" to "Not recording")
        }
        return try {
            recorder?.stop()
            recorder?.release()
            recorder = null
            isRecording = false

            val file = currentFile ?: return mapOf("status" to "error", "message" to "No file")
            val durationSeconds = ((System.currentTimeMillis() - recordingStartTime) / 1000).toInt()
            val deviceIp = NetworkUtils.getLocalIpAddress(context)
            val fileUrl = "http://$deviceIp:8080/mic/file/${file.name}"

            val entry = mapOf(
                "filename" to file.name,
                "file_url" to fileUrl,
                "duration_seconds" to durationSeconds,
                "size_bytes" to file.length()
            )
            recordings.add(entry)
            Log.i(TAG, "Recording stopped: ${file.name} (${durationSeconds}s)")
            entry
        } catch (e: Exception) {
            Log.e(TAG, "Failed to stop recording: ${e.message}")
            isRecording = false
            recorder?.release()
            recorder = null
            mapOf("status" to "error", "message" to (e.message ?: "Stop failed"))
        }
    }

    fun getRecordings(): Map<String, Any> = mapOf("recordings" to recordings.toList())

    fun isCurrentlyRecording() = isRecording
}
