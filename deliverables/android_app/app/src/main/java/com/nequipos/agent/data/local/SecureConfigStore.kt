package com.nequipos.agent.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.nequipos.agent.domain.model.ServerConfig
import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class SecureConfigStore(context: Context) {

    private val prefs: SharedPreferences

    init {
        val masterKey = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()

        prefs = EncryptedSharedPreferences.create(
            context,
            "nequipos_secure_prefs",
            masterKey,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
        )
    }

    fun getServerConfig(): ServerConfig {
        val savedAlias = prefs.getString(KEY_ACCOUNT_ALIAS, "Caja Principal")?.trim().orEmpty()
        val savedRepo = prefs.getString(KEY_GITHUB_REPO, ServerConfig.DEFAULT_GITHUB_REPO)?.trim().orEmpty()
        return ServerConfig(
            serverIp = prefs.getString(KEY_SERVER_IP, "") ?: "",
            serverPort = prefs.getInt(KEY_SERVER_PORT, 8000),
            apiToken = prefs.getString(KEY_API_TOKEN, "") ?: "",
            accountAlias = savedAlias.ifEmpty { "Caja Principal" },
            githubRepo = savedRepo.ifEmpty { ServerConfig.DEFAULT_GITHUB_REPO }
        )
    }

    fun saveServerConfig(config: ServerConfig) {
        val normalizedAlias = config.accountAlias.trim().ifEmpty { "Caja Principal" }
        val normalizedRepo = normalizeRepo(config.githubRepo).ifEmpty { ServerConfig.DEFAULT_GITHUB_REPO }
        prefs.edit()
            .putString(KEY_SERVER_IP, config.serverIp.trim())
            .putInt(KEY_SERVER_PORT, config.serverPort)
            .putString(KEY_API_TOKEN, config.apiToken.trim())
            .putString(KEY_ACCOUNT_ALIAS, normalizedAlias)
            .putString(KEY_GITHUB_REPO, normalizedRepo)
            .apply()
    }

    fun updateGithubRepoIfValid(repo: String) {
        val cleaned = normalizeRepo(repo)
        if (cleaned.isNotEmpty() && cleaned.contains("/") && !cleaned.lowercase().startsWith("tu-usuario/")) {
            prefs.edit().putString(KEY_GITHUB_REPO, cleaned).apply()
        }
    }

    fun setLastSyncStatus(status: String) {
        prefs.edit().putString(KEY_LAST_SYNC_STATUS, status).apply()
    }

    fun getLastSyncStatus(): String {
        return prefs.getString(KEY_LAST_SYNC_STATUS, "Sin sincronizaciones registradas aún") ?: ""
    }

    @Synchronized
    fun appendDiagnosticEvent(message: String) {
        val time = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
        val existing = prefs.getString(KEY_DIAGNOSTIC_LOG, "").orEmpty()
            .split("\n")
            .filter { it.isNotBlank() }
        val updated = (listOf("[$time] $message") + existing).take(8)
        prefs.edit().putString(KEY_DIAGNOSTIC_LOG, updated.joinToString("\n")).apply()
    }

    fun getDiagnosticEvents(): String {
        val raw = prefs.getString(KEY_DIAGNOSTIC_LOG, "").orEmpty()
        return raw.ifBlank { "Aún no se han recibido eventos de Nequi." }
    }

    fun hasPinConfigured(): Boolean = !prefs.getString(KEY_PIN_HASH, null).isNullOrEmpty()

    fun setPin(pin: String) {
        prefs.edit().putString(KEY_PIN_HASH, sha256(pin)).apply()
    }

    fun verifyPin(pin: String): Boolean {
        val stored = prefs.getString(KEY_PIN_HASH, null) ?: return true
        return stored == sha256(pin)
    }

    private fun sha256(input: String): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(input.toByteArray(Charsets.UTF_8))
        return bytes.joinToString("") { "%02x".format(it) }
    }

    companion object {
        private const val KEY_SERVER_IP = "server_ip"
        private const val KEY_SERVER_PORT = "server_port"
        private const val KEY_API_TOKEN = "api_token"
        private const val KEY_ACCOUNT_ALIAS = "account_alias"
        private const val KEY_GITHUB_REPO = "github_repo"
        private const val KEY_PIN_HASH = "local_pin_hash"
        private const val KEY_LAST_SYNC_STATUS = "last_sync_status"
        private const val KEY_DIAGNOSTIC_LOG = "diagnostic_log"

        fun normalizeRepo(raw: String): String {
            return raw.trim()
                .removePrefix("https://github.com/")
                .removePrefix("http://github.com/")
                .removeSuffix(".git")
                .trim('/')
        }
    }
}
