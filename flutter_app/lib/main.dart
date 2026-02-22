import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:wear/wear.dart';

// Global reactive variable
ValueNotifier<String> anomalySignal = ValueNotifier<String>("IDLE");
double anomalyTimestamp = 0.0;

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  startPolling();
  startWatchListener();
  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        body: Center(
          // This will rebuild automatically when anomalySignal changes
          child: ValueListenableBuilder<String>(
            valueListenable: anomalySignal,
            builder: (context, value, child) {
              return Container(
                color: getBackgroundColor(value),
                child: Center(
                  child: Text(
                    getDisplayText(value),
                    style: TextStyle(
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  // Map state to background color
  Color getBackgroundColor(String state) {
    switch (state) {
      case "IDLE":
        return Colors.green;
      case "INCIDENT_DETECTED":
        return Colors.orange;
      case "INCIDENT_CONFIRMED":
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  // Map state to display text
  String getDisplayText(String state) {
    switch (state) {
      case "IDLE":
        return "IDLE";
      case "INCIDENT_DETECTED":
        return "ALERT DETECTED!";
      case "INCIDENT_CONFIRMED":
        return "ALERT CONFIRMED!";
      default:
        return "UNKNOWN";
    }
  }
}

// Poll backend every second
void startPolling() {
  Timer.periodic(Duration(seconds: 1), (timer) async {
    await fetchDataOnce();
    sendStateToWatch();
  });
}

// Fetch one update from backend
Future<void> fetchDataOnce() async {
  final url = 'http://10.136.4.45:8000/pose/anomaly'; // Replace with your backend IP
  try {
    final response = await http.get(Uri.parse(url));
    if (response.statusCode == 200) {
      final data = json.decode(response.body);
      bool isAnomaly = data['is_anomaly'];
      anomalyTimestamp = data['timestamp'];
      anomalySignal.value = isAnomaly ? "INCIDENT_DETECTED" : "IDLE";
      print("Fetched anomaly: ${anomalySignal.value} at $anomalyTimestamp");
    } else {
      print('Failed to fetch data: ${response.statusCode}');
    }
  } catch (e) {
    print("Error fetching data: $e");
  }
}

// Send state to watch via Wear OS
void sendStateToWatch() {
  Wear().sendMessage(
    path: "/state_update",
    data: anomalySignal.value.codeUnits,
  );
  print("Sent to watch: ${anomalySignal.value}");
}

// Listen for messages from the watch
void startWatchListener() {
  Wear().onMessageReceived.listen((messageEvent) {
    final path = messageEvent.path;
    final data = String.fromCharCodes(messageEvent.data);

    if (path == "/watch_data") {
      handleWatchData(data);
    }
  });
}

void handleWatchData(String data) {
  print("Received from watch: $data");

  if (data == "INCIDENT_CONFIRMED") {
    anomalySignal.value = "INCIDENT_CONFIRMED";
    print("Global anomalySignal updated from watch");
  } else {
    // Keep other states as they are, optionally you can handle other watch messages
    print("Other message from watch: $data");
  }
}
