import asyncio
import argparse
import logging
from even_glasses.bluetooth_manager import GlassesManager
from even_glasses.commands import send_text, send_rsvp, send_notification
from even_glasses.models import RSVPConfig, NCSNotification
from even_glasses.notification_handlers import handle_incoming_notification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Even Glasses Text Display Tests")

    # Create mutually exclusive group for test type
    test_type = parser.add_mutually_exclusive_group(required=True)
    test_type.add_argument("--rsvp", action="store_true", help="Run RSVP test")
    test_type.add_argument("--text", action="store_true", help="Run text test")
    test_type.add_argument(
        "--notification", action="store_true", help="Run notification test"
    )

    # Optional arguments for RSVP configuration
    parser.add_argument(
        "--wpm", type=int, default=1200, help="Words per minute for RSVP (default: 750)"
    )
    parser.add_argument(
        "--words-per-group",
        type=int,
        default=4,
        help="Number of words per group for RSVP (default: 3)",
    )
    parser.add_argument(
        "--input-file",
        type=str,
        default="./even_glasses/rsvp_story.txt",
        help="Input text file path (default: ./even_glasses/rsvp_story.txt)",
    )

    args = parser.parse_args()
    return args


async def test_rsvp(manager: GlassesManager, text: str, config: RSVPConfig):
    if not manager.left_glass or not manager.right_glass:
        logger.error("Could not connect to glasses devices.")
        return
    await send_text(
        manager, "Init message!"
    )  # Initialize Even AI message sending
    await asyncio.sleep(5)
    await send_rsvp(manager, text, config)
    await asyncio.sleep(3)
    await send_text(manager, "RSVP Done! Restarting in 3 seconds")
    await asyncio.sleep(3)


async def test_text(manager: GlassesManager, text: str):
    if not manager.left_glass or not manager.right_glass:
        logger.error("Could not connect to glasses devices.")
        return
    await send_text(manager, text)


async def test_notification(manager: GlassesManager, notification: NCSNotification):
    if not manager.left_glass or not manager.right_glass:
        logger.error("Could not connect to glasses devices.")
        return
    await send_notification(manager, notification)


async def main():
    args = parse_args()

    try:
        with open(args.input_file, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        logger.error(f"Input file not found: {args.input_file}")
        return

    config = RSVPConfig(
        words_per_group=args.words_per_group, wpm=args.wpm, padding_char="..."
    )

    manager = GlassesManager(left_address=None, right_address=None)
    connected = await manager.scan_and_connect()

    if connected:
        # Assign notification handlers
        if manager.left_glass:
            manager.left_glass.notification_handler = handle_incoming_notification
        if manager.right_glass:
            manager.right_glass.notification_handler = handle_incoming_notification

        counter = 1

        try:
            while True:
                if args.rsvp:
                    await test_rsvp(manager=manager, text=text, config=config)
                elif args.text:
                    message = f"Test message {counter}"
                    await test_text(manager=manager, text=message)
                elif args.notification:
                    notification = NCSNotification(
                        msg_id=1,
                        title="Test Notification Title",
                        subtitle="Test Notification Subtitle",
                        message="This is a test notification",
                        display_name="Test Notification",
                        app_identifier="org.telegram.messenger",
                    )
                    await test_notification(manager=manager, notification=notification)
                counter += 1
                await asyncio.sleep(1)  # Prevent tight loop
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            await manager.disconnect_all()
    else:
        logger.error("Failed to connect to glasses.")


if __name__ == "__main__":
    asyncio.run(main())