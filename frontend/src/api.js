/**
 * API client for LLM Incident Copilot backend.
 * Handles file uploads, analysis requests, and dataset operations.
 */

const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

/**
 * Upload and ingest a log file.
 * The backend will chunk it, generate embeddings, and store in vector DB.
 */
export async function ingestLog(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/ingest`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Send a question to the LLM for analysis.
 * Returns structured response with summary, evidence, confidence, etc.
 */
export async function analyze(question, top_k = 6, conversationId = null) {
  const payload = { question, top_k };
  if (conversationId) {
    payload.conversation_id = conversationId;
  }

  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Get list of available sample datasets from the server.
 */
export async function getDatasets() {
  const res = await fetch(`${BASE}/datasets`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Get overall stats about ingested data.
 */
export async function getStats() {
  const res = await fetch(`${BASE}/stats`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Health check for the API.
 */
export async function checkHealth() {
  try {
    const res = await fetch(`${BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}
