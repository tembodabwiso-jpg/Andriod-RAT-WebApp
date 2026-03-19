package com.mdm.client.server

import fi.iki.elonen.NanoHTTPD
import java.io.File
import java.text.SimpleDateFormat
import java.util.*

object FileManagerHandler {

    private val dateFormat = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US)

    fun listFiles(path: String): Map<String, Any> {
        val dir = File(path)
        if (!dir.exists() || !dir.isDirectory) {
            return mapOf("success" to false, "path" to path, "files" to emptyList<Any>())
        }
        val files = (dir.listFiles() ?: emptyArray()).map { file ->
            mapOf(
                "name" to file.name,
                "type" to if (file.isDirectory) "folder" else "file",
                "path" to file.absolutePath,
                "size" to if (file.isFile) formatSize(file.length()) else "-",
                "modified" to dateFormat.format(Date(file.lastModified())),
                "icon" to iconFor(file)
            )
        }.sortedWith(compareBy({ it["type"] as String }, { it["name"] as String }))

        return mapOf("success" to true, "path" to path, "files" to files)
    }

    fun deleteFile(path: String): Map<String, Any> {
        if (path.isBlank()) return mapOf("success" to false, "message" to "No path")
        val success = File(path).deleteRecursively()
        return mapOf("success" to success, "message" to if (success) "Deleted" else "Failed")
    }

    fun handleUpload(tempFilePath: String?, destPath: String, fileName: String): Map<String, Any> {
        if (tempFilePath == null) return mapOf("success" to false, "message" to "No file")
        return try {
            val dest = File(destPath, fileName)
            File(tempFilePath).copyTo(dest, overwrite = true)
            mapOf("success" to true, "path" to dest.absolutePath, "message" to "Uploaded")
        } catch (e: Exception) {
            mapOf("success" to false, "message" to (e.message ?: "Upload failed"))
        }
    }

    fun serveDownload(path: String): NanoHTTPD.Response {
        val file = File(path)
        return if (file.exists() && file.isFile) {
            NanoHTTPD.newFixedLengthResponse(
                NanoHTTPD.Response.Status.OK,
                "application/octet-stream",
                file.inputStream(),
                file.length()
            ).apply {
                addHeader("Content-Disposition", "attachment; filename=\"${file.name}\"")
            }
        } else {
            NanoHTTPD.newFixedLengthResponse(
                NanoHTTPD.Response.Status.NOT_FOUND,
                "text/plain",
                "File not found: $path"
            )
        }
    }

    private fun formatSize(bytes: Long): String = when {
        bytes < 1024 -> "${bytes}B"
        bytes < 1024 * 1024 -> "${bytes / 1024}KB"
        bytes < 1024 * 1024 * 1024 -> "${bytes / (1024 * 1024)}MB"
        else -> "${bytes / (1024 * 1024 * 1024)}GB"
    }

    private fun iconFor(file: File): String = when {
        file.isDirectory -> "folder"
        file.name.endsWith(".jpg") || file.name.endsWith(".png") || file.name.endsWith(".jpeg") -> "image"
        file.name.endsWith(".mp4") || file.name.endsWith(".mkv") -> "video"
        file.name.endsWith(".mp3") || file.name.endsWith(".m4a") -> "audio"
        file.name.endsWith(".pdf") -> "pdf"
        file.name.endsWith(".apk") -> "apk"
        else -> "file"
    }
}
