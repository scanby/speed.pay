package com.nequipos.agent.data.local

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import android.content.Context

@Dao
interface PendingDepositDao {
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insert(item: PendingDepositEntity): Long

    @Query("SELECT * FROM pending_deposits ORDER BY capturedAtEpochMs ASC, id ASC")
    suspend fun getAllChronological(): List<PendingDepositEntity>

    @Query("DELETE FROM pending_deposits WHERE id = :id")
    suspend fun deleteById(id: Long)

    @Query("UPDATE pending_deposits SET retryCount = retryCount + 1 WHERE id = :id")
    suspend fun incrementRetry(id: Long)

    @Query("SELECT COUNT(*) FROM pending_deposits")
    suspend fun countPending(): Int
}

@Database(entities = [PendingDepositEntity::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun pendingDepositDao(): PendingDepositDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getInstance(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "nequipos_offline_queue.db"
                ).build().also { INSTANCE = it }
            }
        }
    }
}
