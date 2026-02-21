class BiometricData {
  final double? heartRate;       // bpm
  final double? spo2;            // %
  final int? stepCount;
  final double? skinTemperature; // °C
  final int timestamp;           // epoch ms

  const BiometricData({
    this.heartRate,
    this.spo2,
    this.stepCount,
    this.skinTemperature,
    required this.timestamp,
  });

  factory BiometricData.fromMap(Map<String, dynamic> map) {
    return BiometricData(
      heartRate: (map['heartRate'] as num?)?.toDouble(),
      spo2: (map['spo2'] as num?)?.toDouble(),
      stepCount: map['stepCount'] as int?,
      skinTemperature: (map['skinTemperature'] as num?)?.toDouble(),
      timestamp: (map['timestamp'] as int?) ?? DateTime.now().millisecondsSinceEpoch,
    );
  }

  Map<String, dynamic> toMap() => {
        'heartRate': heartRate,
        'spo2': spo2,
        'stepCount': stepCount,
        'skinTemperature': skinTemperature,
        'timestamp': timestamp,
      };
}
