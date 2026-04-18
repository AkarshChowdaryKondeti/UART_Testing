import { useEffect, useMemo, useRef, useState } from "react";

import {
  createTestRunSocket,
  fetchPorts,
  fetchTestProfiles,
  getTestResults,
  getTestStatus,
  startTests,
} from "../api";


const defaultSelection = {
  mode: "all",
  setup_type: "dual_usb",
  tx_port: "/dev/ttyUSB0",
  rx_port: "/dev/ttyUSB1",
  timeout: 1,
  soak_seconds: 5,
  include_slow: false,
  include_negative: false,
  selected_tests: [],
};

function filterVisiblePorts(ports) {
  return ports.filter((port) => !/ttys0$/i.test(port));
}

function buildPortOptions(selectedPort, otherPort, ports) {
  const uniquePorts = Array.from(new Set([selectedPort, ...ports].filter(Boolean)));
  return uniquePorts.filter((port) => port === selectedPort || port !== otherPort);
}

function getDistinctPortSelection(current, nextPorts) {
  if (!nextPorts.length) {
    return current;
  }

  const txPort = nextPorts.includes(current.tx_port) ? current.tx_port : nextPorts[0];
  const rxCandidates = nextPorts.filter((port) => port !== txPort);
  const rxPort = rxCandidates.includes(current.rx_port) ? current.rx_port : (rxCandidates[0] ?? txPort);

  return { tx_port: txPort, rx_port: rxPort };
}

function getSetupAwarePortSelection(current, nextPorts) {
  if (current.setup_type === "usb_loopback") {
    const selectedPort = nextPorts.includes(current.tx_port) ? current.tx_port : (nextPorts[0] ?? current.tx_port);
    return { tx_port: selectedPort, rx_port: selectedPort };
  }

  return getDistinctPortSelection(current, nextPorts);
}


function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}


function formatTestName(name) {
  return name
    .replace(/^test_/, "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getRunState(status) {
  if (status === "running") {
    return "Running";
  }
  if (status === "completed" || status === "failed") {
    return "Finished";
  }
  return "Idle";
}

function getExpectedRecordedCount(form, profiles) {
  const selectedProfiles = form.mode === "all"
    ? profiles
    : form.selected_tests.length
      ? profiles.filter((profile) => form.selected_tests.includes(profile.id))
      : profiles.filter((profile) => profile.id === "basic");

  return selectedProfiles
    .filter((profile) => form.include_negative || profile.id !== "negative")
    .reduce((total, profile) => {
      const slowCases = form.include_slow ? 0 : (profile.slow_case_count ?? 0);
      return total + Math.max(0, (profile.case_count ?? 0) - slowCases);
    }, 0);
}

function formatDateTime(value) {
  if (!value) {
    return "Not finished";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function formatDuration(startedAt, finishedAt) {
  if (!startedAt || !finishedAt) {
    return "In progress";
  }

  const elapsedMs = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  if (Number.isNaN(elapsedMs) || elapsedMs < 0) {
    return "Unknown";
  }

  if (elapsedMs < 1000) {
    return `${elapsedMs} ms`;
  }

  return `${(elapsedMs / 1000).toFixed(1)} s`;
}

function getRunSummaryText(run, passCount, failCount) {
  if (!run) {
    return "Start a run to see live execution details here.";
  }

  if (run.status === "running") {
    return `This run is in progress. ${passCount} tests have passed and ${failCount} have failed so far.`;
  }

  if (run.status === "failed") {
    return `This run finished with failures. ${passCount} tests passed and ${failCount} tests failed.`;
  }

  return `This run finished successfully. ${passCount} tests passed and ${failCount} tests failed.`;
}

function buildOverviewRows(run, passCount, failCount, passRate) {
  if (!run) {
    return [];
  }

  return [
    ["Run ID", run.run_id],
    ["Run Status", run.status],
    ["Passed", String(passCount)],
    ["Failed", String(failCount)],
    ["Pass Rate", `${passRate}%`],
    ["Duration", formatDuration(run.started_at, run.finished_at)],
    ["Return Code", run.return_code ?? "Running"],
    ["Started", formatDateTime(run.started_at)],
    ["Finished", formatDateTime(run.finished_at)],
  ];
}


export default function TestingPanel() {
  const [ports, setPorts] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [form, setForm] = useState(defaultSelection);
  const [runId, setRunId] = useState("");
  const [status, setStatus] = useState(null);
  const [results, setResults] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const socketRef = useRef(null);

  async function loadOptions() {
    try {
      const [portsData, profilesData] = await Promise.all([fetchPorts(), fetchTestProfiles()]);
      const nextPorts = filterVisiblePorts(portsData.ports ?? []);
      setPorts(nextPorts);
      setProfiles(profilesData.profiles ?? []);
      setForm((current) => ({ ...current, ...getSetupAwarePortSelection(current, nextPorts) }));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadOptions();
    return () => {
      socketRef.current?.close();
    };
  }, []);

  const selectedCount = useMemo(() => form.selected_tests.length, [form.selected_tests]);
  const passCount = useMemo(() => results.filter((item) => item.status === "PASS").length, [results]);
  const failCount = useMemo(() => results.filter((item) => item.status !== "PASS").length, [results]);
  const passRate = results.length ? Math.round((passCount / results.length) * 100) : 0;
  const expectedRecordedCount = useMemo(() => getExpectedRecordedCount(form, profiles), [form, profiles]);
  const runState = getRunState(status?.status);
  const runSummaryText = getRunSummaryText(status, passCount, failCount);
  const overviewRows = useMemo(() => buildOverviewRows(status, passCount, failCount, passRate), [status, passCount, failCount, passRate]);
  const hasEnoughPorts = form.setup_type === "usb_loopback" ? ports.length >= 1 : ports.length >= 2;
  const txOptions = buildPortOptions(form.tx_port, form.rx_port, ports);
  const rxOptions = form.setup_type === "usb_loopback" ? txOptions : buildPortOptions(form.rx_port, form.tx_port, ports);
  const portStatusMessage = !ports.length
    ? "No UART ports detected. Connect your serial adapters and press Refresh Ports or restart the app."
    : !hasEnoughPorts
      ? form.setup_type === "usb_loopback"
        ? "One UART adapter is enough for loopback mode. Connect a serial adapter and refresh the port list."
        : "Only one UART port is detected. Connect one more serial device to choose different TX and RX ports."
      : "";

  function updateField(key, value) {
    setForm((current) => {
      if (key === "setup_type") {
        const next = { ...current, setup_type: value };
        return { ...next, ...getSetupAwarePortSelection(next, ports) };
      }

      if (current.setup_type === "usb_loopback" && (key === "tx_port" || key === "rx_port")) {
        return { ...current, tx_port: value, rx_port: value };
      }

      if (key === "tx_port") {
        const rxCandidates = ports.filter((port) => port !== value);
        const nextRx = value === current.rx_port ? (rxCandidates[0] ?? value) : current.rx_port;
        return { ...current, tx_port: value, rx_port: nextRx };
      }

      if (key === "rx_port") {
        const txCandidates = ports.filter((port) => port !== value);
        const nextTx = value === current.tx_port ? (txCandidates[0] ?? value) : current.tx_port;
        return { ...current, rx_port: value, tx_port: nextTx };
      }

      return { ...current, [key]: value };
    });
  }

  function toggleProfile(id) {
    setForm((current) => {
      const exists = current.selected_tests.includes(id);
      return {
        ...current,
        selected_tests: exists ? current.selected_tests.filter((item) => item !== id) : [...current.selected_tests, id],
      };
    });
  }

  function attachRunSocket(nextRunId) {
    socketRef.current?.close();
    const socket = createTestRunSocket(nextRunId);
    socketRef.current = socket;
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data);
      if (payload.type === "status") {
        setStatus(payload.run);
        setResults(payload.results ?? []);
        if (payload.run?.status !== "running") {
          socket.close();
        }
      }
    };
    socket.onerror = () => {
      getTestStatus(nextRunId).then(setStatus).catch(() => {});
      getTestResults(nextRunId).then((data) => setResults(data.results ?? [])).catch(() => {});
    };
  }

  async function handleRun(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setStatus(null);
    setResults([]);
    try {
      if (form.setup_type !== "usb_loopback" && form.tx_port === form.rx_port) {
        throw new Error("TX and RX ports must be different devices.");
      }
      const response = await startTests({
        ...form,
        timeout: Number(form.timeout),
        soak_seconds: Number(form.soak_seconds),
      });
      setRunId(response.run_id);
      attachRunSocket(response.run_id);
      const [current, initialResults] = await Promise.all([getTestStatus(response.run_id), getTestResults(response.run_id)]);
      setStatus(current);
      setResults(initialResults.results ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel panel-large">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Testing</p>
          <h2>UART Test Report</h2>
          <p className="panel-copy">Run all scenarios or choose specific suites, then review pass/fail results in a simple report view.</p>
        </div>
        <div className="button-row">
          <button type="button" className="ghost-button" onClick={loadOptions}>
            Refresh Ports
          </button>
          <span className={`status-pill ${status?.status === "running" ? "status-running" : ""}`}>{runState}</span>
        </div>
      </div>

      <form className="grid-form" onSubmit={handleRun}>
        <div className="segmented field-wide">
          <button type="button" className={form.mode === "all" ? "segment active" : "segment"} onClick={() => updateField("mode", "all")}>
            Run All Cases
          </button>
          <button type="button" className={form.mode === "custom" ? "segment active" : "segment"} onClick={() => updateField("mode", "custom")}>
            User Defined
          </button>
        </div>

        <Field label="TX Port">
          <select value={form.tx_port} onChange={(event) => updateField("tx_port", event.target.value)}>
            {txOptions.map((port) => (
              <option key={port} value={port}>{port}</option>
            ))}
          </select>
        </Field>

        <Field label="UART Setup">
          <select value={form.setup_type} onChange={(event) => updateField("setup_type", event.target.value)}>
            <option value="usb_loopback">One USB-UART Loopback</option>
            <option value="dual_usb">Two USB-UART Adapters</option>
            <option value="usb_gpio">USB UART + Raspberry Pi GPIO UART</option>
          </select>
        </Field>

        <Field label="RX Port">
          <select value={form.rx_port} onChange={(event) => updateField("rx_port", event.target.value)} disabled={form.setup_type === "usb_loopback"}>
            {rxOptions.map((port) => (
              <option key={port} value={port}>{port}</option>
            ))}
          </select>
        </Field>

        <Field label="Timeout (s)">
          <input type="number" step="0.1" value={form.timeout} onChange={(event) => updateField("timeout", event.target.value)} />
        </Field>

        <Field label="Soak Duration (s)">
          <input type="number" step="1" value={form.soak_seconds} onChange={(event) => updateField("soak_seconds", event.target.value)} />
        </Field>

        <label className="switch field-wide">
          <input type="checkbox" checked={form.include_slow} onChange={(event) => updateField("include_slow", event.target.checked)} />
          <span>Include long stress and soak tests</span>
        </label>

        <label className="switch field-wide">
          <input type="checkbox" checked={form.include_negative} onChange={(event) => updateField("include_negative", event.target.checked)} />
          <span>Include negative and error-handling tests</span>
        </label>

        {form.mode === "custom" ? (
          <div className="selector-card field-wide">
            <div className="selector-head">
              <p>Choose scenario groups</p>
              <strong>{selectedCount} selected · {expectedRecordedCount} tests</strong>
            </div>
            <div className="chips">
              {profiles.map((profile) => {
                const active = form.selected_tests.includes(profile.id);
                return (
                  <button key={profile.id} type="button" className={active ? "chip active" : "chip"} onClick={() => toggleProfile(profile.id)}>
                    {profile.label}
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        <button type="submit" className="primary-button" disabled={loading || !hasEnoughPorts}>
          {loading ? "Starting..." : "Start Test Run"}
        </button>
      </form>

      {error ? <p className="error-box">{error}</p> : null}
      {form.setup_type === "usb_loopback" ? <p className="empty-state">Loopback mode reuses the same serial port for transmit and receive. Tests that need two independent UART endpoints will be skipped automatically.</p> : null}
      {!hasEnoughPorts ? <p className="error-box">{portStatusMessage}</p> : null}

      <div className="summary-grid">
        <div className="summary-card">
          <p className="result-label">Run ID</p>
          <strong>{runId || "Not started"}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Current Status</p>
          <strong>{status?.status ?? "Idle"}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Recorded</p>
          <strong>{results.length}/{expectedRecordedCount}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Passed</p>
          <strong className="pass-text">{passCount}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Failed</p>
          <strong className="fail-text">{failCount}</strong>
        </div>
      </div>

      {status ? (
        <>
          <div className="details-panel">
            <div className="history-header">
              <h3>Selected Run Overview</h3>
              <span>{runSummaryText}</span>
            </div>
            <div className="simple-table report-overview-table">
              <div className="simple-table-head report-overview-head">
                <span>Field</span>
                <span>Value</span>
              </div>
              {overviewRows.map(([label, value]) => (
                <div key={label} className="simple-table-row report-overview-row">
                  <span>{label}</span>
                  <span>{value}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="details-panel">
            <div className="history-header">
              <h3>Run Output</h3>
              <span>Useful when a run fails or behaves unexpectedly</span>
            </div>
            <div className="report-output-grid">
              <div className="output-card">
                <p className="result-label">Standard Output</p>
                <pre>{status.stdout || "No standard output was recorded for this run."}</pre>
              </div>
              <div className="output-card">
                <p className="result-label">Error Output</p>
                <pre>{status.stderr || "No error output was recorded for this run."}</pre>
              </div>
            </div>
          </div>
        </>
      ) : null}

      <div className="history-section">
        <div className="history-header">
          <h3>Selected Run Results</h3>
          <span>{results.length}/{expectedRecordedCount} recorded tests</span>
        </div>

        {results.length ? (
          <div className="simple-table report-table">
            <div className="simple-table-head">
              <span>Result</span>
              <span>Scenario</span>
              <span>Config</span>
              <span>Details</span>
            </div>
            {results.map((item, index) => (
              <div key={`${item.recorded_at}-${index}`} className="simple-table-row report-row">
                <span className={item.status === "PASS" ? "badge-pass" : "badge-fail"}>{item.status}</span>
                <span>{formatTestName(item.test_name)}</span>
                <span>{item.baud} / {item.data_bits} / {item.parity} / {item.stop_bits}</span>
                <span>{item.details || "-"}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-state">No test results yet. Start a run to see pass/fail results here.</p>
        )}
      </div>
    </section>
  );
}
