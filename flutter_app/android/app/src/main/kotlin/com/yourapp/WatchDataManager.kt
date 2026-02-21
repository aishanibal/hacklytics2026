package com.yourapp

import android.content.Context
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.records.HeartRateRecord
import androidx.health.connect.client.records.OxygenSaturationRecord
import androidx.health.connect.client.records.SkinTemperatureRecord
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.ReadRecordsRequest
import androidx.health.connect.client.time.TimeRangeFilter
import java.time.Instant
import java.time.temporal.ChronoUnit

/**
 * Manages Health Connect reads.
 * All sensor reads are wrapped in try/catch — never crash if a sensor is unavailable.
 */
class WatchDataManager(context: Context) {

    private val client: HealthConnectClient = HealthConnectClient.getOrCreate(context)

    /** Returns the most recent heart rate sample, or null if unavailable. */
    suspend fun getLatestHeartRate(): Double? {
        return try {
            val request = ReadRecordsRequest(
                recordType = HeartRateRecord::class,
                timeRangeFilter = TimeRangeFilter.between(
                    Instant.now().minus(5, ChronoUnit.MINUTES),
                    Instant.now()
                )
            )
            val response = client.readRecords(request)
            response.records.lastOrNull()?.samples?.lastOrNull()?.beatsPerMinute?.toDouble()
        } catch (_: Exception) {
            null
        }
    }

    /** Returns the most recent SpO2 reading (%), or null if unavailable. */
    suspend fun getLatestSpO2(): Double? {
        return try {
            val request = ReadRecordsRequest(
                recordType = OxygenSaturationRecord::class,
                timeRangeFilter = TimeRangeFilter.between(
                    Instant.now().minus(5, ChronoUnit.MINUTES),
                    Instant.now()
                )
            )
            val response = client.readRecords(request)
            response.records.lastOrNull()?.percentage?.value
        } catch (_: Exception) {
            null
        }
    }

    /**
     * Returns the step count over the last [durationMinutes] minutes.
     * Returns 0 if unavailable.
     */
    suspend fun getStepCount(durationMinutes: Int = 60): Int {
        return try {
            val request = ReadRecordsRequest(
                recordType = StepsRecord::class,
                timeRangeFilter = TimeRangeFilter.between(
                    Instant.now().minus(durationMinutes.toLong(), ChronoUnit.MINUTES),
                    Instant.now()
                )
            )
            val response = client.readRecords(request)
            response.records.sumOf { it.count }.toInt()
        } catch (_: Exception) {
            0
        }
    }

    /** Returns the most recent skin temperature (°C), or null if unavailable. */
    suspend fun getLatestSkinTemperature(): Double? {
        return try {
            val request = ReadRecordsRequest(
                recordType = SkinTemperatureRecord::class,
                timeRangeFilter = TimeRangeFilter.between(
                    Instant.now().minus(5, ChronoUnit.MINUTES),
                    Instant.now()
                )
            )
            val response = client.readRecords(request)
            response.records.lastOrNull()?.baseline?.inCelsius
        } catch (_: Exception) {
            null
        }
    }
}
