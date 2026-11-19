package com.nequipos.agent.data.remote

import android.content.Context
import com.nequipos.agent.data.local.AppDatabase
import com.nequipos.agent.data.local.SecureConfigStore
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

sealed class SyncQueueResult {
    data object AllSynced : SyncQueueResult()
    data object NotConfigured : SyncQueueResult()
    data class Failed(val detail: String) : SyncQueueResult()
}

object DepositSyncManager {

    private val syncMutex = Mutex()

    suspend fun syncPendingQueue(context: Context): SyncQueueResult = syncMutex.withLock {
        val appCtx = context.applicationContext
        val dao = AppDatabase.getInstance(appCtx).pendingDepositDao()
        val store = SecureConfigStore(appCtx)
        val config = store.getServerConfig()

        if (!config.isConfigured) {
            val msg = "Pendiente: falta configurar IP, Puerto o Token del servidor"
            store.setLastSyncStatus(msg)
            return SyncQueueResult.NotConfigured
        }

        val apiClient = PosApiClient()
        val queue = dao.getAllChronological()
        if (queue.isEmpty()) {
            return SyncQueueResult.AllSynced
        }

        for (item in queue) {
            when (val res = apiClient.sendDeposit(config, item)) {
                is SendResult.Success -> {
                    dao.deleteById(item.id)
                    val okMsg = "Último envío OK: $${item.amountCop} (${item.senderName})"
                    store.setLastSyncStatus(okMsg)
                    store.appendDiagnosticEvent("Enviado al servidor: $${item.amountCop}")
                }
                is SendResult.DuplicateIgnored -> {
                    dao.deleteById(item.id)
                    store.setLastSyncStatus("Duplicado omitido: $${item.amountCop}")
                }
                is SendResult.TransientFailure -> {
                    dao.incrementRetry(item.id)
                    val detail = when (res.code) {
                        401 -> "Error HTTP 401: Token API incorrecto (escanea el QR nuevamente)"
                        403 -> "Error HTTP 403: Cuenta '${item.accountAlias}' inactiva en servidor"
                        else -> "Error de envío (HTTP ${res.code}): ${res.message}"
                    }
                    store.setLastSyncStatus(detail)
                    store.appendDiagnosticEvent(detail)
                    return SyncQueueResult.Failed(detail)
                }
            }
        }
        return SyncQueueResult.AllSynced
    }
}
