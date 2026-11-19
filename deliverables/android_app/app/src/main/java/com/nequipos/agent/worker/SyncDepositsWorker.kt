package com.nequipos.agent.worker

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.nequipos.agent.data.local.AppDatabase
import com.nequipos.agent.data.local.SecureConfigStore
import com.nequipos.agent.data.remote.PosApiClient
import com.nequipos.agent.data.remote.SendResult
import java.util.concurrent.TimeUnit

class SyncDepositsWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val db = AppDatabase.getInstance(applicationContext)
        val dao = db.pendingDepositDao()
        val config = SecureConfigStore(applicationContext).getServerConfig()

        if (!config.isConfigured) {
            return Result.retry()
        }

        val apiClient = PosApiClient()
        // Drena la cola persistente en estricto orden cronológico
        val queue = dao.getAllChronological()

        for (item in queue) {
            when (apiClient.sendDeposit(config, item)) {
                is SendResult.Success,
                is SendResult.DuplicateIgnored -> {
                    dao.deleteById(item.id)
                }
                is SendResult.TransientFailure -> {
                    dao.incrementRetry(item.id)
                    // Detiene la iteración para preservar el orden cronológico en el siguiente reintento
                    return Result.retry()
                }
            }
        }
        return Result.success()
    }

    companion object {
        private const val UNIQUE_SYNC_WORK = "nequipos_chronological_sync"

        fun enqueue(context: Context) {
            val constraints = Constraints.Builder()
                .setRequiredNetworkType(NetworkType.CONNECTED)
                .build()

            val request = OneTimeWorkRequestBuilder<SyncDepositsWorker>()
                .setConstraints(constraints)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 5, TimeUnit.SECONDS)
                .build()

            WorkManager.getInstance(context).enqueueUniqueWork(
                UNIQUE_SYNC_WORK,
                ExistingWorkPolicy.APPEND_OR_REPLACE,
                request
            )
        }
    }
}
