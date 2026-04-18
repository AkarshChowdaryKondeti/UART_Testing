# UART Control Center

UART Control Center is a structured full-stack UART validation project for Raspberry Pi or Linux systems using common UART lab setups such as a single USB-UART loopback, two USB-to-UART adapters, or a USB UART paired with Raspberry Pi GPIO UART.

It combines:

- a reusable Python UART communication package
- a pytest-based UART validation suite
- a FastAPI backend for live communication and test orchestration
- a React frontend with separate communication and testing views

## Project structure

```text
UART/
├── backend/
│   ├── app.py
│   ├── models.py
│   ├── services.py
│   └── test_runner.py
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx
│       ├── api.js
│       ├── styles.css
│       └── components/
│           ├── CommunicationPanel.jsx
│           └── TestingPanel.jsx
├── tests/
│   ├── conftest.py
│   ├── test_uart.py
│   ├── test_config_uart.py
│   ├── test_integrity_uart.py
│   ├── test_negative_uart.py
│   ├── test_protocol_uart.py
│   ├── test_stress_uart.py
│   └── test_timing_uart.py
├── uart/
│   ├── __init__.py
│   └── comm.py
├── pytest.ini
├── requirements.txt
├── run.sh
├── uart_control_center.db
└── uart_results.csv
```

## Core responsibilities

### `uart/comm.py`

Shared UART logic:

- open and configure UART ports
- send and receive data
- duplex exchange
- throughput and timing measurement
- chunked transmission
- sequence framing
- CRC frame helpers
- soak-test helpers

### `tests/`

Pytest scenarios grouped by purpose:

- `test_uart.py`: basic communication and duplex behavior
- `test_config_uart.py`: baud rate, parity, stop bits, data bits, mismatch behavior
- `test_integrity_uart.py`: large, random, binary, empty, and special payloads
- `test_timing_uart.py`: timing, timeout, inter-byte delay, throughput
- `test_stress_uart.py`: continuous stream, burst traffic, sequence stream, soak runs
- `test_protocol_uart.py`: framed command, CRC validation, sequence parsing
- `test_negative_uart.py`: invalid ports and misuse/error cases

## Test Reference

This suite contains `7` scenario groups, `31` test functions, and `90` total pytest cases.
The higher pytest case count comes from `test_uart_configurations`, which expands into `60` UART configuration combinations.

### Basic

| Test | What | Why | When | Hardware |
| --- | --- | --- | --- | --- |
| `test_basic_send_receive` | Sends one normal payload from TX to RX. | Confirms the UART link works at the simplest level. | First check after wiring or setup. | Yes |
| `test_bidirectional_transfer` | Sends data in both directions, one after the other. | Verifies each side can transmit and receive. | After the first basic test passes. | Yes |
| `test_true_duplex_exchange` | Sends from both ends at nearly the same time. | Verifies simultaneous two-way communication. | When full-duplex behavior matters. | Yes |

### Configuration

| Test | What | Why | When | Hardware |
| --- | --- | --- | --- | --- |
| `test_uart_configurations` | Tests multiple baud, data-bit, parity, and stop-bit combinations. | Confirms compatibility across supported UART settings. | After basic communication is stable. | Yes |
| `test_mismatched_baud_behavior` | Uses different baud rates on TX and RX. | Verifies a bad baud pairing does not behave like a correct transfer. | When validating setup mistakes and misconfiguration handling. | Yes |
| `test_extended_uart_parameters_are_forwarded` | Checks that `xonxoff`, `rtscts`, `dsrdtr`, and `exclusive` reach the serial layer. | Verifies software options are forwarded correctly. | After changing UART open/config code. | No |

### Integrity

| Test | What | Why | When | Hardware |
| --- | --- | --- | --- | --- |
| `test_large_data_transmission` | Sends a large payload. | Checks integrity during larger transfers. | Before stress testing. | Yes |
| `test_random_data_transmission` | Sends random bytes. | Catches corruption that simple text may miss. | For realistic data-integrity checks. | Yes |
| `test_binary_data_transmission` | Sends raw binary byte values. | Verifies non-text payload handling. | When your protocol includes binary packets. | Yes |
| `test_empty_data_transmission` | Sends an empty payload. | Validates zero-length edge-case handling. | When checking API robustness. | Yes |
| `test_special_character_payload` | Sends bytes like `0x00`, `0xFF`, newline, carriage return, and tab. | Confirms control characters and special bytes survive the link correctly. | For binary or command-style protocols. | Yes |

### Timing

| Test | What | Why | When | Hardware |
| --- | --- | --- | --- | --- |
| `test_transmission_delay_measurement` | Measures transfer latency. | Checks timing stays within a reasonable bound. | For latency-sensitive UART use. | Yes |
| `test_inter_byte_delay_handling` | Sends one byte at a time with a delay between bytes. | Verifies the receiver handles slow/chunked delivery correctly. | When devices send slowly or byte-by-byte. | Yes |
| `test_timeout_behavior` | Reads when no data arrives. | Confirms timeout and empty-read behavior. | When validating non-response scenarios. | Yes |
| `test_throughput_measurement` | Measures transfer speed during a larger payload send. | Provides a throughput/performance signal. | For benchmark-style checks. | Yes |

### Protocol

| Test | What | Why | When | Hardware |
| --- | --- | --- | --- | --- |
| `test_valid_command_frame` | Sends a valid CRC-framed command. | Confirms frame build/parse logic works correctly. | When using framed UART commands. | Yes |
| `test_invalid_command_frame` | Sends a frame with corrupted markers. | Confirms invalid framing is rejected. | For parser error handling. | Yes |
| `test_partial_command_frame` | Sends an incomplete frame. | Confirms truncated packets are handled safely. | When testing interrupted transfers. | Yes |
| `test_crc_validation` | Corrupts CRC and parses the result. | Confirms bad CRC is detected. | For protocol integrity validation. | Yes |
| `test_sequence_number_parser` | Parses a single sequence-numbered payload. | Validates the sequence parser logic itself. | After parser code changes. | No |
| `test_sequence_reorder_detection` | Checks out-of-order sequence values. | Verifies reordering can be detected logically. | When validating ordered-stream rules. | No |

### Negative

| Test | What | Why | When | Hardware |
| --- | --- | --- | --- | --- |
| `test_invalid_port_usage` | Opens a non-existent serial port. | Confirms invalid device paths fail properly. | For error-handling verification. | No |
| `test_unsupported_uart_parameter_handling` | Uses unsupported data bits. | Confirms bad UART configuration is rejected. | After config validation changes. | No |
| `test_transmission_without_proper_initialization` | Tries to send using an uninitialized serial object. | Confirms misuse is caught cleanly. | For defensive-code checks. | No |
| `test_disconnection_during_transfer` | Closes TX and then writes to it. | Verifies disconnect errors are handled. | For unplug/fault scenarios on transmit. | Yes |
| `test_wrong_connection_behavior` | Closes RX and then tries to read from it. | Verifies closed receiver errors are handled. | For receive-side fault handling. | Yes |

### Stress And Soak

| Test | What | Why | When | Hardware |
| --- | --- | --- | --- | --- |
| `test_continuous_data_stream` | Sends many packets continuously. | Checks stability under sustained traffic. | For long-run reliability testing. | Yes |
| `test_rapid_back_to_back_transmissions` | Sends bursts of packets very quickly. | Checks burst handling and buffering. | For high-frequency traffic testing. | Yes |
| `test_repeated_open_send_close_cycles` | Repeatedly opens, sends, and closes ports. | Checks repeated connection lifecycle stability. | When devices reconnect often. | Yes |
| `test_sequence_numbered_stream` | Streams sequence-numbered packets repeatedly. | Checks order and integrity over repeated transfers. | For sequence-aware stream protocols. | Yes |
| `test_duration_based_soak` | Runs communication for the configured soak duration. | Helps catch intermittent long-run issues. | Final stability and endurance testing. | Yes |

### `backend/`

FastAPI API layer:

- list available UART ports
- send data from one UART to another
- return live transfer results for the UI
- start pytest test runs in the background
- report test status/output
- store runs, results, and communication logs in SQLite
- export CSV from the database when needed

### `frontend/`

React UI:

- **Communication panel** to configure ports, send data, and view received output
- **Testing panel** to run all scenarios or user-selected scenario groups
- **Reports panel** to review run history, summaries, and filtered results
- saved custom test profiles and real-time run updates

## Hardware setup

Supported project setups:

- `usb_loopback`: one USB-to-UART adapter with its `TX` tied to its own `RX`, and `GND` connected
- `dual_usb`: two USB-to-UART adapters cross-connected
- `usb_gpio`: one USB-to-UART adapter cross-connected with Raspberry Pi GPIO UART

For two USB-to-UART adapters:

- adapter A `TX` -> adapter B `RX`
- adapter A `RX` -> adapter B `TX`
- adapter A `GND` -> adapter B `GND`

Default ports:

- `TX`: `/dev/ttyUSB0`
- `RX`: `/dev/ttyUSB1`

For one USB-to-UART loopback:

- adapter `TX` -> same adapter `RX`
- use the same serial device for both TX and RX in the app or pytest
- tests that require two independent UART endpoints, such as duplex and mismatched-baud checks, are skipped automatically

For Raspberry Pi GPIO UART, common device names are:

- `/dev/serial0` as the recommended stable alias
- `/dev/ttyAMA0` for the primary PL011 UART on many Pi setups
- `/dev/ttyS0` for the mini UART on some Pi setups

## Linux and Raspberry Pi permission notes

If you see an error like:

```text
[Errno 13] could not open port /dev/ttyAMA0: [Errno 13] Permission denied
```

the serial device exists, but your current user is not allowed to open it yet.

Check the device ownership and groups:

```bash
ls -l /dev/ttyAMA0
groups
```

Add your user to the serial-access group, then log out and back in:

```bash
sudo usermod -aG dialout $USER
```

On some Raspberry Pi images, the UART device may also be owned by `tty`, so this can help too:

```bash
sudo usermod -aG tty $USER
```

Confirm the UART is enabled:

```bash
sudo raspi-config
```

In `Interface Options`, enable `Serial Port`, and disable the serial login shell if you want the UART for your app.

After logging in again, verify access with:

```bash
python3 -m serial.tools.list_ports -v
```

When possible, prefer `/dev/serial0` in this project because it is a stable alias that tracks the active primary UART device.

## Requirements

### Python

Install backend and test dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Node.js

Install frontend dependencies:

```bash
cd frontend
npm install
cd ..
```

## Running the project

### Start backend and frontend together

Use the provided launcher:

```bash
./run.sh
```

This starts:

- FastAPI backend at `http://127.0.0.1:8000`
- React frontend at `http://127.0.0.1:5173`

Press `Ctrl+C` once to stop both processes.

`run.sh` uses `.venv/` by default. If it does not exist, the script creates it automatically and installs the Python requirements.
If `frontend/node_modules` is missing, it also runs `npm install` automatically.

You can override the virtual environment path with:

```bash
VENV_DIR=/path/to/venv ./run.sh
```

### Start backend manually

```bash
uvicorn backend.app:app --reload
```

### Start frontend manually

```bash
cd frontend
npm run dev
```

## API summary

### Health

- `GET /api/health`

### Ports

- `GET /api/ports`

### Communication

- `POST /api/communicate`

### Test profiles

- `GET /api/test-profiles`

### Saved profiles

- `GET /api/saved-profiles`
- `POST /api/saved-profiles`
- `DELETE /api/saved-profiles/{profile_id}`

### Start tests

- `POST /api/tests/run`

### Get test run status

- `GET /api/tests/{run_id}`

### Get test results for a run

- `GET /api/tests/{run_id}/results`

### Get test run history and dashboard summary

- `GET /api/test-runs`
- `GET /api/dashboard`

### Get recent communication logs

- `GET /api/communications`

### Download CSV results

- `GET /api/results`

## Running tests directly

Run the non-slow suite:

```bash
pytest tests -m "not slow" -q
```

Run hardware-tagged tests:

```bash
pytest tests -m hardware -q --tx-port /dev/ttyUSB0 --rx-port /dev/ttyUSB1
```

Run a long soak test:

```bash
pytest tests/test_stress_uart.py::test_duration_based_soak -m hardware -q --soak-seconds 3600
```

## Notes

- `uart_control_center.db` is the primary storage for test runs, test results, and communication logs.
- `uart_results.csv` is now generated as an export from the SQLite database when requested.
- The frontend expects the backend at `http://127.0.0.1:8000/api` by default.
- Override the frontend API base by setting `VITE_API_BASE` before starting Vite.
