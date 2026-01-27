const BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function ingestLog(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/ingest`, { method: "POST", body: form });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function analyze(question, top_k = 6) {
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, top_k }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

