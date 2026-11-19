package com.nequipos.agent.ui

import android.Manifest
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.text.InputType
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.nequipos.agent.BuildConfig
import com.nequipos.agent.data.local.AppDatabase
import com.nequipos.agent.data.local.PendingDepositEntity
import com.nequipos.agent.data.local.SecureConfigStore
import com.nequipos.agent.data.remote.PosApiClient
import com.nequipos.agent.domain.model.ServerConfig
import com.nequipos.agent.service.AgentForegroundService
import com.nequipos.agent.service.NequiNotificationListenerService
import com.nequipos.agent.worker.SyncDepositsWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

class ConfigActivity : AppCompatActivity() {

    private val activityScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    private lateinit var store: SecureConfigStore
    private lateinit var ipInput: EditText
    private lateinit var portInput: EditText
    private lateinit var tokenInput: EditText
    private lateinit var aliasInput: EditText
    private lateinit var queueStatusText: TextView
    private lateinit var systemStatusText: TextView
    private lateinit var connectionResultText: TextView

    private var pinUnlocked = false

    private val notifPermLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (!granted) {
            Toast.makeText(
                this,
                "Se recomienda permitir notificaciones para mantener el servicio activo.",
                Toast.LENGTH_LONG
            ).show()
        }
    }

    private val qrLauncher = registerForActivityResult(ScanContract()) { result ->
        val raw = result.contents ?: return@registerForActivityResult
        try {
            val json = JSONObject(raw)
            ipInput.setText(json.getString("server_ip"))
            portInput.setText(json.optInt("server_port", 8000).toString())
            tokenInput.setText(json.getString("api_token"))
            saveCurrentConfig()
            Toast.makeText(this, "Configuración cargada desde QR", Toast.LENGTH_SHORT).show()
            testServerConnection()
        } catch (e: Exception) {
            Toast.makeText(this, "QR inválido: ${e.message}", Toast.LENGTH_LONG).show()
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        store = SecureConfigStore(this)
        requestNotificationPermissionIfNeeded()
        AgentForegroundService.ensureRunning(this)

        buildProgrammaticUi()
        promptPinGate()
    }

    override fun onResume() {
        super.onResume()
        if (pinUnlocked) {
            refreshSystemStatus()
            refreshPendingCount()
        }
    }

    override fun onDestroy() {
        activityScope.cancel()
        super.onDestroy()
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this,
                Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                notifPermLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
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
                    pinUnlocked = true
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
                    Toast.makeText(this, "PIN muy corto (mínimo 4 dígitos)", Toast.LENGTH_SHORT).show()
                    askCreateInitialPin()
                } else {
                    store.setPin(pin)
                    pinUnlocked = true
                    loadSavedValues()
                }
            }
            .show()
    }

    private fun buildProgrammaticUi() {
        val scroll = ScrollView(this)
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(48, 48, 48, 64)
        }

        val title = TextView(this).apply {
            text = "NequiPay POS — Agente Android v${BuildConfig.VERSION_NAME}"
            textSize = 20f
        }
        systemStatusText = TextView(this).apply {
            text = "Verificando permisos del sistema..."
            setPadding(0, 16, 0, 8)
        }
        queueStatusText = TextView(this).apply {
            text = "Cola offline pendiente: calculando..."
            setPadding(0, 4, 0, 20)
        }

        ipInput = EditText(this).apply { hint = "IP Servidor LAN (ej. 192.168.1.50)" }
        portInput = EditText(this).apply {
            hint = "Puerto (ej. 8000)"
            inputType = InputType.TYPE_CLASS_NUMBER
        }
        tokenInput = EditText(this).apply { hint = "Token API del Servidor" }
        aliasInput = EditText(this).apply { hint = "Alias Cuenta Nequi (ej. Caja Principal)" }

        connectionResultText = TextView(this).apply {
            text = "Estado conexión LAN: sin probar"
            setPadding(0, 12, 0, 16)
        }

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

        val btnTestConnection = Button(this).apply {
            text = "Probar Conexión al Servidor"
            setOnClickListener {
                saveCurrentConfig()
                testServerConnection()
            }
        }

        val btnSendTest = Button(this).apply {
            text = "Enviar pago de prueba ($15.000)"
            setOnClickListener { enqueueTestPayment() }
        }

        val btnSyncNow = Button(this).apply {
            text = "Forzar Sincronización de Cola"
            setOnClickListener {
                SyncDepositsWorker.enqueue(applicationContext)
                Toast.makeText(this@ConfigActivity, "Sincronización iniciada", Toast.LENGTH_SHORT).show()
                refreshPendingCount()
            }
        }

        val btnNotifPerm = Button(this).apply {
            text = "Habilitar Lectura de Notificaciones"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            }
        }

        val btnBattery = Button(this).apply {
            text = "Permitir Ejecución Sin Restricción de Batería"
            setOnClickListener { requestBatteryExemption() }
        }

        root.addView(title)
        root.addView(systemStatusText)
        root.addView(queueStatusText)
        root.addView(ipInput)
        root.addView(portInput)
        root.addView(tokenInput)
        root.addView(aliasInput)
        root.addView(connectionResultText)
        root.addView(btnScanQr)
        root.addView(btnSave)
        root.addView(btnTestConnection)
        root.addView(btnSendTest)
        root.addView(btnSyncNow)
        root.addView(btnNotifPerm)
        root.addView(btnBattery)

        scroll.addView(root)
        setContentView(scroll)
    }

    private fun loadSavedValues() {
        val cfg = store.getServerConfig()
        ipInput.setText(cfg.serverIp)
        portInput.setText(cfg.serverPort.toString())
        tokenInput.setText(cfg.apiToken)
        aliasInput.setText(cfg.accountAlias)
        refreshSystemStatus()
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

    private fun testServerConnection() {
        val cfg = store.getServerConfig()
        connectionResultText.text = "Probando conexión con ${cfg.serverIp}:${cfg.serverPort}..."
        activityScope.launch {
            val (ok, msg) = PosApiClient().checkHealth(cfg)
            withContext(Dispatchers.Main) {
                connectionResultText.text = if (ok) "OK · $msg" else "Error · $msg"
                Toast.makeText(this@ConfigActivity, msg, Toast.LENGTH_SHORT).show()
            }
        }
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

        activityScope.launch {
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
        activityScope.launch {
            val count = AppDatabase.getInstance(applicationContext).pendingDepositDao().countPending()
            withContext(Dispatchers.Main) {
                queueStatusText.text = "Cola offline pendiente: $count transacciones"
            }
        }
    }

    private fun refreshSystemStatus() {
        val notifEnabled = isNotificationListenerEnabled()
        val batteryIgnored = isIgnoringBatteryOptimizations()
        val notifLabel = if (notifEnabled) "ACTIVO" else "PENDIENTE (habilitar abajo)"
        val batLabel = if (batteryIgnored) "EXENTO (24/7 óptimo)" else "RESTRINGIDO (se sugiere liberar)"
        systemStatusText.text = "Lectura Nequi: $notifLabel\nBatería segundo plano: $batLabel"
    }

    private fun isNotificationListenerEnabled(): Boolean {
        val component = ComponentName(this, NequiNotificationListenerService::class.java).flattenToString()
        val enabled = Settings.Secure.getString(contentResolver, "enabled_notification_listeners").orEmpty()
        return enabled.split(":").any { it.equals(component, ignoreCase = true) }
    }

    private fun isIgnoringBatteryOptimizations(): Boolean {
        val pm = getSystemService(PowerManager::class.java) ?: return false
        return pm.isIgnoringBatteryOptimizations(packageName)
    }

    private fun requestBatteryExemption() {
        if (isIgnoringBatteryOptimizations()) {
            Toast.makeText(this, "La app ya está exenta de ahorro de batería.", Toast.LENGTH_SHORT).show()
            return
        }
        try {
            val intent = Intent(
                Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                Uri.parse("package:$packageName")
            )
            startActivity(intent)
        } catch (_: Exception) {
            startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
        }
    }
}
