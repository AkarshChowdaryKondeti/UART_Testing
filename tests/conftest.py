import os
import random
import sys
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.database import create_manual_test_run, init_db, save_test_result, update_test_run
from backend.services import detect_default_uart_config, infer_setup_type, setup_requires_distinct_ports
from uart.comm import close_uart, open_uart


DEFAULT_SETUP, DEFAULT_TX_PORT, DEFAULT_RX_PORT = detect_default_uart_config()
DEFAULT_TIMEOUT = 1.0
DEFAULT_SOAK_SECONDS = 5.0
TEST_RUN_ID = os.getenv("UART_TEST_RUN_ID", f"manual-{uuid.uuid4()}")


def _default_result_metadata(item):
    test_name = getattr(item, "originalname", None) or item.name.split("[")[0]
    return {
        "test_name": test_name,
        "baud": "-",
        "data_bits": "-",
        "parity": "-",
        "stop_bits": "-",
        "payload_length": 0,
        "details": "Recorded automatically from pytest outcome.",
    }


def _build_result_details(report, metadata):
    details = metadata.get("details") or ""
    if report.failed:
        failure_text = str(report.longrepr)
        return f"{details}\n\n{failure_text}".strip()
    return details or report.outcome.upper()


def _save_report_result(item, report):
    if getattr(item, "_uart_result_saved", False):
        return

    if report.when == "call":
        status = "PASS" if report.passed else "FAIL"
    elif report.failed:
        status = "FAIL"
    else:
        return

    metadata = getattr(item, "_uart_result_metadata", None) or _default_result_metadata(item)
    save_test_result(
        run_id=TEST_RUN_ID,
        test_name=metadata["test_name"],
        tx_port=item.config.getoption("--tx-port"),
        rx_port=item.config.getoption("--rx-port"),
        baud=metadata["baud"],
        data_bits=metadata["data_bits"],
        parity=metadata["parity"],
        stop_bits=metadata["stop_bits"],
        payload_length=metadata["payload_length"],
        status=status,
        details=_build_result_details(report, metadata),
    )
    item._uart_result_saved = True


def pytest_addoption(parser):
    parser.addoption("--uart-setup", action="store", default=os.getenv("UART_SETUP_TYPE", DEFAULT_SETUP))
    parser.addoption("--tx-port", action="store", default=os.getenv("UART_TX_PORT", DEFAULT_TX_PORT))
    parser.addoption("--rx-port", action="store", default=os.getenv("UART_RX_PORT", DEFAULT_RX_PORT))
    parser.addoption("--uart-timeout", action="store", type=float, default=float(os.getenv("UART_TIMEOUT", DEFAULT_TIMEOUT)))
    parser.addoption("--soak-seconds", action="store", type=float, default=float(os.getenv("UART_SOAK_SECONDS", DEFAULT_SOAK_SECONDS)))


def _require_port(path):
    if not Path(path).exists():
        pytest.skip(f"UART port not available: {path}")


@pytest.fixture(scope="session")
def uart_setup(pytestconfig):
    setup_type = pytestconfig.getoption("--uart-setup")
    tx_port = pytestconfig.getoption("--tx-port")
    rx_port = pytestconfig.getoption("--rx-port")
    return setup_type or infer_setup_type(tx_port, rx_port)


@pytest.fixture(scope="session")
def tx_port(pytestconfig):
    return pytestconfig.getoption("--tx-port")


@pytest.fixture(scope="session")
def rx_port(pytestconfig):
    return pytestconfig.getoption("--rx-port")


@pytest.fixture(scope="session")
def uart_timeout(pytestconfig):
    return pytestconfig.getoption("--uart-timeout")


@pytest.fixture(scope="session")
def soak_seconds(pytestconfig):
    return pytestconfig.getoption("--soak-seconds")


@pytest.fixture
def uart_ports_available(tx_port, rx_port, uart_setup):
    _require_port(tx_port)
    if setup_requires_distinct_ports(uart_setup):
        _require_port(rx_port)
    return tx_port, rx_port


@pytest.fixture
def require_distinct_uart_endpoints(uart_setup):
    if not setup_requires_distinct_ports(uart_setup):
        pytest.skip("This test requires two independent UART endpoints and is not valid for usb_loopback setup.")


@pytest.fixture(scope="session", autouse=True)
def database_ready(tx_port, rx_port, uart_timeout, soak_seconds):
    init_db()
    create_manual_test_run(
        TEST_RUN_ID,
        tx_port=tx_port,
        rx_port=rx_port,
        timeout=uart_timeout,
        soak_seconds=soak_seconds,
    )


@pytest.fixture
def record_result(request):
    def _record(test_name, baud, data_bits, parity, stop_bits, payload_len, status, details):
        request.node._uart_result_metadata = {
            "test_name": test_name,
            "baud": baud,
            "data_bits": data_bits,
            "parity": parity,
            "stop_bits": stop_bits,
            "payload_length": payload_len,
            "details": details,
        }

    return _record


@pytest.fixture
def uart_pair(tx_port, rx_port, uart_timeout, uart_setup):
    _require_port(tx_port)
    if setup_requires_distinct_ports(uart_setup):
        _require_port(rx_port)

    opened = []

    def _open_pair(baud=9600, data_bits=8, parity="N", stop_bits=1):
        tx_ser = open_uart(tx_port, baud, data_bits, parity, stop_bits, timeout=uart_timeout)
        if setup_requires_distinct_ports(uart_setup):
            rx_ser = open_uart(rx_port, baud, data_bits, parity, stop_bits, timeout=uart_timeout)
            opened.extend([tx_ser, rx_ser])
        else:
            rx_ser = tx_ser
            opened.append(tx_ser)
        return tx_ser, rx_ser

    yield _open_pair

    for ser in reversed(opened):
        close_uart(ser)


@pytest.fixture(scope="session")
def fixed_payload():
    return b"UART functional test payload"


@pytest.fixture(scope="session")
def binary_payload():
    return bytes(range(256))


@pytest.fixture
def random_payload():
    size = 128
    return bytes(random.getrandbits(8) for _ in range(size))


@pytest.fixture(scope="session")
def large_payload():
    return b"UART-STRESS-" * 512


def pytest_sessionfinish(session, exitstatus):
    final_status = "completed" if exitstatus == 0 else "failed"
    update_test_run(TEST_RUN_ID, status=final_status, return_code=exitstatus)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.when in {"setup", "call", "teardown"}:
        _save_report_result(item, report)
