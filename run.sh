#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_HOST="${BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PIP_TIMEOUT="${PIP_TIMEOUT:-120}"
PIP_RETRIES="${PIP_RETRIES:-10}"
INSTALL_ATTEMPTS="${INSTALL_ATTEMPTS:-3}"
NPM_FETCH_RETRIES="${NPM_FETCH_RETRIES:-5}"
ENABLE_RELOAD="${ENABLE_RELOAD:-1}"

cleanup() {
  local pid

  for pid in "${BACKEND_PID:-}" "${FRONTEND_PID:-}"; do
    if [[ -n "${pid}" ]]; then
      kill -TERM "${pid}" 2>/dev/null || true
    fi
  done

  for pid in "${BACKEND_PID:-}" "${FRONTEND_PID:-}"; do
    if [[ -n "${pid}" ]]; then
      wait "${pid}" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

venv_is_usable() {
  [[ -x "${VENV_DIR}/bin/python" ]] && "${VENV_DIR}/bin/python" -c "import sys" >/dev/null 2>&1
}

frontend_deps_usable() {
  [[ -f "${ROOT_DIR}/frontend/node_modules/vite/dist/node/cli.js" ]]
}

require_command() {
  local command_name="$1"
  local install_hint="$2"

  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Required command not found: ${command_name}"
    echo "${install_hint}"
    exit 1
  fi
}

port_is_in_use() {
  local host="$1"
  local port="$2"

  "${PYTHON_BIN}" - "$host" "$port" <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    sys.exit(0 if sock.connect_ex((host, port)) == 0 else 1)
PY
}

retry_command() {
  local description="$1"
  shift

  local attempt=1
  while (( attempt <= INSTALL_ATTEMPTS )); do
    echo "${description} (attempt ${attempt}/${INSTALL_ATTEMPTS})"
    if "$@"; then
      return 0
    fi

    if (( attempt == INSTALL_ATTEMPTS )); then
      echo "${description} failed after ${INSTALL_ATTEMPTS} attempts."
      return 1
    fi

    echo "${description} failed. Waiting before retry..."
    sleep $(( attempt * 5 ))
    attempt=$(( attempt + 1 ))
  done
}

cd "${ROOT_DIR}"

require_command "${PYTHON_BIN}" "Install Python 3 and ensure it is available on PATH."
require_command "npm" "Install Node.js and npm, then try again."

if venv_is_usable; then
  echo "Activating virtual environment: ${VENV_DIR}"
else
  if [[ -d "${VENV_DIR}" ]]; then
    echo "Existing virtual environment is not usable on this machine."
    echo "Recreating virtual environment at ${VENV_DIR}"
    rm -rf "${VENV_DIR}"
  else
    echo "Virtual environment not found at ${VENV_DIR}"
    echo "Creating virtual environment..."
  fi
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1090
source "${VENV_DIR}/bin/activate"

if ! python -c "import fastapi, uvicorn" >/dev/null 2>&1; then
  retry_command "Installing Python dependencies from requirements.txt" \
    python -m pip install \
      --retries "${PIP_RETRIES}" \
      --timeout "${PIP_TIMEOUT}" \
      --prefer-binary \
      -r "${ROOT_DIR}/requirements.txt" || {
        echo "Python dependency installation could not be completed."
        echo "If this Raspberry Pi has intermittent internet, try again in a minute."
        echo "If it keeps failing, verify network access and system time with: date"
        exit 1
      }
fi

if frontend_deps_usable; then
  :
else
  if [[ -d "${ROOT_DIR}/frontend/node_modules" ]]; then
    echo "Frontend dependencies are not usable on this machine."
    echo "Reinstalling frontend dependencies at ${ROOT_DIR}/frontend/node_modules"
    rm -rf "${ROOT_DIR}/frontend/node_modules"
  else
    echo "Installing frontend dependencies"
  fi
  (
    cd "${ROOT_DIR}/frontend"
    retry_command "Installing frontend dependencies" env \
      npm_config_fetch_retries="${NPM_FETCH_RETRIES}" \
      npm_config_fetch_retry_mintimeout=20000 \
      npm_config_fetch_retry_maxtimeout=120000 \
      npm install
  )
fi

if port_is_in_use "${BACKEND_HOST}" "${BACKEND_PORT}"; then
  echo "Backend port ${BACKEND_PORT} is already in use on ${BACKEND_HOST}."
  echo "Set BACKEND_PORT to a free port or stop the existing process."
  exit 1
fi

if port_is_in_use "127.0.0.1" "${FRONTEND_PORT}"; then
  echo "Frontend port ${FRONTEND_PORT} is already in use on 127.0.0.1."
  echo "Set FRONTEND_PORT to a free port or stop the existing process."
  exit 1
fi

echo "Starting FastAPI backend on http://${BACKEND_HOST}:${BACKEND_PORT}"
UVICORN_ARGS=(backend.app:app --host "${BACKEND_HOST}" --port "${BACKEND_PORT}")
if [[ "${ENABLE_RELOAD}" == "1" ]]; then
  UVICORN_ARGS+=(--reload)
fi
python -m uvicorn "${UVICORN_ARGS[@]}" &
BACKEND_PID=$!

echo "Starting React frontend on http://127.0.0.1:${FRONTEND_PORT}"
(
  cd "${ROOT_DIR}/frontend"
  npm run dev -- --host 0.0.0.0 --port "${FRONTEND_PORT}"
) &
FRONTEND_PID=$!

wait "${BACKEND_PID}" "${FRONTEND_PID}"
