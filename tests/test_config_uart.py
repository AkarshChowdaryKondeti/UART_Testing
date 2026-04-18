import pytest

import uart.comm as uart_comm
from uart.comm import open_uart, send_and_receive


BAUD_RATES = [9600, 19200, 38400, 57600, 115200]
DATA_BITS = [7, 8]
PARITIES = ["N", "E", "O"]
STOP_BITS = [1, 2]


@pytest.mark.hardware
@pytest.mark.parametrize("baud", BAUD_RATES)
@pytest.mark.parametrize("data_bits", DATA_BITS)
@pytest.mark.parametrize("parity", PARITIES)
@pytest.mark.parametrize("stop_bits", STOP_BITS)
def test_uart_configurations(uart_pair, record_result, baud, data_bits, parity, stop_bits):
    payload = f"cfg:{baud}:{data_bits}:{parity}:{stop_bits}".encode()
    tx_ser, rx_ser = uart_pair(baud=baud, data_bits=data_bits, parity=parity, stop_bits=stop_bits)

    received = send_and_receive(tx_ser, rx_ser, payload)
    record_result(
        "test_uart_configurations",
        baud,
        data_bits,
        parity,
        stop_bits,
        len(payload),
        "PASS" if received == payload else "FAIL",
        received.decode(errors="ignore"),
    )

    assert received == payload


@pytest.mark.hardware
def test_mismatched_baud_behavior(uart_ports_available, uart_timeout, require_distinct_uart_endpoints, record_result):
    from uart.comm import close_uart, open_uart, send_and_receive

    tx_port, rx_port = uart_ports_available
    tx_ser = open_uart(tx_port, 9600, 8, "N", 1, timeout=uart_timeout)
    rx_ser = open_uart(rx_port, 115200, 8, "N", 1, timeout=uart_timeout)
    payload = b"baud-mismatch-check"

    try:
        received = send_and_receive(tx_ser, rx_ser, payload)
        record_result(
            "test_mismatched_baud_behavior",
            "9600->115200",
            8,
            "N",
            1,
            len(payload),
            "PASS",
            received.hex(),
        )
        assert received != payload
    finally:
        close_uart(tx_ser)
        close_uart(rx_ser)


def test_extended_uart_parameters_are_forwarded(monkeypatch):
    captured = {}

    class DummySerial:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(uart_comm.serial, "Serial", DummySerial)
    open_uart(
        "/dev/ttyUSB_TEST",
        115200,
        8,
        "N",
        1,
        timeout=2,
        xonxoff=True,
        rtscts=True,
        dsrdtr=True,
        exclusive=False,
    )

    assert captured["xonxoff"] is True
    assert captured["rtscts"] is True
    assert captured["dsrdtr"] is True
    assert captured["exclusive"] is False
