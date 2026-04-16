import pytest

from uart.comm import send_and_receive


@pytest.mark.hardware
def test_large_data_transmission(uart_pair, large_payload, record_result):
    baud = 115200
    tx_ser, rx_ser = uart_pair(baud=baud)

    received = send_and_receive(tx_ser, rx_ser, large_payload, delay=0.5)
    record_result(
        "test_large_data_transmission",
        baud,
        8,
        "N",
        1,
        len(large_payload),
        "PASS" if received == large_payload else "FAIL",
        f"received={len(received)}",
    )

    assert received == large_payload


@pytest.mark.hardware
def test_random_data_transmission(uart_pair, random_payload, record_result):
    baud = 57600
    tx_ser, rx_ser = uart_pair(baud=baud)

    received = send_and_receive(tx_ser, rx_ser, random_payload)
    record_result(
        "test_random_data_transmission",
        baud,
        8,
        "N",
        1,
        len(random_payload),
        "PASS" if received == random_payload else "FAIL",
        received.hex(),
    )

    assert received == random_payload


@pytest.mark.hardware
def test_binary_data_transmission(uart_pair, binary_payload, record_result):
    baud = 38400
    tx_ser, rx_ser = uart_pair(baud=baud)

    received = send_and_receive(tx_ser, rx_ser, binary_payload, delay=0.3)
    record_result(
        "test_binary_data_transmission",
        baud,
        8,
        "N",
        1,
        len(binary_payload),
        "PASS" if received == binary_payload else "FAIL",
        f"received={len(received)}",
    )

    assert received == binary_payload


@pytest.mark.hardware
def test_empty_data_transmission(uart_pair, record_result):
    baud = 9600
    tx_ser, rx_ser = uart_pair(baud=baud)
    payload = b""

    received = send_and_receive(tx_ser, rx_ser, payload, delay=0.0)
    record_result(
        "test_empty_data_transmission",
        baud,
        8,
        "N",
        1,
        len(payload),
        "PASS" if received == payload else "FAIL",
        "empty-payload",
    )

    assert received == payload


@pytest.mark.hardware
def test_special_character_payload(uart_pair, record_result):
    baud = 19200
    payload = b"\x00UART\xff\n\r\tEND\x7f"
    tx_ser, rx_ser = uart_pair(baud=baud)

    received = send_and_receive(tx_ser, rx_ser, payload)
    record_result(
        "test_special_character_payload",
        baud,
        8,
        "N",
        1,
        len(payload),
        "PASS" if received == payload else "FAIL",
        received.hex(),
    )

    assert received == payload
