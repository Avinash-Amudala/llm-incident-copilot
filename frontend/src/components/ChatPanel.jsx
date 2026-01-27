import React, { useState } from "react";
import { analyze } from "../api.js";

// simple syntax highlighting for log lines
function highlightLog(text) {
  if (!text) return text;
  return text.split("\n").map((line, i) => {
    let className = "log-line";
    if (/\b(ERROR|FATAL|CRITICAL)\b/i.test(line)) className += " log-error";
    else if (/\b(WARN|WARNING)\b/i.test(line)) className += " log-warn";
    else if (/\bINFO\b/i.test(line)) className += " log-info";
    else if (/\b(DEBUG|TRACE)\b/i.test(line)) className += " log-debug";
    return <div key={i} className={className}>{line}</div>;
  });
}

export default function ChatPanel({ ingestInfo }) {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [conversationId, setConversationId] = useState(null);

  async function handleAnalyze() {
    if (!question.trim()) return;
    setIsLoading(true);
    setError("");
    try {
      const resp = await analyze(question, 6, conversationId);
      setResponse(resp);
      setConversationId(resp.conversation_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      handleAnalyze();
    }
  }

  function startNewConversation() {
    setConversationId(null);
    setResponse(null);
    setQuestion("");
  }

  return (
    <div className="panel">
      <h3 className="panel-header">💬 Ask a Question</h3>

      {/* Context indicator */}
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        marginBottom: "12px"
      }}>
        <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          {ingestInfo
            ? `📄 ${ingestInfo.filename} (${ingestInfo.chunks_created} chunks)`
            : "No logs ingested yet — upload a file first"}
        </span>
        {conversationId && (
          <button className="btn btn-secondary" onClick={startNewConversation} style={{ padding: "4px 10px", fontSize: "0.8rem" }}>
            New Chat
          </button>
        )}
      </div>

      {/* Question input */}
      <textarea
        className="textarea"
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="e.g., Why are requests timing out? What error patterns do you see?"
        disabled={isLoading}
      />

      <div style={{ marginTop: "12px", display: "flex", gap: "12px", alignItems: "center" }}>
        <button
          onClick={handleAnalyze}
          disabled={!question.trim() || isLoading}
          className="btn"
        >
          {isLoading ? (
            <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <div className="spinner"></div> Analyzing...
            </span>
          ) : (
            "Analyze Logs"
          )}
        </button>
        <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
          Ctrl+Enter to submit
        </span>
      </div>

      {/* Error display */}
      {error && (
        <div className="status error" style={{ marginTop: "12px" }}>
          ⚠️ {error}
        </div>
      )}

      {/* Response display */}
      {response && (
        <div style={{ marginTop: "20px" }}>
          {/* Summary */}
          <div className="section-header">Analysis Summary</div>
          <div className="log-display" style={{ whiteSpace: "pre-wrap" }}>
            {response.summary}
          </div>

          {/* Confidence */}
          <div style={{ marginTop: "16px", display: "flex", alignItems: "center", gap: "12px" }}>
            <span className={`confidence ${response.confidence}`}>
              Confidence: {response.confidence.toUpperCase()}
            </span>
          </div>

          {/* Evidence */}
          <div className="section-header" style={{ marginTop: "20px" }}>
            Evidence ({response.evidence?.length || 0} chunks)
          </div>
          {response.evidence?.map((ev) => (
            <div key={ev.chunk_id} className="evidence-card">
              <div className="evidence-header">
                <span className="evidence-id">{ev.chunk_id}</span>
                <span className="evidence-filename">{ev.filename}</span>
              </div>
              {ev.timestamp && (
                <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "8px" }}>
                  🕐 {ev.timestamp} {ev.level && `• ${ev.level}`}
                </div>
              )}
              <div className="evidence-quote">
                {highlightLog(ev.quote)}
              </div>
            </div>
          ))}

          {/* Next Steps */}
          <div className="section-header" style={{ marginTop: "20px" }}>
            Recommended Next Steps
          </div>
          <ul className="next-steps">
            {response.next_steps?.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
