import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../providers/emergency_provider.dart';
import '../models/incident_report.dart';
import 'alert_detail_screen.dart';

class ResponderDashboardScreen extends ConsumerWidget {
  const ResponderDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final alerts = ref.watch(emergencyProvider);
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Emergency Alerts'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refresh',
            onPressed: () {},
          ),
        ],
      ),
      body: alerts.isEmpty
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.check_circle_outline,
                      size: 72,
                      color: Colors.green.withOpacity(0.4)),
                  const SizedBox(height: 16),
                  Text('No active emergencies',
                      style: theme.textTheme.titleMedium?.copyWith(
                          color:
                              theme.colorScheme.onSurface.withOpacity(0.5))),
                  const SizedBox(height: 6),
                  Text('All monitored users are safe',
                      style: theme.textTheme.bodyMedium?.copyWith(
                          color:
                              theme.colorScheme.onSurface.withOpacity(0.35))),
                ],
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              itemCount: alerts.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (_, i) => _AlertCard(alert: alerts[i]),
            ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _simulateAlert(ref),
        icon: const Icon(Icons.add_alert_outlined),
        label: const Text('Simulate'),
      ),
    );
  }

  void _simulateAlert(WidgetRef ref) {
    final now = DateTime.now();
    ref.read(emergencyProvider.notifier).addAlert(
          EmergencyAlert(
            id: 'sim-${now.millisecondsSinceEpoch}',
            userName: 'Emily Rivera',
            userEmail: 'emily.r@email.com',
            receivedAt: now,
            report: IncidentReport(
              reportId: 'RPT-SIM-${now.millisecondsSinceEpoch}',
              generatedAt: now.millisecondsSinceEpoch,
              severity: 'HIGH',
              summary:
                  'Sudden collapse detected. The individual was walking normally before abruptly falling to the ground. Immediate assessment needed.',
              vitalsAssessment:
                  'Heart rate spiked to 132 bpm before dropping to 60 bpm. SpO2 currently at 91%, below critical threshold. Skin temperature stable at 36.5°C.',
              cvAssessment:
                  'Computer vision detected rapid vertical descent of tracked subject. Body posture transitioned from upright to prone in 0.4 seconds. Minimal limb movement post-event.',
              recommendedAction:
                  'Priority response required. Vital signs indicate potential syncope or cardiac event. Dispatch EMS and approach with AED. Keep the individual in recovery position if unconscious but breathing.',
              rawAnomaly: AnomalyEvent(
                type: 'COLLAPSE',
                confidence: 0.91,
                trackId: 7,
                timestamp: now.millisecondsSinceEpoch,
                durationSeconds: 0.4,
              ),
            ),
          ),
        );
  }
}

class _AlertCard extends ConsumerWidget {
  const _AlertCard({required this.alert});
  final EmergencyAlert alert;

  Color _severityColor(String severity) {
    switch (severity) {
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

  String _timeAgo(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
    if (diff.inHours < 24) return '${diff.inHours}h ago';
    return DateFormat('MMM d').format(dt);
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final sevColor = _severityColor(alert.report.severity);

    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          ref.read(emergencyProvider.notifier).markAsRead(alert.id);
          Navigator.push(
            context,
            MaterialPageRoute(
                builder: (_) => AlertDetailScreen(alert: alert)),
          );
        },
        child: Container(
          decoration: BoxDecoration(
            border: Border(left: BorderSide(color: sevColor, width: 4)),
          ),
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (!alert.isRead)
                Padding(
                  padding: const EdgeInsets.only(top: 4, right: 8),
                  child: Container(
                    width: 10,
                    height: 10,
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primary,
                      shape: BoxShape.circle,
                    ),
                  ),
                ),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                              horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: sevColor.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(
                            alert.report.severity,
                            style: theme.textTheme.labelSmall?.copyWith(
                                color: sevColor, fontWeight: FontWeight.bold),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          alert.report.rawAnomaly.type.replaceAll('_', ' '),
                          style: theme.textTheme.labelMedium?.copyWith(
                              fontWeight: FontWeight.w600),
                        ),
                        const Spacer(),
                        Text(_timeAgo(alert.receivedAt),
                            style: theme.textTheme.labelSmall?.copyWith(
                                color: theme.colorScheme.onSurface
                                    .withOpacity(0.45))),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Text(alert.userName,
                        style: theme.textTheme.bodyMedium
                            ?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 4),
                    Text(
                      alert.report.summary,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall?.copyWith(
                          color:
                              theme.colorScheme.onSurface.withOpacity(0.6)),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 4),
              Icon(Icons.chevron_right,
                  color: theme.colorScheme.onSurface.withOpacity(0.3)),
            ],
          ),
        ),
      ),
    );
  }
}
