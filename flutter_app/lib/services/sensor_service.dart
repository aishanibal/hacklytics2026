import 'package:flutter/services.dart';

import '../models/biometric_data.dart';

class SensorService {
  static const MethodChannel _methodChannel =
      MethodChannel('com.yourapp/samsung_health');

  static const EventChannel _eventChannel =
      EventChannel('com.yourapp/sensor_stream');

  Stream<BiometricData>? _sensorStream;

  /// Start the Health Connect polling loop on the Kotlin side.
  Future<void> startListening() async {
    try {
      await _methodChannel.invokeMethod<void>('startListening');
    } on PlatformException catch (e) {
      // TODO: surface this error to the UI via a Riverpod provider
      // ignore: avoid_print
      print('SensorService.startListening error: ${e.message}');
    }
  }

  /// Stop the polling loop.
  Future<void> stopListening() async {
    try {
      await _methodChannel.invokeMethod<void>('stopListening');
    } on PlatformException catch (_) {
      // Sensor unavailable — fail silently, never crash
    }
  }

  /// Continuous stream of biometric readings from the watch.
  Stream<BiometricData> get sensorStream {
    _sensorStream ??= _eventChannel
        .receiveBroadcastStream()
        .where((event) => event is Map)
        .map((event) => BiometricData.fromMap(Map<String, dynamic>.from(event as Map)));
    return _sensorStream!;
  }
}
