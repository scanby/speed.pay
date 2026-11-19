package com.nequipos.agent

import com.nequipos.agent.domain.parser.NequiNotificationParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal

class NequiNotificationParserTest {

    @Test
    fun `parses standard Recibiste notification with thousands dot`() {
        val result = NequiNotificationParser.parse(
            title = "Nequi",
            body = "Recibiste $45.000 de Carlos Mendoza en tu Nequi",
            capturedAtEpochMs = 1715000000000L
        )
        assertNotNull(result)
        assertEquals(BigDecimal("45000"), result!!.amountCop)
        assertEquals("Carlos Mendoza", result.senderName)
    }

    @Test
    fun `parses Te enviaron notification with Colombian decimal comma`() {
        val result = NequiNotificationParser.parse(
            title = "¡Plata nueva!",
            body = "Te enviaron $ 120.500,50 de María Fernanda Gómez.",
            capturedAtEpochMs = 1715000000000L
        )
        assertNotNull(result)
        assertEquals(BigDecimal("120500.50"), result!!.amountCop)
        assertEquals("María Fernanda Gómez", result.senderName)
    }

    @Test
    fun `parses Pago recibido notification`() {
        val result = NequiNotificationParser.parse(
            title = "Pago recibido",
            body = "Pago recibido por $8.000 de Tienda La Esquina",
            capturedAtEpochMs = 1715000000000L
        )
        assertNotNull(result)
        assertEquals(BigDecimal("8000"), result!!.amountCop)
        assertEquals("Tienda La Esquina", result.senderName)
    }

    @Test
    fun `parses sender te envio format common in Nequi Colombia`() {
        val result = NequiNotificationParser.parse(
            title = "¡Plata nueva!",
            body = "Carlos Mendoza te envió $45.000 a tu Nequi.",
            capturedAtEpochMs = 1715000000000L
        )
        assertNotNull(result)
        assertEquals(BigDecimal("45000"), result!!.amountCop)
        assertEquals("Carlos Mendoza", result.senderName)
    }

    @Test
    fun `parses Te llego plata de remitente por monto`() {
        val result = NequiNotificationParser.parse(
            title = "Nequi",
            body = "Te llegó plata de Laura Martínez por $72.500",
            capturedAtEpochMs = 1715000000000L
        )
        assertNotNull(result)
        assertEquals(BigDecimal("72500"), result!!.amountCop)
        assertEquals("Laura Martínez", result.senderName)
    }

    @Test
    fun `parses Recibiste plata split between title and body and QR payments`() {
        val splitResult = NequiNotificationParser.parse(
            title = "Recibiste plata",
            body = "$30.000 de Andrés Rojas",
            capturedAtEpochMs = 1715000000000L
        )
        assertNotNull(splitResult)
        assertEquals(BigDecimal("30000"), splitResult!!.amountCop)
        assertEquals("Andrés Rojas", splitResult.senderName)

        val qrResult = NequiNotificationParser.parse(
            title = "Pago con QR",
            body = "Recibiste un pago con QR de $18.000",
            capturedAtEpochMs = 1715000000000L
        )
        assertNotNull(qrResult)
        assertEquals(BigDecimal("18000"), qrResult!!.amountCop)
    }

    @Test
    fun `matches Nequi packages safely while excluding self`() {
        assertTrue(NequiNotificationParser.isNequiPackage("com.nequi.MobileApp"))
        assertTrue(NequiNotificationParser.isNequiPackage("com.nequi.negocios"))
        assertFalse(NequiNotificationParser.isNequiPackage("com.nequipos.agent"))
        assertFalse(NequiNotificationParser.isNequiPackage("com.whatsapp"))
    }

    @Test
    fun `ignores outgoing transfers and OTP verification messages`() {
        assertNull(
            NequiNotificationParser.parse(
                title = "Nequi",
                body = "Enviaste $50.000 a Pedro Gómez",
                capturedAtEpochMs = 1715000000000L
            )
        )
        assertNull(
            NequiNotificationParser.parse(
                title = "Nequi",
                body = "Tu código de verificación es 482910",
                capturedAtEpochMs = 1715000000000L
            )
        )
    }
}
