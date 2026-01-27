import React, { useState } from "react";
import { ingestLog } from "../api.js";

export default function UploadPanel({ onIngest }) {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");

  async function handleUpload() {
    if (!file) return;
    setStatus("Ingesting...");
    try {
      const resp = await ingestLog(file);
      setStatus(`Done: ${resp.chunks_created} chunks created`);
      onIngest(resp);
    } catch (e) {
      setStatus(`Error: ${e.message}`);
    }
  }

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
      <h3>1) Upload Logs</h3>
      <input type="file" accept=".log,.txt" onChange={(e) => setFile(e.target.files?.[0] || null)} />
      <div style={{ marginTop: 10 }}>
        <button onClick={handleUpload} style={{ padding: "8px 12px" }}>
          Ingest
        </button>
      </div>
      <div style={{ marginTop: 10, fontSize: 13, opacity: 0.8 }}>{status}</div>
    </div>
  );
}

