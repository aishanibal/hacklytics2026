/// Alert JSON from backend (Gemini + sensor/pose data).
/// Poll GET /ai/alert/latest; when [highAlert] is true, show an on-phone alert.
class AlertPayload {
  final bool highAlert;
  final String alertLevel;
  final String personId;
  final List<String> symptoms;
  final String summary;
  final double? updatedAt;

  const AlertPayload({
    required this.highAlert,
    required this.alertLevel,
    required this.personId,
    required this.symptoms,
    required this.summary,
    this.updatedAt,
  });

  factory AlertPayload.fromMap(Map<String, dynamic> map) {
    final symptoms = map['symptoms'];
    return AlertPayload(
      highAlert: map['high_alert'] as bool? ?? false,
      alertLevel: map['alert_level'] as String? ?? 'NORMAL',
      personId: map['person_id'] as String? ?? 'unknown',
      symptoms: symptoms is List
          ? (symptoms).map((e) => e.toString()).toList()
          : const [],
      summary: map['summary'] as String? ?? '',
      updatedAt: (map['updated_at'] as num?)?.toDouble(),
    );
  }
}
