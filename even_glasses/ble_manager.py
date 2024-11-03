import asyncio
import logging
from bleak import BleakClient, BleakScanner
from collections import defaultdict
from typing import Callable, Dict, Any, List
import sys
import time
import struct
import json


from even_glasses.models import (
    CMD,
    EvenAIStatus,
    StartEvenAI,
    StartEvenAISubCMD,
    MicEnableStatus,
    ScreenAction,
    SendAIResult,
    Notification,
    RSVPConfig,
    create_notification,
)
from even_glasses.service_identifiers import (
    UART_SERVICE_UUID,
    UART_TX_CHAR_UUID,
    UART_RX_CHAR_UUID,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,  # Set to DEBUG for more detailed logs
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


class BleReceive:
    """BLE Receive Data Structure."""

    def __init__(self, lr="L", cmd=0x00, data=None, is_timeout=False):
        self.lr = lr  # Left or Right
        self.cmd = cmd
        self.data = data if data else bytes()
        self.is_timeout = is_timeout


class Glass:
    """Represents a single glasses device (left or right)."""

    def __init__(self, name: str, address: str, side: str):
        self.name = name
        self.address = address
        self.side = side  # 'left' or 'right'
        self.client = BleakClient(
            address, disconnected_callback=self.handle_disconnection
        )
        self._uart_tx = None
        self._uart_rx = None

        self._heartbeat_seq = 0
        self._heartbeat_task = None
        self._last_heartbeat_time = time.time()

        self._received_ack = False
        self._last_device_order = None
        self.recieved_command_handlers: Dict[int, Callable[[bytes], Any]] = {
            CMD.BLE_REQ_HEARTBEAT: self._handle_heartbeat_response,
            CMD.BLE_REQ_INIT: self._handle_init_response,
        }

    async def connect(self):
        """Connect to the glass device."""
        try:
            await self.client.connect()
            if self.client.is_connected:
                logging.info(
                    f"Connected to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
                await self._discover_services()
                await self.send_init_command()
                await self._start_notifications()
                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            else:
                logging.error(
                    f"Failed to connect to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
        except Exception as e:
            logging.error(
                f"Connection error with {self.side.capitalize()} glass ({self.address}): {e}"
            )

    async def disconnect(self):
        """Disconnect from the glass device."""
        if self.client and self.client.is_connected:
            await self.client.disconnect()

            logging.info(
                f"Disconnected from {self.side.capitalize()} glass: {self.name} ({self.address})."
            )

        # Stop heartbeat loop
        if self._heartbeat_task:
            logging.info(
                f"Stopping heartbeat for {self.side.capitalize()} glass: {self.name} ({self.address})."
            )
            self._heartbeat_task.cancel()  # Cancel the heartbeat task
            try:
                await self._heartbeat_task  # Await cancellation
            except asyncio.CancelledError:
                logging.info(
                    f"Heartbeat task cancelled for {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
            self._heartbeat_task = None

    def handle_disconnection(self, client: BleakClient):
        """Handle device disconnection."""
        logging.warning(
            f"{self.side.capitalize()} glass disconnected: {self.name} ({self.address})."
        )
        asyncio.create_task(self.connect())

    async def _discover_services(self):
        """Discover UART characteristics."""
        try:
            services = await self.client.get_services()
            for service in services:
                if service.uuid.lower() == UART_SERVICE_UUID.lower():
                    for char in service.characteristics:
                        if char.uuid.lower() == UART_TX_CHAR_UUID.lower():
                            self._uart_tx = char.uuid
                        elif char.uuid.lower() == UART_RX_CHAR_UUID.lower():
                            self._uart_rx = char.uuid
            if not self._uart_tx or not self._uart_rx:
                logging.error(
                    f"UART characteristics not found for {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
                await self.disconnect()
        except Exception as e:
            logging.error(
                f"Service discovery error for {self.side.capitalize()} glass ({self.address}): {e}"
            )
            await self.disconnect()

    async def send_command(self, command: bytes):
        """Send a command to the glasses via BLE."""
        logging.debug(
            f"Sending command to {self.side} glass: {self.name} ({self.address}): {command.hex()}"
        )
        await self.client.write_gatt_char(self._uart_tx, command)

    async def send_init_command(self):
        """Send initialization command."""
        init_data = bytes([CMD.BLE_REQ_INIT, 0x01])
        await self.send_command(init_data)

    async def _handle_init_response(self, ble_receive: BleReceive):
        """Handle init response."""
        subcommand = ble_receive.data[0]
        response = "SUCCESS" if subcommand == 201 else "FAILURE"
        logging.info(f"Init response: {response}")

    def handle_notification(self, sender, data):
        """Handle incoming notifications."""
        asyncio.create_task(self.process_notification(data))

    async def process_notification(self, data: bytes):
        """Process the incoming notification data."""
        if not data:
            logging.warning(
                f"Received empty data from {self.side.capitalize()} glass: {self.name} ({self.address})."
            )
            return

        cmd = data[0]
        payload = data[1:]
        logging.debug(
            f"Received command {hex(cmd)} from {self.side.capitalize()} glass ({self.address}): {data.hex()}"
        )
        logging.debug(f"Payload: {payload.hex()}")
        ble_receive = BleReceive(lr=self.side, cmd=cmd, data=payload)
        handler = self.recieved_command_handlers.get(cmd, self.handle_unknown_command)
        await handler(ble_receive)

    async def handle_unknown_command(self, ble_receive: BleReceive):
        """Handle unknown CMD."""
        cmd = ble_receive.cmd
        logging.warning(
            f"Unknown command {hex(cmd) if cmd else 'N/A'} from {self.side.capitalize()} glass: {self.name} ({self.address}): {ble_receive.data.hex()}"
        )

    async def _start_notifications(self):
        """Start notifications on UART RX characteristic."""
        await self.client.start_notify(self._uart_rx, self.handle_notification)
        logging.info(
            f"Subscribed to UART RX notifications for {self.side.capitalize()} glass: {self.name} ({self.address})."
        )

    async def _heartbeat(self):
        """Send a single heartbeat."""
        length = 6
        heartbeat_data = struct.pack(
            "BBBBBB",
            CMD.BLE_REQ_HEARTBEAT,
            length & 0xFF,
            (length >> 8) & 0xFF,
            self._heartbeat_seq % 0xFF,
            0x04,
            self._heartbeat_seq % 0xFF,
        )
        self._heartbeat_seq += 1
        await self.send_command(heartbeat_data)
        logging.info(
            f"Sent heartbeat to {self.side.capitalize()} glass: {heartbeat_data.hex()}"
        )

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to maintain connection."""
        frequency = 5.0  # Heartbeat frequency in seconds
        while self.client.is_connected:
            current_time = time.time()
            if current_time - self._last_heartbeat_time > frequency:
                self._last_heartbeat_time = current_time
                await self._heartbeat()
        self._heartbeat_task.cancel()  # Cancel the heartbeat task
        self._heartbeat_task = None

    async def _handle_heartbeat_response(self, ble_receive: BleReceive):
        """Handle heartbeat response."""
        logging.info(f"Heartbeat ack by {self.side.capitalize()} glass: {self.name}).")
        self._received_ack = True

    async def send_text(self, text: str, new_screen=ScreenAction.DISPLAY_NEW_CONTENT):
        """
        Send text to display on glass with proper formatting and status transitions.
        """
        logging.info(
            f"Sending text to {self.side.capitalize()} glass: {self.name} ({self.address})"
        )

        lines = self.format_text_lines(text)
        total_pages = (len(lines) + 4) // 5  # 5 lines per page
        if len(lines) <= 3:
            display_text = "\n\n" + "\n".join(lines)
            success = await self._send_text_packet(
                display_text, new_screen, EvenAIStatus.DISPLAYING, 1, 1
            )
            if not success:
                logging.error(
                    f"Failed to send initial text to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
            success = await self._send_text_packet(
                display_text, new_screen, EvenAIStatus.DISPLAY_COMPLETE, 1, 1
            )
            return success

        elif len(lines) <= 5:
            padding = "\n" if len(lines) == 4 else ""
            display_text = padding + "\n".join(lines)
            success = await self._send_text_packet(
                display_text, new_screen, EvenAIStatus.DISPLAYING, 1, 1
            )
            if not success:
                logging.error(
                    f"Failed to send initial text to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )

            success = await self._send_text_packet(
                display_text, new_screen, EvenAIStatus.DISPLAY_COMPLETE, 1, 1
            )
            return success

        else:
            current_page = 1
            start_idx = 0

            while start_idx < len(lines):
                page_lines = lines[start_idx : start_idx + 5]
                display_text = "\n".join(page_lines)

                is_last_page = start_idx + 5 >= len(lines)
                status = (
                    EvenAIStatus.DISPLAYING if not is_last_page else EvenAIStatus.DISPLAY_COMPLETE
                )
                success = await self._send_text_packet(
                    display_text, new_screen, status, current_page, total_pages
                )
                if not success:
                    logging.error(
                        f"Failed to send page {current_page} to {self.side.capitalize()} glass: {self.name} ({self.address})."
                    )

                if not is_last_page:
                    await asyncio.sleep(5)

                start_idx += 5
                current_page += 1

            return True

    async def _send_text_packet(
        self,
        text: str,
        new_screen: ScreenAction,
        status: EvenAIStatus,
        current_page: int,
        max_pages: int,
    ) -> bool:
        """Send a single text packet with proper formatting."""
        logging.info(
            f"Sending text packet to {self.side.capitalize()} glass: {self.name} ({self.address})"
        )
        text_bytes = text.encode("utf-8")

        max_chunk_size = 191

        chunks = [
            text_bytes[i : i + max_chunk_size]
            for i in range(0, len(text_bytes), max_chunk_size)
        ]

        ai_result = SendAIResult(
            seq=0,
            total_package_num=191,
            current_package_num=len(chunks),
            current_page_num=current_page,
            max_page_num=max_pages,
            new_char_pos0=0,
            new_char_pos1=0,
        )

        ai_result.set_newscreen(new_screen, status)

        for i, chunk in enumerate(chunks):
            self._received_ack = False
            header = struct.pack(
                ">BBBBBBBB",
                ai_result.cmd,
                ai_result.seq % 0xFF,
                ai_result.current_package_num,
                i,
                ai_result.newscreen,  # screen status byte
                ai_result.new_char_pos0,  # pos high byte
                ai_result.new_char_pos1,  # pos low byte
                ai_result.current_page_num,
            )
            packet = header + bytes([ai_result.max_page_num]) + chunk

            await self.send_command(packet)
            logging.debug(
                f"Sent text packet to {self.side.capitalize()} glass: {packet.hex()}"
            )
            if not await self._wait_for_display_complete(timeout=0.1):
                return False

        return True

    async def _wait_for_display_complete(self, timeout=2.0):
        """Wait for display complete status"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._received_ack:
                return True
            await asyncio.sleep(0.01)
        return False

    def format_text_lines(self, text: str) -> list:
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


class EvenGlass(Glass):
    """Represents an EvenGlass device with specific command handlers."""

    def __init__(self, name: str, address: str, side: str):
        super().__init__(name, address, side)
        self.audio_buffer = bytearray()
        self._ack_event = asyncio.Event()
        recive_handlers = {
            CMD.RECEIVE_GLASSES_MIC_DATA: self._handle_receive_mic_data,
            CMD.MIC_RESPONSE: self._handle_mic_response,
            CMD.BLE_REQ_QUICK_NOTE: self._handle_quick_note,
            CMD.BLE_REQ_DASHBOARD: self._handle_dashboard,
            CMD.START_EVEN_AI: self.even_ai_control,
            CMD.SEND_AI_RESULT: self._handle_send_ai_result,
            CMD.NOTIFICATION: self._handle_notification_response,
        }
        self.recieved_command_handlers.update(recive_handlers)

    # Receive command handlers
    async def _handle_receive_mic_data(self, ble_receive: BleReceive):
        """Handle received mic data."""
        audio_data = ble_receive.data[1:]
        logging.debug(
            f"Received mic data from {self.side.capitalize()} glasses] {audio_data.hex()}"
        )
        self.audio_buffer += audio_data

    async def _handle_mic_response(self, ble_receive: BleReceive):
        """Handle mic response."""
        logging.info(
            f"Received mic response from {self.side.capitalize()} glasses ({self.address})."
        )
        # Implement mic response handling here

        subcommand = ble_receive.data[0]
        # res = ResponseStatus(subcommand)
        response = "SUCCESS" if subcommand == 0xC9 else "FAILURE"
        logging.info(f"MIC response: {response}")

    async def _handle_quick_note(self, ble_receive: BleReceive):
        """Handle quick note command."""
        logging.info(
            f"Received quick note command from {self.side.capitalize()} glasses ({self.address})."
        )
        # Implement quick note handling here

    async def _handle_dashboard(self, ble_receive: BleReceive):
        """Handle dashboard command."""
        logging.info(
            f"Received dashboard command from {self.side.capitalize()} glasses ({self.address})."
        )
        # Implement dashboard handling here

    async def even_ai_control(self, ble_receive: BleReceive):
        """Handle Even AI control commands."""

        cmd = ble_receive.cmd
        subcmd = ble_receive.data[0]
        param = ble_receive.data[1:]

        async def start_even_ai(ble_receive: BleReceive):
            logging.info("Start Even AI")
            await self.open_mic()
            # Implement start Even AI logic here

        async def stop_even_ai(ble_receive: BleReceive):
            logging.info("Stop Even AI")
            # Implement stop Even AI logic here

        async def page_control(ble_receive: BleReceive):
            logging.info("Page Control")
            # Implement page control logic here

        async def exit_even_ai(ble_receive: BleReceive):
            logging.info("Exit Even AI")
            await self.close_mic()
            await self.save_audio_data()
            # Implement exit Even AI logic here

        if subcmd in StartEvenAISubCMD:
            even_ai = StartEvenAI(
                cmd=int(ble_receive.cmd),
                subcmd=ble_receive.data[0],
                param=ble_receive.data[1:],
            )

            logging.info(f"Even AI control command: {even_ai.model_dump_json()}")

            if subcmd == StartEvenAISubCMD.START:
                await start_even_ai(ble_receive)
            elif subcmd == StartEvenAISubCMD.STOP:
                await stop_even_ai(ble_receive)
            elif subcmd == StartEvenAISubCMD.PAGE_CONTROL:
                await page_control(ble_receive)
            elif subcmd == StartEvenAISubCMD.EXIT:
                await exit_even_ai(ble_receive)

            elif subcmd == StartEvenAISubCMD.DASHBOARD_RIGHT:
                logging.info("DASHBOARD_RIGHT")
                logging.info(f"Device {self.side.capitalize()} glasses")
                logging.info(f"Even AI control command: {even_ai.model_dump_json()}")
            elif subcmd == StartEvenAISubCMD.DASHBOARD2:
                logging.info("Dashboard2")
                logging.info(f"Device {self.side.capitalize()} glasses")
                logging.info(f"Even AI control command: {even_ai.model_dump_json()}")
            else:
                logging.info(f"Device {self.side.capitalize()} glasses")
                logging.info(f"Even AI control command: {cmd}, {subcmd}, {param}")

    async def _handle_send_ai_result(self, ble_receive: BleReceive):
        """Handle AI result command."""
        logging.info(
            f"Received AI result command from {self.side.capitalize()} glasses ({self.address})."
        )
        # Implement AI result handling here
        ble_receive
        subcommand = ble_receive.data[0]
        # res = ResponseStatus(subcommand)

        logging.info(f"AI result response: {subcommand}")

    async def _handle_notification_response(self, ble_receive: BleReceive):
        """Handle notification response."""
        logging.info(
            f"Received notification response from {self.side.capitalize()} glasses ({self.address})."
        )
        # Implement notification response handling here

        subcommand = ble_receive.data[0]

        logging.info(f"Notification response: {subcommand}")

    async def open_mic(self):
        """Open the mic."""
        await self.send_command(bytes([CMD.OPEN_GLASSES_MIC, MicEnableStatus.ENABLE]))

    async def close_mic(self):
        """Close the mic."""
        await self.send_command(bytes([CMD.OPEN_GLASSES_MIC, MicEnableStatus.DISABLE]))

    async def save_audio_data(self):
        """Save and decode audio data to WAV file."""
        if self.audio_buffer:
            # Save audio data to WAV file
            logging.info("Saving audio data to WAV file...")
            # with wave.open(filename, "wb") as wf:
            #     wf.setnchannels(1)
            #     wf.setsampwidth(2)
            #     wf.setframerate(16000)
            #     wf.writeframes(self.audio_buffer)

        else:
            logging.warning("Audio buffer is empty; no data to save.")

    async def construct_notification(self, notification: Notification):
        json_str = json.dumps(
            notification.model_dump(by_alias=True), separators=(",", ":")
        )
        logging.info(f"Notification JSON: {json_str}")
        json_bytes = json_str.encode("utf-8")

        # Split the data into chunks of 176 bytes (180 bytes total minus 4-byte header)
        max_chunk_size = 180 - 4  # Subtracting 4 bytes for header
        chunks = [
            json_bytes[i : i + max_chunk_size]
            for i in range(0, len(json_bytes), max_chunk_size)
        ]

        total_chunks = len(chunks)
        encoded_chunks = []
        for index, chunk in enumerate(chunks):
            notify_id = 0

            # Construct the header matching the debug output
            header = bytes([CMD.NOTIFICATION, notify_id, total_chunks, index])

            # Debugging: Print the header values
            print(f"Header Bytes: {[hex(b) for b in header]}")

            encoded_chunk = header + chunk
            encoded_chunks.append(encoded_chunk)
        return encoded_chunks

    async def send_notification(
        self,
        notification: Notification,
    ):
        # Serialize JSON without spaces using json.dumps and model_dump

        notification_chunks = await self.construct_notification(notification)
        for chunk in notification_chunks:
            await self.send_command(chunk)
            print(f"Sent chunk to {self.side}: {chunk.hex()}")
            await asyncio.sleep(0.01)  # Small delay between chunks



class GlassesProtocol:
    """Manages both left and right glasses devices."""

    def __init__(self):
        self.glasses: Dict[str, EvenGlass] = {}  # Keyed by device address
        self.device_names: Dict[str, str] = {}  # Address -> Name
        self.on_status_changed: Callable[[str, str], None] = lambda addr, status: None
        self.reconnect_attempts: Dict[str, int] = defaultdict(int)
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 2  # Initial delay in seconds
        self.reconnection_tasks: Dict[
            str, asyncio.Task
        ] = {}  # Track reconnection tasks
        self._write_lock = asyncio.Semaphore(1) 

    async def scan_and_connect(self, timeout: int = 10):
        """Scan for glasses devices and connect to them."""
        logging.info("Scanning for glasses devices...")
        devices = await BleakScanner.discover(timeout=timeout)
        target_devices = []

        for device in devices:
            device_name = device.name if device.name else "Unknown"
            logging.info(f"Found device: {device_name}, Address: {device.address}")
            if device_name and (
                "_L_" in device_name
                or "_R_" in device_name
                or "Even G1_40" in device_name
            ):
                side = "left" if "_L_" in device_name else "right"
                target_devices.append(
                    {"name": device.name, "address": device.address, "side": side}
                )
                self.device_names[device.address] = device.name

        if not target_devices:
            logging.error("No target glasses devices found.")
            return

        for device in target_devices:
            glass = EvenGlass(
                name=device["name"], address=device["address"], side=device["side"]
            )
            self.glasses[device["address"]] = glass
            asyncio.create_task(self.connect_glass(glass))

    async def connect_glass(self, glass: EvenGlass):
        """Connect to a single glass device with reconnection logic."""
        while self.reconnect_attempts[glass.address] < self.max_reconnect_attempts:
            await glass.connect()
            if glass.client.is_connected:
                await asyncio.sleep(3)
                self.reconnect_attempts[glass.address] = 0
                self.on_status_changed(glass.address, "Connected")
                # Remove any existing reconnection task
                if glass.address in self.reconnection_tasks:
                    del self.reconnection_tasks[glass.address]
                return
            else:
                self.reconnect_attempts[glass.address] += 1
                delay = min(
                    self.reconnect_delay
                    * (2 ** (self.reconnect_attempts[glass.address] - 1)),
                    60,
                )
                logging.info(
                    f"Retrying to connect to {glass.side.capitalize()} glasses ({glass.address}) in {delay} seconds (Attempt {self.reconnect_attempts[glass.address]}/{self.max_reconnect_attempts})."
                )
                await asyncio.sleep(delay)

        logging.error(
            f"Failed to connect to {glass.side.capitalize()} glasses ({glass.address}) after {self.max_reconnect_attempts} attempts."
        )

    async def handle_glass_disconnection(self, glass: EvenGlass):
        """Handle disconnection and initiate reconnection."""
        address = glass.address
        if (
            address in self.reconnection_tasks
            and not self.reconnection_tasks[address].done()
        ):
            logging.info(
                f"Reconnection task already running for {glass.side.capitalize()} glasses ({address})."
            )
            return

        logging.info(
            f"Initiating reconnection for {glass.side.capitalize()} glasses ({address})."
        )
        task = asyncio.create_task(self.connect_glass(glass))
        self.reconnection_tasks[address] = task

    async def send_text(self, text: str):
        """Send text message to all connected glasses."""
        tasks = {}
        for glass in self.glasses.values():
            if glass.client.is_connected:
                tasks[glass.address] = asyncio.create_task(glass.send_text(text))
            else:
                logging.warning(
                    f"{glass.side.capitalize()} glasses ({glass.name} - {glass.address}) are not connected."
                )
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        for addr, result in zip(tasks.keys(), results):
            glass = self.glasses.get(addr)
            if glass:
                if isinstance(result, Exception):
                    logging.error(
                        f"Error sending text to {glass.side.capitalize()} glasses ({glass.address}): {result}"
                    )
                else:
                    logging.info(
                        f"Send text to {glass.side.capitalize()} glasses ({glass.address}) {'succeeded' if result else 'failed'}."
                    )

    async def send_notification(self, notification: Notification):
        tasks = {}
        for glass in self.glasses.values():
            if glass.client.is_connected:
                tasks[glass.address] = asyncio.create_task(
                    glass.send_notification(notification)
                )
            else:
                logging.warning(
                    f"{glass.side.capitalize()} glasses ({glass.name} - {glass.address}) are not connected."
                )
    
    async def _safe_send_text(self, text: str, retries: int = 3) -> bool:
        """Send text with retry mechanism and write lock"""
        async with self._write_lock:
            for attempt in range(retries):
                try:
                    await self.send_text(text)
                    return True
                except Exception as e:
                    if attempt == retries - 1:
                        logging.error(f"Failed to send text after {retries} attempts: {e}")
                        return False
                    await asyncio.sleep(0.01 * (attempt + 1))  # Exponential backoff
        return False

    def _group_words(self, words: List[str], config: RSVPConfig) -> List[str]:
        """Group words according to configuration"""
        groups = []
        for i in range(0, len(words), config.words_per_group):
            group = words[i:i + config.words_per_group]
            if len(group) < config.words_per_group:
                group.extend([config.padding_char] * (config.words_per_group - len(group)))
            groups.append(" ".join(group))
        return groups

    async def send_rsvp(self, text: str, config: RSVPConfig):
        """Display text using RSVP method with improved error handling"""
        if not text:
            logging.warning("Empty text provided")
            return False

        try:
            delay = 60.0 / config.wpm
            words = text.split()
            if not words:
                logging.warning("No words to display after splitting")
                return False

            # Add padding groups for initial display
            padding_groups = [""] * (config.words_per_group - 1)
            word_groups = padding_groups + self._group_words(words, config)

            for group in word_groups:
                if not group:  # Skip empty padding groups
                    await asyncio.sleep(delay * config.words_per_group)
                    continue

                success = await self._safe_send_text(group, config.max_retries)
                if not success:
                    logging.error(f"Failed to display group: {group}")
                    return False
                
                await asyncio.sleep(delay * config.words_per_group)

            # Clear display
            await self._safe_send_text("", config.max_retries)
            return True

        except asyncio.CancelledError:
            logging.info("RSVP display cancelled")
            await self._safe_send_text("")  # Clear display on cancellation
            raise
        except Exception as e:
            logging.error(f"Error in RSVP display: {e}")
            await self._safe_send_text("")  # Try to clear display
            return False

    async def graceful_shutdown(self):
        """Disconnect from all glasses gracefully."""
        logging.info("Shutting down GlassesProtocol...")
        tasks = [glass.disconnect() for glass in self.glasses.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logging.info("GlassesProtocol shut down.")


# Singleton instance
glasses = GlassesProtocol()


async def main():
    try:
        await glasses.scan_and_connect(timeout=10)

        def status_changed(address, status):
            logging.info(f"[{address}] Status changed to: {status}")

        glasses.on_status_changed = status_changed

        while True:
            test_message = "Hello, Glasses!\nThis is a test message.\nEnjoy your day!"
            await glasses.send_text(test_message)
            logging.info("Sent test text message to all glasses.")
            await asyncio.sleep(20)
            notification = create_notification(
                msg_id=1,
                app_identifier="org.telegram.messenger",
                title="Notification Title",
                subtitle="Notification Subtitle",
                message="This is a test notification message.",
                display_name="Example App",
            )
            await glasses.send_notification(notification)

    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt received. Initiating shutdown...")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
    finally:
        await glasses.graceful_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Program terminated by user.")
    except Exception as e:
        logging.error(f"Unhandled exception in main: {e}")
