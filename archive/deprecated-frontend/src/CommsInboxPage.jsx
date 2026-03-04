import { useState, useEffect, useCallback } from "react";

// ─── API helpers (match App.jsx pattern) ───
async function apiFetch(path, opts = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...opts.headers },
    ...opts,
  });
  if (!res.ok) {
    const err = new Error(`API ${res.status}: ${res.statusText}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
const api = {
  get: (path) => apiFetch(path),
  post: (path, body) => apiFetch(path, { method: "POST", body: JSON.stringify(body) }),
};

// ─── Channel Icons ───
const CHANNEL_ICONS = {
  imessage: "\u{1F4AC}", email: "\u{1F4E7}", sms: "\u{1F4F1}", voice_note: "\u{1F399}\uFE0F",
  meeting_note: "\u{1F4DD}", manual: "\u{1F4CE}", whatsapp: "\u{1F4AC}", unknown: "\u{1F4E8}",
};

// ─── Urgency Styles ───
const URGENCY_BORDER = {
  urgent: "3px solid var(--err, #E57373)",
  timely: "3px solid var(--warn, #FFB74D)",
  normal: "3px solid transparent",
  fyi: "3px dashed var(--info, #64B5F6)",
};

// ─── Extraction Type Icons ───
const EXTRACTION_ICONS = {
  task: "\u{1F4CB}", event: "\u{1F4C5}", bill: "\u{1F4B0}",
  entity: "\u{1F464}", list_item: "\u{1F4DD}", recurring: "\u{1F504}",
};

// ─── CommsExtractionBadge ───
function CommsExtractionBadge({ extraction, onApprove, onReject }) {
  if (extraction.approved) {
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 6, background: "var(--grn-bg, #E8F5E9)", fontSize: 12 }}>
        {EXTRACTION_ICONS[extraction.type] || "\u{1F4CB}"} {extraction.title} \u2705
      </span>
    );
  }
  if (extraction.rejected) {
    return null; // Faded out
  }
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 4, padding: "2px 8px", borderRadius: 6, background: "var(--teal-bg, #E0F2F1)", fontSize: 12 }}>
      {EXTRACTION_ICONS[extraction.type] || "\u{1F4CB}"} {extraction.title}
      <span style={{ opacity: 0.6, fontSize: 10 }}>({(extraction.confidence * 100).toFixed(0)}%)</span>
      <button onClick={onApprove} style={{ border: "none", background: "none", cursor: "pointer", fontSize: 14, padding: 0 }} title="Approve">\u2705</button>
      <button onClick={onReject} style={{ border: "none", background: "none", cursor: "pointer", fontSize: 14, padding: 0 }} title="Reject">\u274C</button>
    </span>
  );
}

// ─── CommsDraftReview ───
function CommsDraftReview({ draft, draftStatus, channel, onApprove, onReject, onEdit }) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(draft || "");

  if (draftStatus !== "pending") return null;

  return (
    <div style={{ borderLeft: "3px solid var(--pink, #E8A0BF)", padding: "8px 12px", marginTop: 8, background: "var(--pink-bg, #FFF0F5)", borderRadius: "0 8px 8px 0" }}>
      <div style={{ fontSize: 11, color: "var(--tx3, #9B8E82)", marginBottom: 4 }}>
        Draft via {channel} {CHANNEL_ICONS[channel] || ""}
      </div>
      {editing ? (
        <div>
          <textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            style={{ width: "100%", minHeight: 60, padding: 8, borderRadius: 6, border: "1px solid var(--bd, #E8E0D6)", fontSize: 13, fontFamily: "inherit", resize: "vertical" }}
          />
          <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
            <button onClick={() => { onApprove(editText); setEditing(false); }} style={btnStyle("var(--grn, #4CAF50)")}>Send</button>
            <button onClick={() => setEditing(false)} style={btnStyle("var(--tx3, #9B8E82)")}>Cancel</button>
          </div>
        </div>
      ) : (
        <div>
          <div style={{ fontSize: 13, fontStyle: "italic", color: "var(--tx2, #6B5E54)" }}>{draft}</div>
          <div style={{ display: "flex", gap: 6, marginTop: 6 }}>
            <button onClick={() => setEditing(true)} style={btnStyle("var(--info, #64B5F6)")}>Edit</button>
            <button onClick={() => onApprove()} style={btnStyle("var(--grn, #4CAF50)")}>Send</button>
            <button onClick={onReject} style={btnStyle("var(--err, #E57373)")}>Reject</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── CommsReplyComposer ───
function CommsReplyComposer({ channel, recipientName, onSend, onCancel }) {
  const [body, setBody] = useState("");
  const isSms = channel === "sms";

  return (
    <div style={{ padding: 12, background: "var(--bg-input, #F5F0EA)", borderRadius: 8, marginTop: 8, animation: "slideIn 0.2s ease-out" }}>
      <div style={{ fontSize: 11, color: "var(--tx3, #9B8E82)", marginBottom: 6 }}>
        Replying via {channel} {CHANNEL_ICONS[channel] || ""} to {recipientName}
      </div>
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder="Type your reply..."
        style={{ width: "100%", minHeight: 60, padding: 8, borderRadius: 6, border: "1px solid var(--bd, #E8E0D6)", fontSize: 13, fontFamily: "inherit", resize: "vertical" }}
      />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
        <div style={{ display: "flex", gap: 6 }}>
          <button onClick={() => onSend(body)} disabled={!body.trim()} style={{ ...btnStyle("var(--pink, #E8A0BF)"), opacity: body.trim() ? 1 : 0.5 }}>Send</button>
          <button onClick={onCancel} style={btnStyle("var(--tx3, #9B8E82)")}>Cancel</button>
        </div>
        {isSms && <span style={{ fontSize: 11, color: "var(--tx4, #C4B8AC)" }}>{body.length}/160</span>}
      </div>
    </div>
  );
}

// ─── CommsCard ───
function CommsCard({ comm, onAction, compact }) {
  const [showReply, setShowReply] = useState(false);
  const extractions = comm.extracted_items ? JSON.parse(comm.extracted_items) : [];
  const relativeTime = getRelativeTime(comm.date || comm.created_at);

  return (
    <div style={{
      background: "var(--bg-card, #FFFFFF)",
      borderRadius: 12,
      padding: compact ? "12px 14px" : "14px 18px",
      marginBottom: compact ? 8 : 12,
      borderLeft: URGENCY_BORDER[comm.response_urgency] || URGENCY_BORDER.normal,
      boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
      transition: "all 0.15s",
    }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 16 }}>{CHANNEL_ICONS[comm.channel] || CHANNEL_ICONS.unknown}</span>
          <span style={{ fontWeight: 600, fontSize: 14, color: "var(--tx, #2D2926)" }}>{comm.from_addr || "Unknown"}</span>
          <span style={{ fontSize: 12, color: "var(--tx3, #9B8E82)" }}>{comm.channel}</span>
        </div>
        <span style={{ fontSize: 11, color: "var(--tx4, #C4B8AC)" }}>{relativeTime}</span>
      </div>

      {/* Subject */}
      {comm.subject && (
        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--tx2, #6B5E54)", marginBottom: 4 }}>{comm.subject}</div>
      )}

      {/* Body snippet */}
      <div style={{ fontSize: 13, color: "var(--tx2, #6B5E54)", lineHeight: 1.5, display: "-webkit-box", WebkitLineClamp: compact ? 2 : 3, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        {comm.body_snippet || comm.summary}
      </div>

      {/* Extraction badges */}
      {extractions.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          {extractions.map((ext, i) => (
            <CommsExtractionBadge
              key={i}
              extraction={ext}
              onApprove={() => onAction(comm.id, "approve-extraction", { index: i })}
              onReject={() => onAction(comm.id, "reject-extraction", { index: i })}
            />
          ))}
        </div>
      )}

      {/* Draft review */}
      {comm.draft_status === "pending" && (
        <CommsDraftReview
          draft={comm.draft_response}
          draftStatus={comm.draft_status}
          channel={comm.channel}
          onApprove={(edited) => onAction(comm.id, "approve-draft", { edited_body: edited })}
          onReject={() => onAction(comm.id, "reject-draft")}
        />
      )}

      {/* Reply composer */}
      {showReply && (
        <CommsReplyComposer
          channel={comm.channel}
          recipientName={comm.from_addr || "Unknown"}
          onSend={(body) => { onAction(comm.id, "reply", { body }); setShowReply(false); }}
          onCancel={() => setShowReply(false)}
        />
      )}

      {/* Action bar */}
      <div style={{ display: "flex", gap: 6, marginTop: 10, flexWrap: "wrap" }}>
        {comm.needs_response === 1 && (
          <button onClick={() => onAction(comm.id, "mark-responded")} style={btnStyle("var(--grn, #4CAF50)")}>
            Responded
          </button>
        )}
        <button onClick={() => setShowReply(!showReply)} style={btnStyle("var(--pink, #E8A0BF)")}>
          Reply
        </button>
        <button onClick={() => onAction(comm.id, "snooze", { until: getSnoozeDefault() })} style={btnStyle("var(--warn, #FFB74D)")}>
          Snooze
        </button>
        <button onClick={() => onAction(comm.id, "tag", { tag: "follow-up" })} style={btnStyle("var(--tx3, #9B8E82)")}>
          Tag
        </button>
      </div>
    </div>
  );
}

// ─── CommsBatchBar ───
function CommsBatchBar({ batches, activeBatch, onBatchClick }) {
  const windows = [
    { key: "morning", icon: "\u2600\uFE0F", label: "Morning" },
    { key: "midday", icon: "\u{1F324}\uFE0F", label: "Midday" },
    { key: "evening", icon: "\u{1F319}", label: "Evening" },
  ];

  return (
    <div style={{ display: "flex", gap: 8, padding: "12px 0", borderTop: "1px solid var(--bd, #E8E0D6)" }}>
      {windows.map(w => {
        const count = batches?.[w.key] ?? 0;
        const isActive = activeBatch === w.key;
        return (
          <button
            key={w.key}
            onClick={() => onBatchClick(w.key)}
            style={{
              flex: 1, padding: "8px 12px", borderRadius: 8,
              border: "1px solid " + (isActive ? "var(--pink, #E8A0BF)" : "var(--bd, #E8E0D6)"),
              background: isActive ? "var(--pink-bg, #FFF0F5)" : "transparent",
              display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
              fontSize: 13, color: isActive ? "var(--pink, #E8A0BF)" : "var(--tx2, #6B5E54)",
              fontWeight: isActive ? 600 : 400, cursor: "pointer",
            }}
          >
            <span>{w.icon}</span>
            <span>{w.label}</span>
            <span style={{ fontSize: 11, opacity: 0.7 }}>({count})</span>
            {count === 0 && <span>\u2014</span>}
          </button>
        );
      })}
    </div>
  );
}

// ─── CommsInboxPage (main page component) ───
export default function CommsInboxPage() {
  const [comms, setComms] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [filter, setFilter] = useState("all");
  const [channelFilter, setChannelFilter] = useState(null);
  const [batchFilter, setBatchFilter] = useState(null);
  const [batchReviewMode, setBatchReviewMode] = useState(false);
  const [selectedIdx, setSelectedIdx] = useState(0);

  const fetchComms = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (filter === "needs_response") params.set("needs_response", "true");
      if (filter === "urgent") { params.set("needs_response", "true"); params.set("urgency", "urgent"); }
      if (filter === "drafts") params.set("draft_status", "pending");
      if (filter === "fyi") params.set("urgency", "fyi");
      if (channelFilter) params.set("channel", channelFilter);
      if (batchFilter) { params.set("batch_window", batchFilter); params.set("batch_date", new Date().toISOString().slice(0, 10)); }

      const [inbox, cntData] = await Promise.all([
        api.get(`/api/comms/inbox?${params}`),
        api.get("/api/comms/counts"),
      ]);
      setComms(inbox);
      setCounts(cntData);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [filter, channelFilter, batchFilter]);

  useEffect(() => { fetchComms(); }, [fetchComms]);

  // Poll every 60 seconds
  useEffect(() => {
    const iv = setInterval(fetchComms, 60000);
    return () => clearInterval(iv);
  }, [fetchComms]);

  // Action handler — routes to API endpoints
  const handleAction = async (commId, action, payload = {}) => {
    try {
      switch (action) {
        case "mark-responded": await api.post(`/api/comms/${commId}/mark-responded`, payload); break;
        case "snooze": await api.post(`/api/comms/${commId}/snooze`, payload); break;
        case "tag": await api.post(`/api/comms/${commId}/tag`, payload); break;
        case "approve-draft": await api.post(`/api/comms/${commId}/approve-draft`, payload); break;
        case "reject-draft": await api.post(`/api/comms/${commId}/reject-draft`); break;
        case "reply": await api.post(`/api/comms/${commId}/reply`, payload); break;
        case "approve-extraction": await api.post(`/api/comms/${commId}/extraction/${payload.index}/approve`); break;
        case "reject-extraction": await api.post(`/api/comms/${commId}/extraction/${payload.index}/reject`); break;
      }
      // Optimistic: refetch
      fetchComms();
      // In batch review mode, advance to next
      if (batchReviewMode && (action === "mark-responded" || action === "approve-draft")) {
        setSelectedIdx(prev => Math.min(prev + 1, comms.length - 1));
      }
    } catch (e) {
      console.error(`Action ${action} failed:`, e);
    }
  };

  // Batch review mode
  const batchComms = batchFilter ? comms : [];
  const currentBatchComm = batchReviewMode && batchComms.length > 0 ? batchComms[selectedIdx] : null;

  // Filter tabs
  const FILTERS = [
    { id: "all", label: "All", count: counts.total_normal },
    { id: "needs_response", label: "Needs Reply", count: counts.needs_response },
    { id: "urgent", label: "Urgent", count: counts.urgent },
    { id: "drafts", label: "Drafts", count: counts.drafts_pending },
    { id: "fyi", label: "FYI" },
  ];

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, fontFamily: "var(--head, 'Fraunces')", color: "var(--tx, #2D2926)", margin: 0 }}>
          \u{1F4E8} Comms Inbox
        </h1>
      </div>

      {/* Filter tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
        {FILTERS.map(f => (
          <button
            key={f.id}
            onClick={() => { setFilter(f.id); setBatchFilter(null); setBatchReviewMode(false); }}
            style={{
              padding: "6px 14px", borderRadius: 20,
              border: "1px solid " + (filter === f.id ? "var(--pink, #E8A0BF)" : "var(--bd, #E8E0D6)"),
              background: filter === f.id ? "var(--pink-bg, #FFF0F5)" : "transparent",
              fontSize: 13, fontWeight: filter === f.id ? 600 : 400,
              color: filter === f.id ? "var(--pink, #E8A0BF)" : "var(--tx2, #6B5E54)",
              cursor: "pointer",
            }}
          >
            {f.label} {f.count != null && <span style={{ opacity: 0.7, marginLeft: 4 }}>({f.count})</span>}
          </button>
        ))}
      </div>

      {/* Channel filter */}
      <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
        {[null, "imessage", "email", "sms", "voice_note", "manual"].map(ch => (
          <button
            key={ch || "all"}
            onClick={() => setChannelFilter(ch)}
            style={{
              padding: "4px 10px", borderRadius: 12, border: "1px solid var(--bd, #E8E0D6)",
              background: channelFilter === ch ? "var(--bg-hover, #F0EBE4)" : "transparent",
              fontSize: 12, color: "var(--tx2, #6B5E54)", cursor: "pointer",
            }}
          >
            {ch ? `${CHANNEL_ICONS[ch] || ""} ${ch}` : "All channels"}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div style={{ padding: "10px 14px", borderRadius: 8, background: "var(--err-bg, #FFEBEE)", color: "var(--err, #E57373)", fontSize: 13, marginBottom: 12 }}>
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ height: 100, borderRadius: 12, background: "var(--bg-input, #F5F0EA)", animation: "pulse 1.5s infinite" }} />
          ))}
        </div>
      )}

      {/* Batch review carousel mode */}
      {batchReviewMode && currentBatchComm && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span style={{ fontSize: 13, color: "var(--tx3, #9B8E82)" }}>
              Reviewing {selectedIdx + 1} of {batchComms.length}
            </span>
            <button onClick={() => setBatchReviewMode(false)} style={btnStyle("var(--tx3, #9B8E82)")}>Exit Carousel</button>
          </div>
          <CommsCard comm={currentBatchComm} onAction={handleAction} compact />
          <div style={{ display: "flex", justifyContent: "center", gap: 12, marginTop: 8 }}>
            <button onClick={() => setSelectedIdx(Math.max(0, selectedIdx - 1))} disabled={selectedIdx === 0} style={{ ...btnStyle("var(--tx3, #9B8E82)"), opacity: selectedIdx === 0 ? 0.3 : 1 }}>\u2190 Prev</button>
            <button onClick={() => setSelectedIdx(Math.min(batchComms.length - 1, selectedIdx + 1))} disabled={selectedIdx >= batchComms.length - 1} style={{ ...btnStyle("var(--tx3, #9B8E82)"), opacity: selectedIdx >= batchComms.length - 1 ? 0.3 : 1 }}>Next \u2192</button>
          </div>
          {selectedIdx >= batchComms.length - 1 && batchComms.every(c => c.needs_response === 0) && (
            <div style={{ textAlign: "center", padding: 20, fontSize: 18 }}>
              \u{1F389} Inbox clear. {batchComms.length} handled.
            </div>
          )}
        </div>
      )}

      {/* Message list */}
      {!loading && !batchReviewMode && (
        <div>
          {comms.length === 0 ? (
            <div style={{ textAlign: "center", padding: 40, color: "var(--tx3, #9B8E82)" }}>
              {filter !== "all" ? (
                <div>No {filter.replace("_", " ")} messages. <button onClick={() => setFilter("all")} style={{ color: "var(--pink, #E8A0BF)", border: "none", background: "none", cursor: "pointer", textDecoration: "underline" }}>Clear filters</button></div>
              ) : (
                <div>\u{1F4E8} No messages yet. Connect your channels in Settings.</div>
              )}
            </div>
          ) : (
            comms.map(comm => (
              <CommsCard key={comm.id} comm={comm} onAction={handleAction} />
            ))
          )}
        </div>
      )}

      {/* Batch bar */}
      <CommsBatchBar
        batches={counts.by_batch}
        activeBatch={batchFilter}
        onBatchClick={(window) => {
          setBatchFilter(batchFilter === window ? null : window);
          setFilter("all");
          setSelectedIdx(0);
        }}
      />

      {/* Start batch review button */}
      {batchFilter && comms.length > 0 && !batchReviewMode && (
        <div style={{ textAlign: "center", marginTop: 12 }}>
          <button onClick={() => { setBatchReviewMode(true); setSelectedIdx(0); }} style={{ ...btnStyle("var(--pink, #E8A0BF)"), padding: "10px 24px", fontSize: 14 }}>
            Start Batch Review ({comms.length} messages)
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Helpers ───
function btnStyle(color) {
  return {
    padding: "4px 12px", borderRadius: 6, border: `1px solid ${color}`,
    background: "transparent", color, fontSize: 12, fontWeight: 500,
    cursor: "pointer", transition: "all 0.15s",
  };
}

function getRelativeTime(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function getSnoozeDefault() {
  const d = new Date();
  d.setHours(d.getHours() + 4);
  return d.toISOString();
}
