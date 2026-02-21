import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../models/biometric_data.dart';
import '../models/incident_report.dart';
import '../services/report_service.dart';

final _reportServiceProvider = Provider((_) => ReportService());

final reportProvider =
    FutureProvider.family<IncidentReport, AnomalyEvent>((ref, anomaly) async {
  final service = ref.read(_reportServiceProvider);

  // TODO: pass real sensor snapshot from SensorService instead of mock data
  final mockSensor = BiometricData(
    heartRate: null,
    spo2: null,
    stepCount: null,
    skinTemperature: null,
    timestamp: DateTime.now().millisecondsSinceEpoch,
  );

  return service.generateReport(
    anomalyEvent: anomaly,
    sensorSnapshot: mockSensor,
  );
});

class ReportScreen extends ConsumerWidget {
  const ReportScreen({super.key, required this.anomalyEvent});

  final AnomalyEvent anomalyEvent;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final reportAsync = ref.watch(reportProvider(anomalyEvent));

    return Scaffold(
      appBar: AppBar(title: const Text('Incident Report')),
      body: reportAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, _) => Center(child: Text('Error: $err')),
        data: (report) => _ReportBody(report: report),
      ),
    );
  }
}

class _ReportBody extends StatelessWidget {
  const _ReportBody({required this.report});

  final IncidentReport report;

  Color _severityColor() {
    switch (report.severity) {
      case 'CRITICAL':
        return Colors.red;
      case 'HIGH':
        return Colors.orange;
      case 'MODERATE':
        return Colors.amber;
      default:
        return Colors.green;
    }
  }

  @override
  Widget build(BuildContext context) {
    final ts = DateFormat('MMM d, y · HH:mm:ss')
        .format(DateTime.fromMillisecondsSinceEpoch(report.generatedAt));

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Severity chip
        Row(
          children: [
            Chip(
              backgroundColor: _severityColor(),
              label: Text(
                report.severity,
                style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(width: 12),
            Text(ts, style: Theme.of(context).textTheme.bodySmall),
          ],
        ),
        const SizedBox(height: 16),

        _Section(title: 'Summary', body: report.summary),
        _Section(title: 'Vitals Assessment', body: report.vitalsAssessment),
        _Section(title: 'Visual Assessment', body: report.cvAssessment),
        _Section(
          title: 'Recommended Action',
          body: report.recommendedAction,
          highlight: true,
        ),
      ],
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.body,
    this.highlight = false,
  });

  final String title;
  final String body;
  final bool highlight;

  @override
  Widget build(BuildContext context) {
    return Card(
      color: highlight ? Colors.indigo.shade50 : null,
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: Theme.of(context)
                    .textTheme
                    .titleSmall
                    ?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(body, style: Theme.of(context).textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }
}
