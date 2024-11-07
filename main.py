import asyncio
import json
import flet as ft
from even_glasses.bluetooth_manager import GlassesManager
from even_glasses.commands import send_text, send_rsvp, send_notification
from even_glasses.models import NCSNotification, RSVPConfig

manager = GlassesManager(left_address=None, right_address=None)

async def main(page: ft.Page):
    page.title = "Glasses Control Panel"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    connected = False

    status_header = ft.Text(value="Glasses Status", size=20, weight=ft.FontWeight.BOLD)
    left_status = ft.Text(value="Left Glass: Disconnected", size=14)
    right_status = ft.Text(value="Right Glass: Disconnected", size=14)

    # Message Input and Send Button
    message_input = ft.TextField(label="Message to send", width=400)
    send_button = ft.ElevatedButton(text="Send Message", disabled=True)

    # Notification Input Fields
    msg_id_input = ft.TextField(label="Message ID", width=200, value="1")
    app_identifier_field = ft.TextField(
        label="App Identifier", width=400, value="org.telegram.messenger"
    )
    title_input = ft.TextField(label="Title", width=400, value="Message")
    subtitle_input = ft.TextField(label="Subtitle", width=400, value="John Doe")
    notification_message_input = ft.TextField(
        label="Notification Message",
        width=400,
        multiline=True,
        value="You have a new message from John Doe.",
    )
    display_name_input = ft.TextField(label="Display Name", width=400, value="Telegram")

    # Send Notification Button
    send_notification_button = ft.ElevatedButton(
        text="Send Notification", disabled=True
    )

    connect_button = ft.ElevatedButton(text="Connect to Glasses")
    disconnect_button = ft.ElevatedButton(text="Disconnect Glasses", visible=False)

    log_label = ft.Text(value="Event Log:", size=16, weight=ft.FontWeight.BOLD)
    log_output = ft.TextField(
        value="",
        read_only=True,
        multiline=True,
        width=750,
        height=500,
    )

    # RSVP Configuration
    rsvp_header = ft.Text(value="RSVP Settings", size=18, weight=ft.FontWeight.BOLD)

    words_per_group = ft.TextField(
        label="Words per group",
        width=200,
        value="4",
        keyboard_type=ft.KeyboardType.NUMBER
    )

    wpm_input = ft.TextField(
        label="Words per minute",
        width=200,
        value="750",
        keyboard_type=ft.KeyboardType.NUMBER
    )

    padding_char = ft.TextField(
        label="Padding character",
        width=200,
        value="---"
    )

    demo_text =  """
        Fast reading apps that display text word by word or in small groups (like two words at a time) are utilizing a technique known as Rapid Serial Visual Presentation (RSVP). Here’s what this means and why it’s used:

What is RSVP?

RSVP is a method where text is presented sequentially in the same spot on the screen, one word or a small cluster of words at a time, rather than in traditional sentence or paragraph formats. This approach is designed to streamline the reading process.

Why Use Word-by-Word or Two-Word Display?

    1.  Minimizes Eye Movement:
    •   Traditional Reading: Involves frequent eye movements (saccades) as your eyes jump from one word to the next and scan across lines.
    •   RSVP Method: Eliminates the need for these movements by keeping the focus point stationary, reducing the time spent shifting gaze.
    2.  Enhances Focus and Reduces Distractions:
    •   Presenting one or two words at a time helps concentrate the reader’s attention on each word without the distraction of surrounding text.
    3.  Increases Reading Speed:
    •   By controlling the pace at which words appear, these apps can gradually increase the speed, training your brain to process information more quickly.
    4.  Improves Comprehension and Retention:
    •   For some users, especially those practicing speed reading techniques, this method can help improve comprehension by forcing the brain to focus intently on each word or pair of words.
    5.  Efficient Use of Time:
    •   Ideal for people looking"""

    rsvp_text = ft.TextField(
        label="Text for RSVP",
        width=750,
        multiline=True,
        min_lines=3,
        max_lines=10,
        value=f"Enter text for rapid serial visual presentation... {demo_text}"
    )

    rsvp_status = ft.Text(value="RSVP Status: Ready", size=14)
    start_rsvp_button = ft.ElevatedButton(text="Start RSVP", disabled=True)

    def log_message(message):
        log_output.value += message + "\n"
        page.update()

    async def start_rsvp(e):
        try:
            words_count = int(words_per_group.value)
            speed = int(wpm_input.value)
            pad_char = padding_char.value or "..."

            config = RSVPConfig(
                words_per_group=words_count,
                wpm=speed,
                padding_char=pad_char,
                retry_delay=0.005,
                max_retries=2
            )

            start_rsvp_button.disabled = True
            rsvp_status.value = "RSVP Status: Running..."
            page.update()

            await send_rsvp(manager, rsvp_text.value, config)

            rsvp_status.value = "RSVP Status: Complete"
            start_rsvp_button.disabled = False
            page.update()

        except ValueError as e:
            log_message(f"RSVP Error: Invalid number format - {str(e)}")
        except Exception as e:
            log_message(f"RSVP Error: {str(e)}")
        finally:
            start_rsvp_button.disabled = False
            page.update()

    start_rsvp_button.on_click = start_rsvp

    def on_status_changed():
        nonlocal connected
        left_glass = manager.left_glass
        right_glass = manager.right_glass

        if left_glass and left_glass.client.is_connected:
            left_status.value = f"Left Glass ({left_glass.name[:13]}): Connected"
            log_message(f"Left Glass ({left_glass.name[:13]}): Connected")
        else:
            left_status.value = "Left Glass: Disconnected"

        if right_glass and right_glass.client.is_connected:
            right_status.value = f"Right Glass ({right_glass.name[:13]}): Connected"
            log_message(f"Right Glass ({right_glass.name[:13]}): Connected")
        else:
            right_status.value = "Right Glass: Disconnected"

        connected = (left_glass and left_glass.client.is_connected) or \
                    (right_glass and right_glass.client.is_connected)
        connect_button.visible = not connected
        disconnect_button.visible = connected
        send_button.disabled = not connected
        send_notification_button.disabled = not connected
        start_rsvp_button.disabled = not connected
        page.update()

    async def connect_glasses(e):
        connect_button.disabled = True
        page.update()
        await manager.scan_and_connect()
        on_status_changed()
        connect_button.disabled = False
        page.update()

    async def disconnect_glasses(e):
        disconnect_button.disabled = True
        page.update()
        await manager.graceful_shutdown()
        left_status.value = "Left Glass: Disconnected"
        right_status.value = "Right Glass: Disconnected"
        log_message("Disconnected all glasses.")
        connect_button.visible = True
        disconnect_button.visible = False
        send_button.disabled = True
        send_notification_button.disabled = True
        start_rsvp_button.disabled = True
        page.update()

    async def send_message(e):
        msg = message_input.value
        if msg:
            await send_text(manager, msg)
            log_message(f"Sent message to glasses: {msg}")
            message_input.value = ""
            page.update()

    async def send_custom_notification(e):
        try:
            msg_id = int(msg_id_input.value)
            app_identifier = app_identifier_field.value
            title = title_input.value
            subtitle = subtitle_input.value
            message = notification_message_input.value
            display_name = display_name_input.value

            notification = NCSNotification(
                msg_id=msg_id,
                app_identifier=app_identifier,
                title=title,
                subtitle=subtitle,
                message=message,
                display_name=display_name,
            )

            await send_notification(manager, notification)
            log_message(
                f"Sent notification: {json.dumps(notification.model_dump(by_alias=True), separators=(',', ':')) }"
            )

            page.update()
        except ValueError:
            log_message("Invalid Message ID. Please enter a numeric value.")

    # Assign async event handlers directly
    connect_button.on_click = connect_glasses
    disconnect_button.on_click = disconnect_glasses
    send_button.on_click = send_message
    send_notification_button.on_click = send_custom_notification

    page.add(
        ft.Column(
            [
                status_header,
                left_status,
                right_status,
                ft.Row(
                    [connect_button, disconnect_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [message_input],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [send_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Divider(),
                ft.Text(
                    value="Send Custom Notification", size=18, weight=ft.FontWeight.BOLD
                ),
                ft.Row(
                    [msg_id_input],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [app_identifier_field],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [title_input],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [subtitle_input],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [notification_message_input],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [display_name_input],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [send_notification_button],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Divider(),
                rsvp_header,
                ft.Row(
                    [words_per_group, wpm_input, padding_char],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [rsvp_text],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Row(
                    [start_rsvp_button, rsvp_status],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
                ft.Divider(),
                log_label,
                ft.Row(
                    [log_output],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=20,
                ),
            ],
            spacing=30,
            expand=True,
        )
    )

ft.app(target=main)