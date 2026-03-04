import { useState } from "react";

const C = {
  bg: "#06090f",
  bgSubtle: "#0c1018",
  card: "#0f1520",
  cardHover: "#141c2a",
  border: "#1a2438",
  borderLit: "#2a3a55",
  text: "#dce4f0",
  textMid: "#8c9ab5",
  textDim: "#546280",
  // Zones
  hardware: { fill: "#1a1205", border: "#78591a", text: "#f0c040", glow: "rgba(240,192,64,0.07)" },
  bridge: { fill: "#15100a", border: "#6a4a1a", text: "#d0a030", glow: "rgba(208,160,48,0.07)" },
  openclaw: { fill: "#0a150a", border: "#2a7830", text: "#50d060", glow: "rgba(80,208,96,0.07)" },
  channels: { fill: "#0a1520", border: "#2060a0", text: "#60b0f0", glow: "rgba(96,176,240,0.07)" },
  pibL1: { fill: "#100a1a", border: "#5030a0", text: "#9070e0", glow: "rgba(144,112,224,0.07)" },
  pibL2: { fill: "#150a18", border: "#802060", text: "#e060a0", glow: "rgba(224,96,160,0.07)" },
  storage: { fill: "#0a1510", border: "#207050", text: "#40c080", glow: "rgba(64,192,128,0.07)" },
  console: { fill: "#051015", border: "#206080", text: "#40c0e0", glow: "rgba(64,192,224,0.07)" },
  external: { fill: "#0a1520", border: "#1a5078", text: "#40a0e0", glow: "rgba(64,160,224,0.07)" },
};

const ZONES = [
  {
    id: "hardware",
    title: 'COS MAC MINI "PIB-MINI" — BRAIN',
    subtitle: "M2+ · headless · closet · always-on · macOS Sequoia 15+ · Hub in Hub+Spoke topology",
    theme: C.hardware,
    components: [
      { name: "OpenClaw daemon", detail: "L0 infrastructure — Node.js gateway, always-on via launchd" },
      { name: "PIB Python package", detail: "L1-L2 logic — whatNow, rewards, custody, memory, ingest" },
      { name: "/opt/pib/data/pib.db", detail: "SQLite 3.45+ WAL mode — single source of truth" },
      { name: "Console server", detail: "Express :3333 — dashboard, scoreboard, API" },
      { name: "gog CLI", detail: "Google Calendar, Sheets, Gmail access" },
      { name: "BlueBubbles v1.9+", detail: "iMessage bridge (temporary — moves to James Mini later)" },
      { name: "launchd", detail: "Auto-start on boot, restart on crash" },
      { name: "Time Machine", detail: "Backup + hourly SQLite copy" },
    ],
  },
  {
    id: "bridges",
    title: "BRIDGE MINIS — SPOKE NODES",
    subtitle: "Sensor data + iMessage bridges — push to CoS via HTTP webhooks",
    theme: C.bridge,
    children: [
      {
        id: "james-mini",
        title: 'JAMES MAC MINI "JAMES-MINI"',
        subtitle: "Bridge — James's personal sensors + iMessage",
        theme: C.bridge,
        components: [
          { name: "BlueBubbles", detail: "James's iMessage bridge" },
          { name: "Apple Shortcuts", detail: "Health, FindMy, Focus, Siri, Battery" },
          { name: "HomeKit bridge", detail: "Homebridge — smart home integration" },
          { name: "HTTP webhooks → CoS", detail: "POST /api/sensors/ingest → pib-mini" },
        ],
      },
      {
        id: "laura-mini",
        title: 'LAURA MAC MINI "LAURA-MINI"',
        subtitle: "Bridge — Laura's personal sensors + iMessage (privacy: privileged)",
        theme: C.bridge,
        components: [
          { name: "BlueBubbles", detail: "Laura's iMessage bridge" },
          { name: "Apple Shortcuts", detail: "Health, FindMy, Focus, Siri, Battery" },
          { name: "HTTP webhooks → CoS", detail: "POST /api/sensors/ingest (privileged classification)" },
        ],
      },
    ],
  },
  {
    id: "openclaw",
    title: "OPENCLAW L0 — GATEWAY + INFRASTRUCTURE",
    subtitle: "Node.js daemon — channel routing, cron engine, model routing, agent orchestration",
    theme: C.openclaw,
    children: [
      {
        id: "channels",
        title: "CHANNEL ROUTING",
        subtitle: "Inbound messages → unified channel interface → agent dispatch",
        theme: C.channels,
        components: [
          { name: "iMessage (BlueBubbles)", detail: "Webhook from BlueBubbles → channel handler" },
          { name: "SMS (Twilio)", detail: "Inbound webhook + outbound SMS delivery" },
          { name: "Webchat", detail: "Browser-based chat interface" },
          { name: "Channel auth", detail: "Per-channel authentication (replaces old auth.py)" },
        ],
      },
      {
        id: "oc-cron",
        title: "CRON ENGINE",
        subtitle: "Replaces APScheduler — declarative cron jobs calling pib.cli",
        theme: C.openclaw,
        components: [
          { name: "Calendar sync", detail: "gog calendar events → calendar_sync.mjs → pib.cli calendar-ingest" },
          { name: "Morning digest", detail: "6:30 AM — pib.cli morning-digest" },
          { name: "Recurring spawn", detail: "6:00 AM — pib.cli spawn-recurring" },
          { name: "Financial sync", detail: "gog sheets get → pib.cli financial-sync" },
          { name: "Comms ingest", detail: "gog gmail list → pib.cli comms-ingest" },
          { name: "Proactive scan", detail: "*/30 7-22 — pib.cli proactive-scan" },
          { name: "Sensor enrichment", detail: "Process queued sensor data from Bridge Minis" },
        ],
      },
      {
        id: "oc-model",
        title: "MODEL ROUTING",
        subtitle: "Multi-provider LLM access — replaces direct Anthropic client",
        theme: C.openclaw,
        components: [
          { name: "Provider routing", detail: "Anthropic, OpenAI, local — failover + cost control" },
          { name: "Claude Opus", detail: "Complex reasoning, digests, coaching" },
          { name: "Claude Sonnet", detail: "Standard chat, task processing" },
          { name: "Claude Haiku", detail: "Triage, classification, quick responses" },
        ],
      },
      {
        id: "oc-gog",
        title: "GOG CLI — GOOGLE SERVICES",
        subtitle: "CLI tool for Google Calendar, Sheets, Gmail access",
        theme: C.openclaw,
        components: [
          { name: "gog calendar events", detail: "Read calendar data → feed to calendar_sync.mjs" },
          { name: "gog sheets get", detail: "Read Google Sheets → feed to pib.cli financial-sync" },
          { name: "gog gmail list", detail: "Read Gmail → feed to pib.cli comms-ingest" },
        ],
      },
    ],
  },
  {
    id: "pibL1",
    title: "PIB L1 — DETERMINISTIC CORE",
    subtitle: "python -m pib.cli — permission boundary with 6-layer security (allowlist, governance, SQL guard, rate limit, sanitizer, audit)",
    theme: C.pibL1,
    components: [
      { name: "cli.py", detail: "Permission boundary — all access through pib.cli commands" },
      { name: "engine.py / whatNow()", detail: "THE deterministic function — scoring, no LLM, no side effects" },
      { name: "rewards.py", detail: "Variable-ratio reinforcement — 70/20/8/2 reward tiers" },
      { name: "custody.py", detail: "DST-aware custody date math — who_has_child()" },
      { name: "memory.py", detail: "Long-term memory — FTS5 search, dedup, negation detection" },
      { name: "ingest.py", detail: "Unified ingestion — dedup, parse, classify, privacy fence, write" },
      { name: "corrections.py", detail: "Misclassification feedback — fix: and reclassify: commands" },
    ],
  },
  {
    id: "pibL2",
    title: "PIB L2 — INTELLIGENCE LAYER",
    subtitle: "LLM-enhanced — degrades to L1 template fallbacks when API unavailable",
    theme: C.pibL2,
    components: [
      { name: "Claude LLM", detail: "Opus (digest/complex) · Sonnet (chat) · Haiku (triage)" },
      { name: "Context assembly", detail: "~51K tokens: system + summary + context + memory + history" },
      { name: "Coaching protocols", detail: "8 protocols — paralysis detection, velocity celebration, etc." },
      { name: "Proactive engine", detail: "Trigger-based outbound — morning digest, conflict alerts" },
      { name: "Hallucination guard", detail: "Validate LLM output against structured source data" },
      { name: "Deterministic fallback", detail: "API down → template responses + whatNow() still works" },
    ],
  },
  {
    id: "storage",
    title: "SQLITE SSOT — /opt/pib/data/pib.db",
    subtitle: "WAL mode · FTS5 · append-only · never deletes — Layer 1 always works",
    theme: C.storage,
    components: [
      { name: "common_*", detail: "Members, sources, custody, locations, phases, config, audit" },
      { name: "ops_*", detail: "Tasks (state machine), goals, items, recurring, comms, lists, streaks" },
      { name: "cal_*", detail: "Sources, raw events, classified events, daily states, conflicts" },
      { name: "fin_*", detail: "Transactions, budgets, merchant rules, capital expenses, bills" },
      { name: "mem_*", detail: "Sessions, messages, long-term memory (FTS5), digests, approvals" },
      { name: "pib_*", detail: "Reward log, energy states, coach protocols" },
      { name: "meta_*", detail: "Schema version, migrations (up+down), discovery reports" },
      { name: "Backup", detail: "Hourly .backup + daily encrypted cloud backup (age)" },
    ],
  },
  {
    id: "console",
    title: "CONSOLE — EXPRESS :3333",
    subtitle: "Dashboard UI + API — reads SQLite SSOT directly",
    theme: C.console,
    components: [
      { name: "Dashboard", detail: "Today view + tasks + schedule + budget — per-actor views" },
      { name: "James: Carousel", detail: "ONE card · micro-script · Done/Skip/Dismiss · streak display" },
      { name: "Laura: Compressed", detail: "Decisions [Y/N] + task list + household status" },
      { name: "Scoreboard", detail: "Kitchen TV · dark bg · large text · auto-refresh 60s" },
      { name: "Web Chat", detail: "Streaming responses via SSE" },
      { name: "Health Probe", detail: "Read-only · DB check · adapter pings" },
    ],
  },
];

function Badge({ text, color }) {
  return (
    <span style={{
      fontSize: 9,
      fontWeight: 700,
      padding: "2px 6px",
      borderRadius: 3,
      background: `${color}20`,
      border: `1px solid ${color}40`,
      color,
      fontFamily: "'JetBrains Mono', 'SF Mono', 'Fira Code', monospace",
      letterSpacing: "0.06em",
      whiteSpace: "nowrap",
    }}>
      {text}
    </span>
  );
}

function ComponentRow({ comp, theme, isLast }) {
  return (
    <div style={{
      display: "flex",
      gap: 10,
      padding: "7px 0",
      borderBottom: isLast ? "none" : `1px solid ${C.border}`,
      alignItems: "baseline",
    }}>
      <span style={{
        width: 5, height: 5, borderRadius: "50%",
        background: theme.text, flexShrink: 0, marginTop: 5,
        boxShadow: `0 0 6px ${theme.text}60`,
      }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{
          fontSize: 11.5,
          fontWeight: 600,
          color: C.text,
          fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
        }}>
          {comp.name}
        </span>
        <span style={{
          fontSize: 10.5,
          color: C.textDim,
          marginLeft: 8,
        }}>
          {comp.detail}
        </span>
      </div>
    </div>
  );
}

function ZoneBlock({ zone, depth = 0, expandedSet, toggle }) {
  const isOpen = expandedSet.has(zone.id);
  const theme = zone.theme;
  const hasChildren = zone.children && zone.children.length > 0;

  return (
    <div>
      <div
        onClick={() => toggle(zone.id)}
        style={{
          background: isOpen ? theme.fill : C.card,
          border: `1px solid ${isOpen ? theme.border : C.border}`,
          borderRadius: depth === 0 ? 10 : 8,
          padding: depth === 0 ? "14px 18px" : "10px 14px",
          cursor: "pointer",
          transition: "all 0.25s ease",
          boxShadow: isOpen ? `0 0 20px ${theme.glow}, inset 0 0 30px ${theme.glow}` : "none",
          borderBottomLeftRadius: isOpen && hasChildren ? 0 : undefined,
          borderBottomRightRadius: isOpen && hasChildren ? 0 : undefined,
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{
              fontSize: depth === 0 ? 12 : 10.5,
              fontWeight: 800,
              letterSpacing: "0.1em",
              color: theme.text,
              fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
            }}>
              {zone.title}
            </div>
            <div style={{
              fontSize: 10.5,
              color: C.textDim,
              marginTop: 3,
              lineHeight: 1.4,
              fontStyle: "italic",
            }}>
              {zone.subtitle}
            </div>
          </div>
          <div style={{
            display: "flex", alignItems: "center", gap: 8, flexShrink: 0, marginLeft: 12,
          }}>
            {zone.components && (
              <Badge text={`${zone.components.length}`} color={theme.text} />
            )}
            <div style={{
              width: 22, height: 22, borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              background: isOpen ? `${theme.text}20` : "transparent",
              border: `1.5px solid ${theme.text}60`,
              color: theme.text,
              fontSize: 13,
              fontFamily: "monospace",
              transition: "all 0.25s ease",
              transform: isOpen ? "rotate(45deg)" : "rotate(0)",
            }}>
              +
            </div>
          </div>
        </div>
      </div>

      {isOpen && (
        <div style={{
          background: theme.fill,
          border: `1px solid ${theme.border}`,
          borderTop: hasChildren ? `1px dashed ${theme.border}` : "none",
          borderTopLeftRadius: 0,
          borderTopRightRadius: 0,
          borderBottomLeftRadius: depth === 0 ? 10 : 8,
          borderBottomRightRadius: depth === 0 ? 10 : 8,
          padding: hasChildren ? "8px 10px 10px" : "6px 16px 10px",
        }}>
          {zone.components && !hasChildren && (
            <div>
              {zone.components.map((comp, i) => (
                <ComponentRow
                  key={i}
                  comp={comp}
                  theme={theme}
                  isLast={i === zone.components.length - 1}
                />
              ))}
            </div>
          )}

          {hasChildren && (
            <div style={{ display: "grid", gap: 6 }}>
              {zone.children.map((child) => (
                <ZoneBlock
                  key={child.id}
                  zone={child}
                  depth={depth + 1}
                  expandedSet={expandedSet}
                  toggle={toggle}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const CONNECTIONS = [
  { from: "bridges", to: "openclaw", label: "sensor webhooks (HTTP POST)", direction: "fwd" },
  { from: "channels", to: "pibL1", label: "pib.cli commands via agent", direction: "fwd" },
  { from: "openclaw", to: "pibL1", label: "cron → python -m pib.cli", direction: "fwd" },
  { from: "pibL1", to: "storage", label: "read/write SQLite SSOT", direction: "both" },
  { from: "pibL2", to: "pibL1", label: "LLM enhances L1 decisions", direction: "fwd" },
  { from: "storage", to: "console", label: "Express reads SQLite directly", direction: "fwd" },
  { from: "storage", to: "pibL2", label: "assembled context (~51K tokens)", direction: "fwd" },
  { from: "openclaw", to: "pibL2", label: "model routing → Claude", direction: "fwd", style: "dashed" },
  { from: "console", to: "channels", label: "webchat channel", direction: "both", style: "dashed" },
];

function ConnectionLine({ from, to, label, direction, style: lineStyle }) {
  const allZones = [...ZONES, ...ZONES.flatMap(z => z.children || [])];
  const fromZone = allZones.find(z => z.id === from);
  const toZone = allZones.find(z => z.id === to);
  if (!fromZone || !toZone) return null;

  const fromColor = fromZone.theme.text;
  const toColor = toZone.theme.text;

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: 6,
      padding: "1px 8px",
      fontSize: 9.5,
      fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
      color: C.textDim,
    }}>
      <span style={{
        fontSize: 8,
        color: fromColor,
        fontWeight: 700,
        minWidth: 50,
        textAlign: "right",
      }}>
        {fromZone.title?.split(" ")[0] || from}
      </span>
      <span style={{
        width: 5, height: 5, borderRadius: "50%", background: fromColor, flexShrink: 0,
      }} />
      <span style={{
        flex: 1, height: 1,
        background: lineStyle === "dashed"
          ? `repeating-linear-gradient(90deg, ${C.textDim} 0 5px, transparent 5px 9px)`
          : `linear-gradient(90deg, ${fromColor}60, ${toColor}60)`,
      }} />
      <span style={{ color: C.textMid, whiteSpace: "nowrap", fontSize: 9 }}>
        {label}
      </span>
      <span style={{
        flex: 1, height: 1,
        background: lineStyle === "dashed"
          ? `repeating-linear-gradient(90deg, ${C.textDim} 0 5px, transparent 5px 9px)`
          : `linear-gradient(90deg, ${fromColor}60, ${toColor}60)`,
      }} />
      <span style={{ color: toColor, fontSize: 12 }}>
        {direction === "both" ? "⇄" : direction === "back" ? "←" : "→"}
      </span>
      <span style={{
        width: 5, height: 5, borderRadius: "50%", background: toColor, flexShrink: 0,
      }} />
      <span style={{
        fontSize: 8,
        color: toColor,
        fontWeight: 700,
        minWidth: 50,
      }}>
        {toZone.title?.split(" ")[0] || to}
      </span>
    </div>
  );
}

function LayerLegend() {
  const layers = [
    { label: "L0: OPENCLAW", desc: "Infrastructure — gateway, cron, channels, model routing", color: C.openclaw.text },
    { label: "L1: PIB CORE", desc: "Always works — no LLM required", color: C.pibL1.text },
    { label: "L2: PIB ENHANCED", desc: "Claude LLM — degrades gracefully to L1", color: C.pibL2.text },
    { label: "L3: EXTERNAL", desc: "Google APIs, sensors — degrades to L2/L1", color: C.external.text },
  ];
  return (
    <div style={{
      display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 16,
    }}>
      {layers.map(l => (
        <div key={l.label} style={{
          display: "flex", alignItems: "center", gap: 6,
        }}>
          <div style={{
            width: 10, height: 10, borderRadius: 2,
            background: `${l.color}25`, border: `1.5px solid ${l.color}`,
          }} />
          <div>
            <span style={{
              fontSize: 9, fontWeight: 700, color: l.color,
              fontFamily: "monospace", letterSpacing: "0.08em",
            }}>
              {l.label}
            </span>
            <span style={{ fontSize: 9, color: C.textDim, marginLeft: 4 }}>
              {l.desc}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function PIBSystemArchitecture() {
  const allIds = [
    ...ZONES.map(z => z.id),
    ...ZONES.flatMap(z => (z.children || []).map(c => c.id)),
  ];

  const [expanded, setExpanded] = useState(new Set(["openclaw"]));
  const [showConnections, setShowConnections] = useState(true);

  const toggle = (id) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const expandAll = () => setExpanded(new Set(allIds));
  const collapseAll = () => setExpanded(new Set());

  return (
    <div style={{
      background: C.bg,
      minHeight: "100vh",
      padding: "28px 16px",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      color: C.text,
    }}>
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
            <h1 style={{
              fontSize: 20,
              fontWeight: 800,
              margin: 0,
              color: C.text,
              fontFamily: "'JetBrains Mono', 'SF Mono', monospace",
              letterSpacing: "-0.02em",
            }}>
              💩 PIB v5 — System Architecture
            </h1>
            <span style={{
              fontSize: 10,
              color: C.textDim,
              fontFamily: "monospace",
            }}>
              OpenClaw L0 · Hub+Spoke
            </span>
          </div>
          <p style={{
            fontSize: 11.5,
            color: C.textDim,
            margin: "6px 0 0",
            lineHeight: 1.5,
          }}>
            A prosthetic prefrontal cortex running on Mac Minis in the closet.
            OpenClaw gateway · SQLite WAL · LAN-only (pib-mini.local) · 3 Minis · pib.cli permission boundary · 3 Claude models.
          </p>

          <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
            <button onClick={expandAll} style={btnStyle}>expand all</button>
            <button onClick={collapseAll} style={btnStyle}>collapse all</button>
            <button
              onClick={() => setShowConnections(p => !p)}
              style={{ ...btnStyle, borderColor: showConnections ? C.textMid : C.border, color: showConnections ? C.text : C.textDim }}
            >
              {showConnections ? "hide" : "show"} connections
            </button>
          </div>
        </div>

        <LayerLegend />

        {/* Architecture blocks */}
        <div style={{ display: "grid", gap: 8 }}>
          {ZONES.map((zone) => (
            <ZoneBlock
              key={zone.id}
              zone={zone}
              depth={0}
              expandedSet={expanded}
              toggle={toggle}
            />
          ))}
        </div>

        {/* All Connections */}
        {showConnections && (
          <div style={{
            marginTop: 16,
            padding: "14px 16px",
            background: C.bgSubtle,
            border: `1px solid ${C.border}`,
            borderRadius: 8,
          }}>
            <div style={{
              fontSize: 10,
              fontWeight: 700,
              color: C.textMid,
              letterSpacing: "0.1em",
              marginBottom: 8,
              fontFamily: "monospace",
            }}>
              DATA FLOW CONNECTIONS
            </div>
            <div style={{ display: "grid", gap: 2 }}>
              {CONNECTIONS.map((c, i) => (
                <ConnectionLine key={i} {...c} />
              ))}
            </div>
          </div>
        )}

        {/* Degradation Layers */}
        <div style={{
          marginTop: 16,
          padding: "14px 16px",
          background: C.bgSubtle,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
        }}>
          <div style={{
            fontSize: 10,
            fontWeight: 700,
            color: C.textMid,
            letterSpacing: "0.1em",
            marginBottom: 10,
            fontFamily: "monospace",
          }}>
            THREE-LAYER DEGRADATION
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {[
              { layer: "L3 → L2", title: "APIs down", desc: "Google/sensors unavailable → LLM uses last-known data, warns user", color: C.external.text },
              { layer: "L2 → L1", title: "LLM down", desc: "Anthropic API unavailable → template fallbacks, whatNow() still works deterministically", color: C.pibL2.text },
              { layer: "L1 → Core", title: "Always works", desc: "SQLite + whatNow() + pib.cli — no external dependencies required", color: C.pibL1.text },
            ].map((p, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "6px 0",
                borderBottom: i < 2 ? `1px solid ${C.border}` : "none",
              }}>
                <Badge text={p.layer} color={p.color} />
                <span style={{ fontSize: 11, fontWeight: 600, color: C.text, minWidth: 80 }}>
                  {p.title}
                </span>
                <span style={{ fontSize: 10.5, color: C.textMid, flex: 1 }}>
                  {p.desc}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Key Numbers */}
        <div style={{
          marginTop: 12,
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: 8,
        }}>
          {[
            { value: "3", label: "Mac Minis", color: C.hardware.text },
            { value: "3", label: "Channels", color: C.channels.text },
            { value: "6", label: "Security Layers", color: C.pibL1.text },
            { value: "51K", label: "Token Budget", color: C.pibL2.text },
            { value: "3", label: "Claude Models", color: C.external.text },
            { value: "7", label: "DB Domains", color: C.storage.text },
          ].map((s, i) => (
            <div key={i} style={{
              background: C.card,
              border: `1px solid ${C.border}`,
              borderRadius: 6,
              padding: "10px 12px",
              textAlign: "center",
            }}>
              <div style={{
                fontSize: 20,
                fontWeight: 800,
                color: s.color,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {s.value}
              </div>
              <div style={{
                fontSize: 9,
                color: C.textDim,
                fontFamily: "monospace",
                letterSpacing: "0.08em",
                marginTop: 2,
              }}>
                {s.label}
              </div>
            </div>
          ))}
        </div>

        <div style={{
          marginTop: 16,
          fontSize: 9.5,
          color: C.textDim,
          textAlign: "center",
          fontFamily: "monospace",
        }}>
          Click zones to expand · Nested blocks show internal structure · Toggle connections to show data flow
        </div>
      </div>
    </div>
  );
}

const btnStyle = {
  fontSize: 9.5,
  padding: "4px 10px",
  borderRadius: 4,
  background: "transparent",
  border: `1px solid ${C.border}`,
  color: C.textMid,
  cursor: "pointer",
  fontFamily: "'JetBrains Mono', monospace",
  letterSpacing: "0.04em",
};
