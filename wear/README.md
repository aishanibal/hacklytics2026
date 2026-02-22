# Vigil Wear OS app

Wear OS companion app for the Vigil medical alert system. Three states: **IDLE**, **INCIDENT_DETECTED** (red/blue flash, fast vibration, Cancel), **INCIDENT_CONFIRMED** (solid red, "Help is arriving", slow vibration).

## Build and run

1. **Generate Gradle wrapper** (if missing):
   ```bash
   gradle wrapper
   ```
   Or open the `wear` folder in **Android Studio** and let it sync.

2. **Build**:
   ```bash
   ./gradlew assembleDebug
   ```
   (Windows: `gradlew.bat assembleDebug`)

3. **Run on emulator or device**: Use Android Studio Run, or:
   ```bash
   ./gradlew installDebug
   adb -s <watch-device> shell am start -n com.flutter_app.watch/.WatchMainActivity
   ```

## Requirements

- Wear OS device or Wear OS emulator (API 26+)
- Android Studio with Wear OS support
