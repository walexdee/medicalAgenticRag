import { useState, useRef, useEffect } from "react";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

const SOURCE_COLORS = {
  "Medical Q&A Collection": {
    bg: "rgba(16,185,129,0.12)",
    border: "#10b981",
    icon: "🩺",
    label: "Medical Q&A",
  },
  "Medical Device Manual": {
    bg: "rgba(99,102,241,0.12)",
    border: "#6366f1",
    icon: "🔬",
    label: "Device Manual",
  },
  "Web Search (DuckDuckGo)": {
    bg: "rgba(245,158,11,0.12)",
    border: "#f59e0b",
    icon: "🌐",
    label: "Web Search",
  },
  "Web Search": {
    bg: "rgba(245,158,11,0.12)",
    border: "#f59e0b",
    icon: "🌐",
    label: "Web Search",
  },
  default: {
    bg: "rgba(100,116,139,0.12)",
    border: "#64748b",
    icon: "🔍",
    label: "Search",
  },
};

const SAMPLE_QUESTIONS = [
  "What are treatments for Kawasaki disease?",
  "What devices are used in neonatal intensive care?",
  "Latest COVID-19 antiviral medications?",
  "Contraindications for a pacemaker?",
];

function TypingIndicator() {
  return (
    <div style={{ display: "flex", gap: 5, alignItems: "center", padding: "12px 16px" }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: "#64748b",
            animation: `pulse 1.2s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
    </div>
  );
}

function StreamingCursor() {
  return (
    <span
      style={{
        display: "inline-block",
        width: 2,
        height: "1em",
        background: "#6366f1",
        marginLeft: 2,
        verticalAlign: "text-bottom",
        animation: "blink 0.8s step-end infinite",
      }}
    />
  );
}

function MessageBubble({ msg }) {
  // User message
  if (msg.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 16 }}>
        <div
          style={{
            maxWidth: "72%",
            background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
            color: "#fff",
            borderRadius: "18px 18px 4px 18px",
            padding: "12px 16px",
            fontSize: 14,
            lineHeight: 1.6,
            boxShadow: "0 4px 12px rgba(99,102,241,0.25)",
          }}
        >
          {msg.content}
        </div>
      </div>
    );
  }

  // Loading state (before meta arrives)
  if (msg.loading) {
    return (
      <div style={{ display: "flex", gap: 10, marginBottom: 16, alignItems: "flex-start" }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "linear-gradient(135deg,#0f172a,#1e293b)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            flexShrink: 0,
            border: "1px solid #334155",
          }}
        >
          🏥
        </div>
        <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: "18px 18px 18px 4px", overflow: "hidden" }}>
          <TypingIndicator />
        </div>
      </div>
    );
  }

  // Error state
  if (msg.error) {
    return (
      <div style={{ display: "flex", gap: 10, marginBottom: 16, alignItems: "flex-start" }}>
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: "50%",
            background: "linear-gradient(135deg,#0f172a,#1e293b)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            flexShrink: 0,
            border: "1px solid #334155",
          }}
        >
          ⚠️
        </div>
        <div
          style={{
            maxWidth: "78%",
            background: "#7f1d1d",
            border: "1px solid #dc2626",
            borderRadius: "4px 18px 18px 18px",
            padding: "12px 16px",
            color: "#fca5a5",
            fontSize: 13,
            lineHeight: 1.6,
          }}
        >
          {msg.error}
        </div>
      </div>
    );
  }

  // Assistant response (streaming or complete)
  const src = SOURCE_COLORS[msg.source] || SOURCE_COLORS.default;
  const isRerouted = msg.relevance?.is_relevant === false;
  const isStreaming = msg.streaming === true;

  const confidencePct = msg.confidence != null ? Math.round(msg.confidence * 100) : null;
  const confidenceColor =
    confidencePct == null ? null :
    confidencePct >= 80 ? "#10b981" :
    confidencePct >= 55 ? "#f59e0b" : "#ef4444";
  const confidenceBg =
    confidencePct == null ? null :
    confidencePct >= 80 ? "rgba(16,185,129,0.1)" :
    confidencePct >= 55 ? "rgba(245,158,11,0.1)" : "rgba(239,68,68,0.1)";

  return (
    <div style={{ display: "flex", gap: 10, marginBottom: 20, alignItems: "flex-start" }}>
      <div
        style={{
          width: 32,
          height: 32,
          borderRadius: "50%",
          background: "linear-gradient(135deg,#0f172a,#1e293b)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 14,
          flexShrink: 0,
          border: "1px solid #334155",
        }}
      >
        🏥
      </div>

      <div style={{ maxWidth: "78%", display: "flex", flexDirection: "column", gap: 8 }}>
        {/* Agent trace — shown once meta arrives */}
        {msg.source && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
            <span
              style={{
                background: src.bg,
                border: `1px solid ${src.border}`,
                color: src.border,
                borderRadius: 20,
                padding: "3px 10px",
                fontSize: 11,
                fontWeight: 600,
                letterSpacing: 0.5,
              }}
            >
              {src.icon} {src.label}
            </span>
            {msg.source_info?.reason && (
              <span
                style={{
                  background: "rgba(100,116,139,0.1)",
                  border: "1px solid #334155",
                  color: "#94a3b8",
                  borderRadius: 20,
                  padding: "3px 10px",
                  fontSize: 11,
                }}
              >
                {msg.source_info.reason}
              </span>
            )}
            {isRerouted && (
              <span
                style={{
                  background: "rgba(245,158,11,0.1)",
                  border: "1px solid #f59e0b",
                  color: "#f59e0b",
                  borderRadius: 20,
                  padding: "3px 10px",
                  fontSize: 11,
                }}
              >
                Re-routed to web
              </span>
            )}
            {confidencePct != null && !isStreaming && (
              <span
                style={{
                  background: confidenceBg,
                  border: `1px solid ${confidenceColor}`,
                  color: confidenceColor,
                  borderRadius: 20,
                  padding: "3px 10px",
                  fontSize: 11,
                  fontWeight: 600,
                  letterSpacing: 0.3,
                }}
              >
                {confidencePct >= 80 ? "✓" : confidencePct >= 55 ? "~" : "!"} {confidencePct}% confidence
              </span>
            )}
          </div>
        )}

        {/* Answer bubble — shows while streaming and after */}
        <div
          style={{
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "4px 18px 18px 18px",
            padding: "14px 16px",
            color: "#e2e8f0",
            fontSize: 14,
            lineHeight: 1.7,
            boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
            minHeight: 48,
          }}
        >
          {msg.answer || msg.content || ""}
          {isStreaming && <StreamingCursor />}
        </div>

        {/* Metadata — shown once done */}
        {msg.timestamp && (
          <div
            style={{
              fontSize: 11,
              color: "#64748b",
              display: "flex",
              gap: 12,
              marginTop: 4,
            }}
          >
            <span>{new Date(msg.timestamp).toLocaleTimeString()}</span>
            {msg.iteration_count > 0 && <span>Iterations: {msg.iteration_count}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState("connecting");
  const bottomRef = useRef(null);
  const conversationId = useRef(crypto.randomUUID());

  // Check API health on mount
  useEffect(() => {
    checkApiHealth();
    const interval = setInterval(checkApiHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const checkApiHealth = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/health`);
      setApiStatus(res.ok ? "healthy" : "unhealthy");
    } catch {
      setApiStatus("disconnected");
    }
  };

  const sendMessage = async (text) => {
    const question = text || input.trim();
    if (!question || loading || apiStatus === "disconnected") return;

    setInput("");
    const userMsg = { role: "user", content: question };
    // Add user message + streaming placeholder
    setMessages((prev) => [...prev, userMsg, { role: "assistant", loading: true }]);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE}/api/query/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: question,
          conversation_id: conversationId.current,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let assistantMsg = { role: "assistant", streaming: true };

      // Replace loading bubble with initial streaming bubble
      setMessages((prev) => [...prev.slice(0, -1), assistantMsg]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop(); // keep incomplete line

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          let payload;
          try {
            payload = JSON.parse(raw);
          } catch {
            continue;
          }

          if (payload.type === "meta") {
            assistantMsg = {
              ...assistantMsg,
              source: payload.source,
              source_info: payload.source_info,
              relevance: payload.relevance,
              context: payload.context,
            };
            setMessages((prev) => [...prev.slice(0, -1), { ...assistantMsg }]);
          } else if (payload.type === "token") {
            assistantMsg = {
              ...assistantMsg,
              answer: (assistantMsg.answer || "") + payload.token,
            };
            setMessages((prev) => [...prev.slice(0, -1), { ...assistantMsg }]);
          } else if (payload.type === "done") {
            assistantMsg = {
              ...assistantMsg,
              streaming: false,
              answer: payload.answer,
              confidence: payload.confidence,
              iteration_count: payload.iteration_count,
              timestamp: payload.timestamp,
            };
            setMessages((prev) => [...prev.slice(0, -1), { ...assistantMsg }]);
          } else if (payload.type === "error") {
            setMessages((prev) => [
              ...prev.slice(0, -1),
              { role: "assistant", error: payload.message },
            ]);
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev.slice(0, -1),
        {
          role: "assistant",
          error: `Failed to get response: ${err.message}. Check that the backend is running on ${API_BASE}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        background: "#0f172a",
        fontFamily: "'DM Mono', 'JetBrains Mono', monospace",
        color: "#e2e8f0",
      }}
    >
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap');
        * { box-sizing:border-box; margin:0; padding:0; }
        ::-webkit-scrollbar { width:4px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:#334155; border-radius:4px; }
        textarea:focus { outline:none; }
        textarea { resize:none; }
        @keyframes pulse { 0%,100%{opacity:0.3;transform:scale(0.8)} 50%{opacity:1;transform:scale(1)} }
        @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        .msg-in { animation: fadeIn 0.3s ease; }
        .chip:hover { filter:brightness(1.15); cursor:pointer; }
        .status-dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
        .status-healthy { background:#10b981; }
        .status-unhealthy { background:#f59e0b; }
        .status-disconnected { background:#ef4444; }
      `}</style>

      {/* Header */}
      <div
        style={{
          borderBottom: "1px solid #1e293b",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          gap: 12,
          background: "rgba(15,23,42,0.95)",
          backdropFilter: "blur(12px)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            background: "linear-gradient(135deg,#6366f1,#8b5cf6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 18,
          }}
        >
          🏥
        </div>
        <div>
          <div
            style={{
              fontFamily: "'Space Grotesk',sans-serif",
              fontWeight: 700,
              fontSize: 16,
              color: "#f8fafc",
              letterSpacing: -0.5,
            }}
          >
            Medical Agentic RAG
          </div>
          <div style={{ fontSize: 11, color: "#475569", letterSpacing: 0.5 }}>
            ROUTER · RETRIEVER · RELEVANCE CHECK · GENERATE
          </div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{ display: "flex", gap: 6 }}>
            {["QnA DB", "Device DB", "Web"].map((t, i) => (
              <div
                key={t}
                style={{
                  padding: "4px 10px",
                  borderRadius: 20,
                  fontSize: 10,
                  fontWeight: 600,
                  letterSpacing: 0.8,
                  border: `1px solid ${["#10b981", "#6366f1", "#f59e0b"][i]}`,
                  color: ["#10b981", "#6366f1", "#f59e0b"][i],
                  background: [
                    `rgba(16,185,129,0.08)`,
                    `rgba(99,102,241,0.08)`,
                    `rgba(245,158,11,0.08)`,
                  ][i],
                }}
              >
                {t}
              </div>
            ))}
          </div>
          {/* API Status */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              fontSize: 10,
              color:
                apiStatus === "healthy"
                  ? "#10b981"
                  : apiStatus === "unhealthy"
                  ? "#f59e0b"
                  : "#ef4444",
            }}
          >
            <span
              className={`status-dot status-${apiStatus}`}
              style={{
                animation: apiStatus !== "healthy" ? "pulse 1s infinite" : "none",
              }}
            />
            {apiStatus === "healthy"
              ? "Backend Ready"
              : apiStatus === "unhealthy"
              ? "Backend Issues"
              : "Disconnected"}
          </div>
        </div>
      </div>

      {/* Messages */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 20px",
          maxWidth: 800,
          width: "100%",
          margin: "0 auto",
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              gap: 32,
            }}
          >
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>🩺</div>
              <div
                style={{
                  fontFamily: "'Space Grotesk',sans-serif",
                  fontSize: 22,
                  fontWeight: 700,
                  color: "#f1f5f9",
                  marginBottom: 8,
                }}
              >
                Medical Knowledge System
              </div>
              <div
                style={{
                  color: "#475569",
                  fontSize: 13,
                  lineHeight: 1.8,
                  maxWidth: 420,
                  textAlign: "center",
                }}
              >
                Agentic RAG with intelligent routing across medical Q&A, device manuals, and live web search.
              </div>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, width: "100%", maxWidth: 560 }}>
              {SAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  className="chip"
                  onClick={() => sendMessage(q)}
                  style={{
                    background: "#1e293b",
                    border: "1px solid #334155",
                    borderRadius: 12,
                    color: "#94a3b8",
                    padding: "12px 14px",
                    fontSize: 12,
                    lineHeight: 1.5,
                    textAlign: "left",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div>
            {messages.map((m, i) => (
              <div key={i} className="msg-in">
                <MessageBubble msg={m} />
              </div>
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div
        style={{
          borderTop: "1px solid #1e293b",
          padding: "16px 20px",
          background: "rgba(15,23,42,0.95)",
          backdropFilter: "blur(12px)",
        }}
      >
        <div style={{ maxWidth: 800, margin: "0 auto", display: "flex", gap: 10, alignItems: "flex-end" }}>
          <div
            style={{
              flex: 1,
              background: "#1e293b",
              border: "1px solid #334155",
              borderRadius: 14,
              padding: "12px 16px",
              display: "flex",
              gap: 10,
              alignItems: "flex-end",
              transition: "border-color 0.2s",
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = "#6366f1")}
            onBlur={(e) => (e.currentTarget.style.borderColor = "#334155")}
          >
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask about medical conditions, devices, or recent news…"
              rows={1}
              disabled={apiStatus === "disconnected" || loading}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                color: "#e2e8f0",
                fontSize: 14,
                fontFamily: "inherit",
                lineHeight: 1.5,
                maxHeight: 120,
                overflowY: "auto",
                opacity: apiStatus === "disconnected" ? 0.5 : 1,
              }}
            />
          </div>
          <button
            onClick={() => sendMessage()}
            disabled={!input.trim() || loading || apiStatus === "disconnected"}
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background:
                input.trim() && !loading && apiStatus !== "disconnected"
                  ? "linear-gradient(135deg,#6366f1,#8b5cf6)"
                  : "#1e293b",
              border:
                input.trim() && !loading && apiStatus !== "disconnected"
                  ? "none"
                  : "1px solid #334155",
              color:
                input.trim() && !loading && apiStatus !== "disconnected"
                  ? "#fff"
                  : "#475569",
              fontSize: 18,
              cursor:
                input.trim() && !loading && apiStatus !== "disconnected"
                  ? "pointer"
                  : "default",
              transition: "all 0.2s",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            {loading ? "⟳" : "↑"}
          </button>
        </div>
        <div style={{ maxWidth: 800, margin: "6px auto 0", textAlign: "center", fontSize: 10, color: "#334155", letterSpacing: 0.5 }}>
          ROUTES: QnA DB · Device Manual · Web Search · Relevance Check · Max 3 iterations
        </div>
      </div>
    </div>
  );
}
