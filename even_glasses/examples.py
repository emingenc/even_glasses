import asyncio
from bluetooth_manager import GlassesManager
from commands import send_text
import logging


logging.basicConfig(level=logging.INFO)

async def main():
    manager = GlassesManager(left_address=None, right_address=None)
    await manager.scan_and_connect()
    if not manager.left_glass or not manager.right_glass:
        logging.error("Could not connect to glasses devices.")
        return
    await send_text(manager, "Hello, World!")
    counter = 1
    await asyncio.sleep(5)
    while True:
        await send_text(manager, f"Hello, World! {counter}")
        await asyncio.sleep(1)
        counter += 1
    

if __name__ == "__main__":
    asyncio.run(main())