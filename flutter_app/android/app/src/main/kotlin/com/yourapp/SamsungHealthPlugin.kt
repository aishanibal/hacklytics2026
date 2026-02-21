package com.yourapp

import android.content.Context
import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel
import io.flutter.plugin.common.MethodChannel.MethodCallHandler
import kotlinx.coroutines.*

/**
 * Bridges Samsung Health / Health Connect data to Flutter via:
 *   MethodChannel: com.yourapp/samsung_health  (start/stop commands)
 *   EventChannel:  com.yourapp/sensor_stream   (continuous biometric stream)
 *
 * Polling interval: every 15 seconds using coroutines.
 */
class SamsungHealthPlugin(
    private val context: Context,
    private val watchDataManager: WatchDataManager,
) : MethodCallHandler, EventChannel.StreamHandler {

    companion object {
        const val METHOD_CHANNEL = "com.yourapp/samsung_health"
        const val EVENT_CHANNEL = "com.yourapp/sensor_stream"
        private const val POLL_INTERVAL_MS = 15_000L
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private var eventSink: EventChannel.EventSink? = null
    private var pollingJob: Job? = null

    // ---- MethodChannel ----

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "startListening" -> {
                startPolling()
                result.success(null)
            }
            "stopListening" -> {
                stopPolling()
                result.success(null)
            }
            else -> result.notImplemented()
        }
    }

    // ---- EventChannel ----

    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
        eventSink = events
    }

    override fun onCancel(arguments: Any?) {
        eventSink = null
        stopPolling()
    }

    // ---- Polling loop ----

    private fun startPolling() {
        if (pollingJob?.isActive == true) return

        pollingJob = scope.launch {
            while (isActive) {
                val data = fetchSensorData()
                mainHandler.post {
                    eventSink?.success(data)
                }
                delay(POLL_INTERVAL_MS)
            }
        }
    }

    private fun stopPolling() {
        pollingJob?.cancel()
        pollingJob = null
    }

    private suspend fun fetchSensorData(): Map<String, Any?> {
        // All calls are wrapped in WatchDataManager — safe to call concurrently
        val heartRate = watchDataManager.getLatestHeartRate()
        val spo2 = watchDataManager.getLatestSpO2()
        val steps = watchDataManager.getStepCount(durationMinutes = 60)
        val skinTemp = watchDataManager.getLatestSkinTemperature()

        return mapOf(
            "heartRate" to heartRate,
            "spo2" to spo2,
            "stepCount" to steps,
            "skinTemperature" to skinTemp,
            "timestamp" to System.currentTimeMillis(),
        )
    }

    fun dispose() {
        stopPolling()
        scope.cancel()
    }
}
