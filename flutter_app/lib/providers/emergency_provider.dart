import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/incident_report.dart';

class EmergencyAlert {
  final String id;
  final String userName;
  final String userEmail;
  final IncidentReport report;
  final bool isRead;
  final DateTime receivedAt;

  const EmergencyAlert({
    required this.id,
    required this.userName,
    required this.userEmail,
    required this.report,
    this.isRead = false,
    required this.receivedAt,
  });

  EmergencyAlert copyWith({bool? isRead}) => EmergencyAlert(
        id: id,
        userName: userName,
        userEmail: userEmail,
        report: report,
        isRead: isRead ?? this.isRead,
        receivedAt: receivedAt,
      );
}

class EmergencyNotifier extends StateNotifier<List<EmergencyAlert>> {
  EmergencyNotifier() : super(_buildMockAlerts());

  void markAsRead(String alertId) {
    state = [
      for (final alert in state)
        if (alert.id == alertId) alert.copyWith(isRead: true) else alert,
    ];
  }

  void addAlert(EmergencyAlert alert) {
    state = [alert, ...state];
  }

  static List<EmergencyAlert> _buildMockAlerts() {
    final now = DateTime.now();
    return [
      EmergencyAlert(
        id: 'alert-001',
        userName: 'Marcus Johnson',
        userEmail: 'marcus.j@email.com',
        receivedAt: now.subtract(const Duration(minutes: 3)),
        report: IncidentReport(
          reportId: 'RPT-001',
          generatedAt:
              now.subtract(const Duration(minutes: 3)).millisecondsSinceEpoch,
          severity: 'CRITICAL',
          summary:
              'A fall was detected with high confidence. The individual collapsed suddenly and has not moved for 15 seconds. Immediate response required.',
          vitalsAssessment:
              'Heart rate elevated at 118 bpm, indicating acute stress response. SpO2 dropped to 93%, below the normal threshold of 95%. Skin temperature normal at 36.8°C.',
          cvAssessment:
              'Visual analysis detected a rapid transition from upright to horizontal position within 0.3 seconds, consistent with an uncontrolled fall. No subsequent movement detected for 15+ seconds.',
          recommendedAction:
              'Dispatch emergency medical services immediately. The combination of fall detection, elevated heart rate, and low blood oxygen suggests a potential cardiac or neurological event. Do not move the individual until EMS arrives.',
          rawAnomaly: AnomalyEvent(
            type: 'FALL',
            confidence: 0.94,
            trackId: 1,
            timestamp: now
                .subtract(const Duration(minutes: 3))
                .millisecondsSinceEpoch,
            durationSeconds: 0.3,
          ),
        ),
      ),
      EmergencyAlert(
        id: 'alert-002',
        userName: 'Sarah Chen',
        userEmail: 'sarah.c@email.com',
        receivedAt: now.subtract(const Duration(minutes: 18)),
        isRead: true,
        report: IncidentReport(
          reportId: 'RPT-002',
          generatedAt:
              now.subtract(const Duration(minutes: 18)).millisecondsSinceEpoch,
          severity: 'MODERATE',
          summary:
              'Erratic movement pattern detected over a 45-second window. The individual may be experiencing disorientation or distress.',
          vitalsAssessment:
              'Heart rate at 95 bpm, slightly elevated but within acceptable range. SpO2 stable at 97%. Step cadence is irregular compared to baseline.',
          cvAssessment:
              'Movement tracking shows frequent, unpredictable direction changes with acceleration/deceleration patterns inconsistent with normal ambulation. No fall detected.',
          recommendedAction:
              'Perform a welfare check. The erratic movement combined with mildly elevated heart rate may indicate confusion, panic, or a mild medical episode. Approach calmly and assess responsiveness.',
          rawAnomaly: AnomalyEvent(
            type: 'ERRATIC_MOTION',
            confidence: 0.78,
            trackId: 2,
            timestamp: now
                .subtract(const Duration(minutes: 18))
                .millisecondsSinceEpoch,
            durationSeconds: 45.0,
          ),
        ),
      ),
      EmergencyAlert(
        id: 'alert-003',
        userName: 'David Park',
        userEmail: 'david.p@email.com',
        receivedAt: now.subtract(const Duration(minutes: 45)),
        isRead: true,
        report: IncidentReport(
          reportId: 'RPT-003',
          generatedAt:
              now.subtract(const Duration(minutes: 45)).millisecondsSinceEpoch,
          severity: 'HIGH',
          summary:
              'Individual has been stationary in a non-standing position for over 10 minutes with declining vitals. This may indicate a medical emergency.',
          vitalsAssessment:
              'Heart rate dropped to 52 bpm, below resting normal. SpO2 at 94%, trending downward over the last 5 minutes. Skin temperature elevated at 38.1°C, suggesting possible fever.',
          cvAssessment:
              'Person detected in a seated/slumped position against a wall. No significant limb movement detected for 12 minutes. Periodic small head movements suggest consciousness is maintained.',
          recommendedAction:
              'Urgent wellness check required. The combination of prolonged immobility, bradycardia, declining oxygen saturation, and elevated temperature suggests a developing medical condition. Have AED and first aid supplies ready.',
          rawAnomaly: AnomalyEvent(
            type: 'STATIONARY_DOWN',
            confidence: 0.87,
            trackId: 3,
            timestamp: now
                .subtract(const Duration(minutes: 45))
                .millisecondsSinceEpoch,
            durationSeconds: 720.0,
          ),
        ),
      ),
    ];
  }
}

final emergencyProvider =
    StateNotifierProvider<EmergencyNotifier, List<EmergencyAlert>>(
        (ref) => EmergencyNotifier());

final unreadCountProvider = Provider<int>((ref) {
  final alerts = ref.watch(emergencyProvider);
  return alerts.where((a) => !a.isRead).length;
});
