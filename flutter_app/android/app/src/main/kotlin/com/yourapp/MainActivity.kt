package com.yourapp

import android.Manifest
import android.bluetooth.BluetoothAdapter
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.ParcelUuid
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import java.util.UUID

class MainActivity : AppCompatActivity() {

    private var advertiser: BluetoothLeAdvertiser? = null

    // Your unique phone ID – Raspberry Pi can read this from BLE scan to identify this device
    private val UUID_STRING = "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val bluetoothAdapter = BluetoothAdapter.getDefaultAdapter()
        if (bluetoothAdapter == null) {
            println("BLE Advertising failed: no Bluetooth adapter")
            return
        }
        advertiser = bluetoothAdapter.bluetoothLeAdvertiser
        if (advertiser == null) {
            println("BLE Advertising failed: BLE not supported")
            return
        }

        if (hasBleAdvertisePermission()) {
            startAdvertising()
        } else {
            requestBleAdvertisePermission()
        }
    }

    private fun hasBleAdvertisePermission(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_ADVERTISE) == PackageManager.PERMISSION_GRANTED &&
                ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
        } else {
            true
        }
    }

    private fun requestBleAdvertisePermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            ActivityCompat.requestPermissions(
                this,
                arrayOf(Manifest.permission.BLUETOOTH_ADVERTISE, Manifest.permission.BLUETOOTH_CONNECT),
                REQUEST_BLE_ADVERTISE
            )
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == REQUEST_BLE_ADVERTISE && grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            startAdvertising()
        } else if (requestCode == REQUEST_BLE_ADVERTISE) {
            println("BLE Advertising failed: BLUETOOTH_ADVERTISE permission denied")
        }
    }

    companion object {
        private const val REQUEST_BLE_ADVERTISE = 1001
    }

    private fun startAdvertising() {

        val uuid = ParcelUuid(UUID.fromString(UUID_STRING))

        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
            .setConnectable(false)
            .build()

        val data = AdvertiseData.Builder()
            .addServiceUuid(uuid)
            .setIncludeDeviceName(false)
            .build()

        advertiser?.startAdvertising(settings, data, advertiseCallback)
    }

    private val advertiseCallback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings) {
            println("BLE Advertising started")
        }

        override fun onStartFailure(errorCode: Int) {
            println("BLE Advertising failed: $errorCode")
        }
    }
}