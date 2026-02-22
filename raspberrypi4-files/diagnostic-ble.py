import asyncio
from bleak import BleakScanner

async def scan_all():
    devices = await BleakScanner.discover(timeout=10)
    for device in devices:
        print(f"Name: {device.name}, Address: {device.address}")
        print(f"Details: {device.details}")
        print("---")


asyncio.run(scan_all())
