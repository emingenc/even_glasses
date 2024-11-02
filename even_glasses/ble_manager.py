import asyncio
import logging
from bleak import BleakClient, BleakScanner
from collections import defaultdict
from typing import Callable, Dict, Any
import sys
import wave
import time
import struct

from even_glasses.enums import Commands, DisplayStatus, DeviceOrders
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
        self._evenai_seq = 0
        self._received_ack = False
        self._last_device_order = None
        self.command_handlers: Dict[int, Callable[[bytes], Any]] = {}

    async def connect(self):
        """Connect to the glass device."""
        try:
            await self.client.connect()
            if self.client.is_connected:
                logging.info(
                    f"Connected to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
                await self._discover_services()
                await self._send_init_command()
                await self._start_notifications()
                if not self._heartbeat_task or self._heartbeat_task.done():
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

    async def _send_init_command(self):
        """Send initialization command."""
        if self._uart_tx:
            init_data = bytes([Commands.BLE_REQ_INIT, 0x01])
            try:
                await self.client.write_gatt_char(self._uart_tx, init_data)
                logging.info(
                    f"Sent initialization command to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
            except Exception as e:
                logging.error(
                    f"Failed to send init command to {self.side.capitalize()} glass ({self.address}): {e}"
                )

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
        handler = self.command_handlers.get(cmd, self.handle_unknown_command)
        await handler(ble_receive)

    async def handle_unknown_command(self, ble_receive: BleReceive):
        """Handle unknown commands."""
        cmd = ble_receive.cmd
        logging.warning(
            f"Unknown command {hex(cmd) if cmd else 'N/A'} from {self.side.capitalize()} glass: {self.name} ({self.address}): {ble_receive.data.hex()}"
        )

    async def _start_notifications(self):
        """Start notifications on UART RX characteristic."""
        if self._uart_rx:
            try:
                await self.client.start_notify(self._uart_rx, self.handle_notification)
                logging.info(
                    f"Subscribed to UART RX notifications for {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
            except Exception as e:
                logging.error(
                    f"Failed to subscribe to notifications for {self.side.capitalize()} glass ({self.address}): {e}"
                )

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to maintain connection."""
        try:
            while self.client.is_connected:
                try:
                    length = 6
                    heartbeat_data = struct.pack(
                        "BBBBBB",
                        Commands.BLE_REQ_HEARTBEAT,
                        length & 0xFF,
                        (length >> 8) & 0xFF,
                        self._heartbeat_seq % 0xFF,
                        0x04,
                        self._heartbeat_seq % 0xFF,
                    )
                    self._heartbeat_seq += 1
                    await self.client.write_gatt_char(UART_TX_CHAR_UUID, heartbeat_data)
                    logging.debug(
                        f"Sent heartbeat to {self.side.capitalize()} glass: {heartbeat_data.hex()}"
                    )
                    self._received_ack = False
                    await asyncio.sleep(2)
                    if not self._received_ack:
                        logging.warning(
                            f"No heartbeat ack from {self.side.capitalize()} glass: {self.name}"
                        )

                except Exception as e:
                    logging.error(
                        f"Error during heartbeat with {self.side.capitalize()} glass ({self.address}): {e}"
                    )
                    await self.client.disconnect()
                    self._heartbeat_task.cancel()
                    self._heartbeat_task = None
                    break
        except asyncio.CancelledError:
            logging.info(
                f"Heartbeat loop cancelled for {self.side.capitalize()} glass: {self.name} ({self.address})."
            )
            raise  # Re-raise to ensure the task is properly cancelled

    async def _handle_heartbeat_response(self, ble_receive: BleReceive):
        """Handle heartbeat response."""
        logging.info(
            f"Heartbeat {self.side.capitalize()} glass: {self.name} ({self.address})."
        )
        self._received_ack = True

    async def send_text(self, text: str, new_screen=1):
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
                display_text, new_screen, DisplayStatus.NORMAL_TEXT, 1, 1
            )
            if not success:
                logging.error(
                    f"Failed to send initial text to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
                return False
            await asyncio.sleep(1)
            success = await self._send_text_packet(
                display_text, new_screen, DisplayStatus.FINAL_TEXT, 1, 1
            )
            return success

        elif len(lines) <= 5:
            padding = "\n" if len(lines) == 4 else ""
            display_text = padding + "\n".join(lines)
            success = await self._send_text_packet(
                display_text, new_screen, DisplayStatus.NORMAL_TEXT, 1, 1
            )
            if not success:
                logging.error(
                    f"Failed to send initial text to {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
                return False
            await asyncio.sleep(1)
            success = await self._send_text_packet(
                display_text, new_screen, DisplayStatus.FINAL_TEXT, 1, 1
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
                    DisplayStatus.FINAL_TEXT
                    if is_last_page
                    else DisplayStatus.NORMAL_TEXT
                )

                success = await self._send_text_packet(
                    display_text, new_screen, status, current_page, total_pages
                )
                if not success:
                    logging.error(
                        f"Failed to send page {current_page} to {self.side.capitalize()} glass: {self.name} ({self.address})."
                    )
                    return False

                if not is_last_page:
                    await asyncio.sleep(5)

                start_idx += 5
                current_page += 1

            return True

    async def _send_text_packet(
        self,
        text: str,
        new_screen: int,
        status: DisplayStatus,
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

        for i, chunk in enumerate(chunks):
            self._received_ack = False
            header = struct.pack(
                ">BBBBBBBB",
                Commands.BLE_REQ_EVENAI,
                self._evenai_seq % 0xFF,
                len(chunks),
                i,
                status | new_screen,
                0,  # pos high byte
                0,  # pos low byte
                current_page,
            )
            packet = header + bytes([max_pages]) + chunk

            await self.client.write_gatt_char(UART_TX_CHAR_UUID, packet)
            logging.debug(
                f"Sent text packet to {self.side.capitalize()} glass: {packet.hex()}"
            )
            if not await self._wait_for_display_complete(timeout=3.0):
                return False
            await asyncio.sleep(0.1)

        return True

    async def _wait_for_display_complete(self, timeout=2.0):
        """Wait for display complete status"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._received_ack:
                return True
            await asyncio.sleep(0.1)
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
        self.command_handlers: Dict[int, Callable[[BleReceive], Any]] = {
            Commands.BLE_REQ_HEARTBEAT: self._handle_heartbeat_response,
            Commands.BLE_REQ_TRANSFER_MIC_DATA: self.handle_voice_data,
            Commands.BLE_REQ_EVENAI: self.handle_evenai_response,
            Commands.BLE_REQ_DEVICE_ORDER: self.handle_device_order,
            Commands.BLE_REQ_QUICK_NOTE: self.handle_quick_note,
            Commands.BLE_REQ_DASHBOARD: self.handle_dashboard,
        }

    # Command Handlers
    async def handle_voice_data(self, ble_receive: BleReceive):
        """Handle incoming voice data."""
        logging.info(
            f"Received voice data from {self.side.capitalize()} glass: {self.name} ({self.address}): {ble_receive.data.hex()}"
        )
        self.audio_buffer += ble_receive.data
        await self.save_audio()

    async def handle_evenai_response(self, ble_receive: BleReceive):
        """Handle EvenAI response."""
        logging.info(
            f"Received EvenAI response from {self.side.capitalize()} glass: {self.name} ({self.address}): {ble_receive.data.hex()}"
        )
        self._ack_event.set()

    async def handle_device_order(self, ble_receive: BleReceive):
        """Handle device order commands."""
        order = ble_receive.data[0] if ble_receive.data else None
        self._last_device_order = order
        logging.info(
            f"Received device order from {self.side.capitalize()} glass: {self.name} ({self.address}): {hex(order) if order else 'N/A'}"
        )
        if order == DeviceOrders.DISPLAY_COMPLETE:
            self._received_ack = True

    async def handle_quick_note(self, ble_receive: BleReceive):
        """Handle quick note commands."""
        logging.info(
            f"Received quick note from {self.side.capitalize()} glass: {self.name} ({self.address}): {ble_receive.data.hex()}"
        )
        notesbytes = ble_receive.data
        logging.info(f"Quick note: {notesbytes}")

    async def handle_dashboard(self, ble_receive: BleReceive):
        """Handle dashboard commands."""
        logging.info(
            f"Received dashboard data from {self.side.capitalize()} glass: {self.name} ({self.address}): {ble_receive.data.hex()}"
        )

    async def save_audio(self):
        """Save the accumulated audio buffer to a WAV file."""
        try:
            if not self.audio_buffer:
                logging.warning(
                    f"No audio data to save for {self.side.capitalize()} glass: {self.name} ({self.address})."
                )
                return

            timestamp = int(time.time())
            filename = f"{self.name}_{self.address}_audio_{timestamp}.wav"

            with wave.open(filename, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(self.audio_buffer)

            logging.info(
                f"Saved audio to {filename} for {self.side.capitalize()} glass: {self.name} ({self.address})."
            )
            self.audio_buffer = bytearray()

        except Exception as e:
            logging.error(
                f"Error saving audio for {self.side.capitalize()} glass ({self.address}): {e}"
            )


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
