import asyncio
from bleak import BleakScanner

# Target UUID from your Android phone
TARGET_UUID = "a91c8e72-6b91-4f92-9c9b-6bafcd2e1d13"

# RSSI calibration constants
TX_POWER = -59  # RSSI at 1 meter
N = 2.5         # Path loss exponent (indoor ~2-3)

def estimate_distance(rssi):
    """Estimate distance from RSSI"""
    return 10 ** ((TX_POWER - rssi) / (10 * N))

async def scan():
    print("Scanning for target phone...\n")

    
    devices = await BleakScanner.discover(timeout=2)
    
    found = False
    
    results = []
    
    for device in devices:
        # In Bleak 2.x, advertised UUIDs are in device.details["uuids"]
        props = device.details.get('props', {}) if device.details else {}
        uuid = props.get("UUIDs",[])
        if TARGET_UUID in uuid:
            rssi = props.get("RSSI",[])
            distance = estimate_distance(rssi)
            
            results.append({
                "UUID": TARGET_UUID,
                "address": device.address,
                "distance": distance
            })
                
            found = True
            
    if not found:
        print("Target not detected\n")

    return results

    

        
