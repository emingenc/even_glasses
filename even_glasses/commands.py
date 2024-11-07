from even_glasses.models import (
    Command,
    SubCommand,
    MicStatus,
    SendResult,
    ScreenAction,
    AIStatus,
    RSVPConfig,
    NCSNotification,
)
import asyncio
import logging
from typing import List
from even_glasses.utils import construct_notification


def construct_start_ai(subcmd: SubCommand, param: bytes = b"") -> bytes:
    return bytes([Command.START_AI, subcmd]) + param


def construct_mic_command(enable: MicStatus) -> bytes:
    return bytes([Command.OPEN_MIC, enable])


def construct_result(result: SendResult) -> bytes:
    return result.build()


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
    lines = format_text_lines(text_message)
    total_pages = (len(lines) + 4) // 5  # 5 lines per page

    for pn, page in enumerate(range(0, len(lines), 5), start=1):
        page_lines = lines[page : page + 5]

        # Add vertical centering for pages with fewer than 5 lines
        if len(page_lines) < 5:
            padding = (5 - len(page_lines)) // 2
            page_lines = (
                [""] * padding + page_lines + [""] * (5 - len(page_lines) - padding)
            )

        text = "\n".join(page_lines)
        screen_status = ScreenAction.NEW_CONTENT | AIStatus.DISPLAYING

        await send_text_packet(
            manager=manager,
            text_message=text,
            page_number=pn,
            max_pages=total_pages,
            screen_status=screen_status,
        )
        if pn != 1 and total_pages != 1:
            await asyncio.sleep(duration)
        if pn == total_pages:
            screen_status = ScreenAction.NEW_CONTENT | AIStatus.DISPLAY_COMPLETE

            await send_text_packet(
                manager=manager,
                text_message=text,
                page_number=pn,
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
        delay = min(screen_delay - 0.1 , 0.1) # Delay between words set min to 0.1
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
            await manager.left_glass.send(chunk)
            await manager.right_glass.send(chunk)
            print(f"Sent chunk to glasses: {chunk}")
            await asyncio.sleep(0.01)  # Small delay between chunks