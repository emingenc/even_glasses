import struct
from even_glasses.models import Command, NCSNotification, Notification



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


async def construct_notification(ncs_notification=NCSNotification):

    # Create Notification instance
    notification = Notification(ncs_notification=ncs_notification, type="Add")

    # Get notification chunks
    chunks = await notification.construct_notification()
    return chunks
