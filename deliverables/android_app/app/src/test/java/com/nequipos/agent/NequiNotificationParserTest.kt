package com.nequipos.agent

import com.nequipos.agent.domain.parser.NequiNotificationParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
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
