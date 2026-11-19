package com.nequipos.agent.service

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.nequipos.agent.data.local.AppDatabase
import com.nequipos.agent.data.local.PendingDepositEntity
import com.nequipos.agent.data.local.SecureConfigStore
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
        AgentForegroundService.ensureRunning(applicationContext)
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        val notification = sbn ?: return
        if (notification.packageName != NequiNotificationParser.NEQUI_PACKAGE_NAME) {
            return
        }

        val extras = notification.notification?.extras ?: return
        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        val bigText = extras.getCharSequence(Notification.EXTRA_BIG_TEXT)?.toString().orEmpty()
        val body = if (bigText.length > text.length) bigText else text

        val capturedMs = notification.postTime
        val parsed = NequiNotificationParser.parse(title, body, capturedMs) ?: return

        val config = SecureConfigStore(applicationContext).getServerConfig()
        val isoTimestamp = DateTimeFormatter.ISO_INSTANT.format(
            Instant.ofEpochMilli(parsed.capturedAtEpochMs).atOffset(ZoneOffset.UTC)
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
            SyncDepositsWorker.enqueue(applicationContext)
        }
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }
}
