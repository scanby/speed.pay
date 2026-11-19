package com.nequipos.agent.ui

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.nequipos.agent.data.local.AppDatabase
import com.nequipos.agent.data.local.PendingDepositEntity
import com.nequipos.agent.data.local.SecureConfigStore
import com.nequipos.agent.domain.model.ServerConfig
import com.nequipos.agent.service.AgentForegroundService
import com.nequipos.agent.worker.SyncDepositsWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

class ConfigActivity : AppCompatActivity() {

    private lateinit var store: SecureConfigStore
    private lateinit var ipInput: EditText
    private lateinit var portInput: EditText
    private lateinit var tokenInput: EditText
    private lateinit var aliasInput: EditText
    private lateinit var queueStatusText: TextView

    private val qrLauncher = registerForActivityResult(ScanContract()) { result ->
        val raw = result.contents ?: return@registerForActivityResult
        try {
            val json = JSONObject(raw)
            ipInput.setText(json.getString("server_ip"))
            portInput.setText(json.getInt("server_port").toString())
            tokenInput.setText(json.getString("api_token"))
            saveCurrentConfig()
            Toast.makeText(this, "Configuración cargada desde QR", Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            Toast.makeText(this, "QR inválido: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = SecureConfigStore(this)
        AgentForegroundService.ensureRunning(this)

        buildProgrammaticUi()
        promptPinGate()
    }

    private fun promptPinGate() {
        if (!store.hasPinConfigured()) {
            askCreateInitialPin()
            return
        }

        val pinField = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            hint = "PIN de seguridad (4-8 dígitos)"
        }
        AlertDialog.Builder(this)
            .setTitle("Acceso Protegido")
            .setMessage("Ingresa el PIN local para modificar la configuración del servidor POS.")
            .setView(pinField)
            .setCancelable(false)
            .setPositiveButton("Desbloquear") { _, _ ->
                if (!store.verifyPin(pinField.text.toString())) {
                    Toast.makeText(this, "PIN incorrecto", Toast.LENGTH_SHORT).show()
                    finish()
                } else {
                    loadSavedValues()
                }
            }
            .show()
    }

    private fun askCreateInitialPin() {
        val pinField = EditText(this).apply {
            inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
            hint = "Nuevo PIN (mínimo 4 dígitos)"
        }
        AlertDialog.Builder(this)
            .setTitle("Crear PIN Local")
            .setMessage("Protege la configuración del punto de venta en este teléfono.")
            .setView(pinField)
            .setCancelable(false)
            .setPositiveButton("Guardar PIN") { _, _ ->
                val pin = pinField.text.toString().trim()
                if (pin.length < 4) {
                    Toast.makeText(this, "PIN muy corto", Toast.LENGTH_SHORT).show()
                    askCreateInitialPin()
                } else {
                    store.setPin(pin)
                    loadSavedValues()
                }
            }
            .show()
    }

    private fun buildProgrammaticUi() {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 48)
        }

        val title = TextView(this).apply {
            text = "NequiPay POS — Agente Android"
            textSize = 20f
        }
        queueStatusText = TextView(this).apply {
            text = "Cola offline pendiente: calculando..."
            setPadding(0, 12, 0, 24)
        }

        ipInput = EditText(this).apply { hint = "IP Servidor LAN (ej. 192.168.1.50)" }
        portInput = EditText(this).apply {
            hint = "Puerto (ej. 8000)"
            inputType = InputType.TYPE_CLASS_NUMBER
        }
        tokenInput = EditText(this).apply { hint = "Token API del Servidor" }
        aliasInput = EditText(this).apply { hint = "Alias Cuenta Nequi (ej. Caja Principal)" }

        val btnScanQr = Button(this).apply {
            text = "Escanear QR del Servidor"
            setOnClickListener {
                val options = ScanOptions().apply {
                    setDesiredBarcodeFormats(ScanOptions.QR_CODE)
                    setPrompt("Escanea el código QR mostrado en el panel Admin")
                    setBeepEnabled(true)
                }
                qrLauncher.launch(options)
            }
        }

        val btnSave = Button(this).apply {
            text = "Guardar Configuración"
            setOnClickListener { saveCurrentConfig() }
        }

        val btnSendTest = Button(this).apply {
            text = "Enviar pago de prueba ($15.000)"
            setOnClickListener { enqueueTestPayment() }
        }

        val btnNotifPerm = Button(this).apply {
            text = "Habilitar Lectura de Notificaciones"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            }
        }

        root.addView(title)
        root.addView(queueStatusText)
        root.addView(ipInput)
        root.addView(portInput)
        root.addView(tokenInput)
        root.addView(aliasInput)
        root.addView(btnScanQr)
        root.addView(btnSave)
        root.addView(btnSendTest)
        root.addView(btnNotifPerm)

        setContentView(root)
    }

    private fun loadSavedValues() {
        val cfg = store.getServerConfig()
        ipInput.setText(cfg.serverIp)
        portInput.setText(cfg.serverPort.toString())
        tokenInput.setText(cfg.apiToken)
        aliasInput.setText(cfg.accountAlias)
        refreshPendingCount()
    }

    private fun saveCurrentConfig() {
        val port = portInput.text.toString().toIntOrNull() ?: 8000
        val cfg = ServerConfig(
            serverIp = ipInput.text.toString(),
            serverPort = port,
            apiToken = tokenInput.text.toString(),
            accountAlias = aliasInput.text.toString()
        )
        store.saveServerConfig(cfg)
        Toast.makeText(this, "Configuración guardada", Toast.LENGTH_SHORT).show()
    }

    private fun enqueueTestPayment() {
        saveCurrentConfig()
        val cfg = store.getServerConfig()
        if (!cfg.isConfigured) {
            Toast.makeText(this, "Completa IP, Puerto, Token y Alias primero", Toast.LENGTH_LONG).show()
            return
        }
        val nowMs = System.currentTimeMillis()
        val isoNow = DateTimeFormatter.ISO_INSTANT.format(
            Instant.ofEpochMilli(nowMs).atOffset(ZoneOffset.UTC)
        )

        CoroutineScope(Dispatchers.IO).launch {
            val dao = AppDatabase.getInstance(applicationContext).pendingDepositDao()
            dao.insert(
                PendingDepositEntity(
                    accountAlias = cfg.accountAlias,
                    senderName = "Prueba Dispositivo Android",
                    amountCop = "15000.00",
                    rawNotification = "Recibiste \$15.000 de Prueba Dispositivo Android en tu Nequi",
                    capturedAtIso = isoNow,
                    capturedAtEpochMs = nowMs,
                    source = "MANUAL_TEST"
                )
            )
            SyncDepositsWorker.enqueue(applicationContext)
            withContext(Dispatchers.Main) {
                Toast.makeText(
                    this@ConfigActivity,
                    "Pago de prueba encolado para sincronización",
                    Toast.LENGTH_SHORT
                ).show()
                refreshPendingCount()
            }
        }
    }

    private fun refreshPendingCount() {
        CoroutineScope(Dispatchers.IO).launch {
            val count = AppDatabase.getInstance(applicationContext).pendingDepositDao().countPending()
            withContext(Dispatchers.Main) {
                queueStatusText.text = "Cola offline pendiente: $count transacciones"
            }
        }
    }
}
