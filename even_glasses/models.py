# models.py

from enum import IntEnum
from dataclasses import dataclass
from datetime import datetime
import time


class Command(IntEnum):
    START_AI = 0xF5
    OPEN_MIC = 0x0E
    MIC_RESPONSE = 0x0E
    RECEIVE_MIC_DATA = 0xF1
    INIT = 0x4D
    HEARTBEAT = 0x25 
    SEND_RESULT = 0x4E
    QUICK_NOTE = 0x21
    DASHBOARD = 0x22
    NOTIFICATION = 0x4B


class SubCommand(IntEnum):
    EXIT = 0x00
    PAGE_CONTROL = 0x01
    START = 0x17
    STOP = 0x18


class MicStatus(IntEnum):
    ENABLE = 0x01
    DISABLE = 0x00


class ResponseStatus(IntEnum):
    SUCCESS = 0xC9
    FAILURE = 0xCA


class ScreenAction(IntEnum):
    NEW_CONTENT = 0x01

class AIStatus(IntEnum):
    DISPLAYING = 0x30  # Even AI displaying（automatic mode default）
    DISPLAY_COMPLETE = 0x40 # Even AI display complete ( last page of automatic mode)
    MANUAL_MODE = 0x50 # Even AI manual mode
    NETWORK_ERROR = 0x60 # Even AI network error


@dataclass
class SendResult:
    command: int = Command.SEND_RESULT
    seq: int = 0
    total_packages: int = 0
    current_package: int = 0
    screen_status: int = ScreenAction.NEW_CONTENT | AIStatus.DISPLAYING
    new_char_pos0: int = 0
    new_char_pos1: int = 0
    page_number: int = 1
    max_pages: int = 1
    data: bytes = b""

    def build(self) -> bytes:
        header = bytes(
            [
                self.command,
                self.seq,
                self.total_packages,
                self.current_package,
                self.screen_status,
                self.new_char_pos0,
                self.new_char_pos1,
                self.page_number,
                self.max_pages,
            ]
        )
        return header + self.data


@dataclass
class Notification:
    msg_id: int
    app_identifier: str
    title: str
    subtitle: str
    message: str
    display_name: str
    timestamp: int = int(time.time())
    date: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "msg_id": self.msg_id,
            "type": 1,
            "app_identifier": self.app_identifier,
            "title": self.title,
            "subtitle": self.subtitle,
            "message": self.message,
            "time_s": self.timestamp,
            "date": self.date,
            "display_name": self.display_name,
        }


@dataclass
class RSVPConfig:
    words_per_group: int = 1
    wpm: int = 250
    padding_char: str = "..."
    max_retries: int = 3
    retry_delay: float = 0.5
    
class BleReceive:
    """BLE Receive Data Structure."""

    def __init__(self, lr="L", cmd=0x00, data=None, is_timeout=False):
        self.lr = lr  # Left or Right
        self.cmd = cmd
        self.data = data if data else bytes()
        self.is_timeout = is_timeout
