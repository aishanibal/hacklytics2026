class AnomalyEvent {
  final String type;              // FALL | COLLAPSE | ERRATIC_MOTION | STATIONARY_DOWN
  final double confidence;
  final int trackId;
  final int timestamp;            // epoch ms
  final double? durationSeconds;
  final String? frameSnapshotB64; // base64 JPEG thumbnail

  const AnomalyEvent({
    required this.type,
    required this.confidence,
    required this.trackId,
    required this.timestamp,
    this.durationSeconds,
    this.frameSnapshotB64,
  });

  factory AnomalyEvent.fromMap(Map<String, dynamic> map) {
    return AnomalyEvent(
      type: map['type'] as String,
      confidence: (map['confidence'] as num).toDouble(),
      trackId: map['track_id'] as int,
      timestamp: map['timestamp'] as int,
      durationSeconds: (map['duration_seconds'] as num?)?.toDouble(),
      frameSnapshotB64: map['frame_snapshot_b64'] as String?,
    );
  }
}

class IncidentReport {
  final String reportId;
  final int generatedAt;          // epoch ms
  final String severity;          // LOW | MODERATE | HIGH | CRITICAL
  final String summary;
  final String vitalsAssessment;
  final String cvAssessment;
  final String recommendedAction;
  final AnomalyEvent rawAnomaly;

  const IncidentReport({
    required this.reportId,
    required this.generatedAt,
    required this.severity,
    required this.summary,
    required this.vitalsAssessment,
    required this.cvAssessment,
    required this.recommendedAction,
    required this.rawAnomaly,
  });

  factory IncidentReport.fromMap(Map<String, dynamic> map) {
    return IncidentReport(
      reportId: map['report_id'] as String,
      generatedAt: map['generated_at'] as int,
      severity: map['severity'] as String,
      summary: map['summary'] as String,
      vitalsAssessment: map['vitals_assessment'] as String,
      cvAssessment: map['cv_assessment'] as String,
      recommendedAction: map['recommended_action'] as String,
      rawAnomaly: AnomalyEvent.fromMap(map['raw_anomaly'] as Map<String, dynamic>),
    );
  }
}
