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
import com.nequipos.agent.data.remote.DepositSyncManager
import com.nequipos.agent.data.remote.SyncQueueResult
import java.util.concurrent.TimeUnit

class SyncDepositsWorker(
    appContext: Context,
    params: WorkerParameters
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        return when (DepositSyncManager.syncPendingQueue(applicationContext)) {
            is SyncQueueResult.AllSynced -> Result.success()
            is SyncQueueResult.NotConfigured,
            is SyncQueueResult.Failed -> Result.retry()
        }
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

            // REPLACE garantiza ejecución inmediata al capturar un nuevo pago o pulsar sincronizar
            WorkManager.getInstance(context).enqueueUniqueWork(
                UNIQUE_SYNC_WORK,
                ExistingWorkPolicy.REPLACE,
                request
            )
        }
    }
}
