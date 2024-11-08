import logging
from typing import Dict, Union
from uuid import UUID
from even_glasses.models import (
    Command,
    SubCommand,
    MicStatus,
    ResponseStatus,
)
from even_glasses.bluetooth_manager import Glass
from even_glasses.command_logger import debug_command_logs, DEBUG
from typing import Callable, Awaitable


async def handle_heartbeat(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the HEARTBEAT command from the device.

    Command: HEARTBEAT (0x25)
    """
    logging.info(f"Heartbeat received from {glass.side}")
    # Additional processing can be implemented here


async def handle_start_ai(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the START_AI command including subcommands.

    Command: START_AI (0xF5)
    Subcommands:
      - 0x00: Exit to dashboard manually. double tap on the touchpad
      - 0x01: Page up/down control in manual mode
      - 0x17: Start Even AI
      - 0x18: Stop Even AI recording
    """
    if len(data) < 2:
        logging.warning(f"Invalid data length for START_AI command from {glass.side}")
        return

    sub_command_byte = data[1]
    try:
        sub_command = SubCommand(sub_command_byte)
    except ValueError:
        logging.warning(
            f"Unknown subcommand: 0x{sub_command_byte:02X} received from {glass.side}"
        )
        return

    logging.info(
        f"START_AI command with subcommand {sub_command.name} received from {glass.side}"
    )

    # Handle subcommands
    if sub_command == SubCommand.EXIT:
        # Handle exit to dashboard
        logging.info(f"Handling EXIT to dashboard command from {glass.side}")
        # Implement your logic here
    elif sub_command == SubCommand.PAGE_CONTROL:
        # Handle page up/down control
        logging.info(f"Handling PAGE_CONTROL command from {glass.side}")
        # Implement your logic here
    elif sub_command == SubCommand.START:
        # Handle starting Even AI
        logging.info(f"Handling START Even AI command from {glass.side}")
        # Implement your logic here
    elif sub_command == SubCommand.STOP:
        # Handle stopping Even AI recording
        logging.info(f"Handling STOP Even AI recording command from {glass.side}")
        # Implement your logic here
    else:
        logging.warning(
            f"Unhandled subcommand: {sub_command} received from {glass.side}"
        )


async def handle_open_mic(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the OPEN_MIC command.

    Command: OPEN_MIC (0x0E)
    """
    if len(data) < 2:
        logging.warning(f"Invalid data length for OPEN_MIC command from {glass.side}")
        return

    mic_status_byte = data[1]
    try:
        mic_status = MicStatus(mic_status_byte)
    except ValueError:
        logging.warning(
            f"Unknown mic status: 0x{mic_status_byte:02X} received from {glass.side}"
        )
        return

    logging.info(
        f"OPEN_MIC command received from {glass.side} with status {mic_status.name}"
    )
    # Implement your logic here


async def handle_mic_response(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the MIC_RESPONSE command.

    Command: MIC_RESPONSE (0x0E)
    """
    if len(data) < 3:
        logging.warning(
            f"Invalid data length for MIC_RESPONSE command from {glass.side}"
        )
        return

    rsp_status_byte = data[1]
    enable_byte = data[2]

    try:
        rsp_status = ResponseStatus(rsp_status_byte)
        mic_status = MicStatus(enable_byte)
    except ValueError as e:
        logging.warning(f"Error parsing MIC_RESPONSE from {glass.side}: {e}")
        return

    logging.info(
        f"MIC_RESPONSE received from {glass.side}: rsp_status={rsp_status.name}, mic_status={mic_status.name}"
    )
    # Implement your logic here


async def handle_receive_mic_data(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the RECEIVE_MIC_DATA command.

    Command: RECEIVE_MIC_DATA (0xF1)
    """
    if len(data) < 2:
        logging.warning(
            f"Invalid data length for RECEIVE_MIC_DATA command from {glass.side}"
        )
        return

    seq = data[1]
    mic_data = data[2:]

    logging.info(
        f"RECEIVE_MIC_DATA from {glass.side}: seq={seq}, data_length={len(mic_data)}"
    )
    # Implement your logic here (e.g., buffering audio data)


async def handle_send_result(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the SEND_RESULT command.

    Command: SEND_RESULT (0x4E)
    """
    if len(data) < 9:
        logging.warning(
            f"Invalid data length for SEND_RESULT command from {glass.side}"
        )
        return

    # Parse command fields
    seq = data[1]
    total_packages = data[2]

    logging.info(
        f"SEND_RESULT from {glass.side}: seq={seq}, total_packages={total_packages}, "
    )
    # Implement your logic here


async def handle_quick_note(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the QUICK_NOTE command.

    Command: QUICK_NOTE (0x21)
    """
    logging.info(f"QUICK_NOTE received from {glass.side}")
    # Implement your logic here


async def handle_dashboard(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the DASHBOARD command.

    Command: DASHBOARD (0x22)
    """
    logging.info(f"DASHBOARD command received from {glass.side}")
    # Implement your logic here


async def handle_notification(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the NOTIFICATION command.

    Command: NOTIFICATION (0x4B)
    """
    if len(data) < 4:
        logging.warning(
            f"Invalid data length for NOTIFICATION command from {glass.side}"
        )
        return

    notify_id = data[1]
    total_chunks = data[2]
    current_chunk = data[3]
    notification_content = data[4:]

    logging.info(
        f"NOTIFICATION from {glass.side}: notify_id={notify_id}, total_chunks={total_chunks}, "
        f"current_chunk={current_chunk}, content_length={len(notification_content)}"
    )
    # Implement your logic here


async def handle_init(glass: Glass, sender: Union[UUID, int, str], data: bytes) -> None:
    """
    Handle the INIT command.

    Command: INIT (0x4D)
    """
    logging.info(f"INIT command received from {glass.side}")
    # Implement your logic here


# Mapping of commands to handler functions
COMMAND_HANDLERS: Dict[
    Command, Callable[[bytes, Union[UUID, int, str], str], Awaitable[None]]
] = {
    Command.HEARTBEAT: handle_heartbeat,
    Command.START_AI: handle_start_ai,
    Command.OPEN_MIC: handle_open_mic,
    Command.MIC_RESPONSE: handle_mic_response,
    Command.RECEIVE_MIC_DATA: handle_receive_mic_data,
    Command.INIT: handle_init,
    Command.SEND_RESULT: handle_send_result,
    Command.QUICK_NOTE: handle_quick_note,
    Command.DASHBOARD: handle_dashboard,
    Command.NOTIFICATION: handle_notification,
    # Add other command handlers as necessary
}


async def handle_incoming_notification(
    glass: Glass, sender: Union[UUID, int, str], data: Union[bytes, bytearray]
) -> None:
    if DEBUG:
        debug_command_logs(glass.side, sender, data)

    if isinstance(data, bytearray):
        data = bytes(data)

    # Extract the command byte from the data
    if not data:
        logging.warning("No data received in notification")
        return

    command_byte = data[0]
    try:
        command = Command(command_byte)
    except ValueError:
        logging.warning(
            f"Unknown command: 0x{command_byte:02X} received from {glass.side}"
        )
        return

    handler = COMMAND_HANDLERS.get(command)
    if handler:
        await handler(glass, sender, data)
    else:
        logging.warning(
            f"No handler for command: {command.name} (0x{command_byte:02X}) received from {glass.side}"
        )
