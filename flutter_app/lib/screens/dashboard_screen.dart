import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/biometric_data.dart';
import '../providers/auth_provider.dart';
import '../widgets/vital_card.dart';
import 'camera_screen.dart';

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
    final user = ref.watch(authProvider);
    final biometricAsync = ref.watch(biometricProvider);
    final theme = Theme.of(context);
    final firstName = user?.name.split(' ').first ?? 'there';

    return Scaffold(
      appBar: AppBar(
        title: Text('Hi, $firstName'),
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
    final theme = Theme.of(context);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Status banner
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.green.withOpacity(0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.green.withOpacity(0.25)),
          ),
          child: Row(
            children: [
              Container(
                width: 10,
                height: 10,
                decoration: const BoxDecoration(
                  color: Colors.green,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 10),
              Text('All vitals normal',
                  style: theme.textTheme.bodyMedium?.copyWith(
                      color: Colors.green, fontWeight: FontWeight.w600)),
              const Spacer(),
              Text('Monitoring active',
                  style: theme.textTheme.labelSmall
                      ?.copyWith(color: Colors.green.withOpacity(0.7))),
            ],
          ),
        ),
        const SizedBox(height: 20),

        Text('Live Vitals',
            style: theme.textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 12),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.25,
          physics: const NeverScrollableScrollPhysics(),
          children: [
            VitalCard(
              label: 'Heart Rate',
              value: data.heartRate != null
                  ? '${data.heartRate!.toStringAsFixed(0)} bpm'
                  : '--',
              icon: Icons.favorite,
              color: Colors.red,
            ),
            VitalCard(
              label: 'SpO2',
              value: data.spo2 != null
                  ? '${data.spo2!.toStringAsFixed(1)}%'
                  : '--',
              icon: Icons.water_drop,
              color: Colors.blue,
            ),
            VitalCard(
              label: 'Steps',
              value: data.stepCount != null ? '${data.stepCount}' : '--',
              icon: Icons.directions_walk,
              color: Colors.green,
            ),
            VitalCard(
              label: 'Skin Temp',
              value: data.skinTemperature != null
                  ? '${data.skinTemperature!.toStringAsFixed(1)}°C'
                  : '--',
              icon: Icons.thermostat,
              color: Colors.orange,
            ),
          ],
        ),
      ],
    );
  }
}
