package com.nequipos.agent.data.remote

import com.nequipos.agent.BuildConfig
import com.nequipos.agent.data.local.SecureConfigStore
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

data class AndroidReleaseCheck(
    val status: String, // "update_available" | "up_to_date" | "error"
    val currentVersion: String,
    val latestVersion: String,
    val updateAvailable: Boolean,
    val message: String,
    val releaseNotes: String,
    val apkDownloadUrl: String?,
    val sha256SumsUrl: String?
)

class AppUpdaterClient {

    private val apiClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .followRedirects(true)
        .build()

    private val downloadClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(90, TimeUnit.SECONDS)
        .followRedirects(true)
        .build()

    fun checkLatestRelease(githubRepo: String): AndroidReleaseCheck {
        val currentVer = BuildConfig.VERSION_NAME.trim().trimStart('v', 'V')
        val repo = SecureConfigStore.normalizeRepo(githubRepo)

        if (repo.isEmpty() || !repo.contains("/") || repo.lowercase().startsWith("tu-usuario/")) {
            return AndroidReleaseCheck(
                status = "error",
                currentVersion = currentVer,
                latestVersion = currentVer,
                updateAvailable = false,
                message = "Configura el repositorio GitHub (ej. scanby/nequipos).",
                releaseNotes = "",
                apkDownloadUrl = null,
                sha256SumsUrl = null
            )
        }

        val request = Request.Builder()
            .url("https://api.github.com/repos/$repo/releases/latest")
            .addHeader("Accept", "application/vnd.github+json")
            .addHeader("User-Agent", "NequiPayPOS-Android/$currentVer")
            .get()
            .build()

        return try {
            apiClient.newCall(request).execute().use { response ->
                if (response.code == 404) {
                    return AndroidReleaseCheck(
                        status = "error",
                        currentVersion = currentVer,
                        latestVersion = currentVer,
                        updateAvailable = false,
                        message = "No se encontró un Release publicado en '$repo' (HTTP 404).",
                        releaseNotes = "",
                        apkDownloadUrl = null,
                        sha256SumsUrl = null
                    )
                }
                if (!response.isSuccessful) {
                    return AndroidReleaseCheck(
                        status = "error",
                        currentVersion = currentVer,
                        latestVersion = currentVer,
                        updateAvailable = false,
                        message = "GitHub respondió HTTP ${response.code}",
                        releaseNotes = "",
                        apkDownloadUrl = null,
                        sha256SumsUrl = null
                    )
                }

                val data = JSONObject(response.body?.string().orEmpty())
                val tag = data.optString("tag_name", currentVer).trimStart('v', 'V')
                val notes = data.optString("body", "")
                val assets = data.optJSONArray("assets")

                var apkUrl: String? = null
                var sumsUrl: String? = null
                if (assets != null) {
                    for (i in 0 until assets.length()) {
                        val asset = assets.optJSONObject(i) ?: continue
                        val name = asset.optString("name", "")
                        val dlUrl = asset.optString("browser_download_url", "")
                        if (name == ANDROID_ASSET_NAME || (apkUrl == null && name.endsWith(".apk", ignoreCase = true))) {
                            apkUrl = dlUrl
                        } else if (name == "SHA256SUMS.txt") {
                            sumsUrl = dlUrl
                        }
                    }
                }

                val isNewer = isRemoteNewer(tag, currentVer)
                if (isNewer && !apkUrl.isNullOrBlank()) {
                    AndroidReleaseCheck(
                        status = "update_available",
                        currentVersion = currentVer,
                        latestVersion = tag,
                        updateAvailable = true,
                        message = "Nueva versión v$tag disponible (instalada: v$currentVer).",
                        releaseNotes = notes,
                        apkDownloadUrl = apkUrl,
                        sha256SumsUrl = sumsUrl
                    )
                } else if (isNewer && apkUrl.isNullOrBlank()) {
                    AndroidReleaseCheck(
                        status = "error",
                        currentVersion = currentVer,
                        latestVersion = tag,
                        updateAvailable = false,
                        message = "El Release v$tag existe, pero no contiene el archivo $ANDROID_ASSET_NAME.",
                        releaseNotes = notes,
                        apkDownloadUrl = null,
                        sha256SumsUrl = sumsUrl
                    )
                } else {
                    AndroidReleaseCheck(
                        status = "up_to_date",
                        currentVersion = currentVer,
                        latestVersion = tag,
                        updateAvailable = false,
                        message = "Ya tienes la última versión instalada (v$currentVer).",
                        releaseNotes = notes,
                        apkDownloadUrl = apkUrl,
                        sha256SumsUrl = sumsUrl
                    )
                }
            }
        } catch (e: Exception) {
            AndroidReleaseCheck(
                status = "error",
                currentVersion = currentVer,
                latestVersion = currentVer,
                updateAvailable = false,
                message = "No se pudo consultar actualizaciones (${e.message ?: "sin internet"}).",
                releaseNotes = "",
                apkDownloadUrl = null,
                sha256SumsUrl = null
            )
        }
    }

    fun downloadApkAndVerify(
        apkUrl: String,
        sha256SumsUrl: String?,
        cacheDir: File,
        onProgressPercent: (Int) -> Unit
    ): File {
        val updatesDir = File(cacheDir, "updates").apply { mkdirs() }
        val targetFile = File(updatesDir, ANDROID_ASSET_NAME)
        if (targetFile.exists()) {
            targetFile.delete()
        }

        val request = Request.Builder()
            .url(apkUrl)
            .addHeader("User-Agent", "NequiPayPOS-Android")
            .get()
            .build()

        val computedSha256: String
        downloadClient.newCall(request).execute().use { response ->
            if (!response.isSuccessful) {
                throw IllegalStateException("Error descargando APK (HTTP ${response.code})")
            }
            val body = response.body ?: throw IllegalStateException("Respuesta vacía al descargar APK.")
            val totalBytes = body.contentLength()
            val digest = MessageDigest.getInstance("SHA-256")
            var downloaded = 0L
            var lastReported = -1

            body.byteStream().use { input ->
                FileOutputStream(targetFile).use { output ->
                    val buffer = ByteArray(16 * 1024)
                    while (true) {
                        val read = input.read(buffer)
                        if (read <= 0) break
                        output.write(buffer, 0, read)
                        digest.update(buffer, 0, read)
                        downloaded += read
                        if (totalBytes > 0) {
                            val pct = ((downloaded * 100) / totalBytes).toInt().coerceIn(0, 100)
                            if (pct != lastReported) {
                                lastReported = pct
                                onProgressPercent(pct)
                            }
                        }
                    }
                    output.flush()
                }
            }
            computedSha256 = digest.digest().joinToString("") { "%02x".format(it) }.lowercase()
        }

        if (!sha256SumsUrl.isNullOrBlank()) {
            val sumsReq = Request.Builder()
                .url(sha256SumsUrl)
                .addHeader("User-Agent", "NequiPayPOS-Android")
                .get()
                .build()
            downloadClient.newCall(sumsReq).execute().use { sumsResp ->
                if (sumsResp.isSuccessful) {
                    val sumsText = sumsResp.body?.string().orEmpty().lowercase()
                    if (sumsText.isNotBlank() && !sumsText.contains(computedSha256)) {
                        targetFile.delete()
                        throw SecurityException("La verificación SHA-256 del APK falló. Descarga abortada.")
                    }
                }
            }
        }

        return targetFile
    }

    companion object {
        const val ANDROID_ASSET_NAME = "NequiPayPOS_Agent_Android.apk"

        internal fun parseSemver(raw: String): Triple<Int, Int, Int> {
            val match = Regex("""(\d+)\.(\d+)\.(\d+)""").find(raw.trim().trimStart('v', 'V'))
                ?: return Triple(0, 0, 0)
            return Triple(
                match.groupValues[1].toIntOrNull() ?: 0,
                match.groupValues[2].toIntOrNull() ?: 0,
                match.groupValues[3].toIntOrNull() ?: 0
            )
        }

        internal fun isRemoteNewer(remote: String, current: String): Boolean {
            val (r1, r2, r3) = parseSemver(remote)
            val (c1, c2, c3) = parseSemver(current)
            if (r1 != c1) return r1 > c1
            if (r2 != c2) return r2 > c2
            return r3 > c3
        }
    }
}
