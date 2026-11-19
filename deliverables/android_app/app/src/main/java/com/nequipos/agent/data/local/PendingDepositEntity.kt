package com.nequipos.agent.data.local

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "pending_deposits")
data class PendingDepositEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val accountAlias: String,
    val senderName: String,
    val amountCop: String,
    val rawNotification: String,
    val capturedAtIso: String,
    val capturedAtEpochMs: Long,
    val source: String = "ANDROID_NOTIFICATION",
    val retryCount: Int = 0
)
