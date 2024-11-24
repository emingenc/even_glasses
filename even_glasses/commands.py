from even_glasses.models import (
    SendResult,
    ScreenAction,
    AIStatus,
    RSVPConfig,
    NCSNotification,
    SilentModeStatus,
    BrightnessAuto,
    DashboardState,
    GlassesWearStatus,
)
import asyncio
import logging
from typing import List
from even_glasses.utils import (
    construct_note_add,
    construct_silent_mode,
    construct_brightness,
    construct_dashboard_show_state,
    construct_headup_angle,
    construct_note_delete,
    construct_notification,
    construct_glasses_wear_command,
    divide_image_data,
    construct_bmp_data_packet,
    send_data_to_glass,
)
import numpy as np


def format_text_lines(text: str) -> list:
    """Format text into lines that fit the display."""
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    lines = []

    for paragraph in paragraphs:
        while len(paragraph) > 40:
            space_idx = paragraph.rfind(" ", 0, 40)
            if space_idx == -1:
                space_idx = 40
            lines.append(paragraph[:space_idx])
            paragraph = paragraph[space_idx:].strip()
        if paragraph:
            lines.append(paragraph)

    return lines


async def send_text_packet(
    manager,
    text_message: str,
    page_number: int = 1,
    max_pages: int = 1,
    screen_status: int = ScreenAction.NEW_CONTENT | AIStatus.DISPLAYING,
    wait: float = 2,
    delay: float = 0.4,
    seq: int = 0,
) -> str:
    text_bytes = text_message.encode("utf-8")

    result = SendResult(
        seq=seq,
        total_packages=1,
        current_package=0,
        screen_status=screen_status,
        new_char_pos0=0,
        new_char_pos1=0,
        page_number=page_number,
        max_pages=max_pages,
        data=text_bytes,
    )
    ai_result_command = result.build()

    if manager.left_glass and manager.right_glass:
        # Send to the left glass and wait for acknowledgment
        await manager.left_glass.send(ai_result_command)
        await asyncio.sleep(delay)
        # Send to the right glass and wait for acknowledgment
        await manager.right_glass.send(ai_result_command)
        await asyncio.sleep(delay)

        return text_message
    else:
        logging.error("Could not connect to glasses devices.")
        return False


async def send_text(manager, text_message: str, duration: float = 5) -> str:
    """Send text message to the glasses display."""
    lines = format_text_lines(text_message)
    total_pages = (len(lines) + 4) // 5  # 5 lines per page

    if total_pages > 1:
        logging.info(f"Sending {total_pages} pages with {duration} seconds delay")
        screen_status = AIStatus.DISPLAYING | ScreenAction.NEW_CONTENT
        await send_text_packet(
            manager=manager,
            text_message=lines[0],
            page_number=1,
            max_pages=total_pages,
            screen_status=screen_status,
        )
        await asyncio.sleep(0.1)

    for pn, page in enumerate(range(0, len(lines), 5), start=1):
        page_lines = lines[page : page + 5]

        # Add vertical centering for pages with fewer than 5 lines
        if len(page_lines) < 5:
            padding = (5 - len(page_lines)) // 2
            page_lines = (
                [""] * padding + page_lines + [""] * (5 - len(page_lines) - padding)
            )

        text = "\n".join(page_lines)
        screen_status = AIStatus.DISPLAYING

        await send_text_packet(
            manager=manager,
            text_message=text,
            page_number=pn,
            max_pages=total_pages,
            screen_status=screen_status,
        )

        # Wait after sending each page except the last one
        if pn != total_pages:
            await asyncio.sleep(duration)

    # After all pages, send the last page again with DISPLAY_COMPLETE status
    screen_status = AIStatus.DISPLAY_COMPLETE
    await send_text_packet(
        manager=manager,
        text_message=text,
        page_number=total_pages,
        max_pages=total_pages,
        screen_status=screen_status,
    )

    return text_message


def group_words(words: List[str], config: RSVPConfig) -> List[str]:
    """Group words according to configuration"""
    groups = []
    for i in range(0, len(words), config.words_per_group):
        group = words[i : i + config.words_per_group]
        if len(group) < config.words_per_group:
            group.extend([config.padding_char] * (config.words_per_group - len(group)))
        groups.append(" ".join(group))
    return groups


async def send_rsvp(manager, text: str, config: RSVPConfig):
    """Display text using RSVP method with improved error handling"""
    if not text:
        logging.warning("Empty text provided")
        return False

    try:
        # default delay is 01 second we are adding below to that so we need to calculate the delay
        screen_delay = 60 / config.wpm
        logging.info(f"Words screen change delay: {screen_delay}")
        delay = min(screen_delay - 0.1, 0.1)  # Delay between words set min to 0.1
        words = text.split()
        if not words:
            logging.warning("No words to display after splitting")
            return False

        # Add padding groups for initial display
        padding_groups = [""] * (config.words_per_group - 1)
        word_groups = padding_groups + group_words(words, config)

        for group in word_groups:
            if not group:  # Skip empty padding groups
                await asyncio.sleep(delay * config.words_per_group)
                continue

            success = await send_text(manager, group)
            if not success:
                logging.error(f"Failed to display group: {group}")
                return False

            await asyncio.sleep(delay * config.words_per_group)

        # Clear display
        await send_text(manager, "--")
        return True

    except asyncio.CancelledError:
        logging.info("RSVP display cancelled")
        await send_text(manager, "--")  # Clear display on cancellation
        raise
    except Exception as e:
        logging.error(f"Error in RSVP display: {e}")
        await send_text(manager, "--")  # Try to clear display
        return False


async def send_notification(manager, notification: NCSNotification):
    """Send a notification to the glasses."""
    notification_chunks = await construct_notification(notification)
    for chunk in notification_chunks:
        await send_command_to_glasses(manager, chunk)
        print(f"Sent chunk to glasses: {chunk}")
        await asyncio.sleep(0.01)  # Small delay between chunks


async def execute_command(manager, construct_func, *args, log_message: str = ""):
    """Generic function to construct a command, send it to glasses, and log the action."""
    command = construct_func(*args)
    await send_command_to_glasses(manager, command)
    if log_message:
        logging.info(log_message)


async def show_dashboard(manager, position: int):
    """Show the dashboard at the specified position."""
    await execute_command(
        manager,
        construct_dashboard_show_state,
        DashboardState.ON,
        position,
        log_message=f"Dashboard shown at position {position}.",
    )


async def hide_dashboard(manager, position: int):
    """Hide the dashboard."""
    await execute_command(
        manager,
        construct_dashboard_show_state,
        DashboardState.OFF,
        position,
        log_message="Dashboard hidden.",
    )


async def apply_silent_mode(manager, status: SilentModeStatus):
    """Apply silent mode setting."""
    await execute_command(
        manager,
        construct_silent_mode,
        status,
        log_message=f"Silent Mode set to {status.name}.",
    )


async def apply_brightness(manager, level: int, auto: BrightnessAuto):
    """Apply brightness setting."""
    await execute_command(
        manager,
        construct_brightness,
        level,
        auto,
        log_message=f"Brightness set to {level} with Auto {auto.name}.",
    )


async def apply_headup_angle(manager, angle: int):
    """Set head-up display angle."""
    await execute_command(
        manager,
        construct_headup_angle,
        angle,
        log_message=f"Head-up display angle set to {angle} degrees.",
    )


async def add_or_update_note(manager, note_number: int, title: str, text: str):
    """Add or update a note on the glasses."""
    await execute_command(
        manager,
        construct_note_add,
        note_number,
        title,
        text,
        log_message=f"Note {note_number} added/updated.",
    )


async def delete_note(manager, note_number: int):
    """Delete a note from the glasses."""
    await execute_command(
        manager,
        construct_note_delete,
        note_number,
        log_message=f"Note {note_number} deleted.",
    )


async def send_command_to_glasses(manager, command):
    """Helper function to send a command to the glasses."""
    if manager.left_glass:
        await manager.left_glass.send(command)
        await asyncio.sleep(0.1)
    if manager.right_glass:
        await manager.right_glass.send(command)
        await asyncio.sleep(0.1)


async def apply_glasses_wear(manager, status: GlassesWearStatus):
    """Enable or disable glasses wear detection."""
    await execute_command(
        manager,
        construct_glasses_wear_command,
        status,
        log_message=f"Glasses wear detection set to {status.name}."
    )

async def send_image(manager, image_data: bytes):
    """Send image data to the glasses using optimized functions."""
    # Divide image data into packets using NumPy
    packets_array = divide_image_data(image_data)

    # Preconstruct all data packets using list comprehension
    data_packets = [
        construct_bmp_data_packet(seq, packet_array, seq == 0)
        for seq, packet_array in enumerate(packets_array)
    ]

    # Concatenate image data for CRC
    full_image_array = np.concatenate(packets_array)

    # Send data to left glass first
    if manager.left_glass:
        await send_data_to_glass(manager.left_glass, data_packets, full_image_array)

    # Send data to right glass after acknowledgment from left
    if manager.right_glass:
        await send_data_to_glass(manager.right_glass, data_packets, full_image_array)