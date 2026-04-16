const defaultApiBase = `${window.location.protocol}//${window.location.hostname}:8000/api`;
const API_BASE = import.meta.env.VITE_API_BASE ?? defaultApiBase;
const WS_BASE = API_BASE.replace(/^http/, "ws").replace(/\/api$/, "");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const body = await response.json();
      message = body.detail ?? message;
    } catch {
      // ignore json parse errors
    }
    throw new Error(message);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

export function fetchPorts() {
  return request("/ports");
}

export function fetchTestProfiles() {
  return request("/test-profiles");
}

export function runCommunication(payload) {
  return request("/communicate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function startTests(payload) {
  return request("/tests/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTestStatus(runId) {
  return request(`/tests/${runId}`);
}

export function getTestResults(runId) {
  return request(`/tests/${runId}/results`);
}

export function getCommunicationLogs(limit = 20) {
  return request(`/communications?limit=${limit}`);
}

export function getDashboardSummary() {
  return request("/dashboard");
}

export function getTestRunHistory(limit = 50) {
  return request(`/test-runs?limit=${limit}`);
}

export function getResultsDownloadUrl(runId) {
  const suffix = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
  return `${API_BASE.replace(/\/api$/, "")}/api/results${suffix}`;
}

export function createTestRunSocket(runId) {
  return new WebSocket(`${WS_BASE}/ws/tests/${runId}`);
}
