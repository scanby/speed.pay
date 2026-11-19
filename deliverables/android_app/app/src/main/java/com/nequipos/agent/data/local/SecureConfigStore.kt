package com.nequipos.agent.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import com.nequipos.agent.domain.model.ServerConfig
import java.security.MessageDigest

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
        return ServerConfig(
            serverIp = prefs.getString(KEY_SERVER_IP, "") ?: "",
            serverPort = prefs.getInt(KEY_SERVER_PORT, 8000),
            apiToken = prefs.getString(KEY_API_TOKEN, "") ?: "",
            accountAlias = prefs.getString(KEY_ACCOUNT_ALIAS, "Caja Principal") ?: "Caja Principal"
        )
    }

    fun saveServerConfig(config: ServerConfig) {
        prefs.edit()
            .putString(KEY_SERVER_IP, config.serverIp.trim())
            .putInt(KEY_SERVER_PORT, config.serverPort)
            .putString(KEY_API_TOKEN, config.apiToken.trim())
            .putString(KEY_ACCOUNT_ALIAS, config.accountAlias.trim())
            .apply()
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
        private const val KEY_PIN_HASH = "local_pin_hash"
    }
}
