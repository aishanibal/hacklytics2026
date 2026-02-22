import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/alert_payload.dart';
import '../models/biometric_data.dart';
import '../services/alert_service.dart';
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

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key});

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  Timer? _alertPollTimer;
  final AlertService _alertService = AlertService();
  AlertPayload? _lastAlert;
  bool _alertDialogShown = false;

  @override
  void initState() {
    super.initState();
    _startAlertPolling();
  }

  @override
  void dispose() {
    _alertPollTimer?.cancel();
    super.dispose();
  }

  void _startAlertPolling() {
    _alertPollTimer = Timer.periodic(const Duration(seconds: 5), (_) async {
      if (!mounted) return;
      try {
        final alert = await _alertService.fetchLatestAlert();
        if (!mounted) return;
        setState(() => _lastAlert = alert);
        if (alert.highAlert && !_alertDialogShown && mounted) {
          _alertDialogShown = true;
          _showAlertDialog(alert);
        }
      } catch (_) {
        // Ignore network errors; next poll will retry
      }
    });
  }

  void _showAlertDialog(AlertPayload alert) {
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: Row(
          children: [
            Icon(Icons.warning_amber_rounded, color: Theme.of(context).colorScheme.error, size: 28),
            const SizedBox(width: 8),
            const Text('High Alert'),
          ],
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(alert.summary.isNotEmpty ? alert.summary : 'Sensor/pose data suggests attention needed.'),
              if (alert.symptoms.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text('Signs: ${alert.symptoms.join(", ")}', style: Theme.of(context).textTheme.bodySmall),
              ],
              if (alert.personId != 'unknown')
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text('Person: ${alert.personId}', style: Theme.of(context).textTheme.bodySmall),
                ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              _alertDialogShown = false;
              Navigator.of(ctx).pop();
            },
            child: const Text('Dismiss'),
          ),
        ],
      ),
    ).then((_) => _alertDialogShown = false);
  }

  @override
  Widget build(BuildContext context) {
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
        data: (data) => _DashboardBody(data: data, lastAlert: _lastAlert),
      ),
    );
  }
}

class _DashboardBody extends StatelessWidget {
  const _DashboardBody({required this.data, this.lastAlert});

  final BiometricData data;
  final AlertPayload? lastAlert;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (lastAlert != null && lastAlert!.highAlert)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.errorContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.warning_amber_rounded, color: Theme.of(context).colorScheme.onErrorContainer),
                  const SizedBox(width: 8),
                  Expanded(child: Text(lastAlert!.summary.isNotEmpty ? lastAlert!.summary : 'High alert — check details.', style: Theme.of(context).textTheme.bodyMedium)),
                ],
              ),
            ),
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
