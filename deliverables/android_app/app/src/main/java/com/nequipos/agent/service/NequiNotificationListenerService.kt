package com.nequipos.agent.service

import android.app.Notification
import android.content.ComponentName
import android.content.Context
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.nequipos.agent.data.local.AppDatabase
import com.nequipos.agent.data.local.PendingDepositEntity
import com.nequipos.agent.data.local.SecureConfigStore
import com.nequipos.agent.data.remote.DepositSyncManager
import com.nequipos.agent.data.remote.SyncQueueResult
import com.nequipos.agent.domain.parser.NequiNotificationParser
import com.nequipos.agent.worker.SyncDepositsWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

class NequiNotificationListenerService : NotificationListenerService() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onListenerConnected() {
        super.onListenerConnected()
        isConnected = true
        AgentForegroundService.ensureRunning(applicationContext)
        SecureConfigStore(applicationContext).appendDiagnosticEvent(
            "Listener conectado y escuchando Nequi"
        )
    }

    override fun onListenerDisconnected() {
        isConnected = false
        SecureConfigStore(applicationContext).appendDiagnosticEvent(
            "Listener desconectado; solicitando reconexión"
        )
        requestRebind(ComponentName(this, NequiNotificationListenerService::class.java))
        super.onListenerDisconnected()
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        val statusNotification = sbn ?: return
        if (!NequiNotificationParser.isNequiPackage(statusNotification.packageName)) {
            return
        }

        val notif = statusNotification.notification ?: return
        // Ignora notificaciones continuas de sistema o encabezados agrupados vacíos
        if ((notif.flags and Notification.FLAG_ONGOING_EVENT) != 0) {
            return
        }
        if ((notif.flags and Notification.FLAG_GROUP_SUMMARY) != 0) {
            return
        }

        val extras = notif.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString().orEmpty()
        val subText = extras.getCharSequence(Notification.EXTRA_SUB_TEXT)?.toString().orEmpty()
        val textLines = extras.getCharSequenceArray(Notification.EXTRA_TEXT_LINES)
            ?.joinToString(" ") { it?.toString().orEmpty() }
            .orEmpty()
        val ticker = notif.tickerText?.toString().orEmpty()

        val bodyParts = listOf(bigText, text, subText, textLines, ticker)
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .distinct()
        val body = bodyParts.joinToString(" ")

        val capturedMs = statusNotification.postTime
        val store = SecureConfigStore(applicationContext)
        val parsed = NequiNotificationParser.parse(title, body, capturedMs)
        if (parsed == null) {
            val preview = listOf(title, body).filter { it.isNotBlank() }.joinToString(" | ").take(90)
            if (preview.isNotBlank()) {
                store.appendDiagnosticEvent("Nequi ignorada (${statusNotification.packageName}): $preview")
            }
            return
        }

        val config = store.getServerConfig()
        val isoTimestamp = DateTimeFormatter.ISO_INSTANT.format(
            Instant.ofEpochMilli(parsed.capturedAtEpochMs).atOffset(ZoneOffset.UTC)
        )

        store.appendDiagnosticEvent(
            "Capturado $${parsed.amountCop.toPlainString()} de ${parsed.senderName}"
        )

        scope.launch {
            val dao = AppDatabase.getInstance(applicationContext).pendingDepositDao()
            dao.insert(
                PendingDepositEntity(
                    accountAlias = config.accountAlias,
                    senderName = parsed.senderName,
                    amountCop = parsed.amountCop.toPlainString(),
                    rawNotification = parsed.rawNotification,
                    capturedAtIso = isoTimestamp,
                    capturedAtEpochMs = parsed.capturedAtEpochMs,
                    source = "ANDROID_NOTIFICATION"
                )
            )
            val result = DepositSyncManager.syncPendingQueue(applicationContext)
            if (result !is SyncQueueResult.AllSynced) {
                SyncDepositsWorker.enqueue(applicationContext)
            }
        }
    }

    override fun onDestroy() {
        isConnected = false
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        @Volatile
        var isConnected: Boolean = false
            private set

        fun requestRebindIfNeeded(context: Context) {
            if (!isConnected) {
                try {
                    requestRebind(ComponentName(context, NequiNotificationListenerService::class.java))
                } catch (_: Exception) {
                    // El sistema enlazará el servicio cuando el usuario habilite el permiso
                }
            }
        }
    }
}
