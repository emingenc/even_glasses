from pydantic import BaseModel, Field
from typing import Literal
import time
import json
from enum import IntEnum
from datetime import datetime


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
    DISPLAYING = 0x30  # Even AI displaying (automatic mode default)
    DISPLAY_COMPLETE = 0x40  # Even AI display complete (last page of automatic mode)
    MANUAL_MODE = 0x50  # Even AI manual mode
    NETWORK_ERROR = 0x60  # Even AI network error


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
