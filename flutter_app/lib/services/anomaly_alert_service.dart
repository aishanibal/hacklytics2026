import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class AnomalyAlertState {
  final bool hasReceivedMessage;
  final String? anomalyType;
  final bool isAnomaly;
  final Exception? error;

  const AnomalyAlertState({
    this.hasReceivedMessage = false,
    this.anomalyType,
    this.isAnomaly = false,
    this.error,
  });
}

/// Polls GET /pose/anomaly every 2 seconds.
/// Exposes a broadcast stream of [AnomalyAlertState].
/// Call [pausePolling] when an incident is in progress and
/// [resumePolling] to restart after resolution.
class AnomalyAlertService {
  final String backendBaseUrl;

  Timer? _pollTimer;
  final _controller = StreamController<AnomalyAlertState>.broadcast();
  bool _active = false;

  AnomalyAlertService({required this.backendBaseUrl});

  Stream<AnomalyAlertState> get stateStream => _controller.stream;

  void connect() {
    if (_active) return;
    _active = true;
    _startPolling();
  }

  void disconnect() {
    _active = false;
    _stopPolling();
  }

  void pausePolling() {
    _stopPolling();
  }

  void resumePolling() {
    _active = true;
    _startPolling();
  }

  void _startPolling() {
    _stopPolling();
    _poll();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) => _poll());
  }

  void _stopPolling() {
    _pollTimer?.cancel();
    _pollTimer = null;
  }

  Future<void> _poll() async {
    if (!_active) return;
    try {
      final uri = Uri.parse('$backendBaseUrl/pose/anomaly');
      final response = await http.get(uri).timeout(const Duration(seconds: 5));
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body) as Map<String, dynamic>;
        final isAnomaly = data['is_anomaly'] as bool? ?? false;
        final anomalyType = data['anomaly_type'] as String? ?? '';
        _controller.add(AnomalyAlertState(
          hasReceivedMessage: true,
          isAnomaly: isAnomaly,
          anomalyType: isAnomaly && anomalyType.isNotEmpty ? anomalyType : null,
        ));
      }
    } catch (e) {
      _controller.addError(e);
    }
  }

  void dispose() {
    disconnect();
    _controller.close();
  }
}
