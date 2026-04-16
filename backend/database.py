import csv
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "uart_control_center.db"
DEFAULT_CSV_EXPORT_PATH = PROJECT_ROOT / "uart_results.csv"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_db_path():
    return Path(os.getenv("UART_DB_PATH", DEFAULT_DB_PATH))


@contextmanager
def db_connection():
    connection = sqlite3.connect(get_db_path())
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db():
    with db_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS test_runs (
                run_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                tx_port TEXT,
                rx_port TEXT,
                timeout REAL,
                soak_seconds REAL,
                include_slow INTEGER NOT NULL DEFAULT 0,
                selected_tests TEXT,
                command TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                return_code INTEGER,
                stdout TEXT DEFAULT '',
                stderr TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT,
                test_name TEXT NOT NULL,
                tx_port TEXT,
                rx_port TEXT,
                baud TEXT,
                data_bits TEXT,
                parity TEXT,
                stop_bits TEXT,
                payload_length INTEGER,
                status TEXT NOT NULL,
                details TEXT,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (run_id) REFERENCES test_runs(run_id)
            );

            CREATE TABLE IF NOT EXISTS communication_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_port TEXT NOT NULL,
                rx_port TEXT NOT NULL,
                baud INTEGER NOT NULL,
                data_bits INTEGER NOT NULL,
                parity TEXT NOT NULL,
                stop_bits INTEGER NOT NULL,
                payload_mode TEXT NOT NULL,
                payload_sent TEXT NOT NULL,
                payload_received_text TEXT,
                payload_received_hex TEXT,
                elapsed_ms REAL NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS saved_test_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                tx_port TEXT NOT NULL,
                rx_port TEXT NOT NULL,
                timeout REAL NOT NULL,
                soak_seconds REAL NOT NULL,
                include_slow INTEGER NOT NULL DEFAULT 0,
                selected_tests TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )


def mark_incomplete_runs_failed():
    with db_connection() as connection:
        connection.execute(
            """
            UPDATE test_runs
            SET status = 'failed',
                return_code = -1,
                stderr = CASE
                    WHEN COALESCE(stderr, '') = '' THEN 'Run marked failed after backend restart before completion.'
                    ELSE stderr || CHAR(10) || 'Run marked failed after backend restart before completion.'
                END,
                finished_at = ?
            WHERE status = 'running'
            """,
            (utc_now(),),
        )


def create_test_run(run_id, request, command):
    with db_connection() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO test_runs (
                run_id, mode, status, tx_port, rx_port, timeout, soak_seconds,
                include_slow, selected_tests, command, started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                request.mode,
                "running",
                request.tx_port,
                request.rx_port,
                request.timeout,
                request.soak_seconds,
                int(request.include_slow),
                ",".join(request.selected_tests),
                " ".join(command),
                utc_now(),
            ),
        )


def create_manual_test_run(run_id, *, tx_port, rx_port, timeout, soak_seconds):
    with db_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO test_runs (
                run_id, mode, status, tx_port, rx_port, timeout, soak_seconds,
                include_slow, selected_tests, command, started_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                "manual",
                "running",
                tx_port,
                rx_port,
                timeout,
                soak_seconds,
                0,
                "",
                "pytest",
                utc_now(),
            ),
        )


def update_test_run(run_id, *, status, return_code=None, stdout="", stderr=""):
    with db_connection() as connection:
        connection.execute(
            """
            UPDATE test_runs
            SET status = ?, return_code = ?, stdout = ?, stderr = ?, finished_at = ?
            WHERE run_id = ?
            """,
            (status, return_code, stdout, stderr, utc_now(), run_id),
        )


def save_test_result(
    *,
    run_id,
    test_name,
    tx_port,
    rx_port,
    baud,
    data_bits,
    parity,
    stop_bits,
    payload_length,
    status,
    details,
):
    with db_connection() as connection:
        connection.execute(
            """
            INSERT INTO test_results (
                run_id, test_name, tx_port, rx_port, baud, data_bits, parity,
                stop_bits, payload_length, status, details, recorded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                test_name,
                tx_port,
                rx_port,
                str(baud),
                str(data_bits),
                parity,
                str(stop_bits),
                payload_length,
                status,
                details,
                utc_now(),
            ),
        )


def log_communication(
    *,
    tx_port,
    rx_port,
    baud,
    data_bits,
    parity,
    stop_bits,
    payload_mode,
    payload_sent,
    payload_received_text,
    payload_received_hex,
    elapsed_ms,
    status,
    error_message=None,
):
    with db_connection() as connection:
        connection.execute(
            """
            INSERT INTO communication_logs (
                tx_port, rx_port, baud, data_bits, parity, stop_bits, payload_mode,
                payload_sent, payload_received_text, payload_received_hex, elapsed_ms,
                status, error_message, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx_port,
                rx_port,
                baud,
                data_bits,
                parity,
                stop_bits,
                payload_mode,
                payload_sent,
                payload_received_text,
                payload_received_hex,
                elapsed_ms,
                status,
                error_message,
                utc_now(),
            ),
        )


def fetch_test_run(run_id):
    with db_connection() as connection:
        row = connection.execute("SELECT * FROM test_runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None


def fetch_test_results(run_id=None, limit=200):
    query = """
        SELECT run_id, test_name, tx_port, rx_port, baud, data_bits, parity,
               stop_bits, payload_length, status, details, recorded_at
        FROM test_results
    """
    params = []
    if run_id:
        query += " WHERE run_id = ?"
        params.append(run_id)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    with db_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def fetch_communication_logs(limit=100):
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT tx_port, rx_port, baud, data_bits, parity, stop_bits, payload_mode,
                   payload_sent, payload_received_text, payload_received_hex, elapsed_ms,
                   status, error_message, created_at
            FROM communication_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def fetch_test_runs(limit=50):
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT run_id, mode, status, tx_port, rx_port, timeout, soak_seconds,
                   include_slow, selected_tests, command, started_at, finished_at,
                   return_code, stdout, stderr
            FROM test_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def fetch_dashboard_summary():
    with db_connection() as connection:
        totals = connection.execute(
            """
            SELECT
                COUNT(*) AS total_results,
                SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed_results,
                SUM(CASE WHEN status != 'PASS' THEN 1 ELSE 0 END) AS failed_results
            FROM test_results
            """
        ).fetchone()
        run_totals = connection.execute(
            """
            SELECT
                COUNT(*) AS total_runs,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_runs,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_runs,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) AS running_runs
            FROM test_runs
            """
        ).fetchone()
        categories = connection.execute(
            """
            SELECT
                CASE
                    WHEN test_name LIKE 'test_uart%' THEN 'Basic'
                    WHEN test_name LIKE 'test_config%' THEN 'Configuration'
                    WHEN test_name LIKE 'test_integrity%' THEN 'Integrity'
                    WHEN test_name LIKE 'test_stress%' THEN 'Stress'
                    WHEN test_name LIKE 'test_timing%' THEN 'Timing'
                    WHEN test_name LIKE 'test_protocol%' THEN 'Protocol'
                    WHEN test_name LIKE 'test_negative%' THEN 'Negative'
                    ELSE 'Other'
                END AS category,
                SUM(CASE WHEN status = 'PASS' THEN 1 ELSE 0 END) AS passed,
                SUM(CASE WHEN status != 'PASS' THEN 1 ELSE 0 END) AS failed
            FROM test_results
            GROUP BY category
            ORDER BY category
            """
        ).fetchall()

        return {
            "total_results": totals["total_results"] or 0,
            "passed_results": totals["passed_results"] or 0,
            "failed_results": totals["failed_results"] or 0,
            "total_runs": run_totals["total_runs"] or 0,
            "completed_runs": run_totals["completed_runs"] or 0,
            "failed_runs": run_totals["failed_runs"] or 0,
            "running_runs": run_totals["running_runs"] or 0,
            "category_breakdown": [dict(row) for row in categories],
        }


def list_saved_profiles():
    with db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, name, tx_port, rx_port, timeout, soak_seconds, include_slow,
                   selected_tests, created_at, updated_at
            FROM saved_test_profiles
            ORDER BY updated_at DESC, name ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]


def create_saved_profile(*, name, tx_port, rx_port, timeout, soak_seconds, include_slow, selected_tests):
    timestamp = utc_now()
    with db_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO saved_test_profiles (
                name, tx_port, rx_port, timeout, soak_seconds, include_slow,
                selected_tests, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                tx_port,
                rx_port,
                timeout,
                soak_seconds,
                int(include_slow),
                ",".join(selected_tests),
                timestamp,
                timestamp,
            ),
        )
        profile_id = cursor.lastrowid
    return fetch_saved_profile(profile_id)


def fetch_saved_profile(profile_id):
    with db_connection() as connection:
        row = connection.execute(
            """
            SELECT id, name, tx_port, rx_port, timeout, soak_seconds, include_slow,
                   selected_tests, created_at, updated_at
            FROM saved_test_profiles
            WHERE id = ?
            """,
            (profile_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_saved_profile(profile_id):
    with db_connection() as connection:
        connection.execute("DELETE FROM saved_test_profiles WHERE id = ?", (profile_id,))


def export_test_results_csv(destination=None, run_id=None):
    destination = Path(destination or DEFAULT_CSV_EXPORT_PATH)
    rows = fetch_test_results(run_id=run_id, limit=100000)
    with destination.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "Run ID",
                "Test",
                "TX Port",
                "RX Port",
                "Baud",
                "Data Bits",
                "Parity",
                "Stop Bits",
                "Payload Length",
                "Status",
                "Details",
                "Recorded At",
            ]
        )
        for row in reversed(rows):
            writer.writerow(
                [
                    row["run_id"],
                    row["test_name"],
                    row["tx_port"],
                    row["rx_port"],
                    row["baud"],
                    row["data_bits"],
                    row["parity"],
                    row["stop_bits"],
                    row["payload_length"],
                    row["status"],
                    row["details"],
                    row["recorded_at"],
                ]
            )
    return destination
