import 'dart:async';

import 'package:flutter/services.dart';

/// Wraps the platform channels for phone ↔ watch communication.
///
/// MethodChannel  → send commands to native (sendToWatch, vibration, alarm)
/// EventChannel   → receive watch messages streamed from native
class WatchCommunicationService {
  static const _methodChannel = MethodChannel('com.flutter_app/watch');
  static const _eventChannel = EventChannel('com.flutter_app/watch_events');

  Stream<String>? _watchMessages;

  Stream<String> get watchMessages {
    _watchMessages ??= _eventChannel
        .receiveBroadcastStream()
        .map((event) => event.toString());
    return _watchMessages!;
  }

  Future<void> sendToWatch(String message) async {
    try {
      await _methodChannel.invokeMethod('sendToWatch', {'message': message});
    } on PlatformException catch (_) {
      // Watch may not be connected — fail silently
    }
  }

  Future<void> startVibration({bool strong = true}) async {
    try {
      await _methodChannel.invokeMethod('startVibration', {
        'pattern': strong ? 'strong' : 'slow',
      });
    } on PlatformException catch (_) {}
  }

  Future<void> stopVibration() async {
    try {
      await _methodChannel.invokeMethod('stopVibration');
    } on PlatformException catch (_) {}
  }

  Future<void> startAlarm() async {
    try {
      await _methodChannel.invokeMethod('startAlarm');
    } on PlatformException catch (_) {}
  }

  Future<void> stopAlarm() async {
    try {
      await _methodChannel.invokeMethod('stopAlarm');
    } on PlatformException catch (_) {}
  }
}
