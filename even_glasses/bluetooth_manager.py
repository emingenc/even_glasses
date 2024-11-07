import asyncio
import logging
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError
from typing import Optional, Callable

from even_glasses.utils import construct_heartbeat
from even_glasses.service_identifiers import (
    UART_SERVICE_UUID,
    UART_TX_CHAR_UUID,
    UART_RX_CHAR_UUID,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BleDevice:
    """Base class for BLE device communication."""

    def __init__(self, name: str, address: str):
        self.name = name
        self.address = address
        self.client = BleakClient(
            address,
            disconnected_callback=self._handle_disconnection,
        )
        self.uart_tx = None
        self.uart_rx = None
        self._write_lock = asyncio.Lock()
        self.notifications_started = False
        self.notification_handler: Optional[Callable[[int, bytes], None]] = None

    async def connect(self):
        logger.info(f"Connecting to {self.name} ({self.address})")
        try:
            await self.client.connect()
            logger.info(f"Connected to {self.name}")

            # Discover services
            await self.client.get_services()
            services = self.client.services

            uart_service = services.get_service(UART_SERVICE_UUID)
            if not uart_service:
                raise BleakError(f"UART service not found for {self.name}")

            self.uart_tx = uart_service.get_characteristic(UART_TX_CHAR_UUID)
            self.uart_rx = uart_service.get_characteristic(UART_RX_CHAR_UUID)

            if not self.uart_tx or not self.uart_rx:
                raise BleakError(f"UART TX/RX characteristics not found for {self.name}")

            await self.start_notifications()
        except Exception as e:
            logger.error(f"Error connecting to {self.name}: {e}")
            await self.disconnect()
            raise

    async def disconnect(self):
        if self.notifications_started and self.uart_rx:
            await self.client.stop_notify(self.uart_rx)
            self.notifications_started = False
            logger.info(f"Stopped notifications for {self.name}")

        if self.client.is_connected:
            await self.client.disconnect()
            logger.info(f"Disconnected from {self.name}")

    def _handle_disconnection(self, client: BleakClient):
        logger.warning(f"Device {self.name} disconnected")
        asyncio.create_task(self.reconnect())

    async def reconnect(self):
        retries = 3
        for attempt in range(1, retries + 1):
            try:
                logger.info(f"Reconnecting to {self.name} (Attempt {attempt}/{retries})")
                await self.connect()
                logger.info(f"Reconnected to {self.name}")
                return
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt} failed: {e}")
                await asyncio.sleep(5)
        logger.error(f"Failed to reconnect to {self.name} after {retries} attempts")

    async def start_notifications(self):
        if not self.notifications_started and self.uart_rx:
            try:
                await self.client.start_notify(self.uart_rx, self.handle_notification)
                self.notifications_started = True
                logger.info(f"Notifications started for {self.name}")
            except Exception as e:
                logger.error(f"Failed to start notifications for {self.name}: {e}")

    async def send(self, data: bytes) -> bool:
        if not self.client.is_connected:
            logger.warning(f"Cannot send data, {self.name} is disconnected.")
            return False

        if not self.uart_tx:
            logger.warning(f"No TX characteristic available for {self.name}.")
            return False

        try:
            async with self._write_lock:
                await self.client.write_gatt_char(self.uart_tx, data, response=True)
            logger.info(f"Data sent to {self.name}: {data.hex()}")
            return True
        except Exception as e:
            logger.error(f"Error sending data to {self.name}: {e}")
            return False

    async def handle_notification(self, sender: int, data: bytes):
        logger.info(f"Notification from {self.name}: {data.hex()}")
        if self.notification_handler:
            await self.notification_handler(sender, data)


class Glass(BleDevice):
    """Class representing a single glass device."""

    def __init__(
        self,
        name: str,
        address: str,
        side: str,
        heartbeat_freq: int = 5,
    ):
        super().__init__(name, address)
        self.side = side
        self.heartbeat_freq = heartbeat_freq
        self.heartbeat_task: Optional[asyncio.Task] = None

    async def start_heartbeat(self):
        if self.heartbeat_task is None or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self._heartbeat())

    async def _heartbeat(self):
        while self.client.is_connected:
            try:
                heartbeat = construct_heartbeat(1)
                await self.send(heartbeat)
                await asyncio.sleep(self.heartbeat_freq)
            except Exception as e:
                logger.error(f"Heartbeat error for {self.name}: {e}")
                break

    async def connect(self):
        await super().connect()
        await self.start_heartbeat()

    async def disconnect(self):
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        await super().disconnect()


class GlassesManager:
    """Class to manage both left and right glasses."""

    def __init__(
        self,
        left_address: str = None,
        right_address: str = None,
        left_name: str = "G1 Left Glass",
        right_name: str = "G1 Right Glass",
    ):
        self.left_glass: Optional[Glass] = (
            Glass(name=left_name, address=left_address, side="left")
            if left_address
            else None
        )
        self.right_glass: Optional[Glass] = (
            Glass(name=right_name, address=right_address, side="right")
            if right_address
            else None
        )

    async def scan_and_connect(self, timeout: int = 10) -> bool:
        """Scan for glasses devices and connect to them."""
        try:
            logger.info("Scanning for glasses devices...")
            devices = await BleakScanner.discover(timeout=timeout)
            for device in devices:
                device_name = device.name or "Unknown"
                logger.info(f"Found device: {device_name}, Address: {device.address}")
                if "_L_" in device_name and not self.left_glass:
                    self.left_glass = Glass(name=device_name, address=device.address, side="left")
                elif "_R_" in device_name and not self.right_glass:
                    self.right_glass = Glass(name=device_name, address=device.address, side="right")

            connect_tasks = []
            if self.left_glass:
                connect_tasks.append(asyncio.create_task(self.left_glass.connect()))
            if self.right_glass:
                connect_tasks.append(asyncio.create_task(self.right_glass.connect()))

            if connect_tasks:
                await asyncio.gather(*connect_tasks)
                logger.info("All glasses connected successfully.")
                return True
            else:
                logger.error("No glasses devices found during scan.")
                return False
        except Exception as e:
            logger.error(f"Error during scan and connect: {e}")
            return False

    async def disconnect_all(self):
        """Disconnect from all connected glasses."""
        disconnect_tasks = []
        if self.left_glass and self.left_glass.client.is_connected:
            disconnect_tasks.append(asyncio.create_task(self.left_glass.disconnect()))
        if self.right_glass and self.right_glass.client.is_connected:
            disconnect_tasks.append(asyncio.create_task(self.right_glass.disconnect()))
        if disconnect_tasks:
            await asyncio.gather(*disconnect_tasks)
            logger.info("All glasses disconnected.")


# Example Usage
async def main():
    manager = GlassesManager()
    connected = await manager.scan_and_connect()
    if connected:
        try:
            while True:
                # Replace with your actual logic
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
        finally:
            await manager.disconnect_all()
    else:
        logger.error("Failed to connect to glasses.")


if __name__ == "__main__":
    asyncio.run(main())