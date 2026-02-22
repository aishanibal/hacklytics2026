import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/biometric_data.dart';
import 'sensor_service.dart';

/// Listens to SensorService's health stream and pushes each reading
/// to the Python CV backend so it has fresh data when an anomaly fires.
class HealthPushService {
  final SensorService _sensor;
  final String _backendBaseUrl;

  StreamSubscription<BiometricData>? _sub;

  HealthPushService({
    required SensorService sensor,
    required String backendBaseUrl,
  })  : _sensor = sensor,
        _backendBaseUrl = backendBaseUrl;

  Future<void> start() async {
    await _sensor.startListening();
    _sub = _sensor.sensorStream.listen(_push);
  }

  void stop() {
    _sub?.cancel();
    _sub = null;
    _sensor.stopListening();
  }

  Future<void> _push(BiometricData data) async {
    try {
      await http.post(
        Uri.parse('$_backendBaseUrl/pose/health-push'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(data.toHealthPush()),
      );
    } catch (_) {
      // Backend unreachable — ignore, next push will try again.
    }
  }
}
