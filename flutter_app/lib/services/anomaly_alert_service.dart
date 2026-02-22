import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

/// Result of polling the anomaly endpoint: last anomaly type or null, and connection error if any.
class AnomalyAlertState {
  final String? anomalyType;
  final Object? error;
  final bool hasReceivedMessage;

  const AnomalyAlertState({
    this.anomalyType,
    this.error,
    this.hasReceivedMessage = false,
  });
}

/// Polls GET /pose/anomaly on the CV backend and emits anomaly state for the UI.
class AnomalyAlertService {
  final String _backendBaseUrl;

  Timer? _pollTimer;
  final _stateController = StreamController<AnomalyAlertState>.broadcast();

  static const Duration _pollInterval = Duration(milliseconds: 1500);

  AnomalyAlertService({required String backendBaseUrl})
      : _backendBaseUrl = backendBaseUrl;

  /// Stream of anomaly state (connection status + current anomaly type).
  Stream<AnomalyAlertState> get stateStream => _stateController.stream;

  void connect() {
    if (_pollTimer != null) return;
    _pollTimer = Timer.periodic(_pollInterval, (_) => _poll());
    _poll(); // first poll immediately
  }

  void disconnect() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _poll() async {
    final uri = Uri.parse('$_backendBaseUrl/pose/anomaly');
    if (kDebugMode) {
      // ignore: avoid_print
      print('[AnomalyPoll] GET $uri');
    }
    try {
      final response = await http.get(uri).timeout(
        const Duration(seconds: 15),
        onTimeout: () => throw TimeoutException('Anomaly poll timeout'),
      );
      if (response.statusCode != 200) {
        _stateController.add(AnomalyAlertState(
          error: Exception('HTTP ${response.statusCode}'),
          hasReceivedMessage: false,
        ));
        return;
      }
      final map = jsonDecode(response.body) as Map<String, dynamic>;
      final isAnomaly = _parseIsAnomaly(map['is_anomaly']);
      final type = _parseAnomalyType(map['anomaly_type']);
      final anomalyType =
          (isAnomaly && type != null && type.isNotEmpty) ? type : null;
      if (kDebugMode) {
        // ignore: avoid_print
        print('[AnomalyPoll] OK is_anomaly=${isAnomaly} type=${anomalyType ?? "—"}');
      }
      _stateController.add(AnomalyAlertState(
        anomalyType: anomalyType,
        hasReceivedMessage: true,
      ));
    } catch (e) {
      if (kDebugMode) {
        // ignore: avoid_print
        print('[AnomalyPoll] ERROR $e');
      }
      _stateController.add(AnomalyAlertState(
        error: e,
        hasReceivedMessage: false,
      ));
    }
  }

  static bool _parseIsAnomaly(dynamic v) {
    if (v == null) return false;
    if (v is bool) return v;
    if (v is int) return v != 0;
    if (v is String) return v.toLowerCase() == 'true' || v == '1';
    return false;
  }

  static String? _parseAnomalyType(dynamic v) {
    if (v == null) return null;
    final s = (v is String) ? v : v.toString();
    final t = s.trim();
    return t.isEmpty ? null : t;
  }
}
