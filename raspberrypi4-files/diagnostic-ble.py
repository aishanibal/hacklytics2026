import asyncio
from bleak import BleakScanner

async def scan_all():
    discovered = await BleakScanner.discover(timeout=10, return_adv=True)
    for address, (device, adv_data) in discovered.items():
        print(f"Name: {device.name}, Address: {address}")
        print(f"  RSSI: {adv_data.rssi}")
        print(f"  Service UUIDs: {adv_data.service_uuids}")
        print(f"  Local name: {adv_data.local_name}")
        print("---")

asyncio.run(scan_all())
