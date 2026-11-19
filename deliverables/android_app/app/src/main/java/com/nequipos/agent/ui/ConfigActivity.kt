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
import androidx.core.content.FileProvider
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import com.nequipos.agent.BuildConfig
import com.nequipos.agent.data.local.AppDatabase
import com.nequipos.agent.data.local.PendingDepositEntity
import com.nequipos.agent.data.local.SecureConfigStore
import com.nequipos.agent.data.remote.AndroidReleaseCheck
import com.nequipos.agent.data.remote.AppUpdaterClient
import com.nequipos.agent.data.remote.DepositSyncManager
import com.nequipos.agent.data.remote.PosApiClient
import com.nequipos.agent.data.remote.SyncQueueResult
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
import java.io.File
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
    private lateinit var repoInput: EditText
    private lateinit var queueStatusText: TextView
    private lateinit var systemStatusText: TextView
    private lateinit var connectionResultText: TextView
    private lateinit var updateStatusText: TextView
    private lateinit var eventsLogText: TextView

    private var pinUnlocked = false
    private var pendingReleaseDownload: AndroidReleaseCheck? = null

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

    private val unknownSourcesLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) {
        val pending = pendingReleaseDownload
        if (pending != null && packageManager.canRequestPackageInstalls()) {
            pendingReleaseDownload = null
            startApkDownloadAndInstall(pending)
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
            if (isNotificationListenerEnabled()) {
                NequiNotificationListenerService.requestRebindIfNeeded(this)
            }
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

        ipInput = EditText(this).apply { hint = "IP Servidor LAN (ej. 192.168.0.5)" }
        portInput = EditText(this).apply {
            hint = "Puerto (ej. 8000)"
            inputType = InputType.TYPE_CLASS_NUMBER
        }
        tokenInput = EditText(this).apply { hint = "Token API del Servidor" }
        aliasInput = EditText(this).apply { hint = "Alias Cuenta Nequi (ej. Caja Principal)" }
        repoInput = EditText(this).apply { hint = "Repositorio OTA GitHub (ej. scanby/nequipos)" }

        connectionResultText = TextView(this).apply {
            text = "Estado conexión LAN: sin probar"
            setPadding(0, 12, 0, 12)
        }

        updateStatusText = TextView(this).apply {
            text = "Versión instalada: v${BuildConfig.VERSION_NAME} · Sin verificar"
            setPadding(0, 8, 0, 12)
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
                activityScope.launch {
                    val res = DepositSyncManager.syncPendingQueue(applicationContext)
                    if (res !is SyncQueueResult.AllSynced) {
                        SyncDepositsWorker.enqueue(applicationContext)
                    }
                    withContext(Dispatchers.Main) {
                        val toastMsg = when (res) {
                            is SyncQueueResult.AllSynced -> "Cola sincronizada con el servidor"
                            is SyncQueueResult.NotConfigured -> "Configura IP, Puerto y Token primero"
                            is SyncQueueResult.Failed -> res.detail
                        }
                        Toast.makeText(this@ConfigActivity, toastMsg, Toast.LENGTH_SHORT).show()
                        refreshPendingCount()
                    }
                }
            }
        }

        val btnNotifPerm = Button(this).apply {
            text = "1. Habilitar Lectura de Notificaciones"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
            }
        }

        val btnRestrictedHelp = Button(this).apply {
            text = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                "2. Desbloquear Ajuste Restringido (Android 13+)"
            } else {
                "2. Info de App (Inicio Automático y Batería)"
            }
            setOnClickListener { showAppSettingsGuide() }
        }

        val btnBattery = Button(this).apply {
            text = "3. Permitir Ejecución Sin Restricción de Batería"
            setOnClickListener { requestBatteryExemption() }
        }

        val btnCheckUpdate = Button(this).apply {
            text = "Buscar y Actualizar App (APK)"
            setOnClickListener {
                saveCurrentConfig()
                checkForAppUpdates()
            }
        }

        val logsTitle = TextView(this).apply {
            text = "\nDiagnóstico y Últimos Eventos Nequi:"
            textSize = 15f
            setPadding(0, 16, 0, 6)
        }
        eventsLogText = TextView(this).apply {
            text = "Cargando eventos..."
            textSize = 12f
            setPadding(0, 4, 0, 12)
        }
        val btnRefreshLogs = Button(this).apply {
            text = "Actualizar Estado y Logs"
            setOnClickListener {
                if (isNotificationListenerEnabled()) {
                    NequiNotificationListenerService.requestRebindIfNeeded(this@ConfigActivity)
                }
                refreshSystemStatus()
                refreshPendingCount()
            }
        }

        root.addView(title)
        root.addView(systemStatusText)
        root.addView(queueStatusText)
        root.addView(ipInput)
        root.addView(portInput)
        root.addView(tokenInput)
        root.addView(aliasInput)
        root.addView(repoInput)
        root.addView(connectionResultText)
        root.addView(btnScanQr)
        root.addView(btnSave)
        root.addView(btnTestConnection)
        root.addView(btnSendTest)
        root.addView(btnSyncNow)
        root.addView(btnNotifPerm)
        root.addView(btnRestrictedHelp)
        root.addView(btnBattery)
        root.addView(updateStatusText)
        root.addView(btnCheckUpdate)
        root.addView(logsTitle)
        root.addView(eventsLogText)
        root.addView(btnRefreshLogs)

        scroll.addView(root)
        setContentView(scroll)
    }

    private fun loadSavedValues() {
        val cfg = store.getServerConfig()
        ipInput.setText(cfg.serverIp)
        portInput.setText(cfg.serverPort.toString())
        tokenInput.setText(cfg.apiToken)
        aliasInput.setText(cfg.accountAlias)
        repoInput.setText(cfg.githubRepo)
        if (isNotificationListenerEnabled()) {
            NequiNotificationListenerService.requestRebindIfNeeded(this)
        }
        refreshSystemStatus()
        refreshPendingCount()
    }

    private fun saveCurrentConfig() {
        val port = portInput.text.toString().toIntOrNull() ?: 8000
        val alias = aliasInput.text.toString().trim().ifEmpty { "Caja Principal" }
        val repo = repoInput.text.toString().trim().ifEmpty { ServerConfig.DEFAULT_GITHUB_REPO }
        aliasInput.setText(alias)
        repoInput.setText(SecureConfigStore.normalizeRepo(repo).ifEmpty { ServerConfig.DEFAULT_GITHUB_REPO })

        val cfg = ServerConfig(
            serverIp = ipInput.text.toString(),
            serverPort = port,
            apiToken = tokenInput.text.toString(),
            accountAlias = alias,
            githubRepo = repoInput.text.toString()
        )
        store.saveServerConfig(cfg)
        Toast.makeText(this, "Configuración guardada", Toast.LENGTH_SHORT).show()
    }

    private fun testServerConnection() {
        val cfg = store.getServerConfig()
        connectionResultText.text = "Probando conexión con ${cfg.serverIp}:${cfg.serverPort}..."
        activityScope.launch {
            val health = PosApiClient().checkHealth(cfg)
            if (health.ok && health.serverGithubRepo.isNotBlank()) {
                store.updateGithubRepoIfValid(health.serverGithubRepo)
            }
            withContext(Dispatchers.Main) {
                connectionResultText.text = if (health.ok) "OK · ${health.message}" else "Error · ${health.message}"
                if (health.ok && health.serverGithubRepo.isNotBlank() &&
                    !health.serverGithubRepo.lowercase().startsWith("tu-usuario/")
                ) {
                    repoInput.setText(SecureConfigStore.normalizeRepo(health.serverGithubRepo))
                }
                Toast.makeText(this@ConfigActivity, health.message, Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun checkForAppUpdates() {
        val cfg = store.getServerConfig()
        updateStatusText.text = "Consultando GitHub Releases (${cfg.githubRepo})..."
        activityScope.launch {
            val result = AppUpdaterClient().checkLatestRelease(cfg.githubRepo)
            withContext(Dispatchers.Main) {
                updateStatusText.text = result.message
                if (result.updateAvailable && !result.apkDownloadUrl.isNullOrBlank()) {
                    showUpdateAvailableDialog(result)
                } else {
                    Toast.makeText(this@ConfigActivity, result.message, Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun showUpdateAvailableDialog(release: AndroidReleaseCheck) {
        val notesPreview = release.releaseNotes.trim().take(500).ifBlank {
            "Nueva compilación disponible para el agente Android."
        }
        AlertDialog.Builder(this)
            .setTitle("Actualización Disponible: v${release.latestVersion}")
            .setMessage("Versión actual: v${release.currentVersion}\n\n$notesPreview")
            .setPositiveButton("Descargar e Instalar") { _, _ ->
                if (!packageManager.canRequestPackageInstalls()) {
                    pendingReleaseDownload = release
                    AlertDialog.Builder(this)
                        .setTitle("Permiso para instalar APK")
                        .setMessage("Activa 'Permitir desde esta fuente' para NequiPay POS y luego regresa automáticamente a instalar la actualización.")
                        .setPositiveButton("Abrir Ajuste") { _, _ ->
                            val intent = Intent(
                                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                Uri.parse("package:$packageName")
                            )
                            unknownSourcesLauncher.launch(intent)
                        }
                        .setNegativeButton("Cancelar", null)
                        .show()
                } else {
                    startApkDownloadAndInstall(release)
                }
            }
            .setNegativeButton("Más tarde", null)
            .show()
    }

    private fun startApkDownloadAndInstall(release: AndroidReleaseCheck) {
        val apkUrl = release.apkDownloadUrl ?: return
        updateStatusText.text = "Descargando v${release.latestVersion}... 0%"
        activityScope.launch {
            try {
                val apkFile = AppUpdaterClient().downloadApkAndVerify(
                    apkUrl = apkUrl,
                    sha256SumsUrl = release.sha256SumsUrl,
                    cacheDir = cacheDir
                ) { pct ->
                    runOnUiThread {
                        updateStatusText.text = "Descargando v${release.latestVersion}... $pct%"
                    }
                }
                withContext(Dispatchers.Main) {
                    updateStatusText.text = "Descarga verificada (SHA-256). Abriendo instalador..."
                    launchApkInstaller(apkFile)
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    updateStatusText.text = "Error al actualizar: ${e.message}"
                    Toast.makeText(this@ConfigActivity, "Error: ${e.message}", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    private fun launchApkInstaller(apkFile: File) {
        val uri = FileProvider.getUriForFile(
            this,
            "${BuildConfig.APPLICATION_ID}.fileprovider",
            apkFile
        )
        val installIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        startActivity(installIntent)
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
            store.appendDiagnosticEvent("Pago de prueba $15.000 encolado manualmente")
            val res = DepositSyncManager.syncPendingQueue(applicationContext)
            if (res !is SyncQueueResult.AllSynced) {
                SyncDepositsWorker.enqueue(applicationContext)
            }
            withContext(Dispatchers.Main) {
                val msg = when (res) {
                    is SyncQueueResult.AllSynced -> "Pago de prueba enviado al servidor"
                    is SyncQueueResult.NotConfigured -> "Falta configurar el servidor"
                    is SyncQueueResult.Failed -> "Encolado offline: ${res.detail}"
                }
                Toast.makeText(this@ConfigActivity, msg, Toast.LENGTH_SHORT).show()
                refreshPendingCount()
            }
        }
    }

    private fun refreshPendingCount() {
        activityScope.launch {
            val count = AppDatabase.getInstance(applicationContext).pendingDepositDao().countPending()
            val syncInfo = store.getLastSyncStatus()
            val events = store.getDiagnosticEvents()
            withContext(Dispatchers.Main) {
                queueStatusText.text = "Cola offline pendiente: $count transacciones\nÚltima sincronización: $syncInfo"
                eventsLogText.text = events
            }
        }
    }

    private fun refreshSystemStatus() {
        val notifEnabled = isNotificationListenerEnabled()
        val listenerBound = NequiNotificationListenerService.isConnected
        val batteryIgnored = isIgnoringBatteryOptimizations()
        val notifLabel = when {
            notifEnabled && listenerBound -> "CONECTADO Y ESCUCHANDO"
            notifEnabled -> "PERMISO ACTIVO (enlazando servicio...)"
            else -> "PENDIENTE (habilitar abajo)"
        }
        val batLabel = if (batteryIgnored) "EXENTO (24/7 óptimo)" else "RESTRINGIDO (se sugiere liberar)"
        systemStatusText.text = "Lectura Nequi: $notifLabel\nBatería segundo plano: $batLabel"
        eventsLogText.text = store.getDiagnosticEvents()
    }

    private fun showAppSettingsGuide() {
        val isAndroid13Plus = Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU
        val title = if (isAndroid13Plus) {
            "Android 13+: Desbloquear Lectura de Notificaciones"
        } else {
            "Android ${Build.VERSION.RELEASE}: Mantener Escucha Activa 24/7"
        }
        val body = if (isAndroid13Plus) {
            "Si al intentar activar 'NequiPay POS Agente' en Acceso a Notificaciones aparece 'Configuración restringida':\n\n" +
                "1. Pulsa 'Abrir Info de App' abajo.\n" +
                "2. Toca los tres puntos (⋮) arriba a la derecha.\n" +
                "3. Elige 'Permitir configuración restringida'.\n" +
                "4. Regresa y activa '1. Habilitar Lectura de Notificaciones'."
        } else {
            "En Android 11/12 (especialmente Xiaomi, Samsung o Motorola), el sistema puede dormir el servicio en segundo plano.\n\n" +
                "1. Pulsa 'Abrir Info de App' abajo.\n" +
                "2. Activa 'Inicio automático' (si tu teléfono lo tiene).\n" +
                "3. En 'Batería', elige 'Sin restricciones'.\n" +
                "4. En el botón 1, desactiva y vuelve a activar el permiso de notificaciones si no aparece CONECTADO."
        }
        AlertDialog.Builder(this)
            .setTitle(title)
            .setMessage(body)
            .setPositiveButton("Abrir Info de App") { _, _ ->
                val intent = Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.parse("package:$packageName")
                )
                startActivity(intent)
            }
            .setNegativeButton("Cerrar", null)
            .show()
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
