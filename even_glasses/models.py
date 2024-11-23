from pydantic import BaseModel, Field, field_validator
from typing import Literal, List
import time
import json
from enum import IntEnum
from datetime import datetime

class DesiredConnectionState(IntEnum):
    DISCONNECTED = 0x00
    CONNECTED = 0x01

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
    SILENT_MODE = 0x03
    BRIGHTNESS = 0x01
    DASHBOARD_POSITION = 0x26
    HEADUP_ANGLE = 0x0B
    DASHBOARD_SHOW = 0x06

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
    DISPLAYING = 0x30  # Even AI displaying (automatic mode default)
    DISPLAY_COMPLETE = 0x40  # Even AI display complete (last page of automatic mode)
    MANUAL_MODE = 0x50  # Even AI manual mode
    NETWORK_ERROR = 0x60  # Even AI network error

class SilentModeStatus(IntEnum):
    OFF = 0x0A
    ON = 0x0C

class BrightnessAuto(IntEnum):
    OFF = 0x00
    ON = 0x01

class DashboardPosition(IntEnum):
    POSITION_0 = 0x00  # Bottom
    POSITION_1 = 0x01
    POSITION_2 = 0x02
    POSITION_3 = 0x03
    POSITION_4 = 0x04
    POSITION_5 = 0x05
    POSITION_6 = 0x06
    POSITION_7 = 0x07
    POSITION_8 = 0x08  # Top

class DashboardState(IntEnum):
    OFF = 0x00
    ON = 0x01

class SendResult(BaseModel):
    command: int = Field(default=Command.SEND_RESULT)
    seq: int = Field(default=0)
    total_packages: int = Field(default=0)
    current_package: int = Field(default=0)
    screen_status: int = Field(default=ScreenAction.NEW_CONTENT | AIStatus.DISPLAYING)
    new_char_pos0: int = Field(default=0)
    new_char_pos1: int = Field(default=0)
    page_number: int = Field(default=1)
    max_pages: int = Field(default=1)
    data: bytes = Field(default=b"")

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

class NCSNotification(BaseModel):
    msg_id: int = Field(..., alias="msg_id", description="Message ID")
    type: int = Field(1, alias="type", description="Notification type")
    app_identifier: str = Field(
        ..., alias="app_identifier", description="App identifier"
    )
    title: str = Field(..., alias="title", description="Notification title")
    subtitle: str = Field(..., alias="subtitle", description="Notification subtitle")
    message: str = Field(..., alias="message", description="Notification message")
    time_s: int = Field(
        default_factory=lambda: int(time.time()),
        alias="time_s",
        description="Current time in seconds since the epoch",
    )
    date: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        alias="date",
        description="Current date and time",
    )
    display_name: str = Field(..., alias="display_name", description="Display name")

    class ConfigDict:
        populate_by_name = True

class Notification(BaseModel):
    ncs_notification: NCSNotification = Field(
        ..., alias="ncs_notification", description="NCS Notification details"
    )
    type: Literal["Add"] = Field(
        "Add", alias="type", description="Type of notification"
    )

    class ConfigDict:
        populate_by_name = True

    def to_json(self):
        return self.model_dump(by_alias=True)

    def to_bytes(self):
        return json.dumps(self.to_json()).encode("utf-8")

    async def construct_notification(self):
        json_bytes = self.to_bytes()
        max_chunk_size = 180 - 4  # Subtract 4 bytes for header
        chunks = [
            json_bytes[i : i + max_chunk_size]
            for i in range(0, len(json_bytes), max_chunk_size)
        ]
        total_chunks = len(chunks)
        encoded_chunks = []
        for index, chunk in enumerate(chunks):
            notify_id = 0  # Set appropriate notification ID
            header = bytes([Command.NOTIFICATION, notify_id, total_chunks, index])
            encoded_chunk = header + chunk
            encoded_chunks.append(encoded_chunk)
        return encoded_chunks

class RSVPConfig(BaseModel):
    words_per_group: int = Field(default=1)
    wpm: int = Field(default=250)
    padding_char: str = Field(default="...")

class BleReceive(BaseModel):
    lr: str = Field(default="L", description="Left or Right")
    cmd: int = Field(default=0x00)
    data: bytes = Field(default_factory=bytes)
    is_timeout: bool = Field(default=False)

class NoteConstants(IntEnum):
    COMMAND = 0x1E
    FIXED_BYTE = 0x00
    FIXED_BYTE_2 = 0x01

class NoteAdd(BaseModel):
    command: int = Field(default=NoteConstants.COMMAND)
    note_number: int = Field(..., description="Note number (1-4)")
    name: str = Field(..., description="Note name")
    text: str = Field(..., description="Note text")

    @field_validator('note_number')
    def validate_note_number(cls, v):
        if not 1 <= v <= 4:
            raise ValueError('Note number must be between 1 and 4')
        return v

    def _get_fixed_bytes(self) -> bytes:
        """Return the fixed bytes sequence"""
        return bytes([0x03, 0x01, 0x00, 0x01, 0x00])

    def _get_versioning_byte(self) -> int:
        """Generate versioning byte based on timestamp"""
        return int(time.time()) % 256

    def _calculate_payload_length(self, name_bytes: bytes, text_bytes: bytes) -> int:
        """Calculate total payload length"""
        components: List[int] = [
            1,  # Fixed byte
            1,  # Versioning byte
            len(self._get_fixed_bytes()),  # Fixed bytes sequence
            1,  # Note number
            1,  # Fixed byte 2
            1,  # Title length
            len(name_bytes),  # Title bytes
            1,  # Text length
            1,  # Fixed byte after text length
            len(text_bytes),  # Text bytes
            2,  # Final bytes
        ]
        return sum(components)

    def build(self) -> bytes:
        """Build the command bytes sequence"""
        # Encode strings
        name_bytes = self.name.encode('utf-8')
        text_bytes = self.text.encode('utf-8')

        # Get components
        payload_length = self._calculate_payload_length(name_bytes, text_bytes)
        versioning_byte = self._get_versioning_byte()
        fixed_bytes = self._get_fixed_bytes()

        # Assemble command
        command = (
            bytes([
                self.command,
                payload_length & 0xFF,
                NoteConstants.FIXED_BYTE,
                versioning_byte,
            ]) 
            + fixed_bytes 
            + bytes([
                self.note_number,
                NoteConstants.FIXED_BYTE_2,
                len(name_bytes) & 0xFF,
            ]) 
            + name_bytes 
            + bytes([
                len(text_bytes) & 0xFF,
                NoteConstants.FIXED_BYTE,
            ]) 
            + text_bytes
        )

        return command
