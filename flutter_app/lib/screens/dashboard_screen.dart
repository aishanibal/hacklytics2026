import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/biometric_data.dart';
import '../widgets/vital_card.dart';
import 'camera_screen.dart';

// TODO: wire this provider to SensorService.sensorStream
final biometricProvider = StreamProvider<BiometricData>((ref) async* {
  // Placeholder — replace with: ref.read(sensorServiceProvider).sensorStream
  yield BiometricData(
    heartRate: 72,
    spo2: 98.5,
    stepCount: 4200,
    skinTemperature: 36.6,
    timestamp: DateTime.now().millisecondsSinceEpoch,
  );
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final biometricAsync = ref.watch(biometricProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Health Monitor'),
        actions: [
          IconButton(
            icon: const Icon(Icons.videocam_outlined),
            tooltip: 'Open Camera',
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const CameraScreen()),
            ),
          ),
        ],
      ),
      body: biometricAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(child: Text('Sensor error: $err')),
        data: (data) => _DashboardBody(data: data),
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data});

  final BiometricData data;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Live Vitals', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.3,
            physics: const NeverScrollableScrollPhysics(),
            children: [
              VitalCard(
                label: 'Heart Rate',
                value: data.heartRate != null ? '${data.heartRate!.toStringAsFixed(0)} bpm' : '--',
                icon: Icons.favorite_outline,
                color: Colors.red,
              ),
              VitalCard(
                label: 'SpO2',
                value: data.spo2 != null ? '${data.spo2!.toStringAsFixed(1)}%' : '--',
                icon: Icons.water_drop_outlined,
                color: Colors.blue,
              ),
              VitalCard(
                label: 'Steps',
                value: data.stepCount != null ? '${data.stepCount}' : '--',
                icon: Icons.directions_walk_outlined,
                color: Colors.green,
              ),
              VitalCard(
                label: 'Skin Temp',
                value: data.skinTemperature != null
                    ? '${data.skinTemperature!.toStringAsFixed(1)}°C'
                    : '--',
                icon: Icons.thermostat_outlined,
                color: Colors.orange,
              ),
            ],
          ),
          // TODO: add fl_chart sparklines for each vital once data streams in
        ],
      ),
    );
  }
}
