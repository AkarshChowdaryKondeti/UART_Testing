import pytest

from uart.comm import duplex_exchange, send_and_receive


@pytest.mark.hardware
def test_basic_send_receive(uart_pair, fixed_payload, record_result):
    baud = 9600
    data_bits = 8
    parity = "N"
    stop_bits = 1
    tx_ser, rx_ser = uart_pair(baud=baud, data_bits=data_bits, parity=parity, stop_bits=stop_bits)

    received = send_and_receive(tx_ser, rx_ser, fixed_payload)
    record_result(
        "test_basic_send_receive",
        baud,
        data_bits,
        parity,
        stop_bits,
        len(fixed_payload),
        "PASS" if received == fixed_payload else "FAIL",
        received.hex(),
    )

    assert received == fixed_payload


@pytest.mark.hardware
def test_bidirectional_transfer(uart_pair, record_result):
    baud = 9600
    data_bits = 8
    parity = "N"
    stop_bits = 1
    forward_payload = b"pi-port-a-to-b"
    reverse_payload = b"pi-port-b-to-a"
    tx_ser, rx_ser = uart_pair(baud=baud, data_bits=data_bits, parity=parity, stop_bits=stop_bits)

    forward = send_and_receive(tx_ser, rx_ser, forward_payload)
    reverse = send_and_receive(rx_ser, tx_ser, reverse_payload)
    passed = forward == forward_payload and reverse == reverse_payload

    record_result(
        "test_bidirectional_transfer",
        baud,
        data_bits,
        parity,
        stop_bits,
        len(forward_payload) + len(reverse_payload),
        "PASS" if passed else "FAIL",
        f"forward={forward.hex()} reverse={reverse.hex()}",
    )

    assert forward == forward_payload
    assert reverse == reverse_payload


@pytest.mark.hardware
def test_true_duplex_exchange(uart_pair, record_result):
    baud = 115200
    data_bits = 8
    parity = "N"
    stop_bits = 1
    payload_a = b"duplex-a-to-b"
    payload_b = b"duplex-b-to-a"
    ser_a, ser_b = uart_pair(baud=baud, data_bits=data_bits, parity=parity, stop_bits=stop_bits)

    received_a, received_b = duplex_exchange(ser_a, payload_a, ser_b, payload_b, delay=0.05)
    passed = received_a == payload_b and received_b == payload_a
    record_result(
        "test_true_duplex_exchange",
        baud,
        data_bits,
        parity,
        stop_bits,
        len(payload_a) + len(payload_b),
        "PASS" if passed else "FAIL",
        f"received_a={received_a.hex()} received_b={received_b.hex()}",
    )

    assert received_a == payload_b
    assert received_b == payload_a
