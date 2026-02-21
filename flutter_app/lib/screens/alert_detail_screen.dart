import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../providers/emergency_provider.dart';

class AlertDetailScreen extends StatelessWidget {
  const AlertDetailScreen({super.key, required this.alert});

  final EmergencyAlert alert;

  Color _severityColor() {
    switch (alert.report.severity) {
      case 'CRITICAL':
        return Colors.red;
      case 'HIGH':
        return Colors.orange;
      case 'MODERATE':
        return Colors.amber.shade700;
      default:
        return Colors.green;
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final report = alert.report;
    final sevColor = _severityColor();
    final ts = DateFormat('MMM d, y · HH:mm:ss')
        .format(DateTime.fromMillisecondsSinceEpoch(report.generatedAt));

    return Scaffold(
      appBar: AppBar(title: const Text('Alert Details')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // User info header
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  CircleAvatar(
                    radius: 24,
                    backgroundColor:
                        theme.colorScheme.primary.withOpacity(0.15),
                    child: Text(
                      alert.userName.isNotEmpty
                          ? alert.userName[0].toUpperCase()
                          : '?',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: theme.colorScheme.primary,
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(alert.userName,
                            style: theme.textTheme.titleMedium
                                ?.copyWith(fontWeight: FontWeight.bold)),
                        Text(alert.userEmail,
                            style: theme.textTheme.bodySmall?.copyWith(
                                color: theme.colorScheme.onSurface
                                    .withOpacity(0.6))),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Severity + timestamp
          Row(
            children: [
              Container(
                padding:
                    const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
                decoration: BoxDecoration(
                  color: sevColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  report.severity,
                  style: theme.textTheme.labelLarge
                      ?.copyWith(color: sevColor, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(width: 12),
              Flexible(
                child: Text(ts, style: theme.textTheme.bodySmall),
              ),
            ],
          ),
          const SizedBox(height: 8),

          // Anomaly type chip
          Row(
            children: [
              Icon(Icons.warning_amber_rounded,
                  size: 18, color: sevColor),
              const SizedBox(width: 6),
              Text(
                '${report.rawAnomaly.type.replaceAll('_', ' ')} — '
                '${(report.rawAnomaly.confidence * 100).toStringAsFixed(0)}% confidence',
                style: theme.textTheme.bodyMedium,
              ),
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
      ),
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
    final theme = Theme.of(context);
    return Card(
      color: highlight ? theme.colorScheme.primaryContainer : null,
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title,
                style: theme.textTheme.titleSmall
                    ?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text(body, style: theme.textTheme.bodyMedium),
          ],
        ),
      ),
    );
  }
}
