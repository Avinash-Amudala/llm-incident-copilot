import React, { useState, useEffect } from "react";
import UploadPanel from "./components/UploadPanel.jsx";
import ChatPanel from "./components/ChatPanel.jsx";
import { checkHealth } from "./api.js";
import "./styles.css";

export default function App() {
  const [ingestInfo, setIngestInfo] = useState(null);
  const [theme, setTheme] = useState("light");
  const [apiStatus, setApiStatus] = useState("checking");

  // Check if user prefers dark mode
  useEffect(() => {
    const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const savedTheme = localStorage.getItem("theme");
    const initialTheme = savedTheme || (prefersDark ? "dark" : "light");
    setTheme(initialTheme);
    document.documentElement.setAttribute("data-theme", initialTheme);
  }, []);

  // Check API health on mount
  useEffect(() => {
    checkHealth().then((ok) => setApiStatus(ok ? "connected" : "disconnected"));
  }, []);

  function toggleTheme() {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    localStorage.setItem("theme", newTheme);
    document.documentElement.setAttribute("data-theme", newTheme);
  }

  return (
    <div className="app-container">
      <header className="header">
        <div>
          <h1>🔍 LLM Incident Copilot</h1>
          <p className="header-subtitle">
            Upload logs → ask questions → get evidence-based debugging guidance
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span className={`stats-badge ${apiStatus === "connected" ? "success" : "error"}`}>
            {apiStatus === "checking" ? "..." : apiStatus === "connected" ? "● API Connected" : "● API Offline"}
          </span>
          <button className="theme-toggle" onClick={toggleTheme} title="Toggle theme">
            {theme === "light" ? "🌙" : "☀️"}
          </button>
        </div>
      </header>

      <div className="main-grid">
        <UploadPanel onIngest={setIngestInfo} />
        <ChatPanel ingestInfo={ingestInfo} />
      </div>
    </div>
  );
}
