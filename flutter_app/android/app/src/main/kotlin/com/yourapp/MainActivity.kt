package com.yourapp

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.os.Build
import android.os.Bundle
import android.os.ParcelUuid
import java.util.UUID
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat

class MainActivity : AppCompatActivity() {

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
        if (requestCode == REQUEST_BLE && grantResults.isNotEmpty() && grantResults.all { it == android.content.pm.PackageManager.PERMISSION_GRANTED }) {
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
            android.util.Log.e("MainActivity", "BLE failed: no Bluetooth adapter")
            return
        }
        advertiser = bluetoothAdapter.bluetoothLeAdvertiser
        if (advertiser == null) {
            android.util.Log.e("MainActivity", "BLE failed: BLE advertising not supported")
            return
        }

        bluetoothAdapter.name = "TARGET_A15"

        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
            .setConnectable(false)
            .setTimeout(0)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
            .build()

        val data = AdvertiseData.Builder()
            .setIncludeDeviceName(true)
            .addServiceUuid(ParcelUuid(UUID.fromString(UUID_STRING)))
            .build()

        advertiser?.startAdvertising(
            settings,
            data,
            object : AdvertiseCallback() {
                override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
                    android.util.Log.i("MainActivity", "BLE advertising started: TARGET_A15 / $UUID_STRING")
                }
                override fun onStartFailure(errorCode: Int) {
                    android.util.Log.e("MainActivity", "BLE advertising failed: $errorCode")
                }
            }
        )
    }

    companion object {
        private const val REQUEST_BLE = 1001
    }
}