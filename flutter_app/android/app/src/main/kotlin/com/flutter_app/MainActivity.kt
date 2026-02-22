package com.flutter_app

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.os.Build
import android.os.Bundle
import android.os.ParcelUuid
import android.util.Log
import androidx.core.app.ActivityCompat
import io.flutter.embedding.android.FlutterFragmentActivity
import java.util.UUID

/**
 * Health data (heart rate, HRV, SpO2) and accelerometer are handled by the Flutter
 * health and sensors_plus packages. This activity only handles BLE advertising
 * so the Raspberry Pi can discover the phone.
 */
class MainActivity : FlutterFragmentActivity() {

    private var advertiser: BluetoothLeAdvertiser? = null
    private val UUID_STRING = "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

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
    }

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
            checkSelfPermission(Manifest.permission.BLUETOOTH_ADVERTISE) == android.content.pm.PackageManager.PERMISSION_GRANTED &&
                checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == android.content.pm.PackageManager.PERMISSION_GRANTED
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
    }
}
