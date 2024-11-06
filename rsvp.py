import asyncio
from even_glasses.bluetooth_manager import GlassesManager
from even_glasses.commands import send_text, send_rsvp
import logging
from even_glasses.models import RSVPConfig


logging.basicConfig(level=logging.INFO)
rsvp_text_path = "./even_glasses/rsvp_story.txt"
with open(rsvp_text_path, "r") as f:
    text = f.read()

    
config = RSVPConfig(words_per_group=3, wpm=750, padding_char="...")

async def main():
    manager = GlassesManager(left_address=None, right_address=None)
    await manager.scan_and_connect()
    if not manager.left_glass or not manager.right_glass:
        logging.error("Could not connect to glasses devices.")
        return
    await send_text(manager, "Init message!") # we need to send a message to init even ai message sending
    await asyncio.sleep(5)
    counter = 1
    while KeyboardInterrupt:
        # await send_text(manager, f"Hello Wrold! {counter}")
        await send_rsvp(manager, text, config)
        await asyncio.sleep(3)
        await send_text(manager, "RSVP Done! restarting in 3 seconds")
        await asyncio.sleep(3)
        counter += 1
    

if __name__ == "__main__":
    asyncio.run(main())