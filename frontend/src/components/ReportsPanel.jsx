import { useEffect, useState } from "react";

import { getDashboardSummary, getResultsDownloadUrl, getTestRunHistory } from "../api";

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


export default function ReportsPanel() {
  const [summary, setSummary] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRun, setSelectedRun] = useState("");
  const [error, setError] = useState("");

  async function loadReports() {
    try {
      setError("");
      const [summaryData, runsData] = await Promise.all([getDashboardSummary(), getTestRunHistory(30)]);
      const nextRuns = runsData.runs ?? [];
      setSummary(summaryData);
      setRuns(nextRuns);
      if (!nextRuns.length) {
        setSelectedRun("");
        return;
      }

      setSelectedRun((current) => {
        if (nextRuns.some((run) => run.run_id === current)) {
          return current;
        }
        return nextRuns[0].run_id;
      });
    } catch (err) {
      setError(err.message);
    }
  }

  useEffect(() => {
    loadReports();
  }, []);

  return (
    <section className="panel panel-large">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Reports</p>
          <h2>History and Analytics</h2>
          <p className="panel-copy">Review recent runs, inspect one run in detail, and export the recorded results when you need them outside the app.</p>
        </div>
        <div className="button-row">
          <a className="ghost-button link-button" href={getResultsDownloadUrl(selectedRun || undefined)}>
            Export CSV
          </a>
          <button type="button" className="ghost-button" onClick={loadReports}>
            Refresh Report
          </button>
        </div>
      </div>

      {error ? <p className="error-box">{error}</p> : null}

      <div className="summary-grid">
        <div className="summary-card">
          <p className="result-label">Total Runs</p>
          <strong>{summary?.total_runs ?? 0}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Completed Runs</p>
          <strong className="pass-text">{summary?.completed_runs ?? 0}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Running Runs</p>
          <strong>{summary?.running_runs ?? 0}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Failed Runs</p>
          <strong className="fail-text">{summary?.failed_runs ?? 0}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Passed Results</p>
          <strong className="pass-text">{summary?.passed_results ?? 0}</strong>
        </div>
        <div className="summary-card">
          <p className="result-label">Failed Results</p>
          <strong className="fail-text">{summary?.failed_results ?? 0}</strong>
        </div>
      </div>

      <div className="history-section">
        <div className="history-header">
          <h3>Run History</h3>
          <span>{runs.length} recent runs</span>
        </div>

        {runs.length ? (
          <div className="simple-table run-history-table">
            <div className="simple-table-head">
              <span>Status</span>
              <span>Run ID</span>
              <span>Ports</span>
              <span>Started</span>
            </div>
            {runs.map((run) => (
              <button
                key={run.run_id}
                type="button"
                className={selectedRun === run.run_id ? "simple-table-row table-button active-row" : "simple-table-row table-button"}
                onClick={() => setSelectedRun(run.run_id)}
              >
                <span className={run.status === "completed" ? "badge-pass" : run.status === "failed" ? "badge-fail" : "status-pill"}>
                  {run.status}
                </span>
                <span>{run.run_id}</span>
                <span>{run.tx_port} {"->"} {run.rx_port}</span>
                <span>{formatDateTime(run.started_at)}</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="empty-state">No saved test runs yet. Start a test from the Testing tab and it will show up here.</p>
        )}
      </div>

      <p className="empty-state">Use the Testing tab to inspect the live run overview, output, and per-test results. Reports stays focused on history and exports.</p>
    </section>
  );
}
