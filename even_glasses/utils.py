import struct
from even_glasses.models import (
    Command,
    NCSNotification,
    Notification,
    NoteAdd,
    SubCommand,
    MicStatus,
    SendResult,
    SilentModeStatus,
    BrightnessAuto,
    DashboardState,
)


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


def construct_headup_angle(angle: int) -> bytes:
    """Construct command to set head-up display angle."""
    if not 0 <= angle <= 60:
        raise ValueError("Angle must be between 0 and 60 degrees")
    angle_byte = angle & 0xFF
    return bytes([Command.HEADUP_ANGLE, angle_byte, 0x01])


def construct_note_delete(note_number: int) -> bytes:
    """Construct command to delete a note with the given number."""
    if not 1 <= note_number <= 4:
        raise ValueError("Note number must be between 1 and 4")
    return bytes(
        [
            0x1E,
            0x10,
            0x00,
            0xE0,
            0x03,
            0x01,
            0x00,
            0x01,
            0x00,
            note_number,
            0x00,
            0x01,
            0x00,
            0x01,
            0x00,
            0x00,
        ]
    )


def construct_note_add(note_number: int, name: str, text: str) -> bytes:
    """Construct command to add or change a note with a name and text."""
    note_add = NoteAdd(note_number=note_number, name=name, text=text)
    return note_add.build()


def construct_clear_screen() -> bytes:
    """Construct command to clear the screen."""
    return bytes(
        [
            Command.START_AI,
            SubCommand.STOP,
            0x00,
            0x00,
            0x00,
        ]
    )


def construct_start_ai(subcmd: SubCommand, param: bytes = b"") -> bytes:
    return bytes([Command.START_AI, subcmd]) + param


def construct_mic_command(enable: MicStatus) -> bytes:
    return bytes([Command.OPEN_MIC, enable])


def construct_result(result: SendResult) -> bytes:
    return result.build()


def construct_silent_mode(status: SilentModeStatus) -> bytes:
    """Construct command to set silent mode."""
    return bytes([Command.SILENT_MODE, status, 0x00])


def construct_brightness(level: int, auto: BrightnessAuto) -> bytes:
    """Construct command to set brightness with auto setting."""
    if not 0x00 <= level <= 0x29:
        raise ValueError("Brightness level must be between 0x00 and 0x29")
    return bytes([Command.BRIGHTNESS, level, auto])


def construct_dashboard_show_state(state: DashboardState, position: int) -> bytes:
    """Construct command to show or hide the dashboard with position."""
    state_value = 0x01 if state == DashboardState.ON else 0x00
    return bytes(
        [Command.DASHBOARD_POSITION, 0x07, 0x00, 0x01, 0x02, state_value, position]
    )
