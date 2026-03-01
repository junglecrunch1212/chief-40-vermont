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
  external: { fill: "#0a1520", border: "#1a5078", text: "#40a0e0", glow: "rgba(64,160,224,0.07)" },
  auth: { fill: "#1a0a18", border: "#7a2070", text: "#d060c0", glow: "rgba(208,96,192,0.07)" },
  fastapi: { fill: "#0a150a", border: "#2a7830", text: "#50d060", glow: "rgba(80,208,96,0.07)" },
  adapters: { fill: "#0d1520", border: "#2060a0", text: "#60b0f0", glow: "rgba(96,176,240,0.07)" },
  pipeline: { fill: "#100a1a", border: "#5030a0", text: "#9070e0", glow: "rgba(144,112,224,0.07)" },
  storage: { fill: "#0a1510", border: "#207050", text: "#40c080", glow: "rgba(64,192,128,0.07)" },
  intel: { fill: "#150a18", border: "#802060", text: "#e060a0", glow: "rgba(224,96,160,0.07)" },
  scheduler: { fill: "#151005", border: "#806020", text: "#e0a030", glow: "rgba(224,160,48,0.07)" },
  surfaces: { fill: "#051015", border: "#206080", text: "#40c0e0", glow: "rgba(64,192,224,0.07)" },
};

const ZONES = [
  {
    id: "hardware",
    title: 'MAC MINI "COS-1"',
    subtitle: "M2+ · headless · closet · always-on · macOS Sequoia 15+",
    theme: C.hardware,
    components: [
      { name: "/opt/pib/data/pib.db", detail: "SQLite 3.45+ WAL mode" },
      { name: "/opt/pib/venv", detail: "Python 3.12+ virtual environment" },
      { name: "/opt/pib/logs/pib.jsonl", detail: "Rotating JSON logs (50MB × 5)" },
      { name: "BlueBubbles v1.9+", detail: "iMessage bridge — local macOS process" },
      { name: "launchd", detail: "Auto-start on boot, restart on crash" },
      { name: "Time Machine", detail: "Backup + hourly SQLite copy" },
    ],
  },
  {
    id: "external",
    title: "EXTERNAL SERVICES",
    subtitle: "Read-only data sources + outbound delivery — Gene 4: never writes to calendars or moves money",
    theme: C.external,
    components: [
      { name: "Google Calendar", detail: "API v3 incremental sync · sync tokens · full sync daily 2AM" },
      { name: "Gmail", detail: "API push notifications + 5min poll fallback" },
      { name: "Google Sheets", detail: "Bidirectional sync · Apps Script onChange trigger" },
      { name: "Twilio", detail: "Inbound webhooks + outbound SMS delivery" },
      { name: "Anthropic API", detail: "Claude Opus / Sonnet / Haiku — LLM composition" },
      { name: "Cloudflare", detail: "Tunnel (ingress) + Access (Google OAuth)" },
      { name: "Healthchecks.io", detail: "External uptime monitoring — heartbeat every 5min" },
    ],
  },
  {
    id: "auth",
    title: "AUTHENTICATION LAYER",
    subtitle: "From day one — every endpoint authenticated, every webhook validated",
    theme: C.auth,
    components: [
      { name: "Cloudflare Access", detail: "Google OAuth — James + Laura only → web + API" },
      { name: "Twilio Signature", detail: "X-Twilio-Signature HMAC validation on webhooks" },
      { name: "BlueBubbles Secret", detail: "Shared secret header on iMessage webhooks" },
      { name: "Siri Bearer Token", detail: "Authorization: Bearer <token> on shortcut POSTs" },
      { name: "Sheets Service Acct", detail: "Google service account key for webhook auth" },
      { name: "Rate Limiter", detail: "Per-source: SMS 30/min, Siri 20/min, web 10/min" },
    ],
  },
  {
    id: "fastapi",
    title: "FASTAPI APPLICATION — PORT 3141",
    subtitle: "Core application server — async Python · aiosqlite · httpx · anthropic SDK",
    theme: C.fastapi,
    children: [
      {
        id: "adapters",
        title: "ADAPTERS",
        subtitle: "8 sources → unified IngestEvent interface (poll + webhook + send)",
        theme: C.adapters,
        components: [
          { name: "Gmail Adapter", detail: "API push + 5min poll · whitelist + triage keywords" },
          { name: "Google Calendar", detail: "Incremental sync · 15min + 5min volatile" },
          { name: "Apple Reminders", detail: "AppleScript bridge · 5min poll" },
          { name: "iMessage (BB)", detail: "BlueBubbles webhook + 5min backup poll" },
          { name: "Twilio SMS", detail: "Webhook handler + send via API" },
          { name: "Siri Shortcuts", detail: "POST webhook → IngestEvent" },
          { name: "Bank Import", detail: "CSV file watch · 5min poll · Plaid deferred" },
          { name: "Sheets Webhook", detail: "onChange → diff → queue → flush" },
        ],
      },
      {
        id: "pipeline",
        title: "INGESTION PIPELINE",
        subtitle: "8 stages · dedup → parse → classify → privacy → write → observe → confirm",
        theme: C.pipeline,
        components: [
          { name: "Dedup Engine", detail: "SHA256 idempotency keys per source type" },
          { name: "Member Resolver", detail: "Phone/email/handle → member_id mapping" },
          { name: "Five Shapes Parser", detail: "TASK | TIME_BLOCK | MONEY_STATE | RECURRING | ENTITY" },
          { name: "Classifier", detail: "Deterministic domain + urgency + energy level" },
          { name: "Privacy Fence", detail: "full | privileged | redacted — content filtered at read" },
          { name: "Prefix Parser", detail: "20+ regex rules: grocery:, call, buy, meds, sleep..." },
          { name: "Micro-Script Gen", detail: "Deterministic first-physical-action instructions" },
          { name: "Dead Letter Queue", detail: "Failed events stored, retried ×3, alertable" },
        ],
      },
      {
        id: "storage",
        title: "SQLITE SSOT",
        subtitle: "Layer 1 Core — WAL mode · write-batched · append-only · never deletes",
        theme: C.storage,
        components: [
          { name: "common_*", detail: "Members, sources, custody, locations, phases, config, audit, undo" },
          { name: "ops_*", detail: "Tasks (state machine), goals, items, recurring, comms, lists, streaks" },
          { name: "cal_*", detail: "Sources, raw events, classified events, daily states, conflicts" },
          { name: "fin_*", detail: "Transactions, budgets, merchant rules, capital expenses, bills" },
          { name: "mem_*", detail: "Sessions, messages, long-term memory (FTS5), digests, approvals" },
          { name: "pib_*", detail: "Reward log, energy states, coach protocols" },
          { name: "meta_*", detail: "Schema version, migrations (up+down), discovery reports" },
          { name: "WriteQueue", detail: "Batched flush every 100ms/50 items · persistent connection" },
        ],
      },
      {
        id: "intel",
        title: "INTELLIGENCE LAYER",
        subtitle: "Layer 2 Enhanced — degrades to Layer 1 template fallbacks when API unavailable",
        theme: C.intel,
        components: [
          { name: "Relevance Detection", detail: "3-layer: keywords → entity match → always-on summary" },
          { name: "Context Assembly", detail: "~51K tokens: system(2.5K) + summary(500) + context(25K) + memory(3K) + history(20K)" },
          { name: "Model Router", detail: "Opus (digest/complex) · Sonnet (chat) · Haiku (triage/classify)" },
          { name: "15 Tool Functions", detail: "create_task, what_now, query_*, save_memory, send_message, undo..." },
          { name: "Conversation Manager", detail: "Sliding window · SMS: 10 msgs · Web: 50 msgs" },
          { name: "Hallucination Guard", detail: "Validate LLM output against structured source data" },
          { name: "Deterministic Fallback", detail: "API down → template responses + whatNow() still works" },
        ],
      },
      {
        id: "scheduler",
        title: "SCHEDULER + PROACTIVE ENGINE",
        subtitle: "APScheduler AsyncIOScheduler — NEVER BlockingScheduler (freezes event loop)",
        theme: C.scheduler,
        components: [
          { name: "Calendar Sync", detail: "*/15 min cron — incremental + 5min volatile window" },
          { name: "Morning Digest", detail: "6:30 AM — sleep check + top 3 + custody + budget" },
          { name: "Paralysis Detection", detail: "2h silence during peak → micro-task restart (James)" },
          { name: "Post-Meeting Capture", detail: "Event ended <15min ago → prompt for action items" },
          { name: "Conflict Alert", detail: "48h lookahead — critical/high calendar conflicts" },
          { name: "Budget Alert", detail: "Category over threshold — daily cooldown" },
          { name: "Sheets Push", detail: "*/15 min — DB → Google Sheets sync" },
          { name: "Guardrails", detail: "5 msgs/day max · 2/hour · quiet 10pm-7am · focus mode" },
        ],
      },
      {
        id: "surfaces",
        title: "OUTPUT SURFACES",
        subtitle: "Gene 5: whatNow() — ONE task with micro-script · per-actor view modes",
        theme: C.surfaces,
        components: [
          { name: "Web Dashboard", detail: "/dashboard — today view + tasks + schedule + budget" },
          { name: "James: Carousel", detail: "ONE card · micro-script · Done/Skip/Dismiss · streak display" },
          { name: "Laura: Compressed", detail: "Decisions [Y/N] + task list + household status" },
          { name: "Scoreboard /scoreboard", detail: "Kitchen TV · dark bg · large text · auto-refresh 60s" },
          { name: "Web Chat + SSE", detail: "Streaming responses · tool use · up to 5 tool rounds" },
          { name: "iMessage / SMS Out", detail: "Channel-adapted delivery · confirmation messages" },
          { name: "Health Probe /health", detail: "Read-only · DB check · adapter pings · for Healthchecks.io" },
        ],
      },
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
  const indent = depth * 0;

  return (
    <div style={{ marginLeft: indent }}>
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
          marginBottom: isOpen && hasChildren ? 0 : 0,
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

function ConnectionLine({ from, to, label, direction, style: lineStyle }) {
  const fromZone = ZONES.find(z => z.id === from) ||
    ZONES.flatMap(z => z.children || []).find(z => z.id === from);
  const toZone = ZONES.find(z => z.id === to) ||
    ZONES.flatMap(z => z.children || []).find(z => z.id === to);
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
          : lineStyle === "dotted"
          ? `repeating-linear-gradient(90deg, ${C.textDim} 0 2px, transparent 2px 6px)`
          : `linear-gradient(90deg, ${fromColor}60, ${toColor}60)`,
      }} />
      <span style={{ color: C.textMid, whiteSpace: "nowrap", fontSize: 9 }}>
        {label}
      </span>
      <span style={{
        flex: 1, height: 1,
        background: lineStyle === "dashed"
          ? `repeating-linear-gradient(90deg, ${C.textDim} 0 5px, transparent 5px 9px)`
          : lineStyle === "dotted"
          ? `repeating-linear-gradient(90deg, ${C.textDim} 0 2px, transparent 2px 6px)`
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

const CONNECTIONS = [
  { from: "external", to: "auth", label: "inbound requests", direction: "fwd" },
  { from: "auth", to: "adapters", label: "validated events", direction: "fwd" },
  { from: "adapters", to: "pipeline", label: "IngestEvent", direction: "fwd" },
  { from: "pipeline", to: "storage", label: "Five Shapes → WriteQueue", direction: "fwd" },
  { from: "storage", to: "intel", label: "assembled context (~51K tokens)", direction: "fwd" },
  { from: "intel", to: "storage", label: "tool calls → write", direction: "back", style: "dashed" },
  { from: "storage", to: "scheduler", label: "trigger queries", direction: "fwd" },
  { from: "scheduler", to: "intel", label: "compose request", direction: "fwd" },
  { from: "intel", to: "surfaces", label: "LLM responses", direction: "fwd" },
  { from: "scheduler", to: "surfaces", label: "proactive messages", direction: "fwd" },
  { from: "storage", to: "surfaces", label: "whatNow() deterministic", direction: "fwd", style: "dotted" },
  { from: "surfaces", to: "pipeline", label: "user replies loop back", direction: "back", style: "dashed" },
  { from: "storage", to: "external", label: "Sheets push / SMS out", direction: "fwd", style: "dashed" },
];

function LayerLegend() {
  const layers = [
    { label: "LAYER 1: CORE", desc: "Always works — no LLM required", color: C.storage.text },
    { label: "LAYER 2: ENHANCED", desc: "Claude LLM — degrades gracefully", color: C.intel.text },
    { label: "LAYER 3: EXTENDED", desc: "External APIs — degrades to L2/L1", color: C.external.text },
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

  const [expanded, setExpanded] = useState(new Set(["fastapi"]));
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
              pib-v5-build-spec.md
            </span>
          </div>
          <p style={{
            fontSize: 11.5,
            color: C.textDim,
            margin: "6px 0 0",
            lineHeight: 1.5,
          }}>
            A prosthetic prefrontal cortex running on a Mac Mini in the closet.
            FastAPI :3141 · SQLite WAL · Cloudflare Tunnel · 8 adapters · 15 tools · 3 Claude models.
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
          {ZONES.map((zone, zi) => (
            <div key={zone.id}>
              <ZoneBlock
                zone={zone}
                depth={0}
                expandedSet={expanded}
                toggle={toggle}
              />

              {/* Connection lines between zones */}
              {showConnections && zi < ZONES.length - 1 && (
                <div style={{ padding: "4px 0", marginBottom: 2 }}>
                  {CONNECTIONS
                    .filter(c => {
                      const fromIdx = ZONES.findIndex(z => z.id === c.from);
                      const toIdx = ZONES.findIndex(z => z.id === c.to);
                      return (fromIdx === zi && toIdx === zi + 1) ||
                        (toIdx === zi && fromIdx === zi + 1);
                    })
                    .map((c, i) => (
                      <ConnectionLine key={i} {...c} />
                    ))}
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Internal Connections (within FastAPI) */}
        {showConnections && expanded.has("fastapi") && (
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
              INTERNAL DATA FLOW (within FastAPI)
            </div>
            <div style={{ display: "grid", gap: 2 }}>
              {CONNECTIONS
                .filter(c =>
                  ["adapters", "pipeline", "storage", "intel", "scheduler", "surfaces"].includes(c.from) &&
                  ["adapters", "pipeline", "storage", "intel", "scheduler", "surfaces"].includes(c.to)
                )
                .map((c, i) => (
                  <ConnectionLine key={i} {...c} />
                ))}
            </div>
          </div>
        )}

        {/* Build Phases */}
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
            BUILD PHASES
          </div>
          <div style={{ display: "grid", gap: 6 }}>
            {[
              { phase: "Phase 0", hours: "~16h", title: "Operational", desc: "Schema + pipeline + SMS + Siri + whatNow() + web chat + streaks", color: C.fastapi.text },
              { phase: "Phase 1", hours: "~16h", title: "Calendar Intelligence", desc: "Google Calendar sync + classification + custody + morning digest", color: C.adapters.text },
              { phase: "Phase 2", hours: "~16h", title: "Console + Scoreboard", desc: "Dashboard views + iMessage + Reminders + ADHD mechanics", color: C.surfaces.text },
              { phase: "Phase 3", hours: "Weeks 2-4", title: "Finance + Memory + Polish", desc: "Bank import + budgets + Sheets sync + Gmail + weekly review", color: C.scheduler.text },
            ].map((p, i) => (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "6px 0",
                borderBottom: i < 3 ? `1px solid ${C.border}` : "none",
              }}>
                <Badge text={p.phase} color={p.color} />
                <span style={{
                  fontSize: 10, color: C.textDim, fontFamily: "monospace", minWidth: 48,
                }}>
                  {p.hours}
                </span>
                <span style={{ fontSize: 11, fontWeight: 600, color: C.text, minWidth: 100 }}>
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
            { value: "8", label: "Adapters", color: C.adapters.text },
            { value: "15", label: "LLM Tools", color: C.intel.text },
            { value: "7", label: "DB Domains", color: C.storage.text },
            { value: "51K", label: "Token Budget", color: C.intel.text },
            { value: "3", label: "Claude Models", color: C.external.text },
            { value: "10", label: "Invariants", color: C.hardware.text },
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
