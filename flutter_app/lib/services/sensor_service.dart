import 'dart:async';

import '../models/biometric_data.dart';

/// Placeholder stream: no health or accelerometer data. Emits periodic snapshots for the dashboard/backend.
class SensorService {
  StreamController<BiometricData>? _controller;
  Timer? _pollTimer;

  Future<void> startListening() async {
    _controller ??= StreamController<BiometricData>.broadcast();
    if (_pollTimer != null) return;

    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _emitSnapshot());
    _emitSnapshot();
  }

  void _emitSnapshot() {
    _controller?.add(BiometricData(
      heartRate: null,
      hrv: null,
      spo2: null,
      accelX: 0,
      accelY: 0,
      accelZ: 0,
      timestamp: DateTime.now().millisecondsSinceEpoch,
    ));
  }

  void stopListening() {
    _pollTimer?.cancel();
    _pollTimer = null;
    _controller?.close();
    _controller = null;
  }

  Stream<BiometricData> get sensorStream {
    _controller ??= StreamController<BiometricData>.broadcast();
    return _controller!.stream;
  }
}
