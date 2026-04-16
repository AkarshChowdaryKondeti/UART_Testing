import pytest

from uart.comm import build_sequence_payload, parse_sequence_payload, run_soak_iteration, send_and_receive


@pytest.mark.hardware
@pytest.mark.slow
def test_continuous_data_stream(uart_pair, record_result):
    baud = 115200
    iterations = 50
    tx_ser, rx_ser = uart_pair(baud=baud)

    for index in range(iterations):
        payload = f"stream-packet-{index:03d}".encode()
        received = send_and_receive(tx_ser, rx_ser, payload, delay=0.05)
        assert received == payload

    record_result(
        "test_continuous_data_stream",
        baud,
        8,
        "N",
        1,
        iterations,
        "PASS",
        f"iterations={iterations}",
    )


@pytest.mark.hardware
@pytest.mark.slow
def test_rapid_back_to_back_transmissions(uart_pair, record_result):
    baud = 115200
    burst_count = 25
    tx_ser, rx_ser = uart_pair(baud=baud)

    for index in range(burst_count):
        payload = bytes([index]) * 32
        received = send_and_receive(tx_ser, rx_ser, payload, delay=0.01)
        assert received == payload

    record_result(
        "test_rapid_back_to_back_transmissions",
        baud,
        8,
        "N",
        1,
        burst_count * 32,
        "PASS",
        f"bursts={burst_count}",
    )


@pytest.mark.hardware
@pytest.mark.slow
def test_repeated_open_send_close_cycles(uart_ports_available, tx_port, rx_port, uart_timeout, record_result):
    from uart.comm import close_uart, open_uart, send_and_receive

    baud = 57600
    cycles = 20

    for index in range(cycles):
        tx_ser = open_uart(tx_port, baud, 8, "N", 1, timeout=uart_timeout)
        rx_ser = open_uart(rx_port, baud, 8, "N", 1, timeout=uart_timeout)
        payload = f"cycle-{index:03d}".encode()
        try:
            received = send_and_receive(tx_ser, rx_ser, payload, delay=0.05)
            assert received == payload
        finally:
            close_uart(tx_ser)
            close_uart(rx_ser)

    record_result(
        "test_repeated_open_send_close_cycles",
        baud,
        8,
        "N",
        1,
        cycles,
        "PASS",
        f"cycles={cycles}",
    )


@pytest.mark.hardware
@pytest.mark.slow
def test_sequence_numbered_stream(uart_pair, record_result):
    baud = 115200
    iterations = 40
    tx_ser, rx_ser = uart_pair(baud=baud)
    expected_sequence = 0

    for index in range(iterations):
        payload = build_sequence_payload(index, f"seq-payload-{index:03d}".encode())
        received = send_and_receive(tx_ser, rx_ser, payload, delay=0.02)
        sequence, body = parse_sequence_payload(received)
        assert sequence == expected_sequence
        assert body == f"seq-payload-{index:03d}".encode()
        expected_sequence += 1

    record_result(
        "test_sequence_numbered_stream",
        baud,
        8,
        "N",
        1,
        iterations,
        "PASS",
        f"last_sequence={expected_sequence - 1}",
    )


@pytest.mark.hardware
@pytest.mark.slow
def test_duration_based_soak(uart_pair, soak_seconds, record_result):
    baud = 57600
    tx_ser, rx_ser = uart_pair(baud=baud)

    result = run_soak_iteration(
        tx_ser,
        rx_ser,
        payload_factory=lambda index: build_sequence_payload(index, f"soak-{index:05d}".encode()),
        duration_seconds=soak_seconds,
        delay=0.01,
    )
    record_result(
        "test_duration_based_soak",
        baud,
        8,
        "N",
        1,
        result["iterations"],
        "PASS" if result["mismatches"] == 0 else "FAIL",
        f"duration={soak_seconds}s mismatches={result['mismatches']}",
    )

    assert result["iterations"] > 0
    assert result["mismatches"] == 0
