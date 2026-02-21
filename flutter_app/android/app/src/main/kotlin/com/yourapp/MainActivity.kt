package com.yourapp

package com.example.bletracker

import android.bluetooth.BluetoothAdapter
import android.bluetooth.le.*
import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import java.util.*

class MainActivity : AppCompatActivity() {

    private var advertiser: BluetoothLeAdvertiser? = null

    // Your unique phone ID
    private val UUID_STRING = "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13"

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val bluetoothAdapter = BluetoothAdapter.getDefaultAdapter()
        advertiser = bluetoothAdapter.bluetoothLeAdvertiser

        startAdvertising()
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