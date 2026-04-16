import pytest

from uart.comm import (
    build_crc_frame,
    build_sequence_payload,
    parse_crc_frame,
    parse_sequence_payload,
    read_data,
    send_data,
)


@pytest.mark.hardware
def test_valid_command_frame(uart_pair, record_result):
    baud = 38400
    payload = b"PING"
    frame = build_crc_frame(b"C", payload)
    tx_ser, rx_ser = uart_pair(baud=baud)

    send_data(tx_ser, frame)
    received = read_data(rx_ser, len(frame), delay=0.2)
    command, parsed_payload = parse_crc_frame(received)

    record_result(
        "test_valid_command_frame",
        baud,
        8,
        "N",
        1,
        len(frame),
        "PASS",
        f"command={command.decode()} payload={parsed_payload.decode()}",
    )

    assert command == b"C"
    assert parsed_payload == payload


@pytest.mark.hardware
def test_invalid_command_frame(uart_pair, record_result):
    baud = 38400
    payload = b"PING"
    frame = build_crc_frame(b"C", payload)[:-1] + b"\x00"
    tx_ser, rx_ser = uart_pair(baud=baud)

    send_data(tx_ser, frame)
    received = read_data(rx_ser, len(frame), delay=0.2)
    record_result(
        "test_invalid_command_frame",
        baud,
        8,
        "N",
        1,
        len(frame),
        "PASS",
        received.hex(),
    )

    with pytest.raises(ValueError, match="Invalid frame markers"):
        parse_crc_frame(received)


@pytest.mark.hardware
def test_partial_command_frame(uart_pair, record_result):
    baud = 38400
    payload = b"PING"
    full_frame = build_crc_frame(b"C", payload)
    partial_frame = full_frame[:-2]
    tx_ser, rx_ser = uart_pair(baud=baud)

    send_data(tx_ser, partial_frame)
    received = read_data(rx_ser, len(partial_frame), delay=0.2)
    record_result(
        "test_partial_command_frame",
        baud,
        8,
        "N",
        1,
        len(partial_frame),
        "PASS",
        received.hex(),
    )

    with pytest.raises(ValueError):
        parse_crc_frame(received)


@pytest.mark.hardware
def test_crc_validation(uart_pair, record_result):
    baud = 38400
    payload = b"DATA"
    frame = bytearray(build_crc_frame(b"D", payload))
    frame[-2] ^= 0x01
    tx_ser, rx_ser = uart_pair(baud=baud)

    send_data(tx_ser, bytes(frame))
    received = read_data(rx_ser, len(frame), delay=0.2)
    record_result(
        "test_crc_validation",
        baud,
        8,
        "N",
        1,
        len(frame),
        "PASS",
        received.hex(),
    )

    with pytest.raises(ValueError, match="CRC mismatch"):
        parse_crc_frame(received)


def test_sequence_number_parser():
    frame = build_sequence_payload(7, b"payload")
    sequence, payload = parse_sequence_payload(frame)

    assert sequence == 7
    assert payload == b"payload"


def test_sequence_reorder_detection():
    frames = [
        build_sequence_payload(0, b"a"),
        build_sequence_payload(2, b"c"),
        build_sequence_payload(1, b"b"),
    ]
    sequences = [parse_sequence_payload(frame)[0] for frame in frames]

    assert sequences != sorted(sequences)
