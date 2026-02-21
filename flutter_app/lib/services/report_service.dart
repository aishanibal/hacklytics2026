import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/biometric_data.dart';
import '../models/incident_report.dart';

class ReportService {
  // TODO: update host to your FastAPI server IP/hostname
  static const String _baseUrl = 'http://192.168.1.100:8000';

  /// Request a GenAI incident report from the backend.
  Future<IncidentReport> generateReport({
    required AnomalyEvent anomalyEvent,
    required BiometricData sensorSnapshot,
    String? locationContext,
  }) async {
    final body = jsonEncode({
      'anomaly_event': {
        'type': anomalyEvent.type,
        'confidence': anomalyEvent.confidence,
        'track_id': anomalyEvent.trackId,
        'timestamp': anomalyEvent.timestamp,
        'duration_seconds': anomalyEvent.durationSeconds,
        'frame_snapshot_b64': anomalyEvent.frameSnapshotB64,
      },
      'sensor_snapshot': sensorSnapshot.toMap(),
      'location_context': locationContext,
    });

    final response = await http.post(
      Uri.parse('$_baseUrl/report/generate'),
      headers: {'Content-Type': 'application/json'},
      body: body,
    );

    if (response.statusCode == 200) {
      return IncidentReport.fromMap(
          jsonDecode(response.body) as Map<String, dynamic>);
    }

    throw Exception(
        'Failed to generate report: ${response.statusCode} ${response.body}');
  }
}
