import os
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .database import create_test_run, fetch_test_run, update_test_run
from .services import TEST_FILE_MAP


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS: dict[str, dict] = {}
TESTS_ROOT = PROJECT_ROOT / "tests"
TEST_PROFILE_STATS = {
    "basic": {"case_count": 3, "slow_case_count": 0},
    "config": {"case_count": 62, "slow_case_count": 0},
    "integrity": {"case_count": 5, "slow_case_count": 0},
    "stress": {"case_count": 5, "slow_case_count": 5},
    "timing": {"case_count": 4, "slow_case_count": 0},
    "protocol": {"case_count": 6, "slow_case_count": 0},
    "negative": {"case_count": 5, "slow_case_count": 0},
}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _resolve_test_targets(request):
    if request.mode == "all":
        targets = list(TEST_FILE_MAP.values())
    elif request.selected_tests:
        targets = [TEST_FILE_MAP.get(name, name) for name in request.selected_tests]
    else:
        targets = ["test_uart.py"]

    if not request.include_negative:
        targets = [target for target in targets if Path(target).name != TEST_FILE_MAP["negative"]]

    if not targets:
        targets = ["test_uart.py"]

    return [str(TESTS_ROOT / target) for target in targets]


def _build_pytest_command(request):
    command = [sys.executable, "-m", "pytest", "-q"]
    command.extend(_resolve_test_targets(request))

    if not request.include_slow:
        command.extend(["-m", "not slow"])

    command.extend(
        [
            "--uart-setup",
            request.setup_type,
            "--tx-port",
            request.tx_port,
            "--rx-port",
            request.rx_port,
            "--uart-timeout",
            str(request.timeout),
            "--soak-seconds",
            str(request.soak_seconds),
        ]
    )
    return command


def _run_pytest(run_id, command, selected_tests):
    run = RUNS[run_id]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["UART_TEST_RUN_ID"] = run_id
    env["UART_DB_PATH"] = env.get("UART_DB_PATH", str(PROJECT_ROOT / "uart_control_center.db"))
    process = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )
    run["status"] = "completed" if process.returncode == 0 else "failed"
    run["finished_at"] = _utc_now()
    run["return_code"] = process.returncode
    run["stdout"] = process.stdout
    run["stderr"] = process.stderr
    run["selected_tests"] = selected_tests
    update_test_run(
        run_id,
        status=run["status"],
        return_code=process.returncode,
        stdout=process.stdout,
        stderr=process.stderr,
    )


def start_test_run(request):
    run_id = str(uuid.uuid4())
    command = _build_pytest_command(request)
    RUNS[run_id] = {
        "run_id": run_id,
        "status": "running",
        "command": command,
        "started_at": _utc_now(),
        "finished_at": None,
        "return_code": None,
        "selected_tests": request.selected_tests,
        "stdout": "",
        "stderr": "",
    }
    create_test_run(run_id, request, command)
    thread = threading.Thread(target=_run_pytest, args=(run_id, command, request.selected_tests), daemon=True)
    thread.start()
    return RUNS[run_id]


def get_test_run(run_id):
    run = RUNS.get(run_id) or fetch_test_run(run_id)
    if not run:
        return None
    if isinstance(run.get("command"), str):
        run["command"] = run["command"].split()
    if isinstance(run.get("selected_tests"), str):
        run["selected_tests"] = [item for item in run["selected_tests"].split(",") if item]
    return run


def list_test_profiles():
    profiles = []
    for key, value in TEST_FILE_MAP.items():
        stats = TEST_PROFILE_STATS.get(key, {"case_count": 0, "slow_case_count": 0})
        profiles.append(
            {
                "id": key,
                "label": key.title(),
                "file": value,
                "case_count": stats["case_count"],
                "slow_case_count": stats["slow_case_count"],
            }
        )
    return profiles
