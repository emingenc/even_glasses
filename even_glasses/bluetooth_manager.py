import time
import logging
import asyncio
from bleak import BleakClient, BleakScanner
from even_glasses.utils import construct_heartbeat
from even_glasses.service_identifiers import (
    UART_SERVICE_UUID,
    UART_TX_CHAR_UUID,
    UART_RX_CHAR_UUID,
)
from even_glasses.models import BleReceive


class BleDevice:
    """Base class for BLE device communication."""

    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address
        self.uart_tx = UART_TX_CHAR_UUID
        self.uart_rx = UART_RX_CHAR_UUID
        self.client = BleakClient(
            address,
            disconnected_callback=self.handle_disconnection,
            services=[UART_SERVICE_UUID],
        )
        self.message_queue = asyncio.Queue(
            maxsize=0
        )  # Queue to store the last message received
        self._write_lock = asyncio.Lock()

    async def connect(self):
        logging.info(f"Connected to {self.name}")
        await self.client.connect()
        await asyncio.sleep(1)
        try:
            await self.start_notifications()
        except Exception as e:
            logging.error(f"Failed to start notifications: {e}")

    async def disconnect(self):
        await self.client.disconnect()
        logging.info(f"Disconnected from {self.name}")

    async def handle_disconnection(self, client: BleakClient):
        logging.warning(f"Device disconnected: {self.name}")
        await asyncio.sleep(5)  # Wait before attempting to reconnect
        await self.connect()

    async def start_notifications(self):
        await self.client.start_notify(self.uart_rx, self.handle_notification)
        await asyncio.sleep(1)

    async def recieve(self, sender: int, data: bytes):
        """Handle incoming data from the device."""
        logging.info(f"Received from {self.name}: {data.hex()}")
        await self.message_queue.put((sender, data))

    async def send(self, data: bytes, max_retries: int = 3, initial_delay: float = 0.1) -> bool:
        """Send data with retry mechanism.
        
        Args:
            data: Bytes to send
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries (doubles with each attempt)
        
        Returns:
            bool: True if send was successful, False otherwise
        """
        if not self.client.is_connected:
            logging.warning(f"Cannot send data, {self.name} is disconnected.")
            return False

        async with self._write_lock:  # Ensure exclusive access
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    logging.info(f"Attempt {attempt + 1}/{max_retries} to send to {self.name}: {data.hex()}")
                    await self.client.write_gatt_char(self.uart_tx, data)
                    return True
                except Exception as e:
                    if attempt == max_retries - 1:
                        logging.error(f"Failed to send data to {self.name} after {max_retries} attempts: {e}")
                        return False
                    logging.warning(f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff

            return False

    async def handle_notification(self, sender: int, data: bytes):
        try:
            logging.info(f"Received from {self.name}: {data.hex()}")
            await self.recieve(sender, data)
        except Exception as e:
            logging.error(f"Error handling notification from {self.name}: {e}")


class Glass(BleDevice):
    """Class representing a single glass device."""

    def __init__(
        self,
        name: str,
        address: str,
        side: str,
        heartbeat_freq: int = 5,
    ):
        super().__init__(name=name, address=address)
        self.side = side
        self.heartbeat_seq = 0
        self.heartbeat_freq = heartbeat_freq
        self._last_heartbeat_time = time.time()

    async def start_heartbeat(self):
        while self.client.is_connected:
            current_time = time.time()
            if current_time - self._last_heartbeat_time > self.heartbeat_freq:
                heartbeat = construct_heartbeat(self.heartbeat_seq)
                self.heartbeat_seq += 1
                await self.send(heartbeat)
                self._last_heartbeat_time = current_time
                try:
                    sender, recieve = await asyncio.wait_for(
                        self.message_queue.get(), timeout=1
                    )
                except asyncio.TimeoutError:
                    logging.warning(
                        f"No response received from {self.name} within timeout."
                    )
                except Exception as e:
                    logging.error(f"Error in heartbeat for {self.name}: {e}")

    async def connect(self):
        await super().connect()
        asyncio.create_task(self.start_heartbeat())

    async def recieve(self, sender: int, data: bytes):
        """Handle incoming data from the device."""
        recieve = BleReceive(lr=self.side, cmd=data[0], data=data[1:])
        await self.message_queue.put((sender, recieve))


class GlassesManager:
    """Class to manage both left and right glasses."""

    def __init__(
        self,
        left_address: str = None,
        right_address: str = None,
        left_name: str = "G1 Left Glass",
        right_name: str = "G1 Right Glass",
    ):
        self.left_glass = None
        self.right_glass = None

        self.left_address = left_address
        self.right_address = right_address

        self.left_name = left_name
        self.right_name = right_name

        self.evenai_seq = 0

        if left_address and right_address:
            # Initialize with minimal info first
            self.left_glass = Glass(
                name=left_name,
                address=left_address,
                side="left",
            )
            self.right_glass = Glass(
                name=right_name,
                address=right_address,
                side="right",
            )

    async def connect(self):
        if self.left_glass and self.right_glass:
            await self.left_glass.connect()
            await self.right_glass.connect()
            return True
        return False

    async def scan_and_connect(self, timeout: int = 10):
        """Scan for glasses devices and connect to them."""
        if self.left_address and self.right_address:
            await self.connect()
            return True
        attempt = 5
        for i in range(attempt):
            logging.info("Scanning for glasses devices...")
            devices = await BleakScanner.discover(timeout=timeout)
            for device in devices:
                device_name = device.name if device.name else "Unknown"
                logging.info(f"Found device: {device_name}, Address: {device.address}")
                if "_L_" in device_name:
                    side = "left"
                    self.left_name = device.name
                    self.left_address = device.address
                    self.left_glass = Glass(
                        name=device.name, address=device.address, side=side
                    )
                if "_R_" in device_name:
                    side = "right"
                    self.right_name = device.name
                    self.right_address = device.address
                    self.right_glass = Glass(
                        name=device.name, address=device.address, side=side
                    )

            if self.left_glass and self.right_glass:
                break
            await asyncio.sleep(1)
        for i in range(attempt):
            try:
                connected = await self.connect()
                if connected:
                    return True
            except Exception as e:
                logging.error(f"Error connecting to glasses: {e}")
        return False

    async def disconnect(self):
        await self.left_glass.disconnect()
        await self.right_glass.disconnect()

    async def send(self, data: bytes):
        # First send to left glass
        await self.left_glass.send(data)
        await self.right_glass.send(data)
