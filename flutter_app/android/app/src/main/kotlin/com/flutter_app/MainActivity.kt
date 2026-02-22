package com.flutter_app

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.os.Build
import android.os.Bundle
import android.os.ParcelUuid
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.util.Log
import androidx.core.app.ActivityCompat
import com.google.android.gms.wearable.CapabilityClient
import com.google.android.gms.wearable.Node
import com.google.android.gms.wearable.Wearable
import io.flutter.embedding.android.FlutterFragmentActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import java.util.UUID

class MainActivity : FlutterFragmentActivity() {

    private var advertiser: BluetoothLeAdvertiser? = null
    private val UUID_STRING = "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13"

    private var vibrator: Vibrator? = null
    private var mediaPlayer: MediaPlayer? = null
    private var eventSink: EventChannel.EventSink? = null

    private val watchMessageReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context, intent: Intent) {
            val message = intent.getStringExtra("message") ?: return
            Log.d(TAG, "Watch → Phone broadcast received: $message")
            runOnUiThread {
                eventSink?.success(message)
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Log.d(TAG, "onCreate")

        vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vm.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        }

        if (hasBlePermissions()) {
            startBLE()
        } else {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(
                    Manifest.permission.BLUETOOTH_ADVERTISE,
                    Manifest.permission.BLUETOOTH_SCAN,
                    Manifest.permission.BLUETOOTH_CONNECT,
                    Manifest.permission.ACCESS_FINE_LOCATION
                ),
                REQUEST_BLE
            )
        }

        registerWatchReceiver()
    }

    // ── Flutter platform channels ──

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        Log.d(TAG, "configureFlutterEngine — setting up channels")

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL_WATCH)
            .setMethodCallHandler { call, result ->
                Log.d(TAG, "MethodChannel call: ${call.method}")
                when (call.method) {
                    "sendToWatch" -> {
                        val message = call.argument<String>("message") ?: ""
                        sendMessageToWatch(message)
                        result.success(null)
                    }
                    "startVibration" -> {
                        val pattern = call.argument<String>("pattern") ?: "strong"
                        startVibration(pattern)
                        result.success(null)
                    }
                    "stopVibration" -> {
                        stopVibration()
                        result.success(null)
                    }
                    "startAlarm" -> {
                        startAlarm()
                        result.success(null)
                    }
                    "stopAlarm" -> {
                        stopAlarm()
                        result.success(null)
                    }
                    else -> result.notImplemented()
                }
            }

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL_WATCH_EVENTS)
            .setStreamHandler(object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink) {
                    Log.d(TAG, "EventChannel onListen — Flutter is listening for watch messages")
                    eventSink = events
                }
                override fun onCancel(arguments: Any?) {
                    Log.d(TAG, "EventChannel onCancel")
                    eventSink = null
                }
            })
    }

    // ── Watch broadcast receiver ──

    @Suppress("UnspecifiedRegisterReceiverFlag")
    private fun registerWatchReceiver() {
        val filter = IntentFilter(PhoneMessageService.ACTION_WATCH_MESSAGE)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerReceiver(watchMessageReceiver, filter, RECEIVER_NOT_EXPORTED)
        } else {
            registerReceiver(watchMessageReceiver, filter)
        }
        Log.d(TAG, "Watch broadcast receiver registered")
    }

    override fun onDestroy() {
        Log.d(TAG, "onDestroy")
        try { unregisterReceiver(watchMessageReceiver) } catch (_: Exception) {}
        stopAlarm()
        stopVibration()
        super.onDestroy()
    }

    // ── Wearable Data Layer: phone → watch ──

    private fun sendMessageToWatch(message: String) {
        Log.d(TAG, "sendMessageToWatch: $message")

        // Strategy 1: Find watch via CapabilityClient (advertised capability)
        Wearable.getCapabilityClient(this)
            .getCapability(WATCH_CAPABILITY, CapabilityClient.FILTER_REACHABLE)
            .addOnSuccessListener { capabilityInfo ->
                val nodes = capabilityInfo.nodes
                Log.d(TAG, "CapabilityClient found ${nodes.size} node(s) with '$WATCH_CAPABILITY'")
                if (nodes.isNotEmpty()) {
                    sendToNodes(nodes, message)
                } else {
                    Log.d(TAG, "No capability nodes — falling back to getConnectedNodes")
                    sendViaConnectedNodes(message)
                }
            }
            .addOnFailureListener { e ->
                Log.w(TAG, "CapabilityClient failed: ${e.message} — falling back to getConnectedNodes")
                sendViaConnectedNodes(message)
            }
    }

    private fun sendViaConnectedNodes(message: String) {
        Wearable.getNodeClient(this).connectedNodes
            .addOnSuccessListener { nodes ->
                Log.d(TAG, "getConnectedNodes found ${nodes.size} node(s)")
                if (nodes.isEmpty()) {
                    Log.e(TAG, "NO connected nodes! Check Galaxy Wearable pairing and remote connection.")
                } else {
                    sendToNodes(nodes.toSet(), message)
                }
            }
            .addOnFailureListener { e ->
                Log.e(TAG, "getConnectedNodes FAILED: ${e.message}")
            }
    }

    private fun sendToNodes(nodes: Set<Node>, message: String) {
        for (node in nodes) {
            Log.d(TAG, "Sending '$message' to ${node.displayName} (${node.id}), nearby=${node.isNearby}")
            Wearable.getMessageClient(this)
                .sendMessage(node.id, MESSAGE_PATH, message.toByteArray())
                .addOnSuccessListener {
                    Log.d(TAG, "SUCCESS: Sent '$message' to ${node.displayName}")
                }
                .addOnFailureListener { e ->
                    Log.e(TAG, "FAILED to send to ${node.displayName}: ${e.message}")
                }
        }
    }

    // ── Vibration ──

    private fun startVibration(pattern: String) {
        vibrator?.cancel()
        val timings = if (pattern == "strong") {
            longArrayOf(0, 400, 200, 400, 200)
        } else {
            longArrayOf(0, 200, 2000)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(VibrationEffect.createWaveform(timings, 0))
        } else {
            @Suppress("DEPRECATION")
            vibrator?.vibrate(timings, 0)
        }
    }

    private fun stopVibration() {
        vibrator?.cancel()
    }

    // ── Alarm sound ──

    private fun startAlarm() {
        stopAlarm()
        try {
            val alarmUri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
                ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION)
                ?: return
            mediaPlayer = MediaPlayer().apply {
                setDataSource(this@MainActivity, alarmUri)
                isLooping = true
                prepare()
                start()
            }
            Log.d(TAG, "Alarm started")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to start alarm: ${e.message}")
        }
    }

    private fun stopAlarm() {
        try {
            mediaPlayer?.apply {
                if (isPlaying) stop()
                release()
            }
        } catch (_: Exception) {}
        mediaPlayer = null
    }

    // ── BLE advertising ──

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_BLE && grantResults.isNotEmpty() &&
            grantResults.all { it == android.content.pm.PackageManager.PERMISSION_GRANTED }) {
            startBLE()
        }
    }

    private fun hasBlePermissions(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            checkSelfPermission(Manifest.permission.BLUETOOTH_ADVERTISE) ==
                android.content.pm.PackageManager.PERMISSION_GRANTED &&
            checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) ==
                android.content.pm.PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }

    private fun startBLE() {
        val bluetoothAdapter = BluetoothAdapter.getDefaultAdapter()
        if (bluetoothAdapter == null) {
            Log.e(TAG, "BLE failed: no Bluetooth adapter")
            return
        }
        advertiser = bluetoothAdapter.bluetoothLeAdvertiser
        if (advertiser == null) {
            Log.e(TAG, "BLE failed: BLE advertising not supported")
            return
        }
        bluetoothAdapter.name = "TARGET_A15"
        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
            .setConnectable(false)
            .setTimeout(0)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
            .build()
        val advData = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .addServiceUuid(ParcelUuid(UUID.fromString(UUID_STRING)))
            .build()
        val scanResponse = AdvertiseData.Builder()
            .setIncludeDeviceName(true)
            .build()
        advertiser?.startAdvertising(settings, advData, scanResponse,
            object : AdvertiseCallback() {
                override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
                    Log.i(TAG, "BLE advertising started: TARGET_A15 / $UUID_STRING")
                }
                override fun onStartFailure(errorCode: Int) {
                    Log.e(TAG, "BLE advertising failed: $errorCode")
                }
            }
        )
    }

    companion object {
        private const val TAG = "MainActivity"
        private const val REQUEST_BLE = 1001
        private const val CHANNEL_WATCH = "com.flutter_app/watch"
        private const val CHANNEL_WATCH_EVENTS = "com.flutter_app/watch_events"
        private const val WATCH_CAPABILITY = "vigil_watch"
        private const val MESSAGE_PATH = "/state_update"
    }
}
