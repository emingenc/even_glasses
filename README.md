# even_glasses

even-realities g1 smart glasses BLE control pip package

## Installation

To install the package, use pip:

```sh
pip3 install even_glasses
```

## Usage

Here is an example of how to use the even_glasses package to control your smart glasses:

```python

import asyncio
import logging
from even_glasses import GlassesProtocol

logging.basicConfig(level=logging.INFO)
glasses = GlassesProtocol()

async def main():

    try:
        await glasses.scan_and_connect(timeout=10)

        def status_changed(address, status):
            logging.info(f"[{address}] Status changed to: {status}")

        glasses.on_status_changed = status_changed

        while True:
            test_message = "Hello, Glasses!\nThis is a test message.\nEnjoy your day!"
            await glasses.send_text_to_all(test_message)
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

```

## Features

- Scan for nearby smart glasses and connect to them
- Send text messages to all connected glasses
- Receive status updates from glasses

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
