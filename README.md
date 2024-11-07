# even_glasses

even-realities g1 smart glasses BLE control pip package

## Installation

To install the package, use pip:

```sh
pip3 install even_glasses
```

## Flet application

```sh
pip3 install -r requirements.txt
```

```sh
flet run
```

## Usage

Here is an example of how to use the even_glasses package to control your smart glasses:

```sh
# Run RSVP test with default settings
python3 examples.py --rsvp

# Run RSVP test with custom settings
python3 examples.py --rsvp --wpm 500 --words-per-group 2 --input-file custom.txt

# Run text test
python3 examples.py --text

# Run text test with custom text
python3 examples.py --text --input-file custom.txt

# Run notification test
python3 examples.py --notification
```


## Features

- Scan for nearby smart glasses and connect to them
- Send text messages to all connected glasses
- Receive status updates from glasses

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details.
