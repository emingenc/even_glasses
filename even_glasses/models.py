from enum import IntEnum
from pydantic import BaseModel, Field


class DeviceOrders(IntEnum):
    DISPLAY_READY = 0x00
    DISPLAY_BUSY = 0x11
    DISPLAY_UPDATE = 0x0F
    DISPLAY_COMPLETE = 0x09


class CMD(IntEnum):
    START_EVEN_AI = 0xF5
    OPEN_GLASSES_MIC = 0x0E
    RECEIVE_GLASSES_MIC_DATA = 0xF1

    # System commands
    BLE_REQ_INIT = 0x4D
    BLE_REQ_HEARTBEAT = 0x25
    SEND_AI_RESULT = 0x4E
    BLE_REQ_QUICK_NOTE = 0x21
    BLE_REQ_DASHBOARD = 0x22


class StartEvenAISubCMD(IntEnum):
    EXIT = 0x00  # Exit to dashboard manually
    PAGE_CONTROL = 0x01  # Page up/down control in manual mode
    START = 0x17  # Start Even AI
    STOP = 0x18  # Stop Even AI recording


class MicEnableStatus(IntEnum):
    DISABLE = 0x00
    ENABLE = 0x01


class ResponseStatus(IntEnum):
    SUCCESS = 0xC9 # 201
    FAILURE = 0xCA # 202


class ScreenAction(IntEnum):
    DISPLAY_NEW_CONTENT = 0x01  # Lower 4 bits


class EvenAIStatus(IntEnum):
    DISPLAYING = 0x30  # Initial display
    DISPLAY_COMPLETE = 0x40  # Final display after 3 seconds
    MANUAL_MODE = 0x50  # Manual page turning mode
    NETWORK_ERROR = 0x60  # Error display


class StartEvenAI(BaseModel):
    cmd: CMD = Field(CMD.START_EVEN_AI, description="Start Even AI command")
    subcmd: StartEvenAISubCMD = Field(..., description="Subcommand")
    param: bytes = Field(
        b"", description="Specific parameters associated with each subcommand"
    )


class OpenGlassesMic(BaseModel):
    cmd: CMD = Field(CMD.OPEN_GLASSES_MIC, description="Open Glasses Mic command")
    enable: MicEnableStatus = Field(..., description="Enable or disable the MIC")


class OpenGlassesMicResponse(BaseModel):
    cmd: CMD = Field(CMD.OPEN_GLASSES_MIC, description="Open Glasses Mic response")
    rsp_status: ResponseStatus = Field(..., description="Response Status")
    enable: MicEnableStatus = Field(..., description="MIC status after response")


class ReceiveGlassesMicData(BaseModel):
    cmd: CMD = Field(
        CMD.RECEIVE_GLASSES_MIC_DATA, description="Receive Glasses Mic data"
    )
    seq: int = Field(..., ge=0, le=255, description="Sequence Number (0-255)")
    data: bytes = Field(..., description="Audio Data captured by the MIC")


class SendAIResult(BaseModel):
    cmd: CMD = Field(CMD.SEND_AI_RESULT, description="Send AI Result command")
    seq: int = Field(0, ge=0, le=255, description="Sequence Number (0-255)")
    total_package_num: int = Field(
        191, ge=1, le=255, description="Total number of packages being sent"
    )
    current_package_num: int = Field(
        ..., ge=0, le=255, description="Current package number in transmission"
    )
    newscreen: int = Field(1, description="Combined Screen Status byte")
    current_page_num: int = Field(..., ge=0, le=255, description="Current page number")
    max_page_num: int = Field(20, ge=1, le=255, description="Total number of pages")
    new_char_pos0: int = Field(
        0, ge=0, le=255, description="Higher 8 bits of new character position"
    )
    new_char_pos1: int = Field(
        0, ge=0, le=255, description="Lower 8 bits of new character position"
    )

    def set_newscreen(self, screen_action: ScreenAction, even_ai_status: EvenAIStatus):
        """
        Combines ScreenAction and EvenAIStatus into a single byte for the newscreen field.
        """
        self.newscreen = screen_action.value | even_ai_status.value
