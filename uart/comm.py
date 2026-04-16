import time
from concurrent.futures import ThreadPoolExecutor

import serial


BYTE_SIZE_MAP = {
    5: serial.FIVEBITS,
    6: serial.SIXBITS,
    7: serial.SEVENBITS,
    8: serial.EIGHTBITS,
}

PARITY_MAP = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
}

STOP_BITS_MAP = {
    1: serial.STOPBITS_ONE,
    2: serial.STOPBITS_TWO,
}


def open_uart(
    port,
    baud,
    data_bits,
    parity,
    stop_bits,
    timeout=1,
    xonxoff=False,
    rtscts=False,
    dsrdtr=False,
    exclusive=None,
):
    """Open and return a configured serial port."""
    if data_bits not in BYTE_SIZE_MAP:
        raise ValueError(f"Unsupported data bits: {data_bits}")
    if parity not in PARITY_MAP:
        raise ValueError(f"Unsupported parity: {parity}")
    if stop_bits not in STOP_BITS_MAP:
        raise ValueError(f"Unsupported stop bits: {stop_bits}")

    return serial.Serial(
        port=port,
        baudrate=baud,
        bytesize=BYTE_SIZE_MAP[data_bits],
        parity=PARITY_MAP[parity],
        stopbits=STOP_BITS_MAP[stop_bits],
        timeout=timeout,
        write_timeout=timeout,
        xonxoff=xonxoff,
        rtscts=rtscts,
        dsrdtr=dsrdtr,
        exclusive=exclusive,
    )


def ensure_open(ser):
    if not ser.is_open:
        ser.open()


def flush_uart(ser):
    ensure_open(ser)
    ser.reset_input_buffer()
    ser.reset_output_buffer()


def send_data(ser, payload):
    """Send the full payload and wait for the driver to flush it."""
    ensure_open(ser)
    if not isinstance(payload, (bytes, bytearray)):
        raise TypeError("Payload must be bytes-like")

    written = ser.write(payload)
    ser.flush()
    return written


def read_data(ser, expected_length, delay=0.2):
    """Read a fixed number of bytes after an optional settling delay."""
    ensure_open(ser)
    if delay:
        time.sleep(delay)
    return ser.read(expected_length)


def send_and_receive(tx_ser, rx_ser, payload, delay=0.2):
    """Send payload on one UART and read it from another UART."""
    flush_uart(tx_ser)
    flush_uart(rx_ser)
    send_data(tx_ser, payload)
    return read_data(rx_ser, len(payload), delay=delay)


def measure_transfer_time(tx_ser, rx_ser, payload, delay=0.0):
    """Return the received payload and elapsed time in seconds."""
    start = time.perf_counter()
    received = send_and_receive(tx_ser, rx_ser, payload, delay=delay)
    elapsed = time.perf_counter() - start
    return received, elapsed


def duplex_exchange(ser_a, payload_a, ser_b, payload_b, delay=0.05):
    """Send from both UARTs at the same time and collect both responses."""
    flush_uart(ser_a)
    flush_uart(ser_b)

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a_write = executor.submit(send_data, ser_a, payload_a)
        future_b_write = executor.submit(send_data, ser_b, payload_b)
        future_a_read = executor.submit(read_data, ser_a, len(payload_b), delay)
        future_b_read = executor.submit(read_data, ser_b, len(payload_a), delay)

        future_a_write.result()
        future_b_write.result()
        received_a = future_a_read.result()
        received_b = future_b_read.result()

    return received_a, received_b


def send_in_chunks(tx_ser, payload, chunk_size=1, inter_byte_delay=0.01):
    """Send bytes in small chunks to exercise receiver timing."""
    ensure_open(tx_ser)
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    total_written = 0
    for index in range(0, len(payload), chunk_size):
        chunk = payload[index:index + chunk_size]
        total_written += send_data(tx_ser, chunk)
        if inter_byte_delay:
            time.sleep(inter_byte_delay)
    return total_written


def measure_throughput(tx_ser, rx_ser, payload, delay=0.0):
    """Return bytes per second for a transfer along with the received payload."""
    received, elapsed = measure_transfer_time(tx_ser, rx_ser, payload, delay=delay)
    throughput = len(payload) / elapsed if elapsed else float("inf")
    return received, elapsed, throughput


def run_soak_iteration(tx_ser, rx_ser, payload_factory, duration_seconds, delay=0.01):
    """Run repeated transfers for a duration and track sequence/integrity errors."""
    deadline = time.monotonic() + duration_seconds
    iterations = 0
    mismatches = 0

    while time.monotonic() < deadline:
        payload = payload_factory(iterations)
        received = send_and_receive(tx_ser, rx_ser, payload, delay=delay)
        if received != payload:
            mismatches += 1
        iterations += 1

    return {
        "iterations": iterations,
        "mismatches": mismatches,
    }


def crc16_ccitt(data, initial=0xFFFF):
    """Compute CRC-16/CCITT-FALSE for protocol-style integrity checks."""
    crc = initial
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def build_sequence_payload(sequence, payload):
    """Prefix payload with a 4-byte sequence number."""
    return sequence.to_bytes(4, byteorder="big") + payload


def parse_sequence_payload(frame):
    if len(frame) < 4:
        raise ValueError("Sequence frame too short")
    sequence = int.from_bytes(frame[:4], byteorder="big")
    payload = frame[4:]
    return sequence, payload


def build_crc_frame(command, payload):
    """Build a simple framed packet with a CRC-16 trailer."""
    if len(command) != 1:
        raise ValueError("Command must be a single byte")
    body = command + bytes([len(payload)]) + payload
    crc = crc16_ccitt(body)
    return b"\x02" + body + crc.to_bytes(2, byteorder="big") + b"\x03"


def parse_crc_frame(frame):
    if len(frame) < 6:
        raise ValueError("Frame too short")
    if frame[0:1] != b"\x02" or frame[-1:] != b"\x03":
        raise ValueError("Invalid frame markers")

    body = frame[1:-3]
    if len(body) < 2:
        raise ValueError("Frame body too short")

    command = body[0:1]
    payload_len = body[1]
    payload = body[2:]
    if len(payload) != payload_len:
        raise ValueError("Partial payload")

    expected_crc = int.from_bytes(frame[-3:-1], byteorder="big")
    actual_crc = crc16_ccitt(body)
    if actual_crc != expected_crc:
        raise ValueError("CRC mismatch")

    return command, payload


def close_uart(ser):
    if ser and ser.is_open:
        ser.close()
