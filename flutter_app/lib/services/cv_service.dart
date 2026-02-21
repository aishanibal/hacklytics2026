import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/biometric_data.dart';
import '../models/incident_report.dart';

class CvService {
  // TODO: update host to your FastAPI server IP/hostname
  static const String _wsBaseUrl = 'ws://192.168.1.100:8000';

  WebSocketChannel? _channel;
  Stream<Map<String, dynamic>>? _resultStream;

  /// Connect to the CV WebSocket stream.
  void connect() {
    _channel = WebSocketChannel.connect(Uri.parse('$_wsBaseUrl/ws/stream'));

    _resultStream = _channel!.stream
        .cast<String>()
        .map((raw) => jsonDecode(raw) as Map<String, dynamic>);
  }

  /// Disconnect from the WebSocket.
  void disconnect() {
    _channel?.sink.close();
    _channel = null;
    _resultStream = null;
  }

  /// Send a base64-encoded JPEG frame + current sensor data to the backend.
  void sendFrame({
    required String frameB64,
    required BiometricData sensorData,
  }) {
    if (_channel == null) return;
    _channel!.sink.add(jsonEncode({
      'frame': frameB64,
      'sensor_data': sensorData.toMap(),
    }));
  }

  /// Stream of parsed CV results from the backend.
  Stream<Map<String, dynamic>> get resultStream {
    assert(_resultStream != null, 'Call connect() before listening.');
    return _resultStream!;
  }

  /// Convenience: filter result stream to frames that contain anomalies.
  Stream<List<AnomalyEvent>> get anomalyStream {
    return resultStream
        .where((result) =>
            result['anomalies'] != null &&
            (result['anomalies'] as List).isNotEmpty)
        .map((result) => (result['anomalies'] as List)
            .map((a) => AnomalyEvent.fromMap(Map<String, dynamic>.from(a as Map)))
            .toList());
  }
}
