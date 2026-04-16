from typing import Literal

from pydantic import BaseModel, Field


class UARTConfig(BaseModel):
    tx_port: str
    rx_port: str
    baud: int = 9600
    data_bits: int = 8
    parity: str = "N"
    stop_bits: int = 1
    timeout: float = 1.0


class CommunicationRequest(UARTConfig):
    payload: str = Field(..., description="Payload string supplied in text or hex mode")
    payload_mode: Literal["text", "hex"] = "text"
    read_delay: float = 0.2


class CommunicationResponse(BaseModel):
    sent_bytes: int
    received_text: str
    received_hex: str
    elapsed_ms: float


class TestRunRequest(BaseModel):
    mode: Literal["all", "custom"] = "all"
    tx_port: str = "/dev/ttyUSB0"
    rx_port: str = "/dev/ttyUSB1"
    timeout: float = 1.0
    soak_seconds: float = 5.0
    include_slow: bool = False
    include_negative: bool = False
    selected_tests: list[str] = Field(default_factory=list)


class TestRunResponse(BaseModel):
    run_id: str
    status: str


class TestRunStatus(BaseModel):
    run_id: str
    status: str
    command: list[str]
    started_at: str
    finished_at: str | None = None
    return_code: int | None = None
    selected_tests: list[str] = Field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


class SavedProfileRequest(BaseModel):
    name: str
    tx_port: str = "/dev/ttyUSB0"
    rx_port: str = "/dev/ttyUSB1"
    timeout: float = 1.0
    soak_seconds: float = 5.0
    include_slow: bool = False
    selected_tests: list[str] = Field(default_factory=list)


class SavedProfileResponse(SavedProfileRequest):
    id: int
    created_at: str
    updated_at: str
