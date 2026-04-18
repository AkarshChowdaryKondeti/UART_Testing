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

GPIO_UART_PORTS = {"/dev/serial0", "/dev/serial1", "/dev/ttyAMA0", "/dev/ttyS0"}
USB_UART_MARKERS = ("/ttyUSB", "/ttyACM", "/serial/by-id/")


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


def is_gpio_uart_port(port: str) -> bool:
    return port in GPIO_UART_PORTS


def is_usb_uart_port(port: str) -> bool:
    return any(marker in port for marker in USB_UART_MARKERS)


def setup_requires_distinct_ports(setup_type: str) -> bool:
    return setup_type != "usb_loopback"


def infer_setup_type(tx_port: str, rx_port: str) -> str:
    if tx_port and rx_port and tx_port == rx_port:
        return "usb_loopback"
    if (is_usb_uart_port(tx_port) and is_gpio_uart_port(rx_port)) or (is_gpio_uart_port(tx_port) and is_usb_uart_port(rx_port)):
        return "usb_gpio"
    return "dual_usb"


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


def detect_default_uart_config():
    ports = [port for port in list_uart_ports() if Path(port).exists()]
    usb_ports = [port for port in ports if is_usb_uart_port(port)]
    gpio_ports = [port for port in ports if is_gpio_uart_port(port)]

    if usb_ports and gpio_ports:
        return "usb_gpio", usb_ports[0], gpio_ports[0]
    if len(usb_ports) >= 2:
        return "dual_usb", usb_ports[0], usb_ports[1]
    if len(ports) >= 2:
        return infer_setup_type(ports[0], ports[1]), ports[0], ports[1]
    if ports:
        return "usb_loopback", ports[0], ports[0]

    tx_port, rx_port = detect_default_uart_pair()
    return "dual_usb", tx_port, rx_port


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
    setup_type = getattr(config, "setup_type", None) or infer_setup_type(config.tx_port, config.rx_port)
    try:
        if setup_requires_distinct_ports(setup_type) and config.tx_port == config.rx_port:
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

        if setup_requires_distinct_ports(setup_type):
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
        else:
            rx_ser = tx_ser

        received, elapsed = measure_transfer_time(tx_ser, rx_ser, payload, delay=read_delay)
        return received, elapsed
    finally:
        with suppress(Exception):
            close_uart(tx_ser)
        if rx_ser is not tx_ser:
            with suppress(Exception):
                close_uart(rx_ser)
