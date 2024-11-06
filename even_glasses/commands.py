from models import Command, SubCommand, MicStatus, SendResult, ScreenAction, AIStatus
import asyncio


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
    wait: float = 2
) -> str:
    text_bytes = text_message.encode("utf-8")

    result = SendResult(
        seq=manager.evenai_seq,
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

    # Send to the left glass and wait for acknowledgment
    await manager.left_glass.send(ai_result_command)
    await asyncio.wait_for(manager.left_glass.message_queue.get(), wait)
    await asyncio.sleep(0.01)
    # Send to the right glass and wait for acknowledgment
    await manager.right_glass.send(ai_result_command)
    await asyncio.wait_for(manager.right_glass.message_queue.get(), wait)
    # await wait_for_ack(manager.right_glass)
    manager.evenai_seq += 1
    return text_message


async def send_text(manager, text_message: str, wait: float = 3) -> str:
    lines = format_text_lines(text_message)
    total_pages = (len(lines) + 4) // 5  # 5 lines per page

    for pn, page in enumerate(range(0, len(lines), 5), start=1):
        text = "\n".join(lines[page : page + 5])
        screen_status = (
                ScreenAction.NEW_CONTENT | AIStatus.DISPLAYING 
            )
    
        await send_text_packet(
            manager=manager,
            text_message=text,
            page_number=pn,
            max_pages=total_pages,
            screen_status=screen_status,
        )
        if pn != 1:
            await asyncio.sleep(wait)
        if pn == total_pages:
            screen_status = (
                ScreenAction.NEW_CONTENT | AIStatus.DISPLAY_COMPLETE 
            )
        
            await send_text_packet(
                manager=manager,
                text_message=text,
                page_number=pn,
                max_pages=total_pages,
                screen_status=screen_status,
            )
    return text_message


