import pytest
import serial

from uart.comm import open_uart, read_data, send_data


def test_invalid_port_usage(record_result):
    with pytest.raises(serial.SerialException):
        open_uart("/dev/ttyUART_DOES_NOT_EXIST", 9600, 8, "N", 1)

    record_result(
        "test_invalid_port_usage",
        "invalid",
        8,
        "N",
        1,
        0,
        "PASS",
        "invalid port rejected",
    )


def test_unsupported_uart_parameter_handling(record_result):
    with pytest.raises(ValueError, match="Unsupported data bits"):
        open_uart("/dev/null", 9600, 9, "N", 1)

    record_result(
        "test_unsupported_uart_parameter_handling",
        "n/a",
        9,
        "N",
        1,
        0,
        "PASS",
        "unsupported data bits rejected",
    )


def test_transmission_without_proper_initialization(record_result):
    with pytest.raises(AttributeError):
        send_data(None, b"uninitialized")

    record_result(
        "test_transmission_without_proper_initialization",
        "n/a",
        8,
        "N",
        1,
        13,
        "PASS",
        "uninitialized serial object rejected",
    )


@pytest.mark.hardware
def test_disconnection_during_transfer(uart_pair, record_result):
    tx_ser, rx_ser = uart_pair(baud=9600)
    tx_ser.close()

    with pytest.raises(serial.SerialException):
        send_data(tx_ser, b"disconnect-check")

    record_result(
        "test_disconnection_during_transfer",
        9600,
        8,
        "N",
        1,
        16,
        "PASS",
        "write after disconnect rejected",
    )


@pytest.mark.hardware
def test_wrong_connection_behavior(uart_pair, record_result):
    tx_ser, rx_ser = uart_pair(baud=9600)
    send_data(tx_ser, b"connection-check")
    rx_ser.close()

    with pytest.raises(serial.SerialException):
        read_data(rx_ser, 16, delay=0.0)

    record_result(
        "test_wrong_connection_behavior",
        9600,
        8,
        "N",
        1,
        16,
        "PASS",
        "closed receiver rejected read",
    )
