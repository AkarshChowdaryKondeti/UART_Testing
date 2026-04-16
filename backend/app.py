import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .database import (
    create_saved_profile,
    delete_saved_profile,
    export_test_results_csv,
    fetch_communication_logs,
    fetch_dashboard_summary,
    fetch_test_results,
    fetch_test_runs,
    init_db,
    list_saved_profiles,
    log_communication,
    mark_incomplete_runs_failed,
)
from .models import (
    CommunicationRequest,
    CommunicationResponse,
    SavedProfileRequest,
    SavedProfileResponse,
    TestRunRequest,
    TestRunResponse,
    TestRunStatus,
)
from .services import decode_payload, encode_payload, list_uart_ports, run_communication
from .test_runner import get_test_run, list_test_profiles, start_test_run


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_FILE = PROJECT_ROOT / "uart_results.csv"

app = FastAPI(title="UART Control Center", version="1.0.0")
init_db()
mark_incomplete_runs_failed()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/ports")
def ports():
    return {"ports": list_uart_ports()}


@app.get("/api/test-profiles")
def test_profiles():
    return {"profiles": list_test_profiles()}


@app.get("/api/saved-profiles", response_model=list[SavedProfileResponse])
def saved_profiles():
    profiles = list_saved_profiles()
    for profile in profiles:
        profile["selected_tests"] = [item for item in profile["selected_tests"].split(",") if item]
        profile["include_slow"] = bool(profile["include_slow"])
    return profiles


@app.post("/api/saved-profiles", response_model=SavedProfileResponse)
def create_profile(request: SavedProfileRequest):
    try:
        profile = create_saved_profile(
            name=request.name,
            tx_port=request.tx_port,
            rx_port=request.rx_port,
            timeout=request.timeout,
            soak_seconds=request.soak_seconds,
            include_slow=request.include_slow,
            selected_tests=request.selected_tests,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    profile["selected_tests"] = [item for item in profile["selected_tests"].split(",") if item]
    profile["include_slow"] = bool(profile["include_slow"])
    return profile


@app.delete("/api/saved-profiles/{profile_id}")
def remove_profile(profile_id: int):
    delete_saved_profile(profile_id)
    return {"status": "deleted"}


@app.post("/api/communicate", response_model=CommunicationResponse)
def communicate(request: CommunicationRequest):
    try:
        payload = encode_payload(request.payload, request.payload_mode)
        received, elapsed = run_communication(request, payload, request.read_delay)
        received_text, received_hex = decode_payload(received)
        log_communication(
            tx_port=request.tx_port,
            rx_port=request.rx_port,
            baud=request.baud,
            data_bits=request.data_bits,
            parity=request.parity,
            stop_bits=request.stop_bits,
            payload_mode=request.payload_mode,
            payload_sent=request.payload,
            payload_received_text=received_text,
            payload_received_hex=received_hex,
            elapsed_ms=elapsed * 1000,
            status="success",
        )
        return CommunicationResponse(
            sent_bytes=len(payload),
            received_text=received_text,
            received_hex=received_hex,
            elapsed_ms=elapsed * 1000,
        )
    except Exception as exc:
        log_communication(
            tx_port=request.tx_port,
            rx_port=request.rx_port,
            baud=request.baud,
            data_bits=request.data_bits,
            parity=request.parity,
            stop_bits=request.stop_bits,
            payload_mode=request.payload_mode,
            payload_sent=request.payload,
            payload_received_text="",
            payload_received_hex="",
            elapsed_ms=0,
            status="error",
            error_message=str(exc),
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/tests/run", response_model=TestRunResponse)
def run_tests(request: TestRunRequest):
    run = start_test_run(request)
    return TestRunResponse(run_id=run["run_id"], status=run["status"])


@app.get("/api/tests/{run_id}", response_model=TestRunStatus)
def test_status(run_id: str):
    run = get_test_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Unknown run id")
    return TestRunStatus(**run)


@app.get("/api/tests/{run_id}/results")
def test_results(run_id: str):
    return {"results": fetch_test_results(run_id=run_id)}


@app.get("/api/test-runs")
def test_runs(limit: int = 50):
    runs = fetch_test_runs(limit=limit)
    for run in runs:
        run["selected_tests"] = [item for item in (run["selected_tests"] or "").split(",") if item]
        run["command"] = (run["command"] or "").split()
        run["include_slow"] = bool(run["include_slow"])
    return {"runs": runs}


@app.get("/api/dashboard")
def dashboard():
    return fetch_dashboard_summary()


@app.get("/api/communications")
def communications(limit: int = 100):
    return {"logs": fetch_communication_logs(limit=limit)}


@app.get("/api/results")
def results(run_id: str | None = None):
    export_test_results_csv(RESULTS_FILE, run_id=run_id)
    if not RESULTS_FILE.exists():
        raise HTTPException(status_code=404, detail="No results file available")
    return FileResponse(RESULTS_FILE)


@app.websocket("/ws/tests/{run_id}")
async def test_updates(websocket: WebSocket, run_id: str):
    await websocket.accept()
    try:
        while True:
            run = get_test_run(run_id)
            if not run:
                await websocket.send_json({"type": "error", "message": "Unknown run id"})
                break
            await websocket.send_json(
                {
                    "type": "status",
                    "run": run,
                    "results": fetch_test_results(run_id=run_id),
                }
            )
            if run.get("status") != "running":
                break
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
