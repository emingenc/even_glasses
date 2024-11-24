import struct
import asyncio
from typing import List
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
    GlassesWearStatus,
)
import numpy as np
import numba


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

def construct_glasses_wear_command(status: GlassesWearStatus) -> bytes:
    """Construct command to set glasses wear detection."""
    return bytes([Command.GLASSES_WEAR, status])


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

@numba.njit
def crc32_numba(data):
    """Compute CRC32 using Numba JIT compilation."""
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xEDB88320
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF

@numba.njit
def divide_image_data_numba(data_array, packet_size):
    """Divide image data into packets using Numba."""
    total_length = data_array.shape[0]
    num_packets = (total_length + packet_size - 1) // packet_size
    packets = []
    for i in range(num_packets):
        start = i * packet_size
        end = min(start + packet_size, total_length)
        packet = data_array[start:end]
        packets.append(packet)
    return packets

def divide_image_data(image_data: bytes) -> List[np.ndarray]:
    """Divide image data into packets of 194 bytes using NumPy."""
    packet_size = 194
    data_array = np.frombuffer(image_data, dtype=np.uint8)
    # Use Numba-optimized function
    packets = divide_image_data_numba(data_array, packet_size)
    return packets

@numba.njit
def construct_bmp_data_packet_numba(seq, data_packet, is_first_packet):
    """Construct BMP data packet with command 0x15 using Numba."""
    command = 0x15
    seq_byte = seq & 0xFF
    if is_first_packet:
        address = np.array([0x00, 0x1C, 0x00, 0x00], dtype=np.uint8)
        packet_header = np.array([command, seq_byte], dtype=np.uint8)
        full_packet = np.concatenate((packet_header, address, data_packet))
    else:
        packet_header = np.array([command, seq_byte], dtype=np.uint8)
        full_packet = np.concatenate((packet_header, data_packet))
    return full_packet

def construct_bmp_data_packet(seq: int, data_packet: np.ndarray, is_first_packet: bool) -> np.ndarray:
    """Construct BMP data packet with command 0x15."""
    return construct_bmp_data_packet_numba(seq, data_packet, is_first_packet)

def construct_packet_end_command() -> bytes:
    """Construct packet end command [0x20, 0x0d, 0x0e]."""
    return bytes([0x20, 0x0D, 0x0E])

@numba.njit
def construct_crc_check_command_numba(image_data_array):
    """Construct CRC check command with command 0x16 using Numba."""
    command = 0x16
    address = np.array([0x00, 0x1C, 0x00, 0x00], dtype=np.uint8)
    crc_data = np.concatenate((address, image_data_array))
    crc = crc32_numba(crc_data) & 0xFFFFFFFF
    crc_bytes = np.array([
        (crc >> 24) & 0xFF,
        (crc >> 16) & 0xFF,
        (crc >> 8) & 0xFF,
        crc & 0xFF
    ], dtype=np.uint8)
    full_command = np.concatenate((np.array([command], dtype=np.uint8), crc_bytes))
    return full_command

def construct_crc_check_command(image_data_array: np.ndarray) -> bytes:
    """Construct CRC check command with command 0x16."""
    command_array = construct_crc_check_command_numba(image_data_array)
    return command_array.tobytes()

async def send_data_to_glass(glass, data_packets: List[np.ndarray], full_image_array: np.ndarray):
    """Send data packets to a single glass."""
    # Send all data packets sequentially
    for data_packet in data_packets:
        await glass.send(data_packet.tobytes())
    # Send packet end command
    packet_end_command = construct_packet_end_command()
    await glass.send(packet_end_command)
    # Wait for acknowledgment (implement according to your protocol)
    await asyncio.sleep(0.00001)
    # Send CRC check command
    crc_check_command = construct_crc_check_command(full_image_array)
    await glass.send(crc_check_command)