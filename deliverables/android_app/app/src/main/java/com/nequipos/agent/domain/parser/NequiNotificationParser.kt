package com.nequipos.agent.domain.parser

import com.nequipos.agent.domain.model.ParsedNequiDeposit
import java.math.BigDecimal

object NequiNotificationParser {

    const val NEQUI_PACKAGE_NAME = "com.nequi.MobileApp"

    /**
     * Patrones flexibles para las notificaciones reales de ingreso en Nequi Colombia:
     * 1. "Recibiste $45.000 de Carlos Mendoza en tu Nequi"
     * 2. "Te enviaron $ 120.500,00 de María Fernanda Gómez."
     * 3. "Pago recibido por $8.000 de Tienda La Esquina"
     * 4. "Recibiste un envío de $250.000 de Juan Pérez"
     */
    private val INCOME_PATTERNS = listOf(
        Regex(
            pattern = """(?:recibiste|te\s+enviaron|pago\s+recibido(?:\s+por)?|recibiste\s+un\s+env[ií]o(?:\s+de)?)\s*(?:por\s+)?\$?\s*([\d.,]+)\s+(?:de|por\s+parte\s+de)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.'-]+?)(?:\s+en\s+tu\s+nequi|[.!,\n]|$)""",
            options = setOf(RegexOption.IGNORE_CASE)
        ),
        Regex(
            pattern = """(?:recibiste|te\s+enviaron|pago\s+recibido)\s*(?:por\s+)?\$?\s*([\d.,]+)""",
            options = setOf(RegexOption.IGNORE_CASE)
        )
    )

    private val NEGATIVE_KEYWORDS = listOf(
        "enviaste",
        "pagaste",
        "retiraste",
        "recargaste",
        "transferencia rechazada",
        "código de verificación",
        "clave dinámica"
    )

    fun parse(title: String, body: String, capturedAtEpochMs: Long): ParsedNequiDeposit? {
        val combined = listOf(title.trim(), body.trim())
            .filter { it.isNotEmpty() }
            .joinToString(" ")
            .replace(Regex("\\s+"), " ")
            .trim()

        if (combined.isEmpty()) return null

        val lower = combined.lowercase()
        if (NEGATIVE_KEYWORDS.any { lower.contains(it) }) {
            return null
        }

        for ((index, regex) in INCOME_PATTERNS.withIndex()) {
            val match = regex.find(combined) ?: continue
            val rawAmount = match.groupValues.getOrNull(1) ?: continue
            val parsedAmount = normalizeColombianAmount(rawAmount) ?: continue
            if (parsedAmount <= BigDecimal.ZERO) continue

            val sender = if (index == 0) {
                match.groupValues.getOrNull(2)?.trim()?.ifEmpty { "Cliente Nequi" } ?: "Cliente Nequi"
            } else {
                "Cliente Nequi"
            }

            return ParsedNequiDeposit(
                amountCop = parsedAmount,
                senderName = sender,
                rawNotification = combined,
                capturedAtEpochMs = capturedAtEpochMs
            )
        }
        return null
    }

    /**
     * Normaliza formatos monetarios colombianos:
     * "45.000" -> 45000.00
     * "120.500,50" -> 120500.50
     * "1,250,000" -> 1250000.00
     */
    internal fun normalizeColombianAmount(raw: String): BigDecimal? {
        var cleaned = raw.trim().replace(" ", "")
        if (cleaned.isEmpty()) return null

        // Caso formato colombiano estándar con miles en punto y decimales en coma: 120.500,50
        if (cleaned.contains(".") && cleaned.contains(",")) {
            cleaned = cleaned.replace(".", "").replace(",", ".")
        } else if (cleaned.contains(",")) {
            val parts = cleaned.split(",")
            cleaned = if (parts.last().length == 2) {
                cleaned.replace(",", ".")
            } else {
                cleaned.replace(",", "")
            }
        } else if (cleaned.contains(".")) {
            val parts = cleaned.split(".")
            // En Colombia $45.000 usa punto como separador de miles
            cleaned = if (parts.last().length == 3) {
                cleaned.replace(".", "")
            } else {
                cleaned
            }
        }

        return cleaned.toBigDecimalOrNull()
    }
}
