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
};

const LAYERS = [
  {
    id: "sources",
    label: "DATA SOURCES",
    subtitle: "Gene 4: The Read Layer — read-only, never writes",
    color: COLORS.cyan,
    glow: COLORS.cyanGlow,
    items: [
      { id: "gmail", name: "Gmail", transport: "API push + 5min poll", key: "SHA256(gmail:{messageId})", icon: "📧" },
      { id: "gcal", name: "Google Calendar", transport: "API v3 incremental sync", key: "SHA256(gcal:{eventId}:{updated})", icon: "📅" },
      { id: "imessage", name: "iMessage", transport: "BlueBubbles webhook", key: "SHA256(imessage:{guid})", icon: "💬" },
      { id: "sms", name: "Twilio SMS", transport: "Webhook", key: "SHA256(sms:{MessageSid})", icon: "📱" },
      { id: "siri", name: "Siri Shortcuts", transport: "Webhook", key: "SHA256(siri:{ts}:{text})", icon: "🎙️" },
      { id: "reminders", name: "Apple Reminders", transport: "AppleScript 5min poll", key: "SHA256(reminder:{id})", icon: "✅" },
      { id: "bank", name: "Bank Import", transport: "CSV file watch", key: "SHA256(bank:{acct}:{date}:{amt})", icon: "🏦" },
      { id: "sheets", name: "Google Sheets", transport: "Apps Script onChange", key: "SHA256(sheets:{sheet}:{row})", icon: "📊" },
    ],
  },
  {
    id: "ingestion",
    label: "INGESTION PIPELINE",
    subtitle: "Section 6: Unified adapter → 8-stage pipeline → Five Shapes",
    color: COLORS.blue,
    glow: COLORS.blueGlow,
    items: [
      { id: "stage1", name: "① Dedup", desc: "Idempotency key check — SHA256 per source" },
      { id: "stage2", name: "② Member Resolution", desc: "Map sender → household member" },
      { id: "stage3", name: "③ Parse → Five Shapes", desc: "TASK | TIME BLOCK | MONEY STATE | RECURRING | ENTITY" },
      { id: "stage4", name: "④ Classify", desc: "Deterministic domain + urgency + energy" },
      { id: "stage5", name: "⑤ Privacy Fence", desc: "full | privileged | redacted — Gene 6 Rule 3" },
      { id: "stage6", name: "⑥ Route + Write", desc: "Insert into SQLite via WriteQueue (batched)" },
      { id: "stage7", name: "⑦ Cross-Domain Observations", desc: "Detect patterns across domains" },
      { id: "stage8", name: "⑧ Confirm + Emit", desc: "Reply to sender, emit to event bus" },
    ],
  },
  {
    id: "storage",
    label: "SSOT — SQLite (WAL)",
    subtitle: "Layer 1 Core — data on disk, always works, never deletes",
    color: COLORS.green,
    glow: COLORS.greenGlow,
    items: [
      { id: "ops", name: "ops_tasks", desc: "Tasks with state machine (open→in_progress→done)" },
      { id: "cal", name: "cal_classified_events", desc: "Calendar events + conflict detection" },
      { id: "fin", name: "fin_transactions", desc: "Transactions + budget snapshots" },
      { id: "mem", name: "mem_long_term", desc: "FTS5-indexed persistent memory" },
      { id: "energy", name: "pib_energy_states", desc: "Medication, sleep, focus mode, streaks" },
      { id: "common", name: "common_members", desc: "Household members + source classifications" },
    ],
  },
  {
    id: "intelligence",
    label: "INTELLIGENCE LAYER",
    subtitle: "Layer 2: Context Assembly + LLM — degrades to Layer 1 if API down",
    color: COLORS.purple,
    glow: COLORS.purpleGlow,
    items: [
      { id: "relevance", name: "3-Layer Relevance", desc: "Keywords → Entity match → Always-on summary" },
      { id: "context", name: "Context Assembly", desc: "~51K token budget across 5 sections" },
      { id: "llm", name: "Claude LLM", desc: "Opus (digest) / Sonnet (chat) / Haiku (triage)" },
      { id: "tools", name: "15 Tools", desc: "create_task, what_now, query_*, save_memory, etc." },
      { id: "fallback", name: "Deterministic Fallback", desc: "API down → template responses + whatNow()" },
    ],
  },
  {
    id: "engine",
    label: "PROACTIVE ENGINE",
    subtitle: "Section 8: Trigger-based outbound — max 5 msgs/person/day",
    color: COLORS.amber,
    glow: COLORS.amberGlow,
    items: [
      { id: "morning", name: "Morning Digest", desc: "6:30 AM — sleep check + top 3 + custody + budget" },
      { id: "paralysis", name: "Paralysis Detection", desc: "2h silence → gentle micro-task restart" },
      { id: "conflict", name: "Conflict Alert", desc: "48h lookahead — critical calendar conflicts" },
      { id: "velocity", name: "Velocity Celebration", desc: "10+ completions → celebrate + suggest break" },
      { id: "budget", name: "Budget Alert", desc: "Category over threshold — daily cooldown" },
    ],
  },
  {
    id: "surfaces",
    label: "OUTPUT SURFACES",
    subtitle: "Gene 5: whatNow() — ONE task, not a list, with micro-script",
    color: COLORS.pink,
    glow: COLORS.pinkGlow,
    items: [
      { id: "carousel", name: "James: Carousel", desc: "ONE card, micro-script, Done/Skip/Dismiss" },
      { id: "compressed", name: "Laura: Compressed", desc: "Decisions [Y/N] + tasks + household status" },
      { id: "scoreboard", name: "Scoreboard (TV)", desc: "Kitchen display — streaks, stars, Captain" },
      { id: "imsg_out", name: "iMessage / SMS", desc: "Channel-adapted outbound messages" },
      { id: "sheets_out", name: "Sheets Sync", desc: "DB → Sheets push every 15 min" },
    ],
  },
];

const FLOWS = [
  { from: "sources", to: "ingestion", label: "IngestEvent", style: "solid" },
  { from: "ingestion", to: "storage", label: "Five Shapes → Write", style: "solid" },
  { from: "storage", to: "intelligence", label: "Assembled Context", style: "solid" },
  { from: "intelligence", to: "storage", label: "Tool Calls → Write", style: "dashed" },
  { from: "storage", to: "engine", label: "Trigger Queries", style: "solid" },
  { from: "engine", to: "surfaces", label: "Composed Messages", style: "solid" },
  { from: "intelligence", to: "surfaces", label: "LLM Responses", style: "solid" },
  { from: "surfaces", to: "ingestion", label: "User replies loop back", style: "dashed" },
  { from: "storage", to: "surfaces", label: "whatNow() (deterministic)", style: "dotted" },
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
              {(item.desc || item.transport) && (
                <div style={{ fontSize: 11.5, color: COLORS.textMuted, marginTop: 4, lineHeight: 1.5 }}>
                  {item.desc}
                  {item.transport && (
                    <span style={{ display: "block", color: COLORS.textDim, fontSize: 10.5, marginTop: 2 }}>
                      Transport: {item.transport} · Key: <code style={{ color: layer.color, fontSize: 10 }}>{item.key}</code>
                    </span>
                  )}
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

  const isReverse = flow.style === "dashed" && flow.from === "surfaces";
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
        {isReverse ? "↺" : "→"}
      </span>
    </div>
  );
}

function GeneBar({ genes }) {
  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: 6,
      marginBottom: 20,
    }}>
      {genes.map((g) => (
        <span
          key={g.id}
          style={{
            fontSize: 10,
            fontWeight: 600,
            padding: "3px 8px",
            borderRadius: 4,
            background: g.active ? `${g.color}22` : "transparent",
            border: `1px solid ${g.active ? g.color : COLORS.border}`,
            color: g.active ? g.color : COLORS.textDim,
            fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
            letterSpacing: "0.05em",
            transition: "all 0.3s",
          }}
        >
          {g.label}
        </span>
      ))}
    </div>
  );
}

export default function PIBDataFlows() {
  const [expanded, setExpanded] = useState(new Set(["sources", "ingestion"]));

  const toggle = (id) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(LAYERS.map((l) => l.id)));
  const collapseAll = () => setExpanded(new Set());

  const genes = [
    { id: 1, label: "Gene 1: The Loop", color: COLORS.blue, active: expanded.has("ingestion") },
    { id: 2, label: "Gene 2: Vocabulary", color: COLORS.cyan, active: expanded.has("sources") },
    { id: 3, label: "Gene 3: Five Shapes", color: COLORS.blue, active: expanded.has("ingestion") },
    { id: 4, label: "Gene 4: Read Layer", color: COLORS.cyan, active: expanded.has("sources") },
    { id: 5, label: "Gene 5: whatNow()", color: COLORS.pink, active: expanded.has("surfaces") },
    { id: 6, label: "Gene 6: Write Layer", color: COLORS.green, active: expanded.has("storage") },
    { id: 7, label: "Gene 7: Invariants", color: COLORS.green, active: expanded.has("storage") },
    { id: 8, label: "Gene 8: Growth Rule", color: COLORS.purple, active: expanded.has("intelligence") },
    { id: 9, label: "Gene 9: The Probe", color: COLORS.amber, active: expanded.has("engine") },
  ];

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
            Mac Mini COS-1 · FastAPI :3141 · SQLite WAL · Cloudflare Tunnel
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

        {/* Gene indicators */}
        <GeneBar genes={genes} />

        {/* The Three Layers legend */}
        <div style={{
          display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap",
        }}>
          {[
            { label: "L1: Core (always works)", color: COLORS.green },
            { label: "L2: Enhanced (LLM)", color: COLORS.purple },
            { label: "L3: Extended (APIs)", color: COLORS.cyan },
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
                  {/* Show cross-layer flows at relevant positions */}
                  {i === 2 &&
                    FLOWS.filter((f) =>
                      (f.from === "storage" && f.to === "engine") ||
                      (f.from === "storage" && f.to === "surfaces")
                    ).map((f, j) => (
                      <FlowArrow key={`cross-${j}`} flow={f} layers={LAYERS} />
                    ))}
                  {i === 4 &&
                    FLOWS.filter((f) => f.from === "surfaces" && f.to === "ingestion")
                      .map((f, j) => (
                        <FlowArrow key={`loop-${j}`} flow={f} layers={LAYERS} />
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
              "Every task has a micro_script",
              "Classification at onboarding, execution never reclassifies",
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
              "Anthropic API down → template fallbacks, whatNow() still works",
              "Google Calendar down → use last-known + warn",
              "Gmail down → other capture still works",
              "Bank/Plaid down → skip budget context",
              "BlueBubbles down → fall back to Twilio SMS",
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
          pib-v5-build-spec.md · Click layers to expand · Genes highlight when their layer is active
        </div>
      </div>
    </div>
  );
}
