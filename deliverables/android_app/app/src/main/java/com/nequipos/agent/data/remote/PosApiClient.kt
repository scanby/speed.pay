package com.nequipos.agent.data.remote

import com.nequipos.agent.data.local.PendingDepositEntity
import com.nequipos.agent.domain.model.ServerConfig
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.util.concurrent.TimeUnit

sealed class SendResult {
    data object Success : SendResult()
    data object DuplicateIgnored : SendResult()
    data class TransientFailure(val code: Int, val message: String) : SendResult()
}

class PosApiClient {

    private val client = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS)
        .readTimeout(6, TimeUnit.SECONDS)
        .writeTimeout(6, TimeUnit.SECONDS)
        .build()

    fun sendDeposit(config: ServerConfig, deposit: PendingDepositEntity): SendResult {
        if (!config.isConfigured) {
            return SendResult.TransientFailure(0, "Servidor no configurado.")
        }

        val jsonBody = JSONObject().apply {
            put("account_alias", deposit.accountAlias)
            put("sender_name", deposit.senderName)
            put("amount_cop", deposit.amountCop)
            put("raw_notification", deposit.rawNotification)
            put("captured_at", deposit.capturedAtIso)
            put("source", deposit.source)
        }.toString()

        val request = Request.Builder()
            .url("${config.baseUrl()}/api/deposits/ingest")
            .addHeader("X-Api-Token", config.apiToken)
            .addHeader("Content-Type", "application/json")
            .post(jsonBody.toRequestBody("application/json; charset=utf-8".toMediaType()))
            .build()

        return try {
            client.newCall(request).execute().use { response ->
                when (response.code) {
                    in 200..299 -> SendResult.Success
                    409 -> SendResult.DuplicateIgnored // Idempotencia del servidor: ya registrado
                    else -> SendResult.TransientFailure(response.code, response.message)
                }
            }
        } catch (e: Exception) {
            SendResult.TransientFailure(-1, e.message ?: "Error de red LAN")
        }
    }

    fun checkHealth(config: ServerConfig): Pair<Boolean, String> {
        if (config.serverIp.isBlank() || config.serverPort !in 1024..65535) {
            return false to "IP o puerto inválido."
        }
        val request = Request.Builder()
            .url("${config.baseUrl()}/api/health")
            .get()
            .build()

        return try {
            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val body = response.body?.string().orEmpty()
                    val json = JSONObject(body)
                    val version = json.optString("app_version", json.optString("version", "N/A"))
                    true to "Conectado al servidor LAN (v$version · HTTP ${response.code})"
                } else {
                    false to "Servidor respondió HTTP ${response.code}"
                }
            }
        } catch (e: Exception) {
            false to "Sin conexión con ${config.serverIp}:${config.serverPort} (${e.message ?: "timeout"})"
        }
    }
}
