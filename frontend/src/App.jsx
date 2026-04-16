import { useState } from "react";

import CommunicationPanel from "./components/CommunicationPanel";
import ReportsPanel from "./components/ReportsPanel";
import TestingPanel from "./components/TestingPanel";


export default function App() {
  const [activeView, setActiveView] = useState("communication");

  return (
    <main className="app-shell">
      <section className="hero">
        <p className="eyebrow">UART Dashboard</p>
        <h1>Send data between UART ports and check the results.</h1>
        <p className="hero-copy">Use Communication to send messages. Use Testing to run UART checks and review reports.</p>

        <div className="top-switcher" role="tablist" aria-label="UART modes">
          <button
            type="button"
            className={activeView === "communication" ? "top-tab active" : "top-tab"}
            onClick={() => setActiveView("communication")}
          >
            Communication
          </button>
          <button
            type="button"
            className={activeView === "testing" ? "top-tab active" : "top-tab"}
            onClick={() => setActiveView("testing")}
          >
            Testing
          </button>
          <button
            type="button"
            className={activeView === "reports" ? "top-tab active" : "top-tab"}
            onClick={() => setActiveView("reports")}
          >
            Reports
          </button>
        </div>
      </section>

      <section className="single-panel-layout">
        {activeView === "communication" ? <CommunicationPanel /> : null}
        {activeView === "testing" ? <TestingPanel /> : null}
        {activeView === "reports" ? <ReportsPanel /> : null}
      </section>
    </main>
  );
}
