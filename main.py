import json
import flet as ft
from even_glasses import GlassesProtocol
from even_glasses import Notification, NCSNotification

glasses = GlassesProtocol()


async def main(page: ft.Page):
    page.title = "Glasses Control Panel"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = (
        ft.MainAxisAlignment.START
    )  # Changed to START for better layout
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO  # Enable page-wide scrolling

    connected = False  # Track connection status

    status_header = ft.Text(value="Glasses Status", size=20, weight=ft.FontWeight.BOLD)
    left_status = ft.Text(value="Left Glass: Disconnected", size=14)
    right_status = ft.Text(value="Right Glass: Disconnected", size=14)

    # Existing Message Input and Send Button
    message_input = ft.TextField(label="Message to send", width=400)
    send_button = ft.ElevatedButton(text="Send Message", disabled=True)

    # New Notification Input Fields
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

    # New Send Notification Button
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

    def log_message(message):
        log_output.value += message + "\n"
        page.update()

    def on_status_changed(address, status):
        nonlocal connected
        for glass in glasses.glasses.values():
            if glass.side == "left":
                left_status.value = f"Left Glass ({glass.name[:13]}): {status}"
                log_message(f"Left Glass ({glass.name[:13]}): {status}")

            elif glass.side == "right":
                right_status.value = f"Right Glass ({glass.name[:13]}): {status}"
                log_message(f"Right Glass ({glass.name[:13]}): {status}")
        # Check connection status
        connected = any(glass.client.is_connected for glass in glasses.glasses.values())
        connect_button.visible = not connected
        disconnect_button.visible = connected
        send_button.disabled = not connected
        send_notification_button.disabled = not connected
        page.update()

    glasses.on_status_changed = on_status_changed

    async def connect_glasses(e):
        connect_button.disabled = True
        page.update()
        await glasses.scan_and_connect(timeout=10)
        connect_button.disabled = False
        page.update()

    async def disconnect_glasses(e):
        disconnect_button.disabled = True
        page.update()
        await glasses.graceful_shutdown()
        left_status.value = "Left Glasses: Disconnected"
        right_status.value = "Right Glasses: Disconnected"
        log_message("Disconnected all glasses.")
        connect_button.visible = True
        disconnect_button.visible = False
        send_button.disabled = True
        send_notification_button.disabled = True
        page.update()

    async def send_message(e):
        msg = message_input.value
        if msg:
            await glasses.send_text(msg)
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

            notification = Notification(
                ncs_notification=NCSNotification(
                    msg_id=msg_id,
                    app_identifier=app_identifier,
                    title=title,
                    subtitle=subtitle,
                    message=message,
                    display_name=display_name,
                ),
                type="Add",
            )

            await glasses.send_notification(notification)
            log_message(
                f"Sent notification: {json.dumps(notification.model_dump(by_alias=True), separators=(',', ':')) }"
            )

            # Clear input fields after sending
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


if __name__ == "__main__":
    ft.app(target=main)
