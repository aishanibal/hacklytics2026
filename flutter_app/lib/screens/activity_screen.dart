import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

class ActivityScreen extends StatelessWidget {
  const ActivityScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final entries = _buildMockEntries();

    return Scaffold(
      appBar: AppBar(title: const Text('Activity')),
      body: entries.isEmpty
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.history,
                      size: 64,
                      color: theme.colorScheme.onSurface.withOpacity(0.25)),
                  const SizedBox(height: 12),
                  Text('No activity yet',
                      style: theme.textTheme.bodyLarge?.copyWith(
                          color:
                              theme.colorScheme.onSurface.withOpacity(0.5))),
                ],
              ),
            )
          : ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              itemCount: entries.length,
              separatorBuilder: (_, __) => const SizedBox(height: 8),
              itemBuilder: (_, i) => _ActivityTile(entry: entries[i]),
            ),
    );
  }

  List<_ActivityEntry> _buildMockEntries() {
    final now = DateTime.now();
    return [
      _ActivityEntry(
        icon: Icons.favorite,
        color: Colors.red,
        title: 'Heart Rate: 72 bpm',
        subtitle: 'SpO2: 98.5% — Normal range',
        time: now.subtract(const Duration(minutes: 5)),
      ),
      _ActivityEntry(
        icon: Icons.directions_walk,
        color: Colors.green,
        title: '5,000 step milestone',
        subtitle: 'Keep it up!',
        time: now.subtract(const Duration(minutes: 30)),
      ),
      _ActivityEntry(
        icon: Icons.favorite,
        color: Colors.red,
        title: 'Heart Rate: 78 bpm',
        subtitle: 'SpO2: 97.8% — Normal range',
        time: now.subtract(const Duration(hours: 1)),
      ),
      _ActivityEntry(
        icon: Icons.thermostat,
        color: Colors.orange,
        title: 'Skin Temp: 36.7°C',
        subtitle: 'Normal range',
        time: now.subtract(const Duration(hours: 1, minutes: 30)),
      ),
      _ActivityEntry(
        icon: Icons.warning_amber_rounded,
        color: Colors.amber,
        title: 'Slight HR elevation detected',
        subtitle: 'Peaked at 95 bpm during activity',
        time: now.subtract(const Duration(hours: 2)),
      ),
      _ActivityEntry(
        icon: Icons.favorite,
        color: Colors.red,
        title: 'Heart Rate: 68 bpm',
        subtitle: 'SpO2: 99.1% — Normal range',
        time: now.subtract(const Duration(hours: 3)),
      ),
      _ActivityEntry(
        icon: Icons.check_circle_outline,
        color: Colors.green,
        title: 'Monitoring started',
        subtitle: 'Watch connected successfully',
        time: now.subtract(const Duration(hours: 4)),
      ),
    ];
  }
}

class _ActivityEntry {
  final IconData icon;
  final Color color;
  final String title;
  final String subtitle;
  final DateTime time;

  const _ActivityEntry({
    required this.icon,
    required this.color,
    required this.title,
    required this.subtitle,
    required this.time,
  });
}

class _ActivityTile extends StatelessWidget {
  const _ActivityTile({required this.entry});
  final _ActivityEntry entry;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final timeFmt = DateFormat('h:mm a').format(entry.time);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: entry.color.withOpacity(0.12),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(entry.icon, color: entry.color, size: 22),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(entry.title,
                      style: theme.textTheme.bodyMedium
                          ?.copyWith(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text(entry.subtitle,
                      style: theme.textTheme.bodySmall?.copyWith(
                          color:
                              theme.colorScheme.onSurface.withOpacity(0.6))),
                ],
              ),
            ),
            Text(timeFmt,
                style: theme.textTheme.labelSmall?.copyWith(
                    color: theme.colorScheme.onSurface.withOpacity(0.45))),
          ],
        ),
      ),
    );
  }
}
