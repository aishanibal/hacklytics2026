import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/incident_report.dart';
import 'report_screen.dart';

// TODO: wire up CvService WebSocket stream and camera plugin
// TODO: replace placeholder anomaly stream with real CvService.anomalyStream

class CameraScreen extends ConsumerStatefulWidget {
  const CameraScreen({super.key});

  @override
  ConsumerState<CameraScreen> createState() => _CameraScreenState();
}

class _CameraScreenState extends ConsumerState<CameraScreen> {
  bool _anomalyDetected = false;
  AnomalyEvent? _latestAnomaly;

  // TODO: initialize camera controller and CvService here

  @override
  void dispose() {
    // TODO: disconnect CvService, dispose camera controller
    super.dispose();
  }

  // ignore: unused_element — will be called once CvService stream is wired up
  void _onAnomalyDetected(AnomalyEvent event) {
    setState(() {
      _anomalyDetected = true;
      _latestAnomaly = event;
    });

    // Auto-navigate to report screen on anomaly
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReportScreen(anomalyEvent: event),
      ),
    ).then((_) => setState(() => _anomalyDetected = false));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Camera Feed')),
      body: Stack(
        children: [
          // TODO: replace with CameraPreview(controller)
          Container(
            color: Colors.black,
            child: const Center(
              child: Text(
                'Camera preview\n(connect camera plugin)',
                style: TextStyle(color: Colors.white54),
                textAlign: TextAlign.center,
              ),
            ),
          ),

          // Anomaly alert banner
          if (_anomalyDetected && _latestAnomaly != null)
            Positioned(
              top: 0,
              left: 0,
              right: 0,
              child: _AnomalyBanner(anomaly: _latestAnomaly!),
            ),

          // Detection overlay placeholder
          // TODO: draw bounding boxes and track IDs from CV result stream
        ],
      ),
    );
  }
}

class _AnomalyBanner extends StatelessWidget {
  const _AnomalyBanner({required this.anomaly});

  final AnomalyEvent anomaly;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: Colors.red.shade700,
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Colors.white),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'Anomaly detected: ${anomaly.type} '
              '(${(anomaly.confidence * 100).toStringAsFixed(0)}%)',
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }
}
