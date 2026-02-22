package com.flutter_app

import android.content.Intent
import android.util.Log
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService

/**
 * Receives Wearable Data Layer messages from the watch.
 * Forwards them as a local broadcast so [MainActivity] can
 * relay the message to Flutter via EventChannel.
 */
class PhoneMessageService : WearableListenerService() {
    override fun onMessageReceived(messageEvent: MessageEvent) {
        if (messageEvent.path == "/state_update") {
            val message = String(messageEvent.data)
            Log.d(TAG, "Watch → Phone: $message")
            val intent = Intent(ACTION_WATCH_MESSAGE).apply {
                putExtra("message", message)
            }
            sendBroadcast(intent)
        }
    }

    companion object {
        const val ACTION_WATCH_MESSAGE = "com.flutter_app.WATCH_MESSAGE"
        private const val TAG = "PhoneMessageService"
    }
}
