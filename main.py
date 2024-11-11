import asyncio
import json
import flet as ft
from flet import alignment
from even_glasses.bluetooth_manager import GlassesManager
from even_glasses.commands import send_text, send_rsvp, send_notification
from even_glasses.models import NCSNotification, RSVPConfig
from even_glasses.notification_handlers import handle_incoming_notification
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize GlassesManager
manager = GlassesManager(left_address=None, right_address=None)

DEBUG = False  # Toggle for debug features

async def main(page: ft.Page):
    page.title = "Glasses Control Panel"
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    connected = False

    # Event Log
    log_output = ft.TextField(
        value="",
        read_only=True,
        multiline=True,
        expand=True,
    )

    def log_message(message):
        log_output.value += message + "\n"
        page.update()

    # Status Components
    def create_status_section():
        status_header = ft.Text(
            value="Glasses Status", size=20, weight=ft.FontWeight.BOLD
        )

        # Status indicators
        left_status_icon = ft.Icon(
            name=ft.icons.RADIO_BUTTON_UNCHECKED,
            color=ft.colors.RED,
            size=16,
        )
        right_status_icon = ft.Icon(
            name=ft.icons.RADIO_BUTTON_UNCHECKED,
            color=ft.colors.RED,
            size=16,
        )

        # Status texts
        left_status_text = ft.Text(value="Left Glass: Disconnected", size=14)
        right_status_text = ft.Text(value="Right Glass: Disconnected", size=14)

        # Combine icons and texts
        left_status_row = ft.Row(
            [left_status_icon, left_status_text],
            spacing=5,
            alignment=ft.MainAxisAlignment.START,
        )
        right_status_row = ft.Row(
            [right_status_icon, right_status_text],
            spacing=5,
            alignment=ft.MainAxisAlignment.START,
        )

        # Combine both statuses
        status_row = ft.Row(
            [left_status_row, right_status_row],
            spacing=20,
            alignment=ft.MainAxisAlignment.START,
        )

        status_section = ft.Column(
            [
                status_header,
                status_row,
            ],
            spacing=10,
            expand=True,
        )

        return status_section, left_status_icon, right_status_icon, left_status_text, right_status_text

    # Connection Buttons
    def create_connection_buttons():
        connect_button = ft.ElevatedButton(
            text="Connect to Glasses",
            tooltip="Search and connect to nearby glasses"
        )
        disconnect_button = ft.ElevatedButton(text="Disconnect Glasses", visible=False)
        return ft.Row(
            [connect_button, disconnect_button],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
            expand=True,
        ), connect_button, disconnect_button

    # Message Input Section
    def create_message_section():
        message_input = ft.TextField(label="Message to Send", expand=True)
        send_button = ft.ElevatedButton(text="Send Message", disabled=True)
        return ft.Column(
            [
                ft.Text(
                    value="Send Text Message",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Row(
                    [message_input, send_button],
                    spacing=10,
                    expand=True,
                ),
            ],
            spacing=10,
            expand=True,
        ), message_input, send_button

    # Notification Input Section
    def create_notification_section():
        notification_header = ft.Text(
            value="Send Custom Notification", size=18, weight=ft.FontWeight.BOLD
        )
        msg_id_input = ft.TextField(
            label="Message ID",
            width=200,
            value="1",
            keyboard_type=ft.KeyboardType.NUMBER,
        )
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
        display_name_input = ft.TextField(
            label="Display Name", width=400, value="Telegram"
        )
        send_notification_button = ft.ElevatedButton(
            text="Send Notification", disabled=True
        )

        inputs = ft.Column(
            [
                ft.Row(
                    [msg_id_input, app_identifier_field],
                    spacing=10,
                    expand=True,
                ),
                ft.Row(
                    [title_input, subtitle_input],
                    spacing=10,
                    expand=True,
                ),
                notification_message_input,
                display_name_input,
            ],
            spacing=10,
            expand=True,
        )

        return (
            ft.Column(
                [
                    notification_header,
                    inputs,
                    ft.Row(
                        [send_notification_button],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            msg_id_input,
            app_identifier_field,
            title_input,
            subtitle_input,
            notification_message_input,
            display_name_input,
            send_notification_button,
        )

    # RSVP Configuration Section
    def create_rsvp_section():
        DEMO_RSVP_TEXT = """Welcome to the RSVP Demo!

This is a demonstration of Rapid Serial Visual Presentation technology. RSVP allows you to read text quickly by showing words in rapid succession at a fixed point. This eliminates the need for eye movement during reading.

Key Benefits of RSVP:
1. Increased reading speed
2. Better focus and concentration
3. Reduced eye strain
4. Improved comprehension
5. Perfect for small displays

How to use this demo:
- Adjust the Words per group setting (1-4 words recommended)
- Set your desired reading speed in Words Per Minute
- Click Start RSVP to begin
- The text will be displayed word by word or in small groups
- You can pause anytime by disconnecting

This demo contains various sentence lengths and punctuation to test the RSVP system's handling of different text patterns. For example, here's a longer sentence with multiple clauses, commas, and other punctuation marks to demonstrate how the system handles complex text structures in real-world scenarios.

Tips for optimal reading:
* Start with a slower speed (300-500 WPM)
* Gradually increase the speed as you get comfortable
* Use smaller word groups for higher speeds
* Take breaks if you feel eye strain

End of demo text. Thank you for trying out the RSVP feature!"""

        rsvp_header = ft.Text(
            value="RSVP Settings", size=18, weight=ft.FontWeight.BOLD
        )
        words_per_group = ft.TextField(
            label="Words per Group",
            width=200,
            value="4",
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        wpm_input = ft.TextField(
            label="Words per Minute",
            width=200,
            value="750",
            keyboard_type=ft.KeyboardType.NUMBER,
        )
        padding_char = ft.TextField(
            label="Padding Character",
            width=200,
            value="---",
        )
        rsvp_text = ft.TextField(
            label="Text for RSVP",
            multiline=True,
            expand=True,
            min_lines=3,
            max_lines=10,
            value=DEMO_RSVP_TEXT,
        )
        start_rsvp_button = ft.ElevatedButton(text="Start RSVP", disabled=True)
        rsvp_status = ft.Text(value="RSVP Status: Ready", size=14)

        config_inputs = ft.Row(
            [words_per_group, wpm_input, padding_char],
            alignment=ft.MainAxisAlignment.START,
            spacing=20,
        )

        return (
            ft.Column(
                [
                    rsvp_header,
                    config_inputs,
                    rsvp_text,
                    ft.Row(
                        [start_rsvp_button, rsvp_status],
                        alignment=ft.MainAxisAlignment.START,
                        spacing=20,
                    ),
                ],
                spacing=10,
            ),
            words_per_group,
            wpm_input,
            padding_char,
            rsvp_text,
            start_rsvp_button,
            rsvp_status,
        )

    # Command Section (Debug)
    def create_command_section():
        command_header = ft.Text(
            value="Send Command (Debug)", size=18, weight=ft.FontWeight.BOLD
        )
        side_input = ft.TextField(
            label="Side (l, r, or leave empty for both)",
            width=200,
        )
        data_input = ft.TextField(
            label="Data (space-separated hex values)",
            width=400,
        )
        send_command_button = ft.ElevatedButton(
            text="Send Command", disabled=True
        )

        inputs = ft.Row(
            [side_input, data_input],
            spacing=10,
        )

        return ft.Column(
            [
                command_header,
                inputs,
                ft.Row(
                    [send_command_button],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=20,
                ),
            ],
            spacing=10,
        ), side_input, data_input, send_command_button

    # Create Components
    status_section, left_status_icon, right_status_icon, left_status_text, right_status_text = create_status_section()
    connection_buttons, connect_button, disconnect_button = create_connection_buttons()
    connection_buttons = ft.Row(
        [connect_button, disconnect_button],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
        expand=True,
    )
    message_section, message_input, send_button = create_message_section()
    (
        notification_section,
        msg_id_input,
        app_identifier_field,
        title_input,
        subtitle_input,
        notification_message_input,
        display_name_input,
        send_notification_button,
    ) = create_notification_section()
    (
        rsvp_section,
        words_per_group,
        wpm_input,
        padding_char,
        rsvp_text,
        start_rsvp_button,
        rsvp_status,
    ) = create_rsvp_section()

    if DEBUG:
        command_section, side_input, data_input, send_command_button = create_command_section()

    # Update Status Function
    def on_status_changed():
        nonlocal connected
        left_glass = manager.left_glass
        right_glass = manager.right_glass

        previous_connected = connected

        # Update left glass status
        if left_glass and left_glass.client.is_connected:
            left_status_icon.name = ft.icons.RADIO_BUTTON_CHECKED
            left_status_icon.color = ft.colors.GREEN
            left_status_text.value = f"Left Glass ({left_glass.name[:13]}): Connected"
        else:
            left_status_icon.name = ft.icons.RADIO_BUTTON_UNCHECKED
            left_status_icon.color = ft.colors.RED
            left_status_text.value = "Left Glass: Disconnected"

        # Update right glass status
        if right_glass and right_glass.client.is_connected:
            right_status_icon.name = ft.icons.RADIO_BUTTON_CHECKED
            right_status_icon.color = ft.colors.GREEN
            right_status_text.value = f"Right Glass ({right_glass.name[:13]}): Connected"
        else:
            right_status_icon.name = ft.icons.RADIO_BUTTON_UNCHECKED
            right_status_icon.color = ft.colors.RED
            right_status_text.value = "Right Glass: Disconnected"

        # Determine overall connection status
        connected = (left_glass and left_glass.client.is_connected) or (
            right_glass and right_glass.client.is_connected
        )

        if connected != previous_connected:
            if connected:
                log_message("Glasses connected.")
            else:
                log_message("Glasses disconnected.")

        connect_button.visible = not connected
        disconnect_button.visible = connected
        send_button.disabled = not connected
        send_notification_button.disabled = not connected
        start_rsvp_button.disabled = not connected
        if DEBUG:
            send_command_button.disabled = not connected
        page.update()

    # Async Event Handlers
    async def connect_glasses(e):
        progress = ft.ProgressRing()
        connect_button.content = ft.Row([progress, ft.Text("Connecting...")])
        connect_button.disabled = True
        page.update()
        connected = await manager.scan_and_connect()

        if connected:
            # Assign notification handlers
            if manager.left_glass:
                manager.left_glass.notification_handler = handle_incoming_notification
            if manager.right_glass:
                manager.right_glass.notification_handler = handle_incoming_notification

        on_status_changed()
        connect_button.disabled = False
        page.update()

    async def disconnect_glasses(e):
        disconnect_button.disabled = True
        page.update()
        await manager.disconnect_all()
        log_message("Disconnected all glasses.")
        on_status_changed()
        disconnect_button.disabled = False
        page.update()

    async def send_message(e):
        try:
            msg = message_input.value
            if not msg:
                page.show_snack_bar(ft.SnackBar(content=ft.Text("Please enter a message")))
                return
            success = await send_text(manager, msg)
            if success:
                log_message(f"Sent message to glasses: {msg}")
            else:
                log_message(f"Failed to send message to glasses: {msg}")
            message_input.value = ""
            page.update()
        except Exception as ex:
            page.show_snack_bar(ft.SnackBar(content=ft.Text(f"Error: {str(ex)}")))

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

            success = await send_notification(manager, notification)
            if success:
                log_message(
                    f"Sent notification: {json.dumps(notification.model_dump(by_alias=True), separators=(',', ':'))}"
                )
            else:
                log_message("Failed to send notification.")

            page.update()
        except ValueError:
            log_message("Invalid Message ID. Please enter a numeric value.")

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
                max_retries=2,
            )

            start_rsvp_button.disabled = True
            rsvp_status.value = "RSVP Status: Running..."
            page.update()

            success = await send_rsvp(manager, rsvp_text.value, config)

            if success:
                rsvp_status.value = "RSVP Status: Complete"
                log_message("RSVP completed successfully.")
            else:
                rsvp_status.value = "RSVP Status: Failed"
                log_message("RSVP failed.")

            page.update()

        except ValueError as e:
            log_message(f"RSVP Error: Invalid number format - {str(e)}")
        except Exception as e:
            log_message(f"RSVP Error: {str(e)}")
        finally:
            start_rsvp_button.disabled = False
            page.update()

    async def send_command_to_device(e):
        device = side_input.value.strip()
        data_str = data_input.value.strip()

        # Process data input
        data_bytes = bytearray()
        if data_str:
            data_items = data_str.split()
            for item in data_items:
                try:
                    data_int = int(item, 16)
                    data_bytes.append(data_int)
                except ValueError:
                    log_message(f"Invalid data value '{item}'. Please enter hex values.")
                    return

        # Determine targets
        if device == '':
            # Send to both devices
            if manager.left_glass:
                await manager.left_glass.send(data_bytes)
            if manager.right_glass:
                await manager.right_glass.send(data_bytes)
        elif device == 'l':
            if manager.left_glass:
                await manager.left_glass.send(data_bytes)
        elif device == 'r':
            if manager.right_glass:
                await manager.right_glass.send(data_bytes)
        else:
            log_message("Invalid device identifier. Use 'l' for left, 'r' for right, or leave empty for both.")
            return

        log_message(f"Sent command to device '{device}': {data_bytes.hex()}")
        page.update()

    def on_keyboard(e: ft.KeyboardEvent):
        if e.key == "Enter" and e.ctrl:
            send_message(None)
    page.on_keyboard_event = on_keyboard

    # Assign Event Handlers
    connect_button.on_click = connect_glasses
    disconnect_button.on_click = disconnect_glasses
    send_button.on_click = send_message
    send_notification_button.on_click = send_custom_notification
    start_rsvp_button.on_click = start_rsvp
    if DEBUG:
        send_command_button.on_click = send_command_to_device

    # Organize UI into Tabs
    tabs = ft.Tabs(
        selected_index=0,
        tabs=[
            ft.Tab(
                text="Messages",
                content=message_section,
                icon=ft.icons.MESSAGE,
            ),
            ft.Tab(
                text="Notifications",
                content=notification_section,
                icon=ft.icons.NOTIFICATIONS,
            ),
            ft.Tab(
                text="RSVP",
                content=rsvp_section,
                icon=ft.icons.VIEW_AGENDA,
            ),
            ft.Tab(
                text="Logs",
                content=ft.Column(
                    [
                        ft.Text(
                            value="Event Log:",
                            size=16,
                            weight=ft.FontWeight.BOLD,
                        ),
                        log_output,
                    ]
                ),
                icon=ft.icons.LIST,
            ),
        ],
        expand=True,
        adaptive=True,
    )

    if DEBUG:
        tabs.tabs.insert(
            3,
            ft.Tab(
                text="Debug",
                content=command_section,
                icon=ft.icons.BUG_REPORT,
            )
        )

    # Main Layout
    main_content = ft.Column(
        [
            # Top status bar
            ft.Container(
                content=ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(
                                            content=status_section,
                                            padding=10,
                                            col={"xs": 12, "sm": 12, "md": 12, "lg": 12, "xl": 12},
                                        ),
                                    ],
                                ),
                                ft.ResponsiveRow(
                                    [
                                        ft.Container(
                                            content=connection_buttons,
                                            padding=10,
                                            col={"xs": 12, "sm": 12, "md": 12, "lg": 12, "xl": 12},
                                        ),
                                    ],
                                ),
                            ],
                            spacing=10,
                        ),
                        padding=10,
                    ),
                ),
            ),
            
            # Main content area with tabs
            ft.Container(
                content=ft.Column(
                    [
                        tabs,
                    ],
                    expand=True,
                    
                ),
                padding=10,
                expand=True,
            ),
        ],
        spacing=20,
        expand=True,
    )

    # Update page settings
    page.padding = ft.padding.all(20)
    page.bgcolor = ft.colors.BACKGROUND

    # Wrap main content in a centered container
    page.add(
        ft.Container(
            content=main_content,
            expand=True,
            margin=ft.margin.only(left=20, right=20),
        )
    )

    # Background task to monitor status
    async def status_monitor():
        while True:
            await asyncio.sleep(1)  # Check every 1 second
            on_status_changed()

    asyncio.create_task(status_monitor())

ft.app(target=main)