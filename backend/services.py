import glob
import os
from contextlib import suppress
from pathlib import Path

from serial import SerialException
from serial.tools import list_ports

from uart.comm import close_uart, measure_transfer_time, open_uart


TEST_FILE_MAP = {
    "basic": "test_uart.py",
    "config": "test_config_uart.py",
    "integrity": "test_integrity_uart.py",
    "stress": "test_stress_uart.py",
    "timing": "test_timing_uart.py",
    "protocol": "test_protocol_uart.py",
    "negative": "test_negative_uart.py",
}


def list_uart_ports():
    detected_ports = []
    for port_info in list_ports.comports():
        if port_info.device:
            detected_ports.append(port_info.device)

    fallback_ports = (
        glob.glob("/dev/ttyUSB*")
        + glob.glob("/dev/ttyACM*")
        + glob.glob("/dev/ttyAMA*")
        + glob.glob("/dev/ttyS*")
    )
    stable_symlinks = glob.glob("/dev/serial/by-id/*")
    serial_aliases = glob.glob("/dev/serial0") + glob.glob("/dev/serial1")
    ports = sorted(set(detected_ports + fallback_ports + stable_symlinks + serial_aliases))
    return ports


def detect_default_uart_pair():
    env_tx = os.getenv("UART_TX_PORT")
    env_rx = os.getenv("UART_RX_PORT")
    ports = list_uart_ports()

    if env_tx and env_rx:
        return env_tx, env_rx

    available = [port for port in ports if Path(port).exists()]
    preferred_ports = ["/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0"]
    preferred_gpio_port = next((port for port in preferred_ports if port in available), None)
    usb_ports = [port for port in available if "/ttyUSB" in port or "/ttyACM" in port or "/serial/by-id/" in port]

    if env_tx:
        tx_port = env_tx
    elif usb_ports:
        tx_port = usb_ports[0]
    else:
        tx_port = available[0] if len(available) >= 1 else "/dev/ttyUSB0"

    if env_rx:
        rx_port = env_rx
    elif preferred_gpio_port and preferred_gpio_port != tx_port:
        rx_port = preferred_gpio_port
    else:
        rx_candidates = [port for port in available if port != tx_port]
        rx_port = rx_candidates[0] if rx_candidates else "/dev/serial0"
    return tx_port, rx_port


def encode_payload(payload: str, mode: str) -> bytes:
    if mode == "hex":
        cleaned = payload.replace(" ", "")
        return bytes.fromhex(cleaned) if cleaned else b""
    return payload.encode()


def decode_payload(payload: bytes):
    return payload.decode(errors="replace"), payload.hex()


def normalize_uart_error(exc: Exception, port: str) -> Exception:
    message = str(exc)
    if isinstance(exc, PermissionError) or "Permission denied" in message:
        return PermissionError(
            f"Cannot open UART port {port}: permission denied. "
            "On Linux/Raspberry Pi, add your user to the 'dialout' group, "
            "confirm the UART device is enabled, then log out and back in."
        )
    if isinstance(exc, SerialException):
        return RuntimeError(f"Unable to open UART port {port}: {message}")
    return exc


def run_communication(config, payload: bytes, read_delay: float):
    tx_ser = None
    rx_ser = None
    try:
        if config.tx_port == config.rx_port:
            raise ValueError("TX and RX ports must be different serial devices")

        try:
            tx_ser = open_uart(
                config.tx_port,
                config.baud,
                config.data_bits,
                config.parity,
                config.stop_bits,
                timeout=config.timeout,
            )
        except Exception as exc:
            raise normalize_uart_error(exc, config.tx_port) from exc

        try:
            rx_ser = open_uart(
                config.rx_port,
                config.baud,
                config.data_bits,
                config.parity,
                config.stop_bits,
                timeout=config.timeout,
            )
        except Exception as exc:
            raise normalize_uart_error(exc, config.rx_port) from exc

        received, elapsed = measure_transfer_time(tx_ser, rx_ser, payload, delay=read_delay)
        return received, elapsed
    finally:
        with suppress(Exception):
            close_uart(tx_ser)
        with suppress(Exception):
            close_uart(rx_ser)
