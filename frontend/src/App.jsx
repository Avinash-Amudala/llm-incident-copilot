import React, { useState } from "react";
import UploadPanel from "./components/UploadPanel.jsx";
import ChatPanel from "./components/ChatPanel.jsx";

export default function App() {
  const [ingestInfo, setIngestInfo] = useState(null);

  return (
    <div style={{ fontFamily: "system-ui", padding: 18, maxWidth: 1000, margin: "0 auto" }}>
      <h2>LLM Incident Copilot</h2>
      <p style={{ marginTop: -8, opacity: 0.75 }}>
        Upload logs → ask questions → get evidence-based debugging guidance.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <UploadPanel onIngest={setIngestInfo} />
        <ChatPanel ingestInfo={ingestInfo} />
      </div>
    </div>
  );
}

