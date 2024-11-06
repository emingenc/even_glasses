import asyncio
import logging
import struct
from models import Command, ResponseStatus


async def wait_for_ack(device, timeout: int = 5):
    try:
        sender, data = await asyncio.wait_for(device.message_queue.get(), timeout)
        if is_acknowledgment(data):
            logging.info(f"Acknowledgment received from {device.name}")
        else:
            logging.warning(f"Unexpected data from {device.name}: {data.hex()}")
    except asyncio.TimeoutError:
        logging.warning(f"Timeout waiting for acknowledgment from {device.name}")


def is_acknowledgment(data: bytes) -> bool:
    ACK_COMMAND = bytes([ResponseStatus.SUCCESS])
    return data.startswith(ACK_COMMAND)


def construct_heartbeat(seq: int) -> bytes:
    length = 6
    return struct.pack(
        "BBBBBB",
        Command.HEARTBEAT,
        length & 0xFF,
        (length >> 8) & 0xFF,
        seq % 0xFF,
        0x04,
        seq % 0xFF,
    )
