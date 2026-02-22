import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/anomaly_session.dart';

/// Fetches the last anomaly session (features over time) from the CV backend
/// after the watch is deactivated. GET /pose/anomaly-session returns 200 + JSON
/// or 204 when no session is available.
class AnomalySessionService {
  final String _backendBaseUrl;

  AnomalySessionService({required String backendBaseUrl})
      : _backendBaseUrl = backendBaseUrl;

  /// Returns the last anomaly session, or null if 204 / error.
  Future<AnomalySession?> fetchLastSession() async {
    final uri = Uri.parse('$_backendBaseUrl/pose/anomaly-session');
    try {
      final response = await http.get(uri).timeout(
        const Duration(seconds: 10),
      );
      if (response.statusCode == 204 || response.body.isEmpty) {
        return null;
      }
      if (response.statusCode != 200) {
        return null;
      }
      final map = Map<String, dynamic>.from(
        jsonDecode(response.body) as Map,
      );
      return AnomalySession.fromMap(map);
    } catch (_) {
      return null;
    }
  }
}
