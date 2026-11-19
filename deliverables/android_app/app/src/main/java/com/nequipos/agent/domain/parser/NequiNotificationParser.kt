package com.nequipos.agent.domain.parser

import com.nequipos.agent.domain.model.ParsedNequiDeposit
import java.math.BigDecimal

object NequiNotificationParser {

    const val NEQUI_PACKAGE_NAME = "com.nequi.MobileApp"

    fun isNequiPackage(packageName: String?): Boolean {
        val pkg = packageName?.trim()?.lowercase() ?: return false
        if (pkg == "com.nequipos.agent") return false
        return pkg == NEQUI_PACKAGE_NAME.lowercase() ||
            pkg.startsWith("com.nequi") ||
            pkg.startsWith("co.com.nequi")
    }

    private val DECORATIVE_TITLE_PREFIX = Regex(
        pattern = """^(?:nequi|¡?\s*plata\s+nueva\s*!?|¡?\s*lleg[oó]\s+plata\s*!?|¡?\s*qu[eé]\s+chimba\s*!?|¡?\s*nuevo\s+ingreso\s*!?|pago\s+recibido|transferencia\s+recibida|recibiste\s+plata|[^\p{L}\p{N}$]+)+\s*""",
        options = setOf(RegexOption.IGNORE_CASE)
    )

    private const val OPTIONAL_FILLER =
        """(?:\s+(?:plata|dinero|un\s+env[ií]o|un\s+pago|una\s+transferencia|transferencia|pago|con\s+qr|por\s+qr|qr|a\s+tu\s+nequi|en\s+tu\s+nequi|por|de))*"""

    // 1) Verbo de ingreso + monto + "de <remitente>"
    private val PATTERN_VERB_AMOUNT_SENDER = Regex(
        pattern = """(?:recibiste|te\s+enviaron|te\s+transfirieron|te\s+lleg[oó]|lleg[oó]|pago\s+recibido|transferencia\s+recibida|nuevo\s+ingreso|ingreso)$OPTIONAL_FILLER\s*(?:\$|COP)?\s*(\d[\d.,]*)\s*(?:con\s+qr\s+|por\s+qr\s+)?(?:de|por\s+parte\s+de)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.'-]+?)(?:\s+(?:en|a)\s+tu\s+nequi|[.!,\n]|$)""",
        options = setOf(RegexOption.IGNORE_CASE)
    )

    // 2) Verbo de ingreso + "de <remitente>" + "por $<monto>" (ej. "Te llegó plata de Carlos por $45.000")
    private val PATTERN_VERB_SENDER_AMOUNT = Regex(
        pattern = """(?:recibiste|te\s+lleg[oó]|lleg[oó]|te\s+enviaron|pago\s+recibido|transferencia\s+recibida)$OPTIONAL_FILLER\s+(?:de|por\s+parte\s+de)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.'-]+?)\s+(?:por|de)\s+(?:\$|COP)?\s*(\d[\d.,]*)""",
        options = setOf(RegexOption.IGNORE_CASE)
    )

    // 3) "<remitente> te envió / te transfirió $<monto>" (muy común en Nequi)
    private val PATTERN_SENDER_SENT_AMOUNT = Regex(
        pattern = """^([A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9\s.'-]{1,50}?)\s+te\s+(?:envi[oó]|transfiri[oó])$OPTIONAL_FILLER\s*(?:\$|COP)?\s*(\d[\d.,]*)""",
        options = setOf(RegexOption.IGNORE_CASE)
    )

    // 4) Respaldo sin remitente explícito (ej. "Recibiste un pago con QR de $32.000")
    private val PATTERN_INCOME_AMOUNT_ONLY = Regex(
        pattern = """(?:recibiste|te\s+enviaron|te\s+transfirieron|te\s+lleg[oó]|lleg[oó]\s+plata|pago\s+recibido|pago\s+con\s+qr|transferencia\s+recibida|nuevo\s+ingreso|ingreso)$OPTIONAL_FILLER\s*(?:\$|COP)?\s*(\d[\d.,]+)""",
        options = setOf(RegexOption.IGNORE_CASE)
    )

    private val NEGATIVE_KEYWORDS = listOf(
        "enviaste",
        "pagaste",
        "retiraste",
        "sacaste",
        "compraste",
        "recargaste",
        "débito",
        "debito",
        "transferencia rechazada",
        "código de verificación",
        "codigo de verificacion",
        "clave dinámica",
        "clave dinamica",
        "recuerda pagar",
        "paga tu"
    )

    fun parse(title: String, body: String, capturedAtEpochMs: Long): ParsedNequiDeposit? {
        val cleanTitle = title.trim()
        val cleanBody = body.trim()
        val combined = listOf(cleanTitle, cleanBody)
            .filter { it.isNotEmpty() }
            .joinToString(" ")
            .replace(Regex("\\s+"), " ")
            .trim()

        if (combined.isEmpty()) return null

        val lower = combined.lowercase()
        if (NEGATIVE_KEYWORDS.any { lower.contains(it) }) {
            return null
        }

        val candidates = listOf(
            cleanBody.replace(Regex("\\s+"), " ").trim(),
            combined,
            stripDecorativePrefixes(combined)
        ).filter { it.isNotEmpty() }.distinct()

        for (text in candidates) {
            PATTERN_VERB_AMOUNT_SENDER.find(text)?.let { match ->
                val amount = normalizeColombianAmount(match.groupValues[1])
                if (amount != null && amount > BigDecimal.ZERO) {
                    val sender = cleanSender(match.groupValues[2])
                    return ParsedNequiDeposit(amount, sender, combined, capturedAtEpochMs)
                }
            }

            PATTERN_VERB_SENDER_AMOUNT.find(text)?.let { match ->
                val amount = normalizeColombianAmount(match.groupValues[2])
                if (amount != null && amount > BigDecimal.ZERO) {
                    val sender = cleanSender(match.groupValues[1])
                    return ParsedNequiDeposit(amount, sender, combined, capturedAtEpochMs)
                }
            }

            val strippedForSender = stripDecorativePrefixes(text)
            PATTERN_SENDER_SENT_AMOUNT.find(strippedForSender)?.let { match ->
                val rawSender = match.groupValues[1].trim()
                val senderLower = rawSender.lowercase()
                if (!senderLower.startsWith("te ") && !senderLower.startsWith("alguien ")) {
                    val amount = normalizeColombianAmount(match.groupValues[2])
                    if (amount != null && amount > BigDecimal.ZERO) {
                        return ParsedNequiDeposit(amount, cleanSender(rawSender), combined, capturedAtEpochMs)
                    }
                }
            }
        }

        for (text in candidates) {
            PATTERN_INCOME_AMOUNT_ONLY.find(text)?.let { match ->
                val amount = normalizeColombianAmount(match.groupValues[1])
                if (amount != null && amount > BigDecimal.ZERO) {
                    return ParsedNequiDeposit(amount, "Cliente Nequi", combined, capturedAtEpochMs)
                }
            }
        }

        return null
    }

    private fun stripDecorativePrefixes(input: String): String {
        var current = input.trim()
        repeat(4) {
            val next = DECORATIVE_TITLE_PREFIX.replaceFirst(current, "").trim()
            if (next == current) return current
            current = next
        }
        return current
    }

    private fun cleanSender(raw: String): String {
        val trimmed = raw.trim().trimEnd('.', ',', '!', ';', ':')
        return trimmed.ifEmpty { "Cliente Nequi" }
    }

    /**
     * Normaliza formatos monetarios colombianos:
     * "45.000" -> 45000
     * "120.500,50" -> 120500.50
     * "1,250,000" -> 1250000
     */
    internal fun normalizeColombianAmount(raw: String): BigDecimal? {
        var cleaned = raw.trim()
            .replace(" ", "")
            .trimEnd('.', ',')
        if (cleaned.isEmpty()) return null

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
            cleaned = if (parts.last().length == 3) {
                cleaned.replace(".", "")
            } else {
                cleaned
            }
        }

        return cleaned.toBigDecimalOrNull()
    }
}
