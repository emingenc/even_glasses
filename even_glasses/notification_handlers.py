import logging

logger = logging.getLogger(__name__)


async def handle_incoming_notification(sender: int, data: bytes):
    """
    Process incoming notifications from the BLE device.

    Args:
        sender (int): The handle of the characteristic that sent the notification.
        data (bytes): The incoming data.
    """
    message = data.decode('utf-8', errors='ignore')
    logger.info(f"Notification received from {sender}: {message}")
    # Implement your processing logic here
    # For example, parse the message and trigger events or update states