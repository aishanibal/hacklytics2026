class BiometricData {
  final double? heartRate;       // bpm
  final double? hrv;             // ms (RMSSD)
  final double? spo2;            // %
  final int? stepCount;
  final double? skinTemperature; // °C
  final double? accelX;
  final double? accelY;
  final double? accelZ;
  final int timestamp;           // epoch ms

  const BiometricData({
    this.heartRate,
    this.hrv,
    this.spo2,
    this.stepCount,
    this.skinTemperature,
    this.accelX,
    this.accelY,
    this.accelZ,
    required this.timestamp,
  });

  factory BiometricData.fromMap(Map<String, dynamic> map) {
    return BiometricData(
      heartRate: (map['heartRate'] as num?)?.toDouble(),
      hrv: (map['hrv'] as num?)?.toDouble(),
      spo2: (map['spo2'] as num?)?.toDouble(),
      stepCount: map['stepCount'] as int?,
      skinTemperature: (map['skinTemperature'] as num?)?.toDouble(),
      accelX: (map['accelX'] as num?)?.toDouble(),
      accelY: (map['accelY'] as num?)?.toDouble(),
      accelZ: (map['accelZ'] as num?)?.toDouble(),
      timestamp: (map['timestamp'] as int?) ?? DateTime.now().millisecondsSinceEpoch,
    );
  }

  Map<String, dynamic> toMap() => {
        'heartRate': heartRate,
        'hrv': hrv,
        'spo2': spo2,
        'stepCount': stepCount,
        'skinTemperature': skinTemperature,
        'accelX': accelX,
        'accelY': accelY,
        'accelZ': accelZ,
        'timestamp': timestamp,
      };

  /// JSON shape the Python backend expects at /pose/health-push.
  Map<String, dynamic> toHealthPush() => {
        'heart_rate': heartRate,
        'hrv': hrv,
        'spo2': spo2,
        'accelerometer': {
          'x': accelX ?? 0,
          'y': accelY ?? 0,
          'z': accelZ ?? 0,
        },
        'timestamp': timestamp,
      };
}
