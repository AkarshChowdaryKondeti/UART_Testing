import pytest

from uart.comm import measure_throughput, measure_transfer_time, read_data, send_data, send_in_chunks


@pytest.mark.hardware
def test_transmission_delay_measurement(uart_pair, fixed_payload, record_result):
    baud = 115200
    tx_ser, rx_ser = uart_pair(baud=baud)

    received, elapsed = measure_transfer_time(tx_ser, rx_ser, fixed_payload, delay=0.0)
    record_result(
        "test_transmission_delay_measurement",
        baud,
        8,
        "N",
        1,
        len(fixed_payload),
        "PASS" if received == fixed_payload else "FAIL",
        f"elapsed_ms={elapsed * 1000:.3f}",
    )

    assert received == fixed_payload
    assert elapsed < 1.0


@pytest.mark.hardware
def test_inter_byte_delay_handling(uart_pair, record_result):
    baud = 19200
    payload = b"inter-byte-delay-check"
    tx_ser, rx_ser = uart_pair(baud=baud)

    send_in_chunks(tx_ser, payload, chunk_size=1, inter_byte_delay=0.01)
    received = read_data(rx_ser, len(payload), delay=0.2)
    record_result(
        "test_inter_byte_delay_handling",
        baud,
        8,
        "N",
        1,
        len(payload),
        "PASS" if received == payload else "FAIL",
        received.hex(),
    )

    assert received == payload


@pytest.mark.hardware
def test_timeout_behavior(uart_pair, uart_timeout, record_result):
    baud = 9600
    tx_ser, rx_ser = uart_pair(baud=baud)

    send_data(tx_ser, b"")
    received = read_data(rx_ser, 16, delay=0.0)
    record_result(
        "test_timeout_behavior",
        baud,
        8,
        "N",
        1,
        0,
        "PASS" if received == b"" else "FAIL",
        f"timeout={uart_timeout}",
    )

    assert received == b""


@pytest.mark.hardware
def test_throughput_measurement(uart_pair, large_payload, record_result):
    baud = 115200
    tx_ser, rx_ser = uart_pair(baud=baud)

    received, elapsed, throughput = measure_throughput(tx_ser, rx_ser, large_payload, delay=0.0)
    record_result(
        "test_throughput_measurement",
        baud,
        8,
        "N",
        1,
        len(large_payload),
        "PASS" if received == large_payload else "FAIL",
        f"elapsed_ms={elapsed * 1000:.3f} throughput_bps={throughput:.2f}",
    )

    assert received == large_payload
    assert throughput > 0
