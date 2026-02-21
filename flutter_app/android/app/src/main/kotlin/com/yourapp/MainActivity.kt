package com.yourapp

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {

    private lateinit var watchDataManager: WatchDataManager
    private lateinit var healthPlugin: SamsungHealthPlugin

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        watchDataManager = WatchDataManager(this)
        healthPlugin = SamsungHealthPlugin(this, watchDataManager)

        // Register MethodChannel for start/stop commands
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            SamsungHealthPlugin.METHOD_CHANNEL
        ).setMethodCallHandler(healthPlugin)

        // Register EventChannel for the continuous sensor stream
        EventChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            SamsungHealthPlugin.EVENT_CHANNEL
        ).setStreamHandler(healthPlugin)
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        // Handle Health Connect permission result here if needed
        // TODO: forward permission grant/deny back to Flutter via MethodChannel
    }

    override fun onDestroy() {
        healthPlugin.dispose()
        super.onDestroy()
    }
}
