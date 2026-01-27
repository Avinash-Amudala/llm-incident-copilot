import React, { useState } from "react";
import { analyze } from "../api.js";

export default function ChatPanel({ ingestInfo }) {
  const [q, setQ] = useState("");
  const [ans, setAns] = useState(null);
  const [status, setStatus] = useState("");

  async function ask() {
    if (!q.trim()) return;
    setStatus("Thinking...");
    setAns(null);
    try {
      const resp = await analyze(q, 6);
      setAns(resp);
      setStatus("");
    } catch (e) {
      setStatus(`Error: ${e.message}`);
    }
  }

  return (
    <div style={{ border: "1px solid #ddd", borderRadius: 12, padding: 12 }}>
      <h3>2) Ask a Question</h3>
      <div style={{ fontSize: 13, opacity: 0.75, marginBottom: 8 }}>
        {ingestInfo ? `Loaded: ${ingestInfo.filename} (${ingestInfo.chunks_created} chunks)` : "No logs ingested yet."}
      </div>

      <textarea
        rows={4}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="e.g., Why are requests timing out? What changed?"
        style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #ccc" }}
      />

      <div style={{ marginTop: 10 }}>
        <button onClick={ask} style={{ padding: "8px 12px" }}>
          Analyze
        </button>
        <span style={{ marginLeft: 10, fontSize: 13, opacity: 0.8 }}>{status}</span>
      </div>

      {ans && (
        <div style={{ marginTop: 14 }}>
          <h4 style={{ marginBottom: 6 }}>Answer</h4>
          <div style={{ whiteSpace: "pre-wrap", fontSize: 13, border: "1px solid #eee", borderRadius: 10, padding: 10 }}>
            {ans.summary}
          </div>

          <h4 style={{ marginTop: 12, marginBottom: 6 }}>Evidence</h4>
          <ul style={{ marginTop: 0 }}>
            {ans.evidence?.map((e) => (
              <li key={e.chunk_id} style={{ fontSize: 13, marginBottom: 8 }}>
                <code>{e.chunk_id}</code> — <b>{e.filename}</b>
                <div style={{ whiteSpace: "pre-wrap", opacity: 0.85 }}>{e.quote}</div>
              </li>
            ))}
          </ul>

          <h4 style={{ marginTop: 12, marginBottom: 6 }}>Next steps</h4>
          <ul style={{ marginTop: 0 }}>
            {ans.next_steps?.map((s, i) => (
              <li key={i} style={{ fontSize: 13 }}>{s}</li>
            ))}
          </ul>

          <div style={{ marginTop: 10, fontSize: 13 }}>
            Confidence: <b>{ans.confidence}</b>
          </div>
        </div>
      )}
    </div>
  );
}

