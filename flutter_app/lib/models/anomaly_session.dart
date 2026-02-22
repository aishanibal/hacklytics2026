/// One sample of pose/engineered features at a point in time during an anomaly.
class AnomalySample {
  final double t;
  final double score;
  final double threshold;
  final double? noseY;
  final double? hipY;
  final double? torsoLen;
  final double? fullHeight;
  final double? shoulderAngle;
  final double? kneeAngle;
  final double? verticalRatio;

  const AnomalySample({
    required this.t,
    required this.score,
    required this.threshold,
    this.noseY,
    this.hipY,
    this.torsoLen,
    this.fullHeight,
    this.shoulderAngle,
    this.kneeAngle,
    this.verticalRatio,
  });

  factory AnomalySample.fromMap(Map<String, dynamic> map) {
    num? numVal(String key) => map[key] as num?;
    return AnomalySample(
      t: (numVal('t') ?? 0).toDouble(),
      score: (numVal('score') ?? 0).toDouble(),
      threshold: (numVal('threshold') ?? 0).toDouble(),
      noseY: numVal('nose_y')?.toDouble(),
      hipY: numVal('hip_y')?.toDouble(),
      torsoLen: numVal('torso_len')?.toDouble(),
      fullHeight: numVal('full_height')?.toDouble(),
      shoulderAngle: numVal('shoulder_angle')?.toDouble(),
      kneeAngle: numVal('knee_angle')?.toDouble(),
      verticalRatio: numVal('vertical_ratio')?.toDouble(),
    );
  }
}

/// Last anomaly session: type and time-series of features (for graphing after deactivate).
class AnomalySession {
  final String anomalyType;
  final List<AnomalySample> samples;

  const AnomalySession({
    required this.anomalyType,
    required this.samples,
  });

  factory AnomalySession.fromMap(Map<String, dynamic> map) {
    final list = map['samples'] as List<dynamic>? ?? [];
    return AnomalySession(
      anomalyType: map['anomaly_type'] as String? ?? 'UNKNOWN',
      samples: list
          .map((e) => AnomalySample.fromMap(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }
}
