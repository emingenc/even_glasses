import asyncio
import json
import flet as ft
from even_glasses.bluetooth_manager import GlassesManager
from even_glasses.commands import send_text, send_rsvp, send_notification
from even_glasses.models import NCSNotification, RSVPConfig
from even_glasses.notification_handlers import handle_incoming_notification

import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add near the top of the file, before creating the manager
async def log_message(message: str):
    global page, log_output
    if page and log_output:
        log_output.value = f"{time.strftime('%H:%M:%S')} - {message}\n{log_output.value}"
        await page.update_async()

# Initialize GlassesManager with log callback
manager = GlassesManager(
    left_address=None,
    right_address=None,
    log_callback=log_message
)

# Add near the top of the main() function, before creating sections
log_output = ft.Text(
    size=12,
    selectable=True,
    no_wrap=True,
    max_lines=5,
)

# Make page a global variable
page = None

def create_status_section():
    status_header = ft.Text(
        value="Glasses Status", size=16, weight=ft.FontWeight.BOLD
    )
    left_status = ft.Text(value="Left Glass: Disconnected", size=12)
    right_status = ft.Text(value="Right Glass: Disconnected", size=12)
    
    return ft.Column([
        status_header,
        ft.Row(
            [left_status, right_status],
            spacing=20,
        ),
    ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER), left_status, right_status

def create_connection_buttons():
    connect_button = ft.ElevatedButton(text="Connect Glasses")
    disconnect_button = ft.ElevatedButton(text="Disconnect Glasses", visible=False)
    
    return ft.Row(
        [connect_button, disconnect_button],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
    ), connect_button, disconnect_button

def create_message_section():
    message_header = ft.Text(
        value="Send Message", size=18, weight=ft.FontWeight.BOLD
    )
    message_input = ft.TextField(
        label="Message",
        width=400,
        multiline=True,
    )
    send_button = ft.ElevatedButton(text="Send Message", disabled=True)
    
    return ft.Column([
        message_header,
        message_input,
        ft.Row(
            [send_button],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
    ], spacing=10), message_input, send_button

def create_notification_section():
    notification_header = ft.Text(
        value="Send Custom Notification", size=18, weight=ft.FontWeight.BOLD
    )
    msg_id_input = ft.TextField(label="Message ID", width=200, value="1", keyboard_type=ft.KeyboardType.NUMBER)
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

    notification_preset = ft.Dropdown(
        label="Notification Type",
        width=200,
        options=[
            ft.dropdown.Option("Custom", "custom"),
            ft.dropdown.Option("Calendar Event", "calendar"),
            ft.dropdown.Option("Weather Alert", "weather"),
            ft.dropdown.Option("Battery Warning", "battery"),
            ft.dropdown.Option("Navigation", "navigation"),
            ft.dropdown.Option("Fitness Goal", "fitness"),
            ft.dropdown.Option("Reminder", "reminder"),
        ],
        value="custom"
    )

    inputs = ft.Column(
        [
            notification_preset,
            msg_id_input,
            app_identifier_field,
            title_input,
            subtitle_input,
            notification_message_input,
            display_name_input,
        ],
        spacing=10,
    )

    section = ft.Column(
        [
            notification_header,
            inputs,
            ft.Row(
                [send_notification_button],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=20,
            ),
        ],
        spacing=10,
    )

    return section, msg_id_input, app_identifier_field, title_input, subtitle_input, notification_message_input, display_name_input, send_notification_button, notification_preset

def create_rsvp_section():
    rsvp_header = ft.Text(
        value="RSVP Reader", size=18, weight=ft.FontWeight.BOLD
    )
    words_per_group = ft.TextField(
        label="Words per group",
        width=150,
        value="1",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    wpm_input = ft.TextField(
        label="Words per minute",
        width=150,
        value="200",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    padding_char = ft.TextField(
        label="Padding character",
        width=150,
        value="...",
    )
    rsvp_text = ft.TextField(
        label="Text to read",
        width=400,
        multiline=True,
        min_lines=3,
        value="Enter text here to read using RSVP...",
    )
    start_rsvp_button = ft.ElevatedButton(text="Start RSVP", disabled=True)
    rsvp_status = ft.Text(value="RSVP Status: Ready", size=14)

    return ft.Column([
        rsvp_header,
        ft.Row(
            [words_per_group, wpm_input, padding_char],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
        rsvp_text,
        ft.Row(
            [start_rsvp_button, rsvp_status],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
    ], spacing=10), words_per_group, wpm_input, padding_char, rsvp_text, start_rsvp_button, rsvp_status

def create_timer_section():
    timer_header = ft.Text(
        value="Timer Control", size=18, weight=ft.FontWeight.BOLD
    )
    minutes_input = ft.TextField(
        label="Minutes",
        width=100,
        value="1",
        keyboard_type=ft.KeyboardType.NUMBER
    )
    seconds_input = ft.TextField(
        label="Seconds",
        width=100,
        value="0",
        keyboard_type=ft.KeyboardType.NUMBER
    )
    start_timer_button = ft.ElevatedButton(text="Start Timer", disabled=True)
    stop_timer_button = ft.ElevatedButton(text="Stop Timer", disabled=True)
    completion_type = ft.Dropdown(
        label="Completion Alert",
        width=200,
        options=[
            ft.dropdown.Option("Simple", "Simple"),
            ft.dropdown.Option("Detailed", "Detailed"),
        ],
        value="Simple"
    )
    silent_mode = ft.Switch(label="Silent Mode", value=False)
    status_indicator = ft.ProgressRing(width=16, height=16, visible=False)
    timer_status = ft.Text(value="Timer: Ready", size=14)

    return ft.Column([
        timer_header,
        ft.Row(
            [minutes_input, seconds_input],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
        ft.Row(
            [silent_mode, status_indicator],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        ft.Row(
            [completion_type],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        ft.Row(
            [start_timer_button, stop_timer_button, timer_status],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
    ], spacing=10), minutes_input, seconds_input, start_timer_button, stop_timer_button, timer_status, silent_mode, status_indicator, completion_type

def create_pomodoro_section():
    pomodoro_header = ft.Text(
        value="Pomodoro Timer", size=18, weight=ft.FontWeight.BOLD
    )
    
    work_duration = ft.TextField(
        label="Work Duration (min)",
        width=150,
        value="25",
        keyboard_type=ft.KeyboardType.NUMBER
    )
    short_break = ft.TextField(
        label="Short Break (min)",
        width=150,
        value="5",
        keyboard_type=ft.KeyboardType.NUMBER
    )
    long_break = ft.TextField(
        label="Long Break (min)",
        width=150,
        value="15",
        keyboard_type=ft.KeyboardType.NUMBER
    )
    cycles_before_long = ft.TextField(
        label="Cycles before long break",
        width=150,
        value="4",
        keyboard_type=ft.KeyboardType.NUMBER
    )

    start_pomodoro = ft.ElevatedButton(text="Start Pomodoro")
    stop_pomodoro = ft.ElevatedButton(text="Stop Pomodoro", disabled=True)
    skip_phase = ft.ElevatedButton(
        text="Skip Phase",
        visible=True,  # Keep visible
        bgcolor=ft.colors.BLUE_400,
        disabled=True  # Start disabled
    )
    
    pomodoro_status = ft.Text(value="Pomodoro: Ready", size=14)
    cycle_count = ft.Text(value="Cycle: 0/4", size=14)
    phase_indicator = ft.Text(value="Phase: Not Started", size=14, color=ft.colors.BLUE)
    
    auto_start_breaks = ft.Switch(label="Auto-start breaks", value=True)
    notification_type = ft.Dropdown(
        label="Phase Change Alert",
        width=200,
        options=[
            ft.dropdown.Option("Simple", "Simple"),
            ft.dropdown.Option("Detailed", "Detailed"),
        ],
        value="Simple"
    )

    # Create the row with all three buttons
    button_row = ft.Row(
        [start_pomodoro, stop_pomodoro, skip_phase],
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=20,
    )

    return ft.Column([
        pomodoro_header,
        ft.Row(
            [work_duration, short_break, long_break, cycles_before_long],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
        ft.Row(
            [auto_start_breaks, notification_type],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
        button_row,  # Use the button row here
        ft.Row(
            [pomodoro_status, cycle_count, phase_indicator],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20,
        ),
    ], spacing=10), work_duration, short_break, long_break, cycles_before_long, start_pomodoro, stop_pomodoro, skip_phase, pomodoro_status, cycle_count, phase_indicator, auto_start_breaks, notification_type

async def main(page_: ft.Page):
    global page, manager
    page = page_

    # Create log output first
    log_output = ft.Text(
        size=12,
        selectable=True,
        no_wrap=True,
        max_lines=5,
    )

    # Define log message function
    async def log_message(message: str):
        log_output.value = f"{time.strftime('%H:%M:%S')} - {message}\n{log_output.value}"
        await page.update_async()

    # Initialize manager with callback
    manager = GlassesManager(log_callback=log_message)

    page.title = "Glasses Control Panel"
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.padding = 20
    page.scroll = ft.ScrollMode.AUTO

    # Declare variables at the top
    connected = False
    timer_task = None
    pomodoro_task = None
    current_cycle = 0
    is_break = False

    # Create connection buttons first
    connection_buttons, connect_button, disconnect_button = create_connection_buttons()
    
    # Create status section
    status_section, left_status, right_status = create_status_section()
    # connection_buttons, connect_button, disconnect_button = create_connection_buttons()
    message_section, message_input, send_button = create_message_section()
    notification_section, msg_id_input, app_identifier_field, title_input, subtitle_input, notification_message_input, display_name_input, send_notification_button, notification_preset = create_notification_section()
    rsvp_section, words_per_group, wpm_input, padding_char, rsvp_text, start_rsvp_button, rsvp_status = create_rsvp_section()
    timer_section, minutes_input, seconds_input, start_timer_button, stop_timer_button, timer_status, silent_mode, status_indicator, completion_type = create_timer_section()
    pomodoro_section, work_duration, short_break, long_break, cycles_before_long, start_pomodoro, stop_pomodoro, skip_phase, pomodoro_status, cycle_count, phase_indicator, auto_start_breaks, notification_type = create_pomodoro_section()

    # Initialize button states
    stop_pomodoro.disabled = True
    skip_phase.disabled = True
    # start_pomodoro.disabled = True  # Will be enabled by on_status_changed when connected

    # Create AppBar with status and connection buttons
    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.icons.VISIBILITY),
        leading_width=40,
        title=status_section,
        center_title=True,
        bgcolor=ft.colors.SURFACE_VARIANT,
        actions=[
            connect_button,
            disconnect_button,
        ],
    )

    # Create all sections first
    message_section, message_input, send_button = create_message_section()
    notification_section, msg_id_input, app_identifier_field, title_input, subtitle_input, notification_message_input, display_name_input, send_notification_button, notification_preset = create_notification_section()
    rsvp_section, words_per_group, wpm_input, padding_char, rsvp_text, start_rsvp_button, rsvp_status = create_rsvp_section()
    timer_section, minutes_input, seconds_input, start_timer_button, stop_timer_button, timer_status, silent_mode, status_indicator, completion_type = create_timer_section()
    pomodoro_section, work_duration, short_break, long_break, cycles_before_long, start_pomodoro, stop_pomodoro, skip_phase, pomodoro_status, cycle_count, phase_indicator, auto_start_breaks, notification_type = create_pomodoro_section()

    # Initialize button states
    stop_pomodoro.disabled = True
    skip_phase.disabled = True
    # start_pomodoro.disabled = True  # Will be enabled by on_status_changed when connected

    # Define all your async functions here
    async def connect_glasses(e):
        try:
            connected = await manager.scan_and_connect()
            if connected:
                on_status_changed()
        except Exception as e:
            await log_message(f"Error connecting: {str(e)}")

    async def disconnect_glasses(e):
        disconnect_button.disabled = True
        page.update()
        await manager.disconnect_all()  # Updated method name
        left_status.value = "Left Glass: Disconnected"
        right_status.value = "Right Glass: Disconnected"
        log_message("Disconnected all glasses.")
        on_status_changed()
        disconnect_button.disabled = False
        page.update()

    async def send_message(e):
        msg = message_input.value
        if msg:
            success = await send_text(manager, msg)
            if success:
                log_message(f"Sent message to glasses: {msg}")
            else:
                log_message(f"Failed to send message to glasses: {msg}")
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

            start_rsvp_button.disabled = False
            page.update()

        except ValueError as e:
            log_message(f"RSVP Error: Invalid number format - {str(e)}")
        except Exception as e:
            log_message(f"RSVP Error: {str(e)}")
        finally:
            start_rsvp_button.disabled = False
            page.update()

    async def update_timer_display(total_seconds):
        initial_seconds = total_seconds
        status_indicator.visible = True
        end_time = time.time() + total_seconds
        
        while time.time() < end_time:
            remaining = int(end_time - time.time())
            if not silent_mode.value:
                mins, secs = divmod(remaining, 60)
                time_str = f"{mins:02d}:{secs:02d}"
                await send_text(manager, time_str)
                timer_status.value = f"Timer: {time_str}"
            else:
                timer_status.value = f"Timer: Running silently..."
            
            page.update()
            # Sleep for slightly less than a second to account for processing time
            await asyncio.sleep(0.9)

        # Timer complete
        status_indicator.visible = False
        
        # Format completion message based on completion type
        duration_str = f"{initial_seconds//60}m {initial_seconds%60}s"
        if completion_type.value == "Simple":
            completion_msg = "Timer Done!"
        elif completion_type.value == "Detailed":
            completion_msg = f"⏰ Timer Complete! ({duration_str})"
        else:
            completion_msg = "Timer Done!"  # fallback
        
        await send_text(manager, completion_msg)
        timer_status.value = f"Timer: Complete ({duration_str})"
        start_timer_button.disabled = False
        stop_timer_button.disabled = True
        page.update()

    async def start_timer(e):
        nonlocal timer_task
        try:
            mins = int(minutes_input.value)
            secs = int(seconds_input.value)
            total_seconds = mins * 60 + secs
            
            if total_seconds <= 0:
                log_message("Please enter a valid time greater than 0 seconds")
                return
            
            start_timer_button.disabled = True
            stop_timer_button.disabled = False
            page.update()
            
            timer_task = asyncio.create_task(update_timer_display(total_seconds))
            
        except ValueError:
            log_message("Please enter valid numbers for minutes and seconds")

    async def stop_timer(e):
        nonlocal timer_task
        if timer_task:
            timer_task.cancel()
            timer_task = None
            timer_status.value = "Timer: Stopped"
            start_timer_button.disabled = False
            stop_timer_button.disabled = True
            await send_text(manager, "Timer Stopped")
            page.update()

    async def update_pomodoro_display(work_mins, short_break_mins, long_break_mins, max_cycles):
        nonlocal current_cycle, is_break, pomodoro_task
        
        while True:
            # Determine current phase duration
            if is_break:
                if current_cycle >= max_cycles:
                    duration = long_break_mins
                    phase_indicator.value = "Phase: Long Break"
                    phase_indicator.color = ft.colors.ORANGE
                else:
                    duration = short_break_mins
                    phase_indicator.value = "Phase: Short Break"
                    phase_indicator.color = ft.colors.GREEN
            else:
                duration = work_mins
                phase_indicator.value = "Phase: Work"
                phase_indicator.color = ft.colors.RED
            
            # Convert to seconds
            total_seconds = duration * 60
            end_time = time.time() + total_seconds
            
            # Update cycle counter
            cycle_count.value = f"Cycle: {current_cycle}/{max_cycles}"
            
            # Timer loop
            while time.time() < end_time:
                remaining = int(end_time - time.time())
                mins, secs = divmod(remaining, 60)
                time_str = f"{mins:02d}:{secs:02d}"
                
                if not silent_mode.value:
                    await send_text(manager, time_str)
                pomodoro_status.value = f"Pomodoro: {time_str}"
                page.update()
                await asyncio.sleep(0.9)
            
            # Phase complete
            if is_break:
                if current_cycle >= max_cycles:
                    # Pomodoro set complete
                    msg = "Pomodoro complete! Great work! 🎉"
                    current_cycle = 0
                    is_break = False
                    pomodoro_status.value = "Pomodoro: Complete"
                    await send_text(manager, msg)
                    break
                else:
                    msg = "Break complete! Time to work! 💪"
                    is_break = False
            else:
                current_cycle += 1
                is_break = True
                if current_cycle >= max_cycles:
                    msg = "Work phase complete! Time for a long break! 🌟"
                else:
                    msg = "Work phase complete! Time for a short break! ☕"
            
            # Send completion message
            if notification_type.value == "Detailed":
                await send_text(manager, f"⏰ {msg}")
            else:
                await send_text(manager, msg)
            
            # Auto-start next phase or stop
            if not auto_start_breaks.value:
                pomodoro_status.value = "Pomodoro: Waiting to start next phase"
                start_pomodoro.disabled = False
                stop_pomodoro.disabled = True
                skip_phase.disabled = True
                break
        
        # Reset buttons when complete
        start_pomodoro.disabled = False
        stop_pomodoro.disabled = True
        skip_phase.disabled = True
        page.update()

    async def start_pomodoro_handler(e):
        nonlocal pomodoro_task, current_cycle, is_break
        try:
            log_message("Starting pomodoro...")
            
            # Get durations
            work_mins = int(work_duration.value)
            short_mins = int(short_break.value)
            long_mins = int(long_break.value)
            max_cycles = int(cycles_before_long.value)
            
            # Update button states
            start_pomodoro.disabled = True
            stop_pomodoro.disabled = False
            skip_phase.disabled = False
            
            log_message("Enabling skip button")
            
            # Force update the page
            page.update()
            
            # Start the pomodoro timer
            pomodoro_task = asyncio.create_task(
                update_pomodoro_display(work_mins, short_mins, long_mins, max_cycles)
            )
            
        except Exception as e:
            log_message(f"Error in start_pomodoro: {str(e)}")

    async def stop_pomodoro_handler(e):
        nonlocal pomodoro_task, current_cycle, is_break
        if pomodoro_task:
            pomodoro_task.cancel()
            pomodoro_task = None
            current_cycle = 0
            is_break = False
            pomodoro_status.value = "Pomodoro: Stopped"
            phase_indicator.value = "Phase: Not Started"
            phase_indicator.color = ft.colors.BLUE
            cycle_count.value = f"Cycle: 0/{cycles_before_long.value}"
            start_pomodoro.disabled = False
            stop_pomodoro.disabled = True
            skip_phase.visible = False  # Hide skip button when stopped
            await send_text(manager, "Pomodoro Stopped")
            page.update()

    async def skip_phase_handler(e):
        log_message("Skip button clicked!")  # Debug log
        nonlocal pomodoro_task
        if pomodoro_task:
            pomodoro_task.cancel()
            pomodoro_task = None
            # Start new phase
            work_mins = int(work_duration.value)
            short_mins = int(short_break.value)
            long_mins = int(long_break.value)
            max_cycles = int(cycles_before_long.value)
            pomodoro_task = asyncio.create_task(
                update_pomodoro_display(work_mins, short_mins, long_mins, max_cycles)
            )

    # Update Status Function
    def on_status_changed():
        nonlocal connected
        left_glass = manager.left_glass
        right_glass = manager.right_glass

        previous_connected = connected

        # Update left glass status
        if left_glass and left_glass.client.is_connected:
            if left_glass.last_heartbeat and time.time() - left_glass.last_heartbeat < 10:
                emoji = "❤️"  # Recent heartbeat
            else:
                emoji = "💀"  # No recent heartbeat
            left_status.value = f"Left Glass ({left_glass.name[:13]}): Connected {emoji}"
        else:
            left_status.value = "Left Glass: Disconnected"

        # Update right glass status
        if right_glass and right_glass.client.is_connected:
            if right_glass.last_heartbeat and time.time() - right_glass.last_heartbeat < 10:
                emoji = "❤️"  # Recent heartbeat
            else:
                emoji = "💀"  # No recent heartbeat
            right_status.value = f"Right Glass ({right_glass.name[:13]}): Connected {emoji}"
        else:
            right_status.value = "Right Glass: Disconnected"

        connected = (
            (left_glass and left_glass.client.is_connected)
            or (right_glass and right_glass.client.is_connected)
        )

        # Update button states
        connect_button.visible = not connected
        disconnect_button.visible = connected
        send_button.disabled = not connected
        send_notification_button.disabled = not connected
        start_rsvp_button.disabled = not connected
        start_timer_button.disabled = not connected
        start_pomodoro.disabled = not connected
        skip_phase.disabled = True
        page.update()

    # Create the status monitor
    async def status_monitor():
        while True:
            await asyncio.sleep(1)
            on_status_changed()

    # Start the monitor task
    asyncio.create_task(status_monitor())

    # Assign all event handlers
    connect_button.on_click = connect_glasses
    disconnect_button.on_click = disconnect_glasses
    send_button.on_click = send_message
    send_notification_button.on_click = send_custom_notification
    start_rsvp_button.on_click = start_rsvp
    start_timer_button.on_click = start_timer
    stop_timer_button.on_click = stop_timer
    start_pomodoro.on_click = start_pomodoro_handler
    stop_pomodoro.on_click = stop_pomodoro_handler
    skip_phase.on_click = skip_phase_handler

    # Create main layout
    main_content = ft.Column(
        [
            ft.Divider(),
            message_section,
            ft.Divider(),
            notification_section,
            ft.Divider(),
            rsvp_section,
            ft.Divider(),
            timer_section,
            ft.Divider(),
            pomodoro_section,
            ft.Divider(),
            ft.Text(value="Event Log:", size=16, weight=ft.FontWeight.BOLD),
            log_output,
        ],
        spacing=20,
        expand=True,
    )

    page.add(main_content)

ft.app(target=main)