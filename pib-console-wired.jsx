import { useState, useEffect, useRef, useCallback, useMemo } from "react";

// ─── STATIC CONSTANTS (not mock data — stable household config) ───
const MEMBERS = [
  { id: "m-james", name: "James", role: "parent", emoji: "💪", view: "carousel" },
  { id: "m-laura", name: "Laura", role: "parent", emoji: "⚖️", view: "compressed" },
  { id: "m-charlie", name: "Charlie", role: "child", emoji: "🌟", view: "child", age: 6 },
];

// ─── API LAYER ───
const BASE = ""; // Same origin — Express serves both API and console

async function apiFetch(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = new Error(`API ${res.status}: ${res.statusText}`);
    err.status = res.status;
    try { err.body = await res.json(); } catch {}
    throw err;
  }
  return res.json();
}

const api = {
  get: (path) => apiFetch(path),
  post: (path, body) => apiFetch(path, { method: "POST", body: JSON.stringify(body) }),
  put: (path, body) => apiFetch(path, { method: "PUT", body: JSON.stringify(body) }),
};

function useAPI(path, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(!!path);
  const [error, setError] = useState(null);
  const [stale, setStale] = useState(false);
  const lastGood = useRef(null);

  const refetch = useCallback(async () => {
    if (!path) { setLoading(false); return; } // null path = skip fetch (conditional)
    try {
      setLoading(!lastGood.current); // only show loading spinner on first load
      const result = await api.get(path);
      lastGood.current = result;
      setData(result);
      setStale(false);
      setError(null);
    } catch (e) {
      setError(e);
      if (lastGood.current) {
        setData(lastGood.current);
        setStale(true); // Layer 1 degradation: show last-known data with stale indicator
      }
    } finally {
      setLoading(false);
    }
  }, [path]);

  useEffect(() => { refetch(); }, [refetch, ...deps]);

  return { data, loading, error, stale, refetch };
}

// ─── STALE INDICATOR ───
function StaleIndicator({ stale }) {
  if (!stale) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "6px 12px", background: "var(--warn-bg)", borderRadius: 8, fontSize: 12, color: "#B8943D", marginBottom: 12 }}>
      ⚠️ Showing cached data — connection to backend lost
    </div>
  );
}

function LoadingSpinner({ label }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: 60, color: "var(--tx3)" }}>
      <div style={{ width: 32, height: 32, borderRadius: "50%", border: "3px solid var(--bd)", borderTopColor: "var(--pink)", animation: "pulse 1s infinite" }} />
      {label && <div style={{ marginTop: 12, fontSize: 13 }}>{label}</div>}
    </div>
  );
}

// ─── STYLES ───
const CSS = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,400&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --bg: #FFFBF5;
  --bg-card: #FFFFFF;
  --bg-side: #FAF5F0;
  --bg-input: #F5F0EA;
  --bg-hover: #F0EBE4;
  --tx: #2D2926;
  --tx2: #6B5E54;
  --tx3: #9B8E82;
  --tx4: #C4B8AC;
  --bd: #E8E0D6;
  --bd2: #D4C9BC;
  --pink: #E8A0BF;
  --pink-bg: rgba(232,160,191,0.12);
  --pink-bg2: rgba(232,160,191,0.06);
  --lav: #B8A9C9;
  --lav-bg: rgba(184,169,201,0.12);
  --teal: #8EC5C0;
  --teal-bg: rgba(142,197,192,0.10);
  --grn: #7CB98F;
  --grn-bg: rgba(124,185,143,0.12);
  --warn: #E8C07D;
  --warn-bg: rgba(232,192,125,0.12);
  --err: #D4756B;
  --err-bg: rgba(212,117,107,0.10);
  --info: #89B4D4;
  --info-bg: rgba(137,180,212,0.10);
  --r: 12px;
  --rs: 8px;
  --sh: 0 2px 8px rgba(45,41,38,0.06);
  --shc: 0 4px 16px rgba(45,41,38,0.05);
  --head: 'Fraunces', Georgia, serif;
  --body: 'DM Sans', -apple-system, sans-serif;
  --mono: 'JetBrains Mono', monospace;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); color:var(--tx); font-family:var(--body); -webkit-font-smoothing:antialiased; font-size:14px; line-height:1.5; }

@keyframes fadeUp { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }
@keyframes fadeIn { from{opacity:0} to{opacity:1} }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
@keyframes slideIn { from{opacity:0;transform:translateX(20px)} to{opacity:1;transform:translateX(0)} }
@keyframes confetti { 0%{transform:translateY(0) rotate(0);opacity:1} 100%{transform:translateY(-80px) rotate(720deg);opacity:0} }
@keyframes glow { 0%,100%{box-shadow:0 0 0 0 rgba(232,160,191,0)} 50%{box-shadow:0 0 0 8px rgba(232,160,191,0.15)} }
.fi { animation: fadeUp .4s ease-out; }
.si { animation: slideIn .3s ease-out; }

.card { background:var(--bg-card); border:1px solid var(--bd); border-radius:var(--r); padding:20px; box-shadow:var(--shc); transition:border-color .2s,box-shadow .2s; }
.card:hover { border-color:var(--bd2); }
.card-flat { background:var(--bg-card); border:1px solid var(--bd); border-radius:var(--r); padding:20px; }

input,textarea,select { background:var(--bg-input); border:1px solid var(--bd); border-radius:var(--rs); color:var(--tx); font-family:var(--body); font-size:14px; padding:10px 14px; outline:none; width:100%; transition:border-color .2s,box-shadow .2s; }
input:focus,select:focus,textarea:focus { border-color:var(--pink); box-shadow:0 0 0 3px rgba(232,160,191,0.15); }

button { font-family:var(--body); cursor:pointer; border:none; border-radius:var(--rs); font-size:14px; font-weight:500; padding:10px 18px; transition:all .15s ease; }
.btn-p { background:var(--pink); color:#fff; } .btn-p:hover { background:#D990B0; transform:translateY(-1px); box-shadow:0 4px 12px rgba(232,160,191,0.3); }
.btn-s { background:transparent; color:var(--tx2); border:1px solid var(--bd); } .btn-s:hover { border-color:var(--bd2); color:var(--tx); background:var(--bg-hover); }
.btn-g { background:var(--grn); color:#fff; } .btn-g:hover { background:#6DAA80; }
.btn-d { background:var(--err-bg); color:var(--err); } .btn-d:hover { background:rgba(212,117,107,0.18); }
.btn-sm { padding:6px 14px; font-size:13px; }

.badge { display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:600; letter-spacing:.3px; padding:4px 10px; border-radius:20px; }
.badge-pink { background:var(--pink-bg); color:var(--pink); }
.badge-lav { background:var(--lav-bg); color:var(--lav); }
.badge-grn { background:var(--grn-bg); color:var(--grn); }
.badge-warn { background:var(--warn-bg); color:#B8943D; }
.badge-err { background:var(--err-bg); color:var(--err); }
.badge-info { background:var(--info-bg); color:var(--info); }
.badge-teal { background:var(--teal-bg); color:#5DA09A; }

.toggle { width:42px; height:24px; border-radius:12px; cursor:pointer; position:relative; transition:background .2s; }
.toggle-on { background:var(--pink); } .toggle-off { background:var(--bd); }
.toggle-dot { width:18px; height:18px; border-radius:50%; background:#fff; position:absolute; top:3px; transition:left .2s; box-shadow:0 1px 3px rgba(0,0,0,0.15); }

::-webkit-scrollbar { width:6px; } ::-webkit-scrollbar-track { background:transparent; } ::-webkit-scrollbar-thumb { background:var(--bd); border-radius:3px; }
`;

// ─── NAV ICONS (inline SVG) ───
const Icons = {
  Sun: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>,
  Check: (p) => <svg {...p} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>,
  Tasks: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>,
  Calendar: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>,
  List: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>,
  Chat: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>,
  Trophy: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg>,
  Users: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  Gear: (p) => <svg {...p} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  Send: () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>,
  Right: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="9 18 15 12 9 6"/></svg>,
  Left: () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><polyline points="15 18 9 12 15 6"/></svg>,
};

const ELV = { high: { bg: "var(--grn)", bgf: "var(--grn-bg)", label: "High Energy" }, medium: { bg: "var(--warn)", bgf: "var(--warn-bg)", label: "Medium" }, low: { bg: "var(--tx3)", bgf: "var(--bg-input)", label: "Low Energy" }, crashed: { bg: "var(--err)", bgf: "var(--err-bg)", label: "Crashed" } };

const domainColors = { household: "badge-lav", health: "badge-teal", finance: "badge-warn", family: "badge-pink", work: "badge-info", admin: "badge-grn" };

// ─── SHELL ───
function Shell({ children, page, setPage, actor, setActor }) {
  // Fetch inbox count for Tasks badge
  const { data: inboxData } = useAPI("/api/tasks?filter=inbox");
  const inboxCount = inboxData?.tasks?.length ?? 0;

  // Custody indicator — poll from backend
  const { data: custodyData } = useAPI("/api/custody/today");
  const custodyText = custodyData?.text ?? "Loading custody…";

  // Health pulse — poll every 5 minutes
  const { data: healthData } = useAPI("/api/health");
  const [healthOk, setHealthOk] = useState(true);
  useEffect(() => {
    if (healthData) setHealthOk(healthData.status === "healthy");
    const iv = setInterval(async () => {
      try {
        const h = await api.get("/api/health");
        setHealthOk(h.status === "healthy");
      } catch { setHealthOk(false); }
    }, 5 * 60 * 1000); // 5 min
    return () => clearInterval(iv);
  }, [healthData]);

  const nav = [
    { id: "today", icon: Icons.Sun, label: "Today", count: null },
    { id: "tasks", icon: Icons.Tasks, label: "Tasks", count: inboxCount },
    { id: "schedule", icon: Icons.Calendar, label: "Schedule" },
    { id: "lists", icon: Icons.List, label: "Lists" },
    { id: "chat", icon: Icons.Chat, label: "Chat" },
    { id: "scoreboard", icon: Icons.Trophy, label: "Scoreboard" },
    { id: "people", icon: Icons.Users, label: "People" },
    { id: "settings", icon: Icons.Gear, label: "Settings" },
  ];
  const actorData = MEMBERS.find(m => m.id === actor);
  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <nav style={{ width: 220, minWidth: 220, background: "var(--bg-side)", borderRight: "1px solid var(--bd)", display: "flex", flexDirection: "column", padding: "20px 0" }}>
        {/* Logo */}
        <div style={{ padding: "0 20px 20px", borderBottom: "1px solid var(--bd)", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "linear-gradient(135deg, var(--pink), var(--lav))", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, fontWeight: 700, color: "#fff", boxShadow: "0 2px 8px rgba(232,160,191,0.3)" }}>P</div>
            <div>
              <div style={{ fontSize: 17, fontWeight: 700, fontFamily: "var(--head)", letterSpacing: "-.3px", color: "var(--tx)" }}>Poopsy</div>
              <div style={{ fontSize: 10, color: "var(--tx3)", fontWeight: 500, letterSpacing: ".5px" }}>IN-A-BOX · v5</div>
            </div>
          </div>
        </div>

        {/* Actor Switcher */}
        <div style={{ padding: "8px 12px 16px" }}>
          <div style={{ fontSize: 10, color: "var(--tx3)", fontWeight: 600, letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 8, paddingLeft: 8 }}>Viewing as</div>
          <div style={{ display: "flex", gap: 4 }}>
            {MEMBERS.map(m => (
              <button key={m.id} onClick={() => setActor(m.id)} style={{
                flex: 1, padding: "8px 4px", borderRadius: 8, border: "1px solid " + (actor === m.id ? "var(--pink)" : "var(--bd)"),
                background: actor === m.id ? "var(--pink-bg)" : "transparent", fontSize: 12, fontWeight: actor === m.id ? 600 : 400,
                color: actor === m.id ? "var(--pink)" : "var(--tx2)", display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
                transition: "all .15s"
              }}>
                <span style={{ fontSize: 16 }}>{m.emoji}</span>
                {m.name}
              </button>
            ))}
          </div>
        </div>

        {/* Nav Items */}
        <div style={{ flex: 1, padding: "0 10px", overflow: "auto" }}>
          {nav.map(n => {
            if (actor === "m-charlie" && ["tasks", "people", "settings"].includes(n.id)) return null;
            return (
              <button key={n.id} onClick={() => setPage(n.id)} style={{
                display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%",
                padding: "10px 14px", marginBottom: 2, borderRadius: 10,
                background: page === n.id ? "var(--pink-bg)" : "transparent",
                color: page === n.id ? "#C47A9E" : "var(--tx2)",
                border: "none", fontSize: 14, fontWeight: page === n.id ? 600 : 400,
                transition: "all .15s"
              }}>
                <span style={{ display: "flex", alignItems: "center", gap: 12 }}><n.icon />{n.label}</span>
                {n.count > 0 && <span style={{ background: "var(--pink)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "2px 7px", borderRadius: 10 }}>{n.count}</span>}
              </button>
            );
          })}
        </div>

        {/* Custody + Health */}
        <div style={{ padding: "0 12px 8px" }}>
          <div style={{ padding: "10px 14px", borderRadius: 10, background: "var(--lav-bg)", marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14 }}>👦</span>
            <span style={{ fontSize: 12, color: "var(--lav)", fontWeight: 500 }}>{custodyText}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 14px", borderRadius: 10, background: healthOk ? "var(--grn-bg)" : "var(--err-bg)" }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: healthOk ? "var(--grn)" : "var(--err)", animation: "pulse 2s infinite" }} />
            <span style={{ fontSize: 12, color: healthOk ? "var(--grn)" : "var(--err)", fontWeight: 500 }}>{healthOk ? "System Healthy" : "System Unhealthy"}</span>
          </div>
        </div>
      </nav>
      <main style={{ flex: 1, overflow: "auto", padding: "28px 36px", background: "var(--bg)" }}>{children}</main>
    </div>
  );
}

// ─── PROGRESS DOTS ───
// items: [{ state: 'endowed'|'done'|'skipped'|'current'|'urgent'|'pending', label }]
function ProgressDots({ items, activeIdx, onDotClick }) {
  const stateStyles = {
    endowed:  { bg: "var(--tx4)" },
    done:     { bg: "var(--grn)" },
    skipped:  { bg: "var(--warn)" },
    current:  { bg: "var(--pink)" },
    urgent:   { bg: "var(--err)" },
    pending:  { bg: "var(--bd)" },
  };
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center", justifyContent: "center", padding: "12px 0" }}>
      {items.map((item, i) => {
        const isCurrent = i === activeIdx;
        const s = stateStyles[isCurrent ? "current" : item.state] || stateStyles.pending;
        return (
          <div key={i} onClick={() => onDotClick?.(i)} title={item.label || ""} style={{
            width: isCurrent ? 12 : 8, height: isCurrent ? 12 : 8, borderRadius: "50%",
            background: isCurrent ? "var(--pink)" : s.bg,
            boxShadow: isCurrent ? "0 0 0 3px rgba(232,160,191,0.25)" : "none",
            transition: "all .3s cubic-bezier(.4,0,.2,1)", cursor: "pointer",
            opacity: item.state === "endowed" ? 0.5 : 1,
          }} />
        );
      })}
    </div>
  );
}

// ─── CAROUSEL ARROW BUTTON ───
function CarouselArrow({ direction, onClick, disabled }) {
  const [hov, setHov] = useState(false);
  return (
    <button onClick={onClick} disabled={disabled}
      onMouseEnter={() => setHov(true)} onMouseLeave={() => setHov(false)}
      style={{
        width: 40, height: 40, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center",
        background: disabled ? "var(--bg-input)" : hov ? "var(--pink-bg)" : "var(--bg-card)",
        border: "1px solid " + (disabled ? "var(--bd)" : hov ? "var(--pink)" : "var(--bd2)"),
        color: disabled ? "var(--tx4)" : hov ? "var(--pink)" : "var(--tx2)",
        cursor: disabled ? "default" : "pointer", padding: 0,
        boxShadow: disabled ? "none" : "var(--sh)",
        transition: "all .2s", opacity: disabled ? 0.5 : 1, flexShrink: 0,
      }}>
      {direction === "left" ? <Icons.Left /> : <Icons.Right />}
    </button>
  );
}

// ─── TODAY PAGE (James) — WIRED ───
function TodayJames() {
  // Fetch stream from backend — server builds it with whatNow() + endowed + calendar
  const { data, loading, stale, refetch } = useAPI("/api/today-stream?member=m-james");

  const [stream, setStream] = useState([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [reward, setReward] = useState(null);
  const [showSkip, setShowSkip] = useState(false);
  const [energy, setEnergy] = useState({ level: "medium", sleep: "okay", meds: false, meds_at: "", completions: 0, cap: 15, focus: false });
  const [streak, setStreak] = useState({ current: 0, best: 0, grace: 0 });

  // Hydrate state from server response
  useEffect(() => {
    if (!data) return;
    setStream(data.stream || []);
    setActiveIdx(data.activeIdx ?? 0);
    if (data.energy) setEnergy(data.energy);
    if (data.streak) setStreak(data.streak);
  }, [data]);

  const ev = ELV[energy.level] || ELV.medium;
  const doneCount = stream.filter(s => s.state === "done" && s.type !== "endowed").length;
  const currentItem = stream[activeIdx];
  const isViewingPast = currentItem?.state === "done" || currentItem?.state === "skipped";
  const isEndowed = currentItem?.type === "endowed";

  const navigate = (dir) => {
    setShowSkip(false);
    setActiveIdx(i => {
      const next = i + dir;
      return Math.max(0, Math.min(next, stream.length - 1));
    });
  };

  const jumpTo = (i) => {
    setShowSkip(false);
    setActiveIdx(Math.max(0, Math.min(i, stream.length - 1)));
  };

  const complete = async () => {
    if (!currentItem || !currentItem.id) return;
    try {
      // Server rolls the dice, updates streak, returns reward + next index
      const result = await api.post(`/api/tasks/${currentItem.task?.id || currentItem.id}/complete`, { member: "m-james" });
      const r = { tier: result.reward_tier || "simple", msg: result.reward_message || "Done ✓" };
      setReward(r);
      setShowSkip(false);
      // Mark current item done locally for instant feedback
      setStream(prev => prev.map((s, i) => i === activeIdx ? { ...s, state: "done" } : s));
      if (result.streak) setStreak(result.streak);
      setTimeout(() => {
        setReward(null);
        if (result.next_active_idx != null) {
          setActiveIdx(result.next_active_idx);
        } else {
          // Fallback: advance to next pending
          setActiveIdx(prev => {
            const nextPending = stream.findIndex((s, i) => i > prev && s.state === "pending");
            return nextPending >= 0 ? nextPending : Math.min(prev + 1, stream.length - 1);
          });
        }
      }, r.tier === "jackpot" ? 4000 : r.tier === "delight" ? 3000 : 2000);
    } catch (e) {
      console.error("Complete failed:", e);
      // Fallback: still mark done locally
      setStream(prev => prev.map((s, i) => i === activeIdx ? { ...s, state: "done" } : s));
      setReward({ tier: "simple", msg: "Done ✓ (offline)" });
      setTimeout(() => setReward(null), 2000);
    }
  };

  const skip = async () => {
    if (!currentItem) return;
    try {
      await api.post(`/api/tasks/${currentItem.task?.id || currentItem.id}/skip`, {});
    } catch {}
    setStream(prev => prev.map((s, i) => i === activeIdx ? { ...s, state: "skipped" } : s));
    setShowSkip(false);
    const nextPending = stream.findIndex((s, i) => i > activeIdx && s.state === "pending");
    setActiveIdx(nextPending >= 0 ? nextPending : Math.min(activeIdx + 1, stream.length - 1));
  };

  // Keyboard navigation
  useEffect(() => {
    const handler = (e) => {
      if (reward) return;
      if (e.key === "ArrowLeft") { e.preventDefault(); navigate(-1); }
      if (e.key === "ArrowRight") { e.preventDefault(); navigate(1); }
      if (e.key === "Enter" && !isViewingPast && !isEndowed) { e.preventDefault(); complete(); }
      if (e.key === "Escape" && !isViewingPast && !isEndowed) { e.preventDefault(); skip(); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  });

  // Build dot items for ProgressDots
  const dotItems = stream.map(s => ({
    state: s.state === "done" ? (s.type === "endowed" ? "endowed" : "done")
      : s.state === "skipped" ? "skipped"
      : s.urgent ? "urgent"
      : "pending",
    label: s.label,
  }));

  // Radar: next 3 calendar events from stream within ~2 hours
  const radar = stream.filter(s => s.type === "calendar" && s.state === "pending").slice(0, 3);

  // Today's full schedule from stream (calendar items only)
  const scheduleItems = stream.filter(s => s.type === "calendar");

  // Find next pending for Zeigarnik teaser
  const nextPendingItem = stream.find((s, i) => i > activeIdx && s.state === "pending" && s.type === "task");

  if (loading && !stream.length) return <LoadingSpinner label="Loading your day…" />;

  return (
    <div className="fi" style={{ maxWidth: 640, margin: "0 auto" }}>
      <StaleIndicator stale={stale} />
      {/* Energy Bar */}
      <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
        {[
          { l: "Meds", v: energy.meds ? `✓ ${energy.meds_at}` : "Not yet", c: energy.meds ? "var(--grn)" : "var(--warn)" },
          { l: "Sleep", v: energy.sleep, c: energy.sleep === "great" ? "var(--grn)" : "var(--warn)" },
          { l: "Energy", v: energy.level, c: ev.bg },
          { l: "Focus", v: energy.focus ? "ON" : "Off", c: energy.focus ? "var(--pink)" : "var(--tx3)" },
          { l: "Done", v: `${doneCount}/${energy.cap}`, c: "var(--tx)" },
        ].map((s, i) => (
          <div key={i} style={{ padding: "8px 14px", background: "var(--bg-card)", border: "1px solid var(--bd)", borderRadius: 10, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: s.c }}>{s.v}</span>
            <span style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".3px" }}>{s.l}</span>
          </div>
        ))}
      </div>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)", letterSpacing: "-.5px", color: "var(--tx)", lineHeight: 1.2 }}>
          {new Date().getHours() < 12 ? "Good morning" : "Good afternoon"}, James
        </h1>
        <p style={{ fontSize: 15, color: "var(--tx2)", marginTop: 6 }}>
          {doneCount} tasks done.{data?.summary ? ` ${data.summary}` : ""}
        </p>
        <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
          <span className="badge badge-pink">🔥 {streak.current}-day streak</span>
          <span className="badge" style={{ background: ev.bgf, color: ev.bg }}>⚡ {ev.label}</span>
          <span className="badge badge-lav">{doneCount}/{energy.cap} velocity</span>
        </div>
      </div>

      {/* Progress Dots with position indicator */}
      <div style={{ position: "relative", marginBottom: 4 }}>
        <ProgressDots items={dotItems} activeIdx={activeIdx} onDotClick={jumpTo} />
        <div style={{ textAlign: "center", fontSize: 11, color: "var(--tx4)", marginTop: 2 }}>
          {activeIdx + 1} / {stream.length}
          {isViewingPast && !isEndowed && <span style={{ marginLeft: 6, color: "var(--tx3)" }}>· reviewing</span>}
        </div>
      </div>

      {/* ═══ CAROUSEL WITH ARROWS ═══ */}
      {!reward && currentItem && (
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 8 }}>
          {/* Left Arrow */}
          <CarouselArrow direction="left" onClick={() => navigate(-1)} disabled={activeIdx === 0} />

          {/* Card */}
          <div style={{ flex: 1, minWidth: 0 }}>
            {/* ── Calendar Event Card ── */}
            {currentItem.type === "calendar" && (
              <div key={currentItem.id} className="card" style={{
                borderColor: isViewingPast ? "var(--grn)" : "var(--info)",
                borderWidth: 2, animation: "slideIn .25s ease-out", position: "relative",
                opacity: isViewingPast ? 0.75 : 1,
              }}>
                {isViewingPast && (
                  <div style={{ position: "absolute", top: 12, right: 14 }}>
                    <span className="badge badge-grn">Completed</span>
                  </div>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span className="badge badge-info">📅 Calendar</span>
                  <span style={{ fontSize: 12, fontFamily: "var(--mono)", color: "var(--tx3)" }}>{currentItem.time}–{currentItem.end}</span>
                </div>
                <h2 style={{ fontSize: 22, fontWeight: 600, fontFamily: "var(--head)", color: "var(--tx)", lineHeight: 1.3 }}>{currentItem.title}</h2>
                {!isViewingPast && (
                  <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
                    <button className="btn-g" onClick={complete} style={{ flex: 1, padding: 14, fontSize: 16, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                      <Icons.Check style={{ color: "#fff" }} /> Done
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ── Endowed Card (read-only) ── */}
            {currentItem.type === "endowed" && (
              <div key={currentItem.id} className="card" style={{ borderColor: "var(--tx4)", animation: "slideIn .25s ease-out", textAlign: "center", padding: 36, opacity: 0.7 }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>✓</div>
                <div style={{ fontSize: 18, fontWeight: 600, fontFamily: "var(--head)", color: "var(--tx2)" }}>{currentItem.title}</div>
                <div style={{ fontSize: 13, color: "var(--tx3)", marginTop: 6 }}>Endowed progress — this already counts.</div>
              </div>
            )}

            {/* ── Task Card ── */}
            {currentItem.type === "task" && (
              <div key={currentItem.id} className="card" style={{
                borderColor: isViewingPast
                  ? (currentItem.state === "skipped" ? "var(--warn)" : "var(--grn)")
                  : currentItem.urgent ? "var(--err)" : "var(--pink)",
                borderWidth: 2,
                animation: isViewingPast ? "slideIn .25s ease-out" : "slideIn .25s ease-out, glow 3s ease-in-out infinite",
                ...((!isViewingPast && !currentItem.urgent) ? { boxShadow: "0 4px 16px rgba(45,41,38,0.05)" } : {}),
                opacity: isViewingPast ? 0.75 : 1,
                position: "relative",
              }}>
                {/* Status badge for past items */}
                {isViewingPast && (
                  <div style={{ position: "absolute", top: 12, right: 14 }}>
                    <span className={`badge ${currentItem.state === "skipped" ? "badge-warn" : "badge-grn"}`}>
                      {currentItem.state === "skipped" ? "Skipped" : "Completed"}
                    </span>
                  </div>
                )}
                {/* Urgent/overdue banner */}
                {currentItem.urgent && !isViewingPast && (
                  <div style={{ background: "var(--err-bg)", borderRadius: 8, padding: "8px 12px", marginBottom: 14, display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--err)", fontWeight: 600 }}>
                    🔴 Overdue — momentum fading
                  </div>
                )}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
                  <span className={`badge ${domainColors[currentItem.task?.domain] || "badge-lav"}`}>{currentItem.task?.domain}</span>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 12, color: "var(--tx3)" }}>~{currentItem.task?.effort === "tiny" ? "2" : currentItem.task?.effort === "small" ? "5" : "15"} min</span>
                    <span style={{ fontSize: 12, color: "var(--tx3)" }}>·</span>
                    <span style={{ fontSize: 12, color: "var(--pink)", fontWeight: 600 }}>+{currentItem.task?.points} pts</span>
                  </div>
                </div>
                <h2 style={{ fontSize: 24, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 16, lineHeight: 1.3, color: "var(--tx)" }}>{currentItem.title}</h2>
                {currentItem.task?.micro && (
                  <div style={{ background: "var(--pink-bg2)", border: "1px solid var(--pink-bg)", borderRadius: 10, padding: 16, marginBottom: isViewingPast ? 0 : 20 }}>
                    <div style={{ fontSize: 10, fontWeight: 600, color: "var(--pink)", textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 8 }}>Micro-script</div>
                    <div style={{ fontSize: 15, lineHeight: 1.7, color: "var(--tx)" }}>
                      {currentItem.task.micro.split("→").map((s, i) => (
                        <span key={i}>{i > 0 && <span style={{ color: "var(--pink)", margin: "0 6px", fontWeight: 500 }}>→</span>}{s.trim()}</span>
                      ))}
                    </div>
                  </div>
                )}
                {/* Action buttons — only for pending/active items */}
                {!isViewingPast && (
                  <>
                    <div style={{ display: "flex", gap: 10, marginBottom: showSkip ? 12 : 0 }}>
                      <button className="btn-g" onClick={complete} style={{ flex: 1, padding: 14, fontSize: 16, fontWeight: 600, display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                        <Icons.Check style={{ color: "#fff" }} /> Done
                      </button>
                      <button className="btn-s" onClick={() => setShowSkip(!showSkip)} style={{ padding: "14px 20px" }}>Skip →</button>
                    </div>
                    {showSkip && (
                      <div style={{ display: "flex", gap: 8 }}>
                        <button className="btn-d btn-sm" onClick={skip} style={{ minWidth: 80 }}>Skip now</button>
                        <input placeholder="Or reschedule… (tomorrow, Monday)" style={{ flex: 1 }} />
                        <button className="btn-p btn-sm" style={{ minWidth: 70 }}>Set</button>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          {/* Right Arrow */}
          <CarouselArrow direction="right" onClick={() => navigate(1)} disabled={activeIdx === stream.length - 1} />
        </div>
      )}

      {/* Reward Animation */}
      {reward && (
        <div className="card" style={{
          borderColor: reward.tier === "jackpot" ? "var(--pink)" : reward.tier === "delight" ? "var(--lav)" : "var(--grn)",
          borderWidth: 2, textAlign: "center", padding: reward.tier === "jackpot" ? 56 : 44,
          animation: "fadeUp .3s ease-out",
          background: reward.tier === "jackpot" ? "linear-gradient(135deg, var(--pink-bg), var(--lav-bg))" : "var(--bg-card)"
        }}>
          {reward.tier === "jackpot" && (
            <div style={{ position: "relative", height: 40, marginBottom: 8 }}>
              {[...Array(12)].map((_, i) => (
                <div key={i} style={{ position: "absolute", left: `${20 + Math.random() * 60}%`, top: 20, width: 8, height: 8, borderRadius: "50%", background: ["var(--pink)", "var(--lav)", "var(--teal)", "var(--warn)"][i % 4], animation: `confetti ${1 + Math.random()}s ease-out forwards`, animationDelay: `${i * 0.05}s` }} />
              ))}
            </div>
          )}
          <div style={{ fontSize: reward.tier === "jackpot" ? 48 : 36, marginBottom: 12 }}>
            {reward.tier === "jackpot" ? "🎰" : reward.tier === "delight" ? "🎉" : reward.tier === "warm" ? "✨" : "✓"}
          </div>
          <div style={{ fontSize: reward.tier === "jackpot" ? 20 : 18, fontWeight: 600, fontFamily: "var(--head)", lineHeight: 1.4, color: "var(--tx)" }}>{reward.msg}</div>
          {reward.tier !== "simple" && <div style={{ fontSize: 12, color: "var(--tx3)", marginTop: 8 }}>{reward.tier.toUpperCase()} REWARD</div>}
        </div>
      )}

      {/* Zeigarnik Teaser */}
      {nextPendingItem && !reward && !isViewingPast && (
        <div style={{ textAlign: "center", marginTop: 20, padding: 16, borderTop: "1px dashed var(--bd)", color: "var(--tx2)", fontSize: 14 }}>
          One more? — <span style={{ fontWeight: 500, color: "var(--tx)" }}>"{nextPendingItem.title}"</span> <span style={{ color: "var(--tx3)" }}>({nextPendingItem.task?.effort})</span>
        </div>
      )}

      {/* Keyboard hint */}
      <div style={{ textAlign: "center", marginTop: 12, fontSize: 11, color: "var(--tx4)" }}>
        ← → browse · click dots to jump · Enter = done · Esc = skip
      </div>

      {/* Radar */}
      {radar.length > 0 && (
        <div style={{ marginTop: 28 }}>
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 10 }}>🎯 Radar — next 2 hours</h3>
          <div style={{ display: "flex", gap: 12 }}>
            {radar.map((s, i) => (
              <div key={i} style={{ flex: 1, padding: "10px 14px", background: "var(--bg-card)", border: "1px solid var(--bd)", borderRadius: 10 }}>
                <div style={{ fontSize: 12, fontFamily: "var(--mono)", color: "var(--tx3)", marginBottom: 2 }}>{s.time}</div>
                <div style={{ fontSize: 13, color: "var(--tx2)" }}>{s.title}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Today Schedule */}
      <div style={{ marginTop: 28 }}>
        <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 10 }}>Today's Schedule</h3>
        {scheduleItems.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 14, padding: "8px 0", borderBottom: "1px solid var(--bg-input)" }}>
            <span style={{ color: "var(--tx3)", fontFamily: "var(--mono)", fontSize: 12, minWidth: 48 }}>{s.time}</span>
            <span style={{ fontSize: 14, color: "var(--tx2)" }}>{s.title}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── TODAY PAGE (Laura) — WIRED ───
function TodayLaura() {
  const { data: decData, stale: decStale, refetch: decRefetch } = useAPI("/api/decisions?member=m-laura");
  const { data: taskData } = useAPI("/api/tasks?assignee=m-laura&status=ready");
  const { data: statusData } = useAPI("/api/household-status");

  const [decisions, setDecisions] = useState([]);
  useEffect(() => { if (decData?.decisions) setDecisions(decData.decisions); }, [decData]);

  const tasks = taskData?.tasks ?? [];
  const statusItems = statusData?.items ?? [];

  const handleDecision = async (id, decision) => {
    try {
      await api.post(`/api/approvals/${id}/decide`, { decision });
      setDecisions(p => p.filter(x => x.id !== id));
    } catch (e) {
      console.error("Decision failed:", e);
      if (decision === "approved") setDecisions(p => p.filter(x => x.id !== id)); // optimistic
    }
  };

  return (
    <div className="fi" style={{ maxWidth: 640, margin: "0 auto" }}>
      <StaleIndicator stale={decStale} />
      <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)", letterSpacing: "-.5px", marginBottom: 6 }}>Good afternoon, Laura</h1>
      <p style={{ fontSize: 15, color: "var(--tx2)", marginBottom: 28 }}>
        {decisions.length} decision{decisions.length !== 1 ? "s" : ""} need{decisions.length === 1 ? "s" : ""} you.
      </p>

      {/* Decision Queue */}
      {decisions.length > 0 && (
        <div className="card" style={{ borderColor: "var(--lav)", borderWidth: 2, marginBottom: 20 }}>
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--lav)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 14 }}>Decisions Needed</h3>
          {decisions.map((d, i) => (
            <div key={d.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 0", borderTop: i ? "1px solid var(--bd)" : "none" }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 500, color: "var(--tx)" }}>{d.title}</div>
                <div style={{ fontSize: 13, color: "var(--tx3)", marginTop: 2 }}>{d.detail}</div>
              </div>
              <div style={{ display: "flex", gap: 6, flexShrink: 0, marginLeft: 16 }}>
                <button className="btn-g btn-sm" onClick={() => handleDecision(d.id, "approved")}>Approve</button>
                <button className="btn-d btn-sm" onClick={() => handleDecision(d.id, "rejected")}>Decline</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tasks */}
      <div className="card-flat" style={{ marginBottom: 20 }}>
        <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 14 }}>
          Your Tasks ({tasks.length})
        </h3>
        {tasks.map((t, i) => (
          <div key={t.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderTop: i ? "1px solid var(--bd)" : "none" }}>
            <span style={{ fontSize: 15, color: "var(--tx)" }}>{t.title}</span>
            <span className={`badge ${domainColors[t.domain]}`}>{t.domain}</span>
          </div>
        ))}
      </div>

      {/* Status */}
      <div className="card-flat">
        <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 14 }}>Household Status</h3>
        {statusItems.map((x, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", fontSize: 14, color: x.color || "var(--tx2)" }}>
            <span>{x.icon}</span>{x.text}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── TODAY PAGE (Charlie) — WIRED ───
function TodayCharlie() {
  const { data, loading, refetch } = useAPI("/api/chores?member=m-charlie");
  const { data: sbData } = useAPI("/api/scoreboard?member=m-charlie");

  const [chores, setChores] = useState([]);
  useEffect(() => { if (data?.chores) setChores(data.chores); }, [data]);

  const weekStars = sbData?.weekStars ?? 0;
  const charlieStreak = sbData?.streak?.current ?? 0;
  const milestone = sbData?.nextMilestone ?? "Pick Friday movie";
  const milestoneTarget = sbData?.nextMilestoneTarget ?? 25;

  const toggleChore = async (id) => {
    // Optimistic update
    setChores(p => p.map(x => x.id === id ? { ...x, done: !x.done } : x));
    try {
      await api.post(`/api/chores/${id}/toggle`, {});
    } catch {
      // Revert on failure
      setChores(p => p.map(x => x.id === id ? { ...x, done: !x.done } : x));
    }
  };

  if (loading && !chores.length) return <LoadingSpinner label="Loading chores…" />;

  return (
    <div className="fi" style={{ maxWidth: 500, margin: "0 auto", textAlign: "center" }}>
      <div style={{ fontSize: 48, marginBottom: 8 }}>🌟</div>
      <h1 style={{ fontSize: 32, fontWeight: 700, fontFamily: "var(--head)", color: "var(--tx)" }}>Hi Charlie!</h1>
      <div style={{ fontSize: 18, color: "var(--tx2)", marginTop: 8, marginBottom: 4 }}>You have <b style={{ color: "var(--pink)" }}>{weekStars} stars</b> this week!</div>
      <div style={{ fontSize: 14, color: "var(--tx3)", marginBottom: 28 }}>🏆 {milestoneTarget} stars = {milestone}!</div>

      <div style={{ display: "grid", gap: 10 }}>
        {chores.map(c => (
          <button key={c.id} onClick={() => toggleChore(c.id)} style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "16px 20px", borderRadius: 14,
            background: c.done ? "var(--grn-bg)" : "var(--bg-card)",
            border: "2px solid " + (c.done ? "var(--grn)" : "var(--bd)"),
            cursor: "pointer", transition: "all .2s", width: "100%", textAlign: "left"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              {c.done ? <span style={{ color: "var(--grn)", fontSize: 20 }}>✓</span> : <div style={{ width: 22, height: 22, borderRadius: 6, border: "2px solid var(--bd)" }} />}
              <span style={{ fontSize: 17, fontWeight: 500, textDecoration: c.done ? "line-through" : "none", color: c.done ? "var(--tx3)" : "var(--tx)" }}>{c.title}</span>
            </div>
            <span style={{ fontSize: 15, color: "var(--warn)" }}>+{c.stars} ⭐</span>
          </button>
        ))}
      </div>

      <div style={{ marginTop: 28, padding: 20, background: "var(--pink-bg2)", borderRadius: 14 }}>
        <div style={{ fontSize: 14, color: "var(--tx2)" }}>🔥 {charlieStreak}-day streak! Keep going!</div>
      </div>
    </div>
  );
}

// ─── TASKS PAGE — WIRED ───
function TasksPage() {
  const [filter, setFilter] = useState("all");
  const filters = ["all", "mine", "inbox", "overdue", "waiting", "done"];
  const { data, loading, stale } = useAPI(`/api/tasks?filter=${filter}`, [filter]);
  const tasks = data?.tasks ?? [];

  return (
    <div className="fi">
      <StaleIndicator stale={stale} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)" }}>Tasks</h1>
        <button className="btn-p">+ Capture</button>
      </div>
      <div style={{ display: "flex", gap: 4, marginBottom: 20, flexWrap: "wrap" }}>
        {filters.map(f => (
          <button key={f} onClick={() => setFilter(f)} style={{
            padding: "7px 16px", borderRadius: 20, fontSize: 13, fontWeight: 500, textTransform: "capitalize",
            background: filter === f ? "var(--pink)" : "var(--bg-card)", color: filter === f ? "#fff" : "var(--tx2)",
            border: "1px solid " + (filter === f ? "var(--pink)" : "var(--bd)"), cursor: "pointer", transition: "all .15s"
          }}>{f}</button>
        ))}
      </div>
      {loading && !tasks.length ? <LoadingSpinner /> : (
        <div className="card-flat" style={{ padding: 0, overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--bd)" }}>
                {["Score", "Status", "Task", "Due", "Domain", "Owner", "Effort"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "12px 14px", fontSize: 11, fontWeight: 600, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".3px" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tasks.map(t => (
                <tr key={t.id} style={{ borderBottom: "1px solid var(--bd)", cursor: "pointer", transition: "background .15s" }}
                  onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
                  onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                  <td style={{ padding: "12px 14px", fontFamily: "var(--mono)", fontSize: 12, color: "var(--tx3)" }}>{t.score}</td>
                  <td style={{ padding: "12px 14px" }}>
                    <span className={`badge ${t.status === "done" ? "badge-grn" : t.status === "inbox" ? "badge-warn" : t.status === "waiting" ? "badge-lav" : "badge-info"}`}>{t.status}</span>
                  </td>
                  <td style={{ padding: "12px 14px" }}>
                    <div style={{ fontWeight: 500, color: "var(--tx)" }}>{t.title}</div>
                    <div style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "var(--mono)" }}>{t.id}</div>
                  </td>
                  <td style={{ padding: "12px 14px", fontSize: 13, color: "var(--tx2)" }}>{t.due || "—"}</td>
                  <td style={{ padding: "12px 14px" }}><span className={`badge ${domainColors[t.domain]}`}>{t.domain}</span></td>
                  <td style={{ padding: "12px 14px", fontSize: 13, color: "var(--tx2)" }}>{MEMBERS.find(m => m.id === t.assignee)?.name || "—"}</td>
                  <td style={{ padding: "12px 14px", fontSize: 13, color: "var(--tx3)" }}>{t.effort}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── SCHEDULE PAGE — WIRED ───
function SchedulePage() {
  const today = new Date().toISOString().split("T")[0];
  const { data, loading, stale } = useAPI(`/api/schedule?date=${today}`);
  const events = data?.events ?? [];
  const custodyLabel = data?.custody ?? "";

  const hours = Array.from({ length: 15 }, (_, i) => i + 7);
  const now = new Date().getHours() + new Date().getMinutes() / 60;
  const memberCols = [
    { id: "m-james", name: "James", color: "var(--pink)" },
    { id: "m-laura", name: "Laura", color: "var(--lav)" },
    { id: "all", name: "Family", color: "var(--teal)" },
  ];

  return (
    <div className="fi">
      <StaleIndicator stale={stale} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)" }}>Schedule</h1>
          <p style={{ fontSize: 14, color: "var(--tx2)", marginTop: 4 }}>{new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })}</p>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {["Day", "Week", "Month"].map(v => (
            <button key={v} className={v === "Day" ? "btn-p btn-sm" : "btn-s btn-sm"}>{v}</button>
          ))}
        </div>
      </div>

      {/* Custody Ribbon */}
      {custodyLabel && (
        <div style={{ padding: "10px 16px", borderRadius: 10, background: "var(--lav-bg)", marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: 13, color: "var(--lav)", fontWeight: 500 }}>{custodyLabel}</span>
          <span className="badge badge-lav">Schedule A</span>
        </div>
      )}

      {/* Timeline */}
      {loading && !events.length ? <LoadingSpinner /> : (
        <div className="card-flat" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "60px repeat(3, 1fr)", borderBottom: "2px solid var(--bd)" }}>
            <div style={{ padding: "12px 8px", fontSize: 11, fontWeight: 600, color: "var(--tx3)", textAlign: "center" }}>TIME</div>
            {memberCols.map(m => (
              <div key={m.id} style={{ padding: "12px 14px", fontSize: 12, fontWeight: 600, color: m.color, textAlign: "center", textTransform: "uppercase", letterSpacing: ".3px" }}>{m.name}</div>
            ))}
          </div>
          <div style={{ position: "relative" }}>
            {hours.map(h => (
              <div key={h} style={{ display: "grid", gridTemplateColumns: "60px repeat(3, 1fr)", minHeight: 48, borderBottom: "1px solid var(--bg-input)" }}>
                <div style={{ padding: "4px 8px", fontSize: 11, fontFamily: "var(--mono)", color: "var(--tx4)", textAlign: "center" }}>
                  {h > 12 ? h - 12 : h}{h >= 12 ? "pm" : "am"}
                </div>
                {memberCols.map(mc => {
                  const ev = events.find(s => parseInt(s.time?.split(":")[0]) === h && (s.member === mc.id || s.member === "all"));
                  if (!ev) return <div key={mc.id} />;
                  const durH = ev.end ? (parseInt(ev.end.split(":")[0]) + parseInt(ev.end.split(":")[1])/60) - (parseInt(ev.time.split(":")[0]) + parseInt(ev.time.split(":")[1])/60) : 0.5;
                  return (
                    <div key={mc.id} style={{ padding: "4px 6px" }}>
                      <div style={{
                        padding: "8px 12px", borderRadius: 8, fontSize: 13, fontWeight: 500,
                        background: mc.color + "18", borderLeft: `3px solid ${mc.color}`, color: "var(--tx)",
                        minHeight: Math.max(durH * 48, 36)
                      }}>
                        <div>{ev.title}</div>
                        <div style={{ fontSize: 11, color: "var(--tx3)", marginTop: 2 }}>{ev.time}–{ev.end}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
            {/* NOW line */}
            <div style={{ position: "absolute", top: (now - 7) * 48, left: 0, right: 0, height: 2, background: "var(--err)", zIndex: 5 }}>
              <div style={{ position: "absolute", left: 4, top: -8, fontSize: 10, fontWeight: 700, color: "var(--err)", background: "var(--bg)", padding: "1px 6px", borderRadius: 4 }}>NOW</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── LISTS PAGE — WIRED ───
function ListsPage() {
  const [tab, setTab] = useState("grocery");
  const { data, loading, refetch } = useAPI(`/api/lists/${tab}`, [tab]);
  const [items, setItems] = useState([]);
  const [newItem, setNewItem] = useState("");

  useEffect(() => { if (data?.items) setItems(data.items); }, [data]);

  const tabs = data?.available_lists ?? [
    { id: "grocery", label: "🛒 Grocery" },
    { id: "honey-do", label: "🔨 Honey-Do" },
    { id: "packing", label: "👶 Baby Packing" },
  ];

  const addItem = async () => {
    if (!newItem.trim()) return;
    const tempId = `new-${Date.now()}`;
    const optimistic = { id: tempId, text: newItem, done: false };
    setItems(p => [optimistic, ...p]);
    setNewItem("");
    try {
      const result = await api.post(`/api/lists/${tab}/items`, { text: newItem });
      setItems(p => p.map(x => x.id === tempId ? { ...x, id: result.id || tempId } : x));
    } catch {
      setItems(p => p.filter(x => x.id !== tempId)); // revert
    }
  };

  const toggleItem = async (id) => {
    setItems(p => p.map(x => x.id === id ? { ...x, done: !x.done } : x));
    try {
      await api.post(`/api/lists/${tab}/items/${id}/toggle`, {});
    } catch {
      setItems(p => p.map(x => x.id === id ? { ...x, done: !x.done } : x)); // revert
    }
  };

  const unchecked = items.filter(x => !x.done).length;

  return (
    <div className="fi" style={{ maxWidth: 600, margin: "0 auto" }}>
      <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 24 }}>Lists</h1>
      <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding: "8px 16px", borderRadius: 20, fontSize: 13, fontWeight: 500,
            background: tab === t.id ? "var(--pink)" : "var(--bg-card)", color: tab === t.id ? "#fff" : "var(--tx2)",
            border: "1px solid " + (tab === t.id ? "var(--pink)" : "var(--bd)"), cursor: "pointer"
          }}>{t.label} ({tab === t.id ? unchecked : ""})</button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 20 }}>
        <input value={newItem} onChange={e => setNewItem(e.target.value)} onKeyDown={e => e.key === "Enter" && addItem()} placeholder="Quick add…" />
        <button className="btn-p" onClick={addItem} style={{ minWidth: 70 }}>Add</button>
      </div>
      <div className="card-flat" style={{ padding: 0 }}>
        {items.map((item, i) => (
          <div key={item.id} onClick={() => toggleItem(item.id)} style={{
            display: "flex", alignItems: "center", gap: 14, padding: "14px 20px", borderBottom: i < items.length - 1 ? "1px solid var(--bd)" : "none",
            cursor: "pointer", transition: "background .15s"
          }}
          onMouseEnter={e => e.currentTarget.style.background = "var(--bg-hover)"}
          onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
            <div style={{ width: 22, height: 22, borderRadius: 6, border: "2px solid " + (item.done ? "var(--grn)" : "var(--bd)"), background: item.done ? "var(--grn)" : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              {item.done && <Icons.Check style={{ color: "#fff", width: 14, height: 14 }} />}
            </div>
            <span style={{ fontSize: 15, textDecoration: item.done ? "line-through" : "none", color: item.done ? "var(--tx3)" : "var(--tx)" }}>{item.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── CHAT PAGE — WIRED (SSE streaming) ───
function ChatPage() {
  const [sessionId] = useState(() => `sess-${Date.now()}`);
  const { data: histData } = useAPI(`/api/chat/history?session_id=${sessionId}`);
  const [msgs, setMsgs] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const ref = useRef(null);
  const chips = ["today", "now", "grocery list", "schedule", "status", "diff", "help"];

  useEffect(() => { if (histData?.messages) setMsgs(histData.messages); }, [histData]);
  useEffect(() => { ref.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const send = async (text) => {
    const t = text || input;
    if (!t.trim() || streaming) return;
    const userMsg = { role: "user", content: t, ts: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) };
    setMsgs(p => [...p, userMsg]);
    setInput("");
    setStreaming(true);

    try {
      // Send message
      await api.post("/api/chat/send", { message: t, session_id: sessionId });

      // Stream response via SSE
      const asstMsg = { role: "assistant", content: "", ts: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) };
      setMsgs(p => [...p, asstMsg]);

      const evtSource = new EventSource(`${BASE}/api/chat/stream?session_id=${sessionId}`);
      evtSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.done) {
          evtSource.close();
          setStreaming(false);
          return;
        }
        if (data.token) {
          setMsgs(p => {
            const updated = [...p];
            const last = updated[updated.length - 1];
            if (last?.role === "assistant") {
              updated[updated.length - 1] = { ...last, content: last.content + data.token };
            }
            return updated;
          });
        }
        if (data.content) {
          // Full message (non-streaming fallback)
          setMsgs(p => {
            const updated = [...p];
            updated[updated.length - 1] = { ...updated[updated.length - 1], content: data.content };
            return updated;
          });
          evtSource.close();
          setStreaming(false);
        }
      };
      evtSource.onerror = () => {
        evtSource.close();
        setStreaming(false);
      };
    } catch (e) {
      console.error("Chat send failed:", e);
      setMsgs(p => [...p, { role: "assistant", content: "⚠️ Connection lost. Try again.", ts: new Date().toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" }) }]);
      setStreaming(false);
    }
  };

  return (
    <div className="fi" style={{ display: "flex", flexDirection: "column", height: "calc(100vh - 56px)", maxWidth: 700, margin: "0 auto" }}>
      <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 16, flexShrink: 0 }}>Chat with Poopsy</h1>
      <div style={{ flex: 1, overflow: "auto", marginBottom: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        {msgs.map((m, i) => (
          <div key={i} style={{ display: "flex", justifyContent: m.role === "user" ? "flex-end" : "flex-start" }}>
            <div style={{
              maxWidth: "80%", padding: "12px 16px", borderRadius: 16, fontSize: 15, lineHeight: 1.5,
              background: m.role === "user" ? "var(--pink)" : "var(--bg-card)",
              color: m.role === "user" ? "#fff" : "var(--tx)",
              border: m.role === "user" ? "none" : "1px solid var(--bd)",
              borderBottomRightRadius: m.role === "user" ? 4 : 16,
              borderBottomLeftRadius: m.role === "user" ? 16 : 4,
              boxShadow: m.role === "user" ? "0 2px 8px rgba(232,160,191,0.3)" : "var(--sh)",
            }}>
              {m.content}
              {streaming && i === msgs.length - 1 && m.role === "assistant" && <span style={{ animation: "pulse 1s infinite" }}>▌</span>}
              <div style={{ fontSize: 10, marginTop: 6, opacity: .6 }}>{m.ts}</div>
            </div>
          </div>
        ))}
        <div ref={ref} />
      </div>
      {/* Quick Chips */}
      <div style={{ display: "flex", gap: 6, marginBottom: 10, flexWrap: "wrap", flexShrink: 0 }}>
        {chips.map(c => (
          <button key={c} onClick={() => send(c)} className="btn-s" style={{ padding: "5px 14px", fontSize: 12, borderRadius: 20 }} disabled={streaming}>{c}</button>
        ))}
      </div>
      <div style={{ display: "flex", gap: 10, flexShrink: 0, paddingBottom: 8 }}>
        <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && send()}
          placeholder='Talk to Poopsy… (try: "grocery: milk, eggs")' style={{ fontSize: 15, padding: "14px 18px", borderRadius: 28, flex: 1 }} disabled={streaming} />
        <button onClick={() => send()} className="btn-p" style={{ width: 48, height: 48, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", padding: 0 }} disabled={streaming}>
          <Icons.Send />
        </button>
      </div>
    </div>
  );
}

// ─── SCOREBOARD PAGE — WIRED (60-second polling) ───
function ScoreboardPage({ actor }) {
  const { data, loading, stale, refetch } = useAPI("/api/scoreboard");

  // 60-second auto-refresh
  useEffect(() => {
    const iv = setInterval(refetch, 60_000);
    return () => clearInterval(iv);
  }, [refetch]);

  const cards = data?.cards ?? [];
  const layers = data?.layers ?? [];
  const overallScore = data?.overallScore ?? 0;
  const rewardHistory = data?.rewardHistory ?? [];
  const domainWins = data?.domainWins ?? [];
  const captain = data?.captain ?? { walked: false, fed: false, nextWalk: "" };
  const familyTotal = data?.familyTotal ?? { points: 0, record: false };
  const chores = data?.chores ?? [];

  const tierColors = { simple: "var(--tx3)", warm: "var(--teal)", delight: "var(--lav)", jackpot: "var(--pink)" };

  if (loading && !cards.length) return <LoadingSpinner label="Loading scoreboard…" />;

  return (
    <div className="fi">
      <StaleIndicator stale={stale} />
      <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 24 }}>Scoreboard</h1>

      {/* Family Cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 24 }}>
        {cards.map(m => (
          <div key={m.id} className="card" style={{ textAlign: "center", padding: 24 }}>
            <div style={{ fontSize: 36, marginBottom: 6 }}>{m.emoji}</div>
            <div style={{ fontSize: 20, fontWeight: 700, fontFamily: "var(--head)" }}>{m.name}</div>
            <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 6, margin: "12px 0" }}>
              🔥 <span style={{ fontSize: 22, fontWeight: 700, color: "var(--pink)" }}>{m.streak?.current ?? 0}</span>
              <span style={{ fontSize: 13, color: "var(--tx3)" }}>day streak</span>
            </div>
            {/* Grace dots */}
            <div style={{ display: "flex", gap: 3, justifyContent: "center", marginBottom: 12 }}>
              {[...Array(Math.min(m.streak?.current ?? 0, 5))].map((_, i) => <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--grn)" }} />)}
              {[...Array(m.streak?.grace ?? 0)].map((_, i) => <div key={`g${i}`} style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--bd)", opacity: .5 }} />)}
            </div>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--grn)" }}>{m.star ? `${m.wk} ⭐` : m.done}</div>
            <div style={{ fontSize: 13, color: "var(--tx3)" }}>{m.star ? "stars this week" : "done today"}</div>
            <div style={{ marginTop: 10, fontSize: 12, color: "var(--tx4)" }}>Week: {m.wk} {m.star ? "⭐" : "pts"} · Best: {m.streak?.best ?? 0} days</div>
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
        {/* Neuroprosthetic Layers */}
        <div className="card-flat">
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 14 }}>Neuroprosthetic Layers</h3>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
            <div style={{ textAlign: "center" }}>
              <div style={{ fontSize: 36, fontWeight: 700, color: "var(--pink)", fontFamily: "var(--head)" }}>{overallScore}</div>
              <div style={{ fontSize: 12, color: "var(--tx3)" }}>/ 100 overall</div>
            </div>
          </div>
          {layers.map(l => (
            <div key={l.name} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <span style={{ fontSize: 12, color: "var(--tx2)", minWidth: 70 }}>{l.name}</span>
              <div style={{ flex: 1, height: 6, background: "var(--bg-input)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${l.score}%`, background: l.score > 40 ? "var(--grn)" : l.score > 20 ? "var(--warn)" : "var(--err)", borderRadius: 3, transition: "width .5s" }} />
              </div>
              <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--tx3)", minWidth: 24 }}>{l.score}</span>
            </div>
          ))}
        </div>

        {/* Reward History */}
        <div className="card-flat">
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 14 }}>Recent Rewards</h3>
          {rewardHistory.map((r, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderTop: i ? "1px solid var(--bd)" : "none" }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: tierColors[r.tier] || "var(--tx3)", flexShrink: 0 }} />
              <span style={{ fontSize: 13, color: "var(--tx2)", flex: 1 }}>{r.msg}</span>
              <span style={{ fontSize: 11, color: "var(--tx4)", fontFamily: "var(--mono)" }}>{r.ts}</span>
            </div>
          ))}
          <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--pink-bg2)", borderRadius: 8, fontSize: 13, color: "var(--pink)" }}>
            ✨ Next jackpot is statistically due soon…
          </div>
        </div>
      </div>

      {/* Domain Wins + Captain + Family Total */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16, marginBottom: 16 }}>
        <div className="card-flat">
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 12 }}>Weekly Wins by Domain</h3>
          {domainWins.map((w, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", fontSize: 13 }}>
              <span style={{ color: "var(--tx2)" }}>{w.d}</span>
              <span style={{ color: w.warn ? "var(--warn)" : "var(--tx)" }}>{w.n} {w.trend} {w.warn || ""}</span>
            </div>
          ))}
        </div>
        <div className="card-flat" style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span style={{ fontSize: 36 }}>🐕</span>
          <div>
            <div style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)" }}>Captain</div>
            <div style={{ fontSize: 13, color: "var(--tx2)" }}>{captain.walked ? "Walked ✓" : "Not walked"} · {captain.fed ? "Fed ✓" : "Not fed"}</div>
            <div style={{ fontSize: 12, color: "var(--tx3)" }}>Next walk: {captain.nextWalk}</div>
          </div>
        </div>
        <div className="card-flat" style={{ display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ textAlign: "center" }}>
            <div style={{ fontSize: 12, color: "var(--tx3)", marginBottom: 4 }}>Family Total This Week</div>
            <span style={{ fontSize: 32, fontWeight: 700, color: "var(--grn)", fontFamily: "var(--head)" }}>{familyTotal.points?.toLocaleString()}</span>
            <span style={{ fontSize: 14, color: "var(--tx3)", marginLeft: 6 }}>pts</span>
            {familyTotal.record && <div style={{ fontSize: 12, color: "var(--pink)", marginTop: 4 }}>🏆 New weekly record!</div>}
          </div>
        </div>
      </div>

      {/* Charlie Chores */}
      <div className="card-flat">
        <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 12 }}>Charlie's Chores Today</h3>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
          {chores.map(c => (
            <div key={c.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10,
              background: c.done ? "var(--grn-bg)" : "var(--bg-input)", border: "1px solid " + (c.done ? "var(--grn)" : "var(--bd)")
            }}>
              <span style={{ fontSize: 13, textDecoration: c.done ? "line-through" : "none", color: c.done ? "var(--tx3)" : "var(--tx)" }}>{c.title}</span>
              <span style={{ fontSize: 12, color: "var(--warn)" }}>+{c.stars}⭐</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── PEOPLE PAGE — WIRED ───
function PeoplePage() {
  const [tab, setTab] = useState("contacts");
  const { data: contactsData } = useAPI("/api/people/contacts");
  const { data: commsData } = useAPI("/api/people/comms?limit=20");
  const { data: obsData } = useAPI("/api/people/observations");
  const { data: tiersData } = useAPI("/api/people/autonomy-tiers");

  const contacts = contactsData?.contacts ?? [];
  const comms = commsData?.comms ?? [];
  const observations = obsData?.observations ?? [];
  const tiers = tiersData?.tiers ?? [];

  return (
    <div className="fi">
      <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 24 }}>People</h1>
      <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
        {["contacts", "comms", "observations", "autonomy"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: "8px 16px", borderRadius: 20, fontSize: 13, fontWeight: 500, textTransform: "capitalize",
            background: tab === t ? "var(--pink)" : "var(--bg-card)", color: tab === t ? "#fff" : "var(--tx2)",
            border: "1px solid " + (tab === t ? "var(--pink)" : "var(--bd)"), cursor: "pointer"
          }}>{t}</button>
        ))}
      </div>

      {tab === "contacts" && (
        <div>
          {/* Household */}
          <div className="card-flat" style={{ marginBottom: 16 }}>
            <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 12 }}>Household</h3>
            {MEMBERS.map(m => (
              <div key={m.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 0", borderTop: "1px solid var(--bd)" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <span style={{ fontSize: 24 }}>{m.emoji}</span>
                  <div>
                    <div style={{ fontWeight: 500 }}>{m.name}</div>
                    <div style={{ fontSize: 12, color: "var(--tx3)" }}>{m.role}{m.age ? ` · age ${m.age}` : ""}</div>
                  </div>
                </div>
                <span className={`badge ${m.role === "parent" ? "badge-pink" : "badge-lav"}`}>{m.role}</span>
              </div>
            ))}
          </div>
          {/* Contacts */}
          <div className="card-flat">
            <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 12 }}>Contacts & Vendors</h3>
            {contacts.map((p, i) => (
              <div key={p.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderTop: i ? "1px solid var(--bd)" : "none" }}>
                <div>
                  <div style={{ fontWeight: 500, color: "var(--tx)" }}>{p.name}</div>
                  <div style={{ fontSize: 12, color: "var(--tx3)" }}>{p.phone} · {p.type}</div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  {p.ghost && <span className="badge badge-err">👻 Ghosting</span>}
                  <span style={{ fontSize: 12, color: p.days > 14 ? "var(--warn)" : "var(--tx3)" }}>{p.days}d ago</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "observations" && (
        <div className="card-flat">
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 12 }}>Observations</h3>
          {observations.map((o, i) => (
            <div key={i} style={{ padding: "14px 0", borderTop: i ? "1px solid var(--bd)" : "none" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontWeight: 600, fontSize: 13, color: "var(--pink)" }}>{o.person}</span>
                <span style={{ fontSize: 11, color: "var(--tx4)", fontFamily: "var(--mono)" }}>{o.ts}</span>
              </div>
              <p style={{ fontSize: 14, color: "var(--tx2)" }}>{o.note}</p>
            </div>
          ))}
          <button className="btn-s" style={{ marginTop: 12, fontSize: 13, width: "100%" }}>+ Add Observation</button>
        </div>
      )}

      {tab === "comms" && (
        <div className="card-flat">
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 12 }}>Recent Communications</h3>
          {comms.map((c, i) => (
            <div key={i} style={{ display: "flex", gap: 12, padding: "12px 0", borderTop: i ? "1px solid var(--bd)" : "none" }}>
              <div style={{ width: 6, borderRadius: 3, background: c.dir === "in" ? "var(--teal)" : "var(--lav)", flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontWeight: 500, fontSize: 13 }}>{c.person}</span>
                  <span style={{ fontSize: 11, color: "var(--tx4)" }}>{c.ts}</span>
                </div>
                <p style={{ fontSize: 14, color: "var(--tx2)" }}>{c.msg}</p>
                <span className="badge" style={{ background: "var(--bg-input)", color: "var(--tx3)", marginTop: 4 }}>{c.ch} · {c.dir === "in" ? "received" : "sent"}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "autonomy" && (
        <div className="card-flat">
          <h3 style={{ fontSize: 11, fontWeight: 600, color: "var(--tx3)", letterSpacing: ".5px", textTransform: "uppercase", marginBottom: 12 }}>Autonomy Tiers</h3>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--bd)" }}>
                {["Action", "Gate Level", "Behavior"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "10px 12px", fontSize: 11, fontWeight: 600, color: "var(--tx3)", textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {tiers.map((t, i) => (
                <tr key={i} style={{ borderBottom: "1px solid var(--bd)" }}>
                  <td style={{ padding: "10px 12px", fontSize: 14, fontWeight: 500 }}>{t.action}</td>
                  <td style={{ padding: "10px 12px" }}>
                    <span className={`badge ${t.level === "Autonomous" ? "badge-grn" : t.level === "Low" ? "badge-teal" : t.level === "Medium" ? "badge-warn" : t.level === "High" ? "badge-pink" : "badge-err"}`}>{t.level}</span>
                  </td>
                  <td style={{ padding: "10px 12px", fontSize: 13, color: "var(--tx2)" }}>{t.desc}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── SETTINGS PAGE — WIRED ───
function SettingsPage() {
  const [tab, setTab] = useState("health");
  const tabs = ["health", "costs", "models", "sources", "phases", "config", "budget", "household", "permissions", "coaching", "gates", "memory"];
  const tl = { health: "System Health", costs: "Costs", models: "AI Models", sources: "Sources", phases: "Life Phases", config: "Config", budget: "Budget", household: "Household", permissions: "Permissions", coaching: "Coaching", gates: "Gates", memory: "Memory" };

  // Each tab fetches its own data — pass [tab] so fetches trigger on tab switch
  const { data: healthData } = useAPI(tab === "health" ? "/api/health" : null, [tab]);
  const { data: costsData } = useAPI(tab === "costs" ? "/api/costs" : null, [tab]);
  const { data: sourcesData } = useAPI(tab === "sources" ? "/api/sources" : null, [tab]);
  const { data: phasesData } = useAPI(tab === "phases" ? "/api/phases" : null, [tab]);
  const { data: configData, refetch: configRefetch } = useAPI(tab === "config" ? "/api/config" : null, [tab]);
  const { data: budgetData } = useAPI(tab === "budget" ? "/api/budget" : null, [tab]);
  const { data: modelsData } = useAPI(tab === "models" ? "/api/config/models" : null, [tab]);

  const health = healthData || { status: "unknown", uptime: 0, checks: {} };
  const costs = costsData || { total: "—", items: [] };
  const sources = sourcesData?.sources ?? [];
  const phases = phasesData?.phases ?? [];
  const config = configData?.config ?? [];
  const budget = budgetData?.categories ?? [];
  const models = modelsData?.models ?? [];

  const handleConfigEdit = async (key) => {
    const current = config.find(c => c.key === key);
    const newVal = prompt(`Edit ${key}:`, current?.val || "");
    if (newVal !== null && newVal !== current?.val) {
      try {
        await api.post(`/api/config/${key}`, { value: newVal });
        configRefetch();
      } catch (e) { console.error("Config update failed:", e); }
    }
  };

  return (
    <div className="fi">
      <h1 style={{ fontSize: 28, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 24 }}>Settings</h1>
      <div style={{ display: "flex", gap: 4, marginBottom: 24, overflowX: "auto", paddingBottom: 4 }}>
        {tabs.map(x => (
          <button key={x} onClick={() => setTab(x)} style={{
            padding: "7px 14px", borderRadius: 20, fontSize: 12, fontWeight: 500, whiteSpace: "nowrap",
            background: tab === x ? "var(--pink)" : "var(--bg-card)", color: tab === x ? "#fff" : "var(--tx2)",
            border: "1px solid " + (tab === x ? "var(--pink)" : "var(--bd)"), cursor: "pointer"
          }}>{tl[x]}</button>
        ))}
      </div>

      {tab === "health" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="card-flat" style={{ gridColumn: "1/-1" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)" }}>System Status</h3>
              <span className={`badge ${health.status === "healthy" ? "badge-grn" : "badge-err"}`}>{health.status === "healthy" ? "Healthy" : "Unhealthy"} · {health.uptime}h uptime</span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              {Object.entries(health.checks || {}).map(([n, c]) => (
                <div key={n} style={{ padding: "14px 16px", borderRadius: 10, background: "var(--bg-input)", border: "1px solid " + (c.ok ? "var(--bd)" : "var(--err)") }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                    <div style={{ width: 8, height: 8, borderRadius: "50%", background: c.ok ? "var(--grn)" : "var(--err)" }} />
                    <span style={{ fontSize: 13, fontWeight: 600, textTransform: "capitalize" }}>{n.replace(/_/g, " ")}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--tx3)" }}>{c.age !== undefined ? `${c.age}m ago` : c.pending !== undefined ? `${c.pending} pending` : "Connected"}</div>
                </div>
              ))}
            </div>
          </div>
          <div className="card-flat">
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>Backups</h3>
            <div style={{ fontSize: 14, color: "var(--tx2)", lineHeight: 2 }}>
              Hourly: <span style={{ color: "var(--grn)" }}>{health.backups?.hourly ?? "—"} ✓</span><br/>
              Daily cloud: <span style={{ color: "var(--grn)" }}>{health.backups?.daily ?? "—"} ✓</span><br/>
              DB size: <span style={{ fontFamily: "var(--mono)" }}>{health.dbSize ?? "—"}</span>
            </div>
          </div>
          <div className="card-flat">
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>Key Rotation</h3>
            <div style={{ fontSize: 14, color: "var(--tx2)", lineHeight: 2 }}>
              Anthropic: <span style={{ color: "var(--warn)" }}>{health.keyRotation?.anthropic ?? "—"}</span><br/>
              Twilio: <span style={{ color: "var(--grn)" }}>{health.keyRotation?.twilio ?? "—"}</span><br/>
              <span style={{ fontSize: 12, color: "var(--tx3)" }}>Quarterly rotation active</span>
            </div>
          </div>
        </div>
      )}

      {tab === "costs" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <div className="card-flat" style={{ gridColumn: "1/-1" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
              <h3 style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)" }}>Monthly Operating Cost</h3>
              <span style={{ fontSize: 28, fontWeight: 700, color: "var(--pink)", fontFamily: "var(--head)" }}>{costs.total}</span>
            </div>
            {costs.items.map((c, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 0", borderTop: i ? "1px solid var(--bd)" : "none" }}>
                <div><span style={{ fontWeight: 500 }}>{c.name}</span>{c.note && <span style={{ fontSize: 12, color: "var(--tx3)", marginLeft: 8 }}>{c.note}</span>}</div>
                <span style={{ fontFamily: "var(--mono)", fontWeight: 600, fontSize: 14 }}>{c.amt}</span>
              </div>
            ))}
          </div>
          <div className="card-flat">
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>API Budget</h3>
            <div style={{ fontSize: 32, fontWeight: 700, color: "var(--pink)", fontFamily: "var(--head)" }}>{costs.apiSpend ?? "—"}</div>
            <div style={{ fontSize: 13, color: "var(--tx3)", marginBottom: 12 }}>of {costs.apiThreshold ?? "$75.00"} alert threshold</div>
            <div style={{ height: 8, background: "var(--bg-input)", borderRadius: 4, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${costs.apiPct ?? 0}%`, background: "linear-gradient(90deg, var(--pink), var(--lav))", borderRadius: 4 }} />
            </div>
          </div>
          <div className="card-flat">
            <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 10 }}>Message Volume</h3>
            <div style={{ fontSize: 32, fontWeight: 700, fontFamily: "var(--head)" }}>{costs.smsCount ?? "—"}</div>
            <div style={{ fontSize: 13, color: "var(--tx3)", marginBottom: 8 }}>SMS this month</div>
            <div style={{ fontSize: 13, color: "var(--tx2)", lineHeight: 1.8 }}>
              iMessage: {costs.imessageCount ?? "—"} (free)<br/>Web chat: {costs.webChatCount ?? "—"} sessions<br/>Proactive nudges: {costs.nudgeCount ?? "—"}
            </div>
          </div>
        </div>
      )}

      {tab === "models" && (
        <div className="card-flat">
          <h3 style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 16 }}>Active Models</h3>
          {models.map(m => (
            <div key={m.key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px 0", borderTop: "1px solid var(--bd)" }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 500 }}>{m.tier}</div>
                <div style={{ fontSize: 12, color: "var(--tx3)" }}>{m.pct}</div>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <code style={{ fontSize: 12, color: "var(--pink)", fontFamily: "var(--mono)", background: "var(--pink-bg)", padding: "4px 10px", borderRadius: 6 }}>{m.val}</code>
                <button className="btn-s btn-sm">Change</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "sources" && (
        <div className="card-flat" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: 20 }}><h3 style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)" }}>Source Classifications</h3></div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--bd)", background: "var(--bg-input)" }}>
                {["Source", "Type", "Relevance", "Privacy", "Authority"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "var(--tx3)", textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sources.map(s => (
                <tr key={s.id} style={{ borderBottom: "1px solid var(--bd)" }}>
                  <td style={{ padding: "12px 14px" }}>
                    <div style={{ fontWeight: 500 }}>{s.name}</div>
                    <div style={{ fontSize: 11, color: "var(--tx4)", fontFamily: "var(--mono)" }}>{s.id}</div>
                  </td>
                  <td style={{ padding: "12px 14px", color: "var(--tx2)", fontSize: 13 }}>{s.type}</td>
                  <td style={{ padding: "12px 14px" }}><span className="badge badge-info">{s.relevance}</span></td>
                  <td style={{ padding: "12px 14px" }}>
                    <span className={`badge ${s.privacy === "privileged" ? "badge-err" : "badge-grn"}`}>
                      {s.privacy === "privileged" ? "🔒 " : ""}{s.privacy}
                    </span>
                  </td>
                  <td style={{ padding: "12px 14px", color: "var(--tx2)", fontSize: 13 }}>{s.authority}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "phases" && (
        <div className="card-flat">
          <h3 style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 16 }}>Life Phase Timeline</h3>
          {phases.map((p, i) => (
            <div key={p.id} style={{
              display: "flex", alignItems: "flex-start", gap: 16, padding: 16, borderRadius: 12, marginBottom: 8,
              background: p.status === "active" ? "var(--pink-bg2)" : "var(--bg-input)",
              border: "1px solid " + (p.status === "active" ? "var(--pink)" : "var(--bd)"),
            }}>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", paddingTop: 4 }}>
                <div style={{ width: 14, height: 14, borderRadius: "50%", background: p.status === "active" ? "var(--pink)" : "var(--bd)", border: "3px solid var(--bg-card)" }} />
                {i < phases.length - 1 && <div style={{ width: 2, height: 40, background: "var(--bd)", marginTop: 4 }} />}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
                  <span style={{ fontSize: 15, fontWeight: 600 }}>{p.name}</span>
                  <span className={`badge ${p.status === "active" ? "badge-pink" : "badge-lav"}`}>{p.status}</span>
                </div>
                <div style={{ fontSize: 13, color: "var(--tx2)" }}>{p.start} → {p.end} · Cap: {p.cap}/day</div>
                <div style={{ fontSize: 13, color: "var(--tx3)", marginTop: 2 }}>{p.desc}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "config" && (
        <div className="card-flat" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: 20 }}><h3 style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)" }}>pib_config</h3></div>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ borderBottom: "2px solid var(--bd)", background: "var(--bg-input)" }}>
                {["Key", "Value", "Description", ""].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "10px 14px", fontSize: 11, fontWeight: 600, color: "var(--tx3)", textTransform: "uppercase" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {config.map(c => (
                <tr key={c.key} style={{ borderBottom: "1px solid var(--bd)" }}>
                  <td style={{ padding: "10px 14px", fontFamily: "var(--mono)", fontSize: 12, color: "var(--pink)" }}>{c.key}</td>
                  <td style={{ padding: "10px 14px", fontFamily: "var(--mono)", fontSize: 12 }}>{c.val}</td>
                  <td style={{ padding: "10px 14px", fontSize: 13, color: "var(--tx2)" }}>{c.desc}</td>
                  <td style={{ padding: "10px 14px" }}><button className="btn-s" style={{ padding: "4px 10px", fontSize: 11 }} onClick={() => handleConfigEdit(c.key)}>Edit</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "budget" && (
        <div className="card-flat">
          <h3 style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 20 }}>Budget</h3>
          {budget.map(b => {
            const pct = b.target ? (b.spent / b.target) * 100 : 0;
            const rem = (b.target || 0) - (b.spent || 0);
            return (
              <div key={b.cat} style={{ marginBottom: 18 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                  <span style={{ fontSize: 14, fontWeight: 500, display: "flex", alignItems: "center", gap: 6 }}>
                    {b.icon} {b.cat} {b.warn && <span style={{ fontSize: 11, color: "var(--warn)" }}>⚠️</span>}
                  </span>
                  <span style={{ fontSize: 13, fontFamily: "var(--mono)", color: "var(--tx2)" }}>${b.spent} / ${b.target}</span>
                </div>
                <div style={{ height: 8, background: "var(--bg-input)", borderRadius: 4, overflow: "hidden" }}>
                  <div style={{ height: "100%", borderRadius: 4, width: `${Math.min(pct, 100)}%`, background: pct >= 90 ? "var(--err)" : pct >= 75 ? "var(--warn)" : "var(--grn)", transition: "width .5s" }} />
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 11, color: "var(--tx3)" }}>
                  <span>{pct.toFixed(0)}% used</span><span>${rem} remaining</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Fallback for unbuilt tabs */}
      {["household", "permissions", "coaching", "gates", "memory"].includes(tab) && (
        <div className="card-flat" style={{ textAlign: "center", padding: 48 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>🚧</div>
          <div style={{ fontSize: 16, fontWeight: 600, fontFamily: "var(--head)", marginBottom: 8 }}>{tl[tab]}</div>
          <div style={{ fontSize: 14, color: "var(--tx3)" }}>Configuration panel — Edit → Preview → Confirm workflow</div>
          <div style={{ fontSize: 13, color: "var(--tx4)", marginTop: 8 }}>Maps to real config files. Coming in Sprint 7.</div>
        </div>
      )}
    </div>
  );
}

// ─── STANDALONE SCOREBOARD (TV mode — dark bg, no sidebar, auto-refresh) ───
function ScoreboardTV() {
  return (
    <div style={{ background: "#1A1714", minHeight: "100vh", padding: "32px 48px" }}>
      <style>{`
        body { background: #1A1714 !important; }
        .card, .card-flat { background: #2D2926 !important; border-color: #3D3530 !important; }
        .badge-grn { background: rgba(124,185,143,0.15) !important; }
        .badge-pink { background: rgba(232,160,191,0.15) !important; }
        .badge-lav { background: rgba(184,169,201,0.15) !important; }
        .badge-warn { background: rgba(232,192,125,0.15) !important; }
        .badge-err { background: rgba(212,117,107,0.15) !important; }
        .badge-info { background: rgba(137,180,212,0.15) !important; }
        .badge-teal { background: rgba(142,197,192,0.15) !important; }
      `}</style>
      <div style={{ color: "var(--tx4)", maxWidth: 1200, margin: "0 auto" }}>
        <ScoreboardPage actor="m-james" />
      </div>
    </div>
  );
}

// ─── ROOT ───
export default function App() {
  const [page, setPage] = useState("today");
  // Persist actor selection
  const [actor, setActorState] = useState(() => {
    try { return localStorage.getItem("pib_actor") || "m-james"; } catch { return "m-james"; }
  });
  const setActor = (id) => {
    setActorState(id);
    try { localStorage.setItem("pib_actor", id); } catch {}
  };

  // Hash-based routing for standalone views
  const [route, setRoute] = useState(() => window.location.hash.replace("#", "") || "");
  useEffect(() => {
    const onHash = () => setRoute(window.location.hash.replace("#", ""));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // Standalone /scoreboard route (TV mode — dark, no sidebar)
  if (route === "scoreboard" || route === "/scoreboard") {
    return <><style>{CSS}</style><ScoreboardTV /></>;
  }

  const content = () => {
    if (actor === "m-charlie") {
      switch (page) {
        case "today": return <TodayCharlie />;
        case "scoreboard": return <ScoreboardPage actor={actor} />;
        case "chat": return <ChatPage />;
        case "lists": return <ListsPage />;
        case "schedule": return <SchedulePage />;
        default: return <TodayCharlie />;
      }
    }
    switch (page) {
      case "today": return actor === "m-james" ? <TodayJames /> : <TodayLaura />;
      case "tasks": return <TasksPage />;
      case "schedule": return <SchedulePage />;
      case "lists": return <ListsPage />;
      case "chat": return <ChatPage />;
      case "scoreboard": return <ScoreboardPage actor={actor} />;
      case "people": return <PeoplePage />;
      case "settings": return <SettingsPage />;
      default: return <TodayJames />;
    }
  };

  return (
    <>
      <style>{CSS}</style>
      <Shell page={page} setPage={setPage} actor={actor} setActor={setActor}>
        {content()}
      </Shell>
    </>
  );
}
