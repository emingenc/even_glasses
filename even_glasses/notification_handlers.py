import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Union, List
from uuid import UUID
import binascii
from even_glasses.models import (
    Command,
    SubCommand,
    MicStatus,
    ScreenAction,
    AIStatus,
    ResponseStatus,
)
from even_glasses.bluetooth_manager import Glass
from typing import Callable, Awaitable


DEBUG = True


class CommandLogger:
    MAX_TIMESTAMPS = 5  # Keep only last 5 timestamps

    COMMAND_TYPES = {
        Command.START_AI: "Start Even AI",
        Command.OPEN_MIC: "Mic Control",
        Command.MIC_RESPONSE: "Mic Response",
        Command.RECEIVE_MIC_DATA: "Mic Data",
        Command.INIT: "Initialize",
        Command.HEARTBEAT: "Heartbeat",
        Command.SEND_RESULT: "AI Result",
        Command.QUICK_NOTE: "Quick Note",
        Command.DASHBOARD: "Dashboard",
        Command.NOTIFICATION: "Notification",
    }

    def __init__(self):
        self.data_dir = Path("./notification_logs")
        self.data_dir.mkdir(exist_ok=True)
        self.log_file = self.data_dir / "notification_logs.json"
        self.command_history: Dict[str, List[Dict]] = {}
        self._load_existing_logs()
        self.command_history: Dict[str, Dict[str, Dict]] = {}

    def _parse_command(self, data: bytes) -> Dict:
        if not data:
            return self._create_error_parse("Empty data received")

        try:
            cmd = data[0]
            parsed = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "command": {
                    "hex": f"0x{cmd:02X}",
                    "int": cmd,
                    "type": self.COMMAND_TYPES.get(
                        cmd, f"Unknown command: 0x{cmd:02X}"
                    ),
                },
                "raw": {
                    "hex": data.hex(),
                    "hex_dump": binascii.hexlify(data).decode("ascii"),
                    "pretty_hex": " ".join(f"{b:02x}" for b in data),
                    "bytes": str(data),
                    "int_array": list(data),
                    "crc32": f"0x{binascii.crc32(data):08x}",  # Add CRC32 checksum
                },
            }
            # Parse specific commands
            if cmd == Command.START_AI:
                subcmd = data[1] if len(data) > 1 else None
                parsed["subcmd"] = {
                    "hex": f"0x{subcmd:02X}" if subcmd is not None else None,
                    "int": subcmd,
                    "description": {
                        SubCommand.EXIT: "Exit to dashboard",
                        SubCommand.PAGE_CONTROL: "Page up/down control",
                        SubCommand.START: "Start Even AI",
                        SubCommand.STOP: "Stop Even AI recording",
                    }.get(
                        subcmd,
                        f"Unknown subcmd: 0x{subcmd:02X}"
                        if subcmd is not None
                        else "No subcmd",
                    ),
                }

            elif cmd == Command.OPEN_MIC:
                enable = data[1] if len(data) > 1 else None
                parsed["mic_control"] = {
                    "hex": f"0x{enable:02X}" if enable is not None else None,
                    "int": enable,
                    "status": "Enable MIC"
                    if enable == MicStatus.ENABLE
                    else "Disable MIC",
                }

            elif cmd == Command.SEND_RESULT:
                if len(data) >= 9:
                    parsed["ai_result"] = {
                        "sequence": data[1],
                        "total_packages": data[2],
                        "current_package": data[3],
                        "screen_status": {
                            "action": data[4] & 0x0F,  # Lower 4 bits
                            "ai_status": data[4] & 0xF0,  # Upper 4 bits
                            "description": self._get_screen_status_description(data[4]),
                        },
                        "page_info": {"current": data[7], "total": data[8]},
                    }

            elif cmd == Command.NOTIFICATION:
                if len(data) >= 4:
                    parsed["notification"] = {
                        "notify_id": data[1],
                        "total_chunks": data[2],
                        "current_chunk": data[3],
                    }

            return parsed

        except Exception as e:
            return self._create_error_parse(f"Error parsing command: {str(e)}")

    def _get_screen_status_description(self, status: int) -> str:
        """Get human readable description of screen status"""
        action = status & 0x0F
        ai_status = status & 0xF0

        action_desc = (
            "New content" if action == ScreenAction.NEW_CONTENT else "Unknown action"
        )
        ai_desc = {
            AIStatus.DISPLAYING: "Displaying (auto)",
            AIStatus.DISPLAY_COMPLETE: "Complete",
            AIStatus.MANUAL_MODE: "Manual mode",
            AIStatus.NETWORK_ERROR: "Network error",
        }.get(ai_status, "Unknown AI status")

        return f"{action_desc} - {ai_desc}"

    def _create_error_parse(self, error_msg: str) -> Dict:
        """Create error parsing result"""
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": error_msg,
            "command": {"type": "Error"},
        }

    def log_command(
        self, side: str, sender: Union[UUID, int, str], data: Union[bytes, bytearray]
    ) -> Dict:
        sender_key = f"{sender} {side}"
        if isinstance(data, bytearray):
            data = bytes(data)

        parsed_cmd = self._parse_command(data)
        current_time = parsed_cmd["timestamp"]

        cmd_identifier = json.dumps(
            {k: v for k, v in parsed_cmd.items() if k != "timestamp"},
            sort_keys=True,
        )

        if sender_key not in self.command_history:
            self.command_history[sender_key] = {}

        if cmd_identifier not in self.command_history[sender_key]:
            # New command - initialize with deque
            self.command_history[sender_key][cmd_identifier] = {
                "command": parsed_cmd,
                "timestamps": deque([current_time], maxlen=self.MAX_TIMESTAMPS),
            }
        else:
            # Existing command - append timestamp to deque
            self.command_history[sender_key][cmd_identifier]["timestamps"].append(
                current_time
            )

        self._save_logs()
        return self.command_history[sender_key][cmd_identifier]

    def _save_logs(self):
        try:
            serializable_history = {}
            for sender, commands in self.command_history.items():
                serializable_history[sender] = []
                for cmd_data in commands.values():
                    entry = cmd_data["command"].copy()
                    # Convert deque to list for serialization
                    entry["timestamps"] = list(cmd_data["timestamps"])
                    serializable_history[sender].append(entry)

            with open(self.log_file, "w") as f:
                json.dump(serializable_history, f, indent=2)
        except Exception as e:
            logging.debug(f"Error saving command logs: {e}")

    def _load_existing_logs(self):
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    loaded_data = json.load(f)
                    self.command_history = {}

                    for sender, commands in loaded_data.items():
                        self.command_history[sender] = {}
                        for entry in commands:
                            timestamps = entry.pop("timestamps", [])
                            cmd_identifier = json.dumps(entry, sort_keys=True)
                            # Convert timestamps list to deque
                            self.command_history[sender][cmd_identifier] = {
                                "command": entry,
                                "timestamps": deque(
                                    timestamps[-self.MAX_TIMESTAMPS :],
                                    maxlen=self.MAX_TIMESTAMPS,
                                ),
                            }
            except json.JSONDecodeError:
                self.command_history = {}


command_logger = CommandLogger()


def debug_command_logs(side: str, sender: UUID | int | str, data: bytes | bytearray):
    # Log the command first
    cmd_log = command_logger.log_command(side, sender, data)

    # Create serializable version of cmd_log
    serializable_log = {
        "side": side,
        "command": cmd_log["command"],
        "timestamps": list(cmd_log["timestamps"]),  # Convert deque to list
    }

    logging.debug(f"Command received: {json.dumps(serializable_log, indent=2)}")

    # Rest of your existing notification handling code...
    if isinstance(data, bytearray):
        data = bytes(data)


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
        logging.warning(f"Unhandled subcommand: {sub_command} received from {glass.side}")


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

    logging.info(f"OPEN_MIC command received from {glass.side} with status {mic_status.name}")
    # Implement your logic here


async def handle_mic_response(
    glass: Glass, sender: Union[UUID, int, str], data: bytes
) -> None:
    """
    Handle the MIC_RESPONSE command.

    Command: MIC_RESPONSE (0x0E)
    """
    if len(data) < 3:
        logging.warning(f"Invalid data length for MIC_RESPONSE command from {glass.side}")
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
        logging.warning(f"Invalid data length for RECEIVE_MIC_DATA command from {glass.side}")
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
        logging.warning(f"Invalid data length for SEND_RESULT command from {glass.side}")
        return

    # Parse command fields
    seq = data[1]
    total_packages = data[2]
    current_package = data[3]
    screen_status_byte = data[4]
    new_char_pos0 = data[5]
    new_char_pos1 = data[6]
    current_page_num = data[7]
    max_page_num = data[8]
    content_data = data[9:]

    # Parse screen status
    screen_action = screen_status_byte & 0x0F  # Lower 4 bits
    ai_status = screen_status_byte & 0xF0  # Upper 4 bits

    logging.info(
        f"SEND_RESULT from {glass.side}: seq={seq}, total_packages={total_packages}, "
        f"current_package={current_package}, screen_action=0x{screen_action:02X}, "
        f"ai_status=0x{ai_status:02X}, current_page_num={current_page_num}, "
        f"max_page_num={max_page_num}, content_length={len(content_data)}"
        f"new_char_pos0={new_char_pos0}, new_char_pos1={new_char_pos1}"
        f"content_data={content_data}"
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
        logging.warning(f"Invalid data length for NOTIFICATION command from {glass.side}")
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
        logging.warning(f"Unknown command: 0x{command_byte:02X} received from {glass.side}")
        return

    handler = COMMAND_HANDLERS.get(command)
    if handler:
        await handler(glass, sender, data)
    else:
        logging.warning(
            f"No handler for command: {command.name} (0x{command_byte:02X}) received from {glass.side}"
        )
