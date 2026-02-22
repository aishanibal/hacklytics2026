package com.flutter_app

import android.content.Intent
import android.util.Log
import com.google.android.gms.wearable.MessageEvent
import com.google.android.gms.wearable.WearableListenerService

class StateReceiverService : WearableListenerService() {
    override fun onMessageReceived(messageEvent: MessageEvent) {
        if (messageEvent.path == "/state_update") {
            val state = String(messageEvent.data)
            Log.d("Vigil", "State received: $state")
            val intent = Intent("com.flutter_app.watch.STATE_CHANGE").apply {
                putExtra("state", state)
            }
            sendBroadcast(intent)
        }
    }
}
