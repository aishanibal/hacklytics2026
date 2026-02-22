import 'package:http/http.dart' as http;
import 'dart:convert';
import 'global.dart';
import 'package:wear/wear.dart';

String anomalySignal = "IDLE";

Future<void> fetchData() async {
    while (true) {
        final url = 'http://10.136.4.45:8000/pose/anomaly';
        final response = await http.get(Uri.parse(url));
        if (response.statusCode == 200) {
            final data = json.decode(response.body);
            bool isAnomaly = data['is_anomaly'];
            time = data['timestamp'];
            if (isAnomaly) {
                anomalySignal = "INCIDENT_DETECTED";
            } 
        } else {
            print('Failed to fetch data: ${response.statusCode}');
        }
        await Future.delayed(const Duration(seconds: 1));
    }
}

void sendStateToWatch() {
    Wear().sendMessage(
        path: "/state_update",
        data: anomalySignal.codeUnits.
    );
}

void main() {
    fetchData();
}

