import 'dart:async';

import 'package:flutter/material.dart';

import '../services/anomaly_alert_service.dart';
import '../services/watch_communication_service.dart';

const _backendUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'http://10.136.4.45:8000',
);

enum IncidentState {
  idle,
  waitingForWatch,
  incidentActive,
  incidentAcknowledged,
}

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen>
    with TickerProviderStateMixin {
  final _alertService = AnomalyAlertService(backendBaseUrl: _backendUrl);
  final _watchService = WatchCommunicationService();

  IncidentState _state = IncidentState.idle;
  bool _isConnected = false;
  bool _hasError = false;
  String? _anomalyType;

  StreamSubscription<AnomalyAlertState>? _alertSub;
  StreamSubscription<String>? _watchSub;

  int _tapCount = 0;
  DateTime _lastTapTime = DateTime(2000);

  late AnimationController _pulseController;
  late Animation<double> _pulseAnimation;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    )..repeat(reverse: true);
    _pulseAnimation = Tween<double>(begin: 0.4, end: 1.0).animate(
      CurvedAnimation(parent: _pulseController, curve: Curves.easeInOut),
    );
    _startListening();
  }

  void _startListening() {
    _alertService.connect();
    _alertSub = _alertService.stateStream.listen(
      _onAnomalyState,
      onError: (_) {
        if (mounted) setState(() => _hasError = true);
      },
    );
    _watchSub = _watchService.watchMessages.listen(_onWatchMessage);
  }

  // ── API polling callback ──

  void _onAnomalyState(AnomalyAlertState alertState) {
    if (!mounted || _state != IncidentState.idle) return;

    setState(() {
      _isConnected = alertState.hasReceivedMessage;
      _hasError = false;
    });

    if (alertState.isAnomaly && alertState.anomalyType != null) {
      _onAnomalyDetected(alertState.anomalyType!);
    }
  }

  void _onAnomalyDetected(String anomalyType) {
    setState(() {
      _state = IncidentState.waitingForWatch;
      _anomalyType = anomalyType;
    });
    _alertService.pausePolling();
    _watchService.sendToWatch('INCIDENT_DETECTED');
    _watchService.startVibration(strong: true);
  }

  // ── Watch message callback ──

  void _onWatchMessage(String message) {
    if (!mounted) return;

    if (message == 'INCIDENT_CONFIRMED' &&
        _state == IncidentState.waitingForWatch) {
      setState(() {
        _state = IncidentState.incidentActive;
        _tapCount = 0;
      });
      _watchService.startVibration(strong: true);
      _watchService.startAlarm();
    } else if (message == 'IDLE' &&
        _state == IncidentState.waitingForWatch) {
      _watchService.stopVibration();
      setState(() {
        _state = IncidentState.idle;
        _anomalyType = null;
      });
      _alertService.resumePolling();
    }
  }

  // ── Tap handling ──

  void _onScreenTap() {
    if (_state != IncidentState.incidentActive &&
        _state != IncidentState.incidentAcknowledged) return;

    final now = DateTime.now();
    if (now.difference(_lastTapTime).inMilliseconds > 600) {
      _tapCount = 0;
    }
    _tapCount++;
    _lastTapTime = now;

    if (_state == IncidentState.incidentActive && _tapCount >= 2) {
      _tapCount = 0;
      setState(() => _state = IncidentState.incidentAcknowledged);
      _watchService.stopAlarm();
      _watchService.stopVibration();
      _watchService.startVibration(strong: false);
    } else if (_state == IncidentState.incidentAcknowledged && _tapCount >= 3) {
      _tapCount = 0;
      _resolveIncident();
    }
  }

  void _resolveIncident() {
    _watchService.stopAlarm();
    _watchService.stopVibration();
    setState(() {
      _state = IncidentState.idle;
      _anomalyType = null;
    });
    _alertService.resumePolling();
  }

  /// User taps "Resolved" while waiting for watch — go back to idle without watch response.
  void _resolveFromWaiting() {
    _watchService.stopVibration();
    setState(() {
      _state = IncidentState.idle;
      _anomalyType = null;
    });
    _alertService.resumePolling();
  }

  // ── Lifecycle ──

  @override
  void dispose() {
    _alertSub?.cancel();
    _watchSub?.cancel();
    _alertService.dispose();
    _watchService.stopAlarm();
    _watchService.stopVibration();
    _pulseController.dispose();
    super.dispose();
  }

  // ── Build ──

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _onScreenTap,
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 300),
          child: _buildScreen(),
        ),
      ),
    );
  }

  Widget _buildScreen() {
    switch (_state) {
      case IncidentState.idle:
        if (_hasError) {
          return const _StatusScreen(
            key: ValueKey('error'),
            icon: Icons.cloud_off_rounded,
            message: 'Detection server unavailable',
            detail: 'Check that the backend is running and reachable.',
            backgroundColor: Color(0xFF000000),
          );
        }
        if (!_isConnected) {
          return _StatusScreen(
            key: const ValueKey('connecting'),
            icon: Icons.hourglass_empty_rounded,
            message: 'Connecting…',
            detail: 'Reaching anomaly detection server.',
            backgroundColor: Colors.grey.shade800,
          );
        }
        return const _StatusScreen(
          key: ValueKey('monitoring'),
          icon: Icons.check_circle_outline_rounded,
          message: 'Monitoring',
          detail: 'No anomaly detected.',
          backgroundColor: Color(0xFF8DDBE0),
        );

      case IncidentState.waitingForWatch:
        return _WaitingForWatchScreen(
          key: const ValueKey('waiting'),
          anomalyType: _anomalyType,
          onResolved: _resolveFromWaiting,
        );

      case IncidentState.incidentActive:
        return _AlertScreen(
          key: const ValueKey('alert_active'),
          animation: _pulseAnimation,
          anomalyType: _anomalyType ?? 'UNKNOWN',
          instruction: 'TAP TWICE TO ACKNOWLEDGE',
        );

      case IncidentState.incidentAcknowledged:
        return _AcknowledgedScreen(
          key: const ValueKey('acknowledged'),
          anomalyType: _anomalyType ?? 'UNKNOWN',
        );
    }
  }
}

// ─────────────────────────────────────────────────────────────
//  Idle / waiting / error full-page status
// ─────────────────────────────────────────────────────────────

class _StatusScreen extends StatelessWidget {
  const _StatusScreen({
    super.key,
    required this.icon,
    required this.message,
    required this.detail,
    required this.backgroundColor,
  });

  final IconData icon;
  final String message;
  final String detail;
  final Color backgroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      height: double.infinity,
      color: backgroundColor,
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
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  detail,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Color(0xDDFFFFFF),
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

// ─────────────────────────────────────────────────────────────
//  Waiting for watch — with "Resolved" button to return to idle
// ─────────────────────────────────────────────────────────────

class _WaitingForWatchScreen extends StatelessWidget {
  const _WaitingForWatchScreen({
    super.key,
    required this.anomalyType,
    required this.onResolved,
  });

  final String? anomalyType;
  final VoidCallback onResolved;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      height: double.infinity,
      color: Colors.deepOrange.shade800,
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.watch_rounded, size: 80, color: Colors.white),
              const SizedBox(height: 24),
              const Text(
                'Incident Detected',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                'Waiting for watch response…\n${anomalyType ?? ''}',
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xDDFFFFFF),
                  fontSize: 16,
                ),
              ),
              const SizedBox(height: 40),
              FilledButton.icon(
                onPressed: onResolved,
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('Resolved'),
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: Colors.deepOrange.shade800,
                  padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
                  textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  Full-screen flashing alert  (INCIDENT_CONFIRMED)
// ─────────────────────────────────────────────────────────────

class _AlertScreen extends StatelessWidget {
  const _AlertScreen({
    super.key,
    required this.animation,
    required this.anomalyType,
    required this.instruction,
  });

  final Animation<double> animation;
  final String anomalyType;
  final String instruction;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: animation,
      builder: (context, _) {
        final bg = Color.lerp(
          const Color(0xFF8B0000),
          const Color(0xFFFF0000),
          animation.value,
        )!;
        return Container(
          width: double.infinity,
          height: double.infinity,
          color: bg,
          child: SafeArea(
            child: Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 32),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(
                      Icons.warning_amber_rounded,
                      size: 100,
                      color: Colors.white.withOpacity(animation.value),
                    ),
                    const SizedBox(height: 24),
                    const Text(
                      'INCIDENT CONFIRMED',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 28,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      anomalyType,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Color(0xDDFFFFFF),
                        fontSize: 18,
                      ),
                    ),
                    const SizedBox(height: 48),
                    Text(
                      instruction,
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                        color: Color(0xAAFFFFFF),
                        fontSize: 14,
                        letterSpacing: 2,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }
}

// ─────────────────────────────────────────────────────────────
//  Acknowledged screen  (sound off, slow vibration continues)
// ─────────────────────────────────────────────────────────────

class _AcknowledgedScreen extends StatelessWidget {
  const _AcknowledgedScreen({
    super.key,
    required this.anomalyType,
  });

  final String anomalyType;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      height: double.infinity,
      color: const Color(0xFFBF360C),
      child: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(
                  Icons.notifications_active_rounded,
                  size: 80,
                  color: Colors.white,
                ),
                const SizedBox(height: 24),
                const Text(
                  'ACKNOWLEDGED',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 1,
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  anomalyType,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: Color(0xDDFFFFFF),
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 48),
                const Text(
                  'TAP 3 TIMES TO RESOLVE',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    color: Color(0xAAFFFFFF),
                    fontSize: 14,
                    letterSpacing: 2,
                    fontWeight: FontWeight.w600,
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
