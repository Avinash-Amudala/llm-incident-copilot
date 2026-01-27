import React, { useState, useEffect } from "react";
import { ingestLog, getDatasets } from "../api.js";

export default function UploadPanel({ onIngest }) {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState({ type: "", message: "" });
  const [isLoading, setIsLoading] = useState(false);
  const [datasets, setDatasets] = useState([]);
  const [stats, setStats] = useState(null);

  // fetch available datasets on mount
  useEffect(() => {
    getDatasets()
      .then(setDatasets)
      .catch(() => {}); // silently fail if API not ready
  }, []);

  async function handleUpload() {
    if (!file) return;
    setIsLoading(true);
    setStatus({ type: "loading", message: "Parsing and embedding log file..." });
    try {
      const resp = await ingestLog(file);
      setStatus({
        type: "success",
        message: `Created ${resp.chunks_created} chunks from ${resp.filename}`
      });
      setStats(resp.stats);
      onIngest(resp);
    } catch (e) {
      setStatus({ type: "error", message: e.message });
    } finally {
      setIsLoading(false);
    }
  }

  function handleFileChange(e) {
    const selectedFile = e.target.files?.[0] || null;
    setFile(selectedFile);
    setStatus({ type: "", message: "" });
    setStats(null);
  }

  return (
    <div className="panel">
      <h3 className="panel-header">📁 Upload Logs</h3>

      {/* File input */}
      <div style={{ marginBottom: "16px" }}>
        <input
          type="file"
          accept=".log,.txt,.json"
          onChange={handleFileChange}
          className="input"
          style={{ padding: "8px" }}
        />
        {file && (
          <div style={{ marginTop: "8px", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
            Selected: <strong>{file.name}</strong> ({(file.size / 1024).toFixed(1)} KB)
          </div>
        )}
      </div>

      {/* Upload button */}
      <button
        onClick={handleUpload}
        disabled={!file || isLoading}
        className="btn"
        style={{ width: "100%" }}
      >
        {isLoading ? (
          <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
            <div className="spinner"></div> Processing...
          </span>
        ) : (
          "Ingest Log File"
        )}
      </button>

      {/* Status message */}
      {status.message && (
        <div className={`status ${status.type}`}>
          {status.type === "loading" && <div className="spinner"></div>}
          {status.message}
        </div>
      )}

      {/* Log stats after ingestion */}
      {stats && (
        <div style={{ marginTop: "16px" }}>
          <div className="section-header">Log Statistics</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
            <span className="stats-badge info">{stats.total_lines} lines</span>
            <span className="stats-badge success">{stats.info_count} info</span>
            <span className="stats-badge warn">{stats.warn_count} warnings</span>
            <span className="stats-badge error">{stats.error_count} errors</span>
          </div>
          {stats.first_timestamp && (
            <div style={{ marginTop: "8px", fontSize: "0.8rem", color: "var(--text-muted)" }}>
              Time range: {stats.first_timestamp} → {stats.last_timestamp}
            </div>
          )}
        </div>
      )}

      {/* Sample datasets */}
      {datasets.length > 0 && (
        <div style={{ marginTop: "20px" }}>
          <div className="divider"></div>
          <div className="section-header">Sample Datasets</div>
          <div className="dataset-list">
            {datasets.slice(0, 5).map((ds) => (
              <div key={ds.path} className="dataset-item">
                <div>
                  <div className="dataset-name">{ds.name}</div>
                  <div className="dataset-meta">{ds.description}</div>
                </div>
                <span className="stats-badge info">{ds.line_count.toLocaleString()} lines</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
