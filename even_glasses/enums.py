from enum import IntEnum

class Commands(IntEnum):
    # System commands
    BLE_REQ_INIT = 0x4D
    BLE_REQ_HEARTBEAT = 0x25
    BLE_REQ_EVENAI = 0x4E

    # Voice commands
    BLE_REQ_TRANSFER_MIC_DATA = 0xF1
    BLE_REQ_DEVICE_ORDER = 0xF5

    # Display commands
    BLE_REQ_NORMAL_TEXT = 0x30
    BLE_REQ_FINAL_TEXT = 0x40
    BLE_REQ_MANUAL_PAGE = 0x50
    BLE_REQ_ERROR_TEXT = 0x60


class DeviceOrders(IntEnum):
    DISPLAY_READY = 0x00
    DISPLAY_BUSY = 0x11
    DISPLAY_UPDATE = 0x0F
    DISPLAY_COMPLETE = 0x09


class DisplayStatus(IntEnum):
    NORMAL_TEXT = 0x30  # Initial display
    FINAL_TEXT = 0x40  # Final display after 3 seconds
    MANUAL_PAGE = 0x50  # Manual page turning mode
    ERROR_TEXT = 0x60  # Error display

