import asyncio
from bleak import BleakScanner

# Target UUID from your Android phone
TARGET_UUID = "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13"

# RSSI calibration constants
TX_POWER = -59  # RSSI at 1 meter
N = 2.5         # Path loss exponent (indoor ~2-3)

def estimate_distance(rssi):
    """Convert RSSI to distance in meters, clamped to [0.1, 30]."""
    dist = 10 ** ((TX_POWER - rssi) / (10 * N))
    return max(0.1, min(dist, 30.0))

SCAN_ROUNDS = 5
SCAN_TIMEOUT = 1  # seconds per round (~5s total)


async def scan():
    print(f"Scanning for target phone ({SCAN_ROUNDS} rounds)...\n")

    rssi_readings: dict[str, list[int]] = {}

    for i in range(SCAN_ROUNDS):
        devices = await BleakScanner.discover(timeout=SCAN_TIMEOUT)
        for device in devices:
            props = device.details.get('props', {}) if device.details else {}
            uuids = props.get("UUIDs", [])
            if TARGET_UUID in uuids:
                rssi = props.get("RSSI", None)
                if rssi is not None:
                    rssi_readings.setdefault(device.address, []).append(rssi)

    if not rssi_readings:
        print("Target not detected\n")
        return []

    results = []
    for address, readings in rssi_readings.items():
        readings.sort()
        trimmed = readings[1:-1] if len(readings) > 3 else readings
        avg_rssi = sum(trimmed) / len(trimmed)
        distance = estimate_distance(avg_rssi)
        print(f"  {address}: {len(readings)} readings, "
              f"avg RSSI={avg_rssi:.1f}, dist={distance:.2f}m")
        results.append({
            "UUID": TARGET_UUID,
            "address": address,
            "distance": round(distance, 2),
        })

    return results

    

        
