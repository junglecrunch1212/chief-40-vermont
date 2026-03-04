import { useState } from "react";

const COLORS = {
  bg: "#0a0e17",
  card: "#111827",
  cardHover: "#1a2332",
  border: "#1e293b",
  borderActive: "#3b82f6",
  text: "#e2e8f0",
  textMuted: "#94a3b8",
  textDim: "#64748b",
  blue: "#3b82f6",
  blueGlow: "rgba(59,130,246,0.15)",
  green: "#10b981",
  greenGlow: "rgba(16,185,129,0.15)",
  amber: "#f59e0b",
  amberGlow: "rgba(245,158,11,0.15)",
  purple: "#8b5cf6",
  purpleGlow: "rgba(139,92,246,0.15)",
  red: "#ef4444",
  redGlow: "rgba(239,68,68,0.15)",
  cyan: "#06b6d4",
  cyanGlow: "rgba(6,182,212,0.15)",
  pink: "#ec4899",
  pinkGlow: "rgba(236,72,153,0.15)",
  lime: "#84cc16",
  limeGlow: "rgba(132,204,22,0.15)",
};

const LAYERS = [
  {
    id: "channels",
    label: "OPENCLAW CHANNELS",
    subtitle: "Inbound messages → OpenClaw gateway → agent dispatch → pib.cli",
    color: COLORS.cyan,
    glow: COLORS.cyanGlow,
    items: [
      { id: "imessage", name: "iMessage (BlueBubbles)", desc: "Webhook → OpenClaw channel handler → agent routes to pib.cli", icon: "💬" },
      { id: "sms", name: "SMS (Twilio)", desc: "Inbound webhook → OpenClaw channel → agent → pib.cli", icon: "📱" },
      { id: "webchat", name: "Webchat", desc: "Browser → OpenClaw channel → agent → pib.cli", icon: "🌐" },
    ],
  },
  {
    id: "taskflow",
    label: "TASK FLOW",
    subtitle: "User message → OpenClaw channel → agent → pib.cli what-now/task-complete/capture → SQLite → response",
    color: COLORS.blue,
    glow: COLORS.blueGlow,
    items: [
      { id: "tf1", name: "① Channel receives message", desc: "OpenClaw gateway authenticates and routes to channel handler" },
      { id: "tf2", name: "② Agent processes intent", desc: "OpenClaw agent determines command: what-now, task-complete, capture, etc." },
      { id: "tf3", name: "③ pib.cli executes", desc: "python -m pib.cli <cmd> $PIB_DB_PATH — 6-layer permission boundary" },
      { id: "tf4", name: "④ SQLite SSOT updated", desc: "WAL mode write → append-only (never deletes)" },
      { id: "tf5", name: "⑤ JSON response", desc: "pib.cli returns structured JSON → OpenClaw → channel → user" },
    ],
  },
  {
    id: "calflow",
    label: "CALENDAR FLOW",
    subtitle: "Google Cal API → gog calendar events → calendar_sync.mjs → pib.cli calendar-ingest $PIB_DB_PATH → SQLite",
    color: COLORS.purple,
    glow: COLORS.purpleGlow,
    items: [
      { id: "cf1", name: "① OpenClaw cron triggers", desc: "Cron job fires every 15 min (replaces old APScheduler)" },
      { id: "cf2", name: "② gog calendar events", desc: "gog CLI reads Google Calendar API v3 — incremental sync with sync tokens" },
      { id: "cf3", name: "③ calendar_sync.mjs", desc: "Transforms raw calendar data → normalized format" },
      { id: "cf4", name: "④ pib.cli calendar-ingest", desc: "python -m pib.cli calendar-ingest $PIB_DB_PATH — writes to cal_* tables" },
      { id: "cf5", name: "⑤ Classification + conflicts", desc: "Events classified, custody computed, conflicts detected" },
    ],
  },
  {
    id: "sensorflow",
    label: "SENSOR FLOW",
    subtitle: "Apple Shortcuts → HTTP POST from Bridge Mini → /api/sensors/ingest → SQLite → enrichment",
    color: COLORS.amber,
    glow: COLORS.amberGlow,
    items: [
      { id: "sf1", name: "① Apple Shortcuts fires", desc: "Health, FindMy, Focus, Siri, Battery data on James/Laura Mini" },
      { id: "sf2", name: "② HTTP POST → pib-mini", desc: "Bridge Mini pushes to CoS via POST /api/sensors/ingest" },
      { id: "sf3", name: "③ Privacy classification", desc: "Laura's data → privileged classification (never enters LLM context)" },
      { id: "sf4", name: "④ SQLite write", desc: "Sensor data stored in pib_energy_states, common_* tables" },
      { id: "sf5", name: "⑤ Enrichment", desc: "Energy levels, medication tracking, sleep quality → feeds whatNow() scoring" },
    ],
  },
  {
    id: "finflow",
    label: "FINANCIAL FLOW",
    subtitle: "Google Sheets → gog sheets get → pib.cli financial-sync → SQLite",
    color: COLORS.green,
    glow: COLORS.greenGlow,
    items: [
      { id: "ff1", name: "① OpenClaw cron triggers", desc: "Scheduled financial sync job" },
      { id: "ff2", name: "② gog sheets get", desc: "gog CLI reads financial data from Google Sheets" },
      { id: "ff3", name: "③ pib.cli financial-sync", desc: "Transforms and writes to fin_* tables in SQLite" },
      { id: "ff4", name: "④ Budget snapshots", desc: "Category budgets, merchant rules, bill tracking updated" },
    ],
  },
  {
    id: "commsflow",
    label: "COMMS FLOW",
    subtitle: "Gmail → gog gmail list → pib.cli comms-ingest → SQLite → batch windows",
    color: COLORS.pink,
    glow: COLORS.pinkGlow,
    items: [
      { id: "cmf1", name: "① OpenClaw cron triggers", desc: "Scheduled comms ingest job" },
      { id: "cmf2", name: "② gog gmail list", desc: "gog CLI reads Gmail — whitelist + triage keywords" },
      { id: "cmf3", name: "③ pib.cli comms-ingest", desc: "Writes to ops_comms, mem_* tables" },
      { id: "cmf4", name: "④ Batch windows", desc: "Messages batched for delivery within guardrail windows" },
    ],
  },
  {
    id: "consoleflow",
    label: "CONSOLE FLOW",
    subtitle: "Browser → Express :3333 → reads SQLite → JSON API → dashboard render",
    color: COLORS.lime,
    glow: COLORS.limeGlow,
    items: [
      { id: "cnf1", name: "① Browser requests", desc: "User opens console at pib-mini.local:3333" },
      { id: "cnf2", name: "② Express server", desc: "Express :3333 handles API requests (replaces old FastAPI :3141)" },
      { id: "cnf3", name: "③ SQLite read", desc: "Direct read from /opt/pib/data/pib.db — WAL mode allows concurrent reads" },
      { id: "cnf4", name: "④ JSON API response", desc: "/api/today-stream, /api/tasks, /api/scoreboard-data, etc." },
      { id: "cnf5", name: "⑤ Dashboard render", desc: "Per-actor views: James carousel, Laura compressed, scoreboard TV" },
    ],
  },
];

const FLOWS = [
  { from: "channels", to: "taskflow", label: "User messages → task commands", style: "solid" },
  { from: "taskflow", to: "calflow", label: "Both write to SQLite SSOT", style: "dotted" },
  { from: "sensorflow", to: "taskflow", label: "Energy data feeds whatNow() scoring", style: "dashed" },
  { from: "finflow", to: "consoleflow", label: "Budget data shown in dashboard", style: "dashed" },
  { from: "commsflow", to: "channels", label: "Outbound via OpenClaw channels", style: "dashed" },
];

function LayerCard({ layer, isExpanded, onToggle }) {
  return (
    <div
      onClick={onToggle}
      style={{
        background: isExpanded ? layer.glow : COLORS.card,
        border: `1px solid ${isExpanded ? layer.color : COLORS.border}`,
        borderRadius: 12,
        padding: "16px 20px",
        cursor: "pointer",
        transition: "all 0.3s ease",
        boxShadow: isExpanded ? `0 0 24px ${layer.glow}` : "none",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{
            fontSize: 11,
            fontWeight: 700,
            letterSpacing: "0.12em",
            color: layer.color,
            textTransform: "uppercase",
            fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
          }}>
            {layer.label}
          </div>
          <div style={{ fontSize: 12, color: COLORS.textDim, marginTop: 2, fontStyle: "italic" }}>
            {layer.subtitle}
          </div>
        </div>
        <div style={{
          width: 28, height: 28,
          borderRadius: "50%",
          background: isExpanded ? layer.color : "transparent",
          border: `1.5px solid ${layer.color}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14,
          color: isExpanded ? "#fff" : layer.color,
          transition: "all 0.3s ease",
          fontFamily: "monospace",
        }}>
          {isExpanded ? "−" : "+"}
        </div>
      </div>

      {isExpanded && (
        <div style={{ marginTop: 14, display: "grid", gap: 8 }}>
          {layer.items.map((item) => (
            <div
              key={item.id}
              style={{
                background: "rgba(0,0,0,0.3)",
                border: `1px solid ${layer.color}22`,
                borderRadius: 8,
                padding: "10px 14px",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                {item.icon && <span style={{ fontSize: 16 }}>{item.icon}</span>}
                <span style={{
                  fontSize: 13,
                  fontWeight: 600,
                  color: COLORS.text,
                  fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
                }}>
                  {item.name}
                </span>
              </div>
              {item.desc && (
                <div style={{ fontSize: 11.5, color: COLORS.textMuted, marginTop: 4, lineHeight: 1.5 }}>
                  {item.desc}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FlowArrow({ flow, layers }) {
  const fromLayer = layers.find((l) => l.id === flow.from);
  const toLayer = layers.find((l) => l.id === flow.to);
  if (!fromLayer || !toLayer) return null;

  const color = fromLayer.color;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 8,
      padding: "2px 0",
      fontSize: 10.5,
      color: COLORS.textDim,
      fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
    }}>
      <span style={{
        width: 6, height: 6,
        borderRadius: "50%",
        background: color,
        flexShrink: 0,
      }} />
      <span style={{
        flex: 1,
        height: 1,
        background: flow.style === "dotted"
          ? `repeating-linear-gradient(90deg, ${color} 0 3px, transparent 3px 7px)`
          : flow.style === "dashed"
          ? `repeating-linear-gradient(90deg, ${color} 0 6px, transparent 6px 10px)`
          : color,
        opacity: 0.5,
      }} />
      <span style={{ color: COLORS.textMuted, whiteSpace: "nowrap" }}>{flow.label}</span>
      <span style={{
        flex: 1,
        height: 1,
        background: flow.style === "dotted"
          ? `repeating-linear-gradient(90deg, ${toLayer.color} 0 3px, transparent 3px 7px)`
          : flow.style === "dashed"
          ? `repeating-linear-gradient(90deg, ${toLayer.color} 0 6px, transparent 6px 10px)`
          : toLayer.color,
        opacity: 0.5,
      }} />
      <span style={{
        color: toLayer.color,
        fontSize: 14,
        flexShrink: 0,
      }}>
        →
      </span>
    </div>
  );
}

export default function PIBDataFlows() {
  const [expanded, setExpanded] = useState(new Set(["channels", "taskflow"]));

  const toggle = (id) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(LAYERS.map((l) => l.id)));
  const collapseAll = () => setExpanded(new Set());

  return (
    <div style={{
      background: COLORS.bg,
      minHeight: "100vh",
      padding: "32px 20px",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      color: COLORS.text,
    }}>
      <div style={{ maxWidth: 720, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 24 }}>
          <h1 style={{
            fontSize: 22,
            fontWeight: 800,
            color: COLORS.text,
            margin: 0,
            letterSpacing: "-0.02em",
            fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
          }}>
            💩 PIB v5 — Data Flow Architecture
          </h1>
          <p style={{ fontSize: 12, color: COLORS.textDim, margin: "6px 0 0", lineHeight: 1.5 }}>
            OpenClaw L0 · Hub+Spoke topology · pib-mini.local · gog CLI + pib.cli pipeline
          </p>
          <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
            <button
              onClick={expandAll}
              style={{
                fontSize: 10, padding: "4px 10px", borderRadius: 4,
                background: "transparent", border: `1px solid ${COLORS.border}`,
                color: COLORS.textMuted, cursor: "pointer", fontFamily: "monospace",
              }}
            >
              expand all
            </button>
            <button
              onClick={collapseAll}
              style={{
                fontSize: 10, padding: "4px 10px", borderRadius: 4,
                background: "transparent", border: `1px solid ${COLORS.border}`,
                color: COLORS.textMuted, cursor: "pointer", fontFamily: "monospace",
              }}
            >
              collapse all
            </button>
          </div>
        </div>

        {/* The Layers legend */}
        <div style={{
          display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap",
        }}>
          {[
            { label: "L0: OpenClaw (infra)", color: COLORS.cyan },
            { label: "L1: Core (always works)", color: COLORS.green },
            { label: "L2: Enhanced (LLM)", color: COLORS.purple },
            { label: "L3: Extended (APIs)", color: COLORS.amber },
          ].map((l) => (
            <span key={l.label} style={{
              fontSize: 10, color: l.color,
              display: "flex", alignItems: "center", gap: 4,
              fontFamily: "monospace",
            }}>
              <span style={{
                width: 8, height: 8, borderRadius: 2,
                background: `${l.color}44`, border: `1px solid ${l.color}`,
              }} />
              {l.label}
            </span>
          ))}
        </div>

        {/* Main flow */}
        <div style={{ display: "grid", gap: 0 }}>
          {LAYERS.map((layer, i) => (
            <div key={layer.id}>
              <LayerCard
                layer={layer}
                isExpanded={expanded.has(layer.id)}
                onToggle={() => toggle(layer.id)}
              />
              {/* Flow arrows between layers */}
              {i < LAYERS.length - 1 && (
                <div style={{ padding: "6px 20px" }}>
                  {FLOWS
                    .filter((f) => {
                      const fromIdx = LAYERS.findIndex((l) => l.id === f.from);
                      const toIdx = LAYERS.findIndex((l) => l.id === f.to);
                      return (fromIdx === i && toIdx === i + 1) || (toIdx === i && fromIdx === i + 1);
                    })
                    .map((f, j) => (
                      <FlowArrow key={j} flow={f} layers={LAYERS} />
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Key invariants */}
        <div style={{
          marginTop: 24,
          padding: "16px 20px",
          background: `${COLORS.red}08`,
          border: `1px solid ${COLORS.red}33`,
          borderRadius: 10,
        }}>
          <div style={{
            fontSize: 11,
            fontWeight: 700,
            color: COLORS.red,
            letterSpacing: "0.1em",
            marginBottom: 8,
            fontFamily: "monospace",
          }}>
            INVARIANTS — NEVER VIOLATED
          </div>
          <div style={{
            fontSize: 11.5,
            color: COLORS.textMuted,
            lineHeight: 1.8,
            fontFamily: "monospace",
          }}>
            {[
              "No row is ever deleted from the task store",
              "The system never writes to a calendar",
              "The system never moves money",
              "Privileged data never enters the context window",
              "whatNow() is deterministic — no LLM in the function",
              "All access through pib.cli permission boundary (6 layers)",
              "The LLM recommends. The write layer executes.",
            ].map((inv, i) => (
              <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ color: COLORS.red, flexShrink: 0 }}>✕</span>
                <span>{inv}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Degradation */}
        <div style={{
          marginTop: 12,
          padding: "16px 20px",
          background: `${COLORS.amber}08`,
          border: `1px solid ${COLORS.amber}33`,
          borderRadius: 10,
        }}>
          <div style={{
            fontSize: 11,
            fontWeight: 700,
            color: COLORS.amber,
            letterSpacing: "0.1em",
            marginBottom: 8,
            fontFamily: "monospace",
          }}>
            GRACEFUL DEGRADATION
          </div>
          <div style={{
            fontSize: 11.5,
            color: COLORS.textMuted,
            lineHeight: 1.8,
            fontFamily: "monospace",
          }}>
            {[
              "L3 → L2: Google APIs down → use last-known data + warn",
              "L3 → L2: Sensors offline → skip energy context, use defaults",
              "L2 → L1: Anthropic API down → template fallbacks, whatNow() still works",
              "L2 → L1: Model routing fails → OpenClaw tries alternate provider",
              "BlueBubbles down → fall back to Twilio SMS channel",
            ].map((d, i) => (
              <div key={i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <span style={{ color: COLORS.amber, flexShrink: 0 }}>⚡</span>
                <span>{d}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{
          marginTop: 20,
          fontSize: 10,
          color: COLORS.textDim,
          textAlign: "center",
          fontFamily: "monospace",
        }}>
          OpenClaw L0 · Hub+Spoke · Click flows to expand · All data through pib.cli permission boundary
        </div>
      </div>
    </div>
  );
}
