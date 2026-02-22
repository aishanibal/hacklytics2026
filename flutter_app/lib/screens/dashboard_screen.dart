import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/anomaly_alert_service.dart';

// Backend runs on your computer (not the Pi). Pi = 10.136.28.70, your computer = 10.136.4.45
const _backendUrl = String.fromEnvironment('BACKEND_URL', defaultValue: 'http://10.136.4.45:8000');

final _anomalyAlerts = AnomalyAlertService(backendBaseUrl: _backendUrl);

final anomalyAlertStateProvider = StreamProvider<AnomalyAlertState>((ref) {
  _anomalyAlerts.connect();
  ref.onDispose(() => _anomalyAlerts.disconnect());
  return _anomalyAlerts.stateStream;
});

class DashboardScreen extends ConsumerWidget {
  const DashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final anomalyAsync = ref.watch(anomalyAlertStateProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Anomaly Monitor'),
      ),
      body: anomalyAsync.when(
        data: (state) => _AlertPage(state: state),
        loading: () => const _AlertPage(
          state: AnomalyAlertState(hasReceivedMessage: false),
          isLoading: true,
        ),
        error: (_, __) => _AlertPage(
          state: AnomalyAlertState(error: Exception('Connection failed'), hasReceivedMessage: false),
          isError: true,
        ),
      ),
    );
  }
}

class _AlertPage extends StatelessWidget {
  const _AlertPage({
    required this.state,
    this.isLoading = false,
    this.isError = false,
  });

  final AnomalyAlertState state;
  final bool isLoading;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    if (isError || state.error != null) {
      return _FullPageStatus(
        icon: Icons.cloud_off_rounded,
        message: 'Detection server unavailable',
        detail: 'Check that the backend is running and reachable.',
        color: Colors.orange.shade800,
      );
    }

    if (isLoading || !state.hasReceivedMessage) {
      return _FullPageStatus(
        icon: Icons.hourglass_empty_rounded,
        message: 'Connecting to detection server…',
        detail: 'Polling for anomalies.',
        color: Colors.grey.shade700,
      );
    }

    if (state.anomalyType != null && state.anomalyType!.isNotEmpty) {
      return _FullPageStatus(
        icon: Icons.warning_amber_rounded,
        message: 'Anomaly detected',
        detail: state.anomalyType!,
        color: Colors.red.shade700,
      );
    }

    return _FullPageStatus(
      icon: Icons.check_circle_outline_rounded,
      message: 'Monitoring for anomalies',
      detail: 'No anomaly right now.',
      color: Colors.green.shade800,
    );
  }
}

class _FullPageStatus extends StatelessWidget {
  const _FullPageStatus({
    required this.icon,
    required this.message,
    required this.detail,
    required this.color,
  });

  final IconData icon;
  final String message;
  final String detail;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      color: color,
      child: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(icon, size: 80, color: Colors.white),
                const SizedBox(height: 24),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  detail,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white.withOpacity(0.9),
                    fontSize: 16,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
