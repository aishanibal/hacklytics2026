import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/alert_payload.dart';

/// Fetches the latest alert JSON from the backend so the app can show an alert on the phone.
class AlertService {
  // Use same base URL as report_service — update to your FastAPI server
  static const String _baseUrl = 'http://192.168.1.100:8000';

  /// GET /ai/alert/latest — returns the latest Gemini alert (high_alert, symptoms, etc.).
  /// When [AlertPayload.highAlert] is true, show a dialog or notification on the phone.
  Future<AlertPayload> fetchLatestAlert() async {
    final response = await http.get(
      Uri.parse('$_baseUrl/ai/alert/latest'),
    );

    if (response.statusCode == 200) {
      final map = jsonDecode(response.body) as Map<String, dynamic>;
      return AlertPayload.fromMap(map);
    }

    throw Exception(
        'Failed to fetch alert: ${response.statusCode} ${response.body}');
  }
}
