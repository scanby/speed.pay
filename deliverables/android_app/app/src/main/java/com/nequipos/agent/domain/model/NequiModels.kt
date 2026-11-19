package com.nequipos.agent.domain.model

import java.math.BigDecimal

data class ParsedNequiDeposit(
    val amountCop: BigDecimal,
    val senderName: String,
    val rawNotification: String,
    val capturedAtEpochMs: Long
)

data class ServerConfig(
    val serverIp: String,
    val serverPort: Int,
    val apiToken: String,
    val accountAlias: String
) {
    val isConfigured: Boolean
        get() = serverIp.isNotBlank() && serverPort in 1024..65535 && apiToken.isNotBlank() && accountAlias.isNotBlank()

    fun baseUrl(): String = "http://$serverIp:$serverPort"
}
