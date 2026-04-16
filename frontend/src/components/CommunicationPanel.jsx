import { useEffect, useState } from "react";

import { fetchPorts, getCommunicationLogs, runCommunication } from "../api";


const defaultConfig = {
  tx_port: "/dev/ttyUSB0",
  rx_port: "/dev/ttyUSB1",
  baud: 9600,
  data_bits: 8,
  parity: "N",
  stop_bits: 1,
  timeout: 1,
  payload: "Hello UART",
  payload_mode: "text",
  read_delay: 0.2,
};

const baudRates = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200];

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


function Field({ label, children }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}


export default function CommunicationPanel() {
  const [ports, setPorts] = useState([]);
  const [form, setForm] = useState(defaultConfig);
  const [result, setResult] = useState(null);
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function loadPortsAndLogs() {
    try {
      const [portsData, logsData] = await Promise.all([fetchPorts(), getCommunicationLogs(10)]);
      const nextPorts = filterVisiblePorts(portsData.ports ?? []);
      setPorts(nextPorts);
      setLogs(logsData.logs ?? []);
      setForm((current) => ({ ...current, ...getDistinctPortSelection(current, nextPorts) }));
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadPortsAndLogs();
  }, []);

  function updateField(key, value) {
    setForm((current) => {
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

  const hasEnoughPorts = ports.length >= 2;
  const txOptions = buildPortOptions(form.tx_port, form.rx_port, ports);
  const rxOptions = buildPortOptions(form.rx_port, form.tx_port, ports);

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setResult(null);
    try {
      if (form.tx_port === form.rx_port) {
        throw new Error("TX and RX ports must be different devices.");
      }
      const response = await runCommunication({
        ...form,
        baud: Number(form.baud),
        data_bits: Number(form.data_bits),
        stop_bits: Number(form.stop_bits),
        timeout: Number(form.timeout),
        read_delay: Number(form.read_delay),
      });
      setResult(response);
      const logsData = await getCommunicationLogs(10);
      setLogs(logsData.logs ?? []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Communication</p>
          <h2>Live UART Transfer</h2>
          <p className="panel-copy">Send data from one UART to another and review the latest received payload below.</p>
        </div>
        <button type="button" className="ghost-button" onClick={loadPortsAndLogs}>
          Refresh Ports
        </button>
      </div>

      <form className="grid-form" onSubmit={handleSubmit}>
        <Field label="TX Port">
          <select value={form.tx_port} onChange={(event) => updateField("tx_port", event.target.value)}>
            {txOptions.map((port) => (
              <option key={port} value={port}>
                {port}
              </option>
            ))}
          </select>
        </Field>

        <Field label="RX Port">
          <select value={form.rx_port} onChange={(event) => updateField("rx_port", event.target.value)}>
            {rxOptions.map((port) => (
              <option key={port} value={port}>
                {port}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Baud">
          <select value={form.baud} onChange={(event) => updateField("baud", event.target.value)}>
            {baudRates.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Data Bits">
          <select value={form.data_bits} onChange={(event) => updateField("data_bits", event.target.value)}>
            {[5, 6, 7, 8].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Parity">
          <select value={form.parity} onChange={(event) => updateField("parity", event.target.value)}>
            {["N", "E", "O"].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Stop Bits">
          <select value={form.stop_bits} onChange={(event) => updateField("stop_bits", event.target.value)}>
            {[1, 2].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Timeout (s)">
          <input type="number" step="0.1" value={form.timeout} onChange={(event) => updateField("timeout", event.target.value)} />
        </Field>

        <Field label="Read Delay (s)">
          <input type="number" step="0.05" value={form.read_delay} onChange={(event) => updateField("read_delay", event.target.value)} />
        </Field>

        <Field label="Payload Mode">
          <select value={form.payload_mode} onChange={(event) => updateField("payload_mode", event.target.value)}>
            <option value="text">Text</option>
            <option value="hex">Hex</option>
          </select>
        </Field>

        <label className="field field-wide">
          <span>Payload</span>
          <textarea
            rows="4"
            value={form.payload}
            onChange={(event) => updateField("payload", event.target.value)}
            placeholder="Type text or hex payload to transmit"
          />
        </label>

        <button type="submit" className="primary-button" disabled={loading || !hasEnoughPorts}>
          {loading ? "Sending..." : "Send and Receive"}
        </button>
      </form>

      {error ? <p className="error-box">{error}</p> : null}
      {!hasEnoughPorts ? <p className="error-box">Connect at least two UART ports to choose different TX and RX devices.</p> : null}

      {result ? (
        <div className="result-card report-card">
          <div>
            <p className="result-label">Sent Bytes</p>
            <strong>{result.sent_bytes}</strong>
          </div>
          <div>
            <p className="result-label">Elapsed</p>
            <strong>{result.elapsed_ms.toFixed(2)} ms</strong>
          </div>
          <div className="result-block">
            <p className="result-label">Received Text</p>
            <pre>{result.received_text || "(empty)"}</pre>
          </div>
          <div className="result-block">
            <p className="result-label">Received Hex</p>
            <pre>{result.received_hex || "(empty)"}</pre>
          </div>
        </div>
      ) : null}

      <div className="history-section">
        <div className="history-header">
          <h3>Recent Communication Log</h3>
          <span>{logs.length} entries</span>
        </div>
        {logs.length ? (
          <div className="simple-table communication-log-table">
            <div className="simple-table-head communication-log-head">
              <span>Status</span>
              <span>From UART</span>
              <span>To UART</span>
              <span>Baud</span>
              <span>Sent</span>
              <span>Received</span>
            </div>
            {logs.map((log, index) => (
              <div key={`${log.created_at}-${index}`} className="simple-table-row communication-log-row">
                <span className={log.status === "success" ? "badge-pass" : "badge-fail"}>{log.status}</span>
                <span>{log.tx_port}</span>
                <span>{log.rx_port}</span>
                <span>{log.baud}</span>
                <span>{log.payload_sent || "(empty)"}</span>
                <span>{log.payload_received_text || "(empty)"}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="empty-state">No communication records yet. Send a payload to create the first entry.</p>
        )}
      </div>
    </section>
  );
}
