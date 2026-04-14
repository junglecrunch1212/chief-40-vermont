/**
 * console/comms_routes.mjs
 * Express router for Comms Inbox operations
 */

import { Router } from "express";

export function createCommsRouter(getDB, auditLog, guardedWrite) {
  const router = Router();

  // Helper: Check if member has access to a channel
  function hasChannelAccess(db, memberId, channelId) {
    try {
      const access = db.prepare(
        "SELECT access_level FROM comms_channel_member_access WHERE member_id = ? AND channel_id = ?"
      ).get(memberId, channelId);
      return access && access.access_level !== 'none';
    } catch {
      return false;
    }
  }

  // Helper: Get member's visible channels
  function getMemberChannels(db, memberId) {
    try {
      const channels = db.prepare(`
        SELECT channel_id 
        FROM comms_channel_member_access 
        WHERE member_id = ? AND access_level != 'none' AND show_in_inbox = 1
      `).all(memberId);
      return channels.map(c => c.channel_id);
    } catch {
      return [];
    }
  }

  // GET /api/comms/inbox — filtered by member's visible channels
  router.get("/inbox", (req, res) => {
    const db = getDB();
    const memberId = req.memberId;
    const channelFilter = req.query.channel;
    const batchWindow = req.query.batch_window;
    const draftStatus = req.query.draft_status;
    const needsResponse = req.query.needs_response;
    const search = req.query.search;

    try {
      // Get member's visible channels
      const visibleChannels = getMemberChannels(db, memberId);
      if (visibleChannels.length === 0) {
        return res.json({ items: [] });
      }

      let sql = `
        SELECT oc.*, 
               cc.display_name as channel_name, 
               cc.icon as channel_icon,
               cc.adapter_id,
               cma.access_level
        FROM ops_comms oc
        LEFT JOIN comms_channels cc ON cc.id = oc.channel
        LEFT JOIN comms_channel_member_access cma ON cma.channel_id = oc.channel AND cma.member_id = ?
        WHERE oc.channel IN (${visibleChannels.map(() => '?').join(',')})
      `;
      const params = [memberId, ...visibleChannels];

      if (channelFilter) {
        sql += " AND oc.channel = ?";
        params.push(channelFilter);
      }
      if (batchWindow) {
        sql += " AND oc.batch_window = ?";
        params.push(batchWindow);
      }
      if (draftStatus) {
        sql += " AND oc.draft_status = ?";
        params.push(draftStatus);
      }
      if (needsResponse !== undefined) {
        sql += " AND oc.needs_response = ?";
        params.push(needsResponse === 'true' || needsResponse === '1' ? 1 : 0);
      }
      if (search) {
        sql += " AND (oc.summary LIKE ? OR oc.subject LIKE ? OR oc.body_snippet LIKE ?)";
        const searchPattern = `%${search}%`;
        params.push(searchPattern, searchPattern, searchPattern);
      }

      // Order by urgency within batch windows
      sql += ` 
        ORDER BY 
          CASE oc.response_urgency 
            WHEN 'urgent' THEN 1 
            WHEN 'timely' THEN 2 
            WHEN 'normal' THEN 3 
            ELSE 4 
          END,
          oc.batch_window,
          oc.created_at DESC
        LIMIT 200
      `;

      const items = db.prepare(sql).all(...params);

      // Apply privacy enforcement
      const result = items.filter(item => {
        if (item.direction === 'outbound' && item.member_id !== memberId) return false;
        if (item.draft_status && item.draft_status !== 'none' && item.member_id !== memberId) return false;
        const access = db.prepare("SELECT access_level FROM comms_channel_member_access WHERE member_id = ? AND channel_id = ?").get(memberId, item.channel);
        if (!access || access.access_level === 'none') return false;
        return true;
      }).map(item => {
        const access = db.prepare("SELECT access_level FROM comms_channel_member_access WHERE member_id = ? AND channel_id = ?").get(memberId, item.channel);
        if (access?.access_level === 'read' && item.member_id !== memberId) {
          return { ...item, body_snippet: '[privileged — open in source app]', summary: '[busy]' };
        }
        return item;
      });

      // Apply privacy filtering for metadata access level
      const filtered = result.map(item => {
        if (item.access_level === 'metadata') {
          return {
            id: item.id,
            channel: item.channel,
            channel_name: item.channel_name,
            channel_icon: item.channel_icon,
            created_at: item.created_at,
            batch_window: item.batch_window,
            response_urgency: item.response_urgency,
            needs_response: item.needs_response,
            outcome: item.outcome,
            access_level: item.access_level,
            // No content shown for metadata-only access
            summary: null,
            subject: null,
            body_snippet: null,
          };
        }
        return item;
      });

      res.json({ items: filtered });
    } catch (e) {
      res.status(500).json({ error: e.message, items: [] });
    }
  });

  // GET /api/comms/counts — badge counts
  router.get("/counts", (req, res) => {
    const db = getDB();
    const memberId = req.memberId;

    try {
      const visibleChannels = getMemberChannels(db, memberId);
      if (visibleChannels.length === 0) {
        return res.json({ needs_response: 0, urgent: 0, drafts_pending: 0, by_batch: {} });
      }

      const channelPlaceholders = visibleChannels.map(() => '?').join(',');

      const needsResponse = db.prepare(`
        SELECT COUNT(*) as count 
        FROM ops_comms 
        WHERE channel IN (${channelPlaceholders}) AND needs_response = 1
      `).get(...visibleChannels)?.count || 0;

      const urgent = db.prepare(`
        SELECT COUNT(*) as count 
        FROM ops_comms 
        WHERE channel IN (${channelPlaceholders}) AND response_urgency = 'urgent' AND needs_response = 1
      `).get(...visibleChannels)?.count || 0;

      const draftsPending = db.prepare(`
        SELECT COUNT(*) as count 
        FROM ops_comms 
        WHERE channel IN (${channelPlaceholders}) AND draft_status = 'pending'
      `).get(...visibleChannels)?.count || 0;

      const byBatch = {};
      for (const bw of ['morning', 'midday', 'evening']) {
        const count = db.prepare(`
          SELECT COUNT(*) as count 
          FROM ops_comms 
          WHERE channel IN (${channelPlaceholders}) AND batch_window = ? AND needs_response = 1
        `).get(...visibleChannels, bw)?.count || 0;
        byBatch[bw] = count;
      }

      res.json({ needs_response: needsResponse, urgent, drafts_pending: draftsPending, by_batch: byBatch });
    } catch (e) {
      res.status(500).json({ error: e.message, needs_response: 0, urgent: 0, drafts_pending: 0, by_batch: {} });
    }
  });

  // GET /api/comms/:id — single comm detail
  router.get("/:id", (req, res) => {
    const db = getDB();
    const memberId = req.memberId;

    try {
      const comm = db.prepare(`
        SELECT oc.*, 
               cc.display_name as channel_name, 
               cc.icon as channel_icon,
               cma.access_level
        FROM ops_comms oc
        LEFT JOIN comms_channels cc ON cc.id = oc.channel
        LEFT JOIN comms_channel_member_access cma ON cma.channel_id = oc.channel AND cma.member_id = ?
        WHERE oc.id = ?
      `).get(memberId, req.params.id);

      if (!comm) {
        return res.status(404).json({ error: "Comm not found" });
      }

      if (!hasChannelAccess(db, memberId, comm.channel)) {
        return res.status(403).json({ error: "No access to this channel" });
      }

      // Apply privacy filtering
      if (comm.access_level === 'metadata') {
        comm.summary = null;
        comm.subject = null;
        comm.body_snippet = null;
        comm.draft_response = null;
      }

      res.json({ comm });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  });

  // POST /api/comms/:id/draft — stub (requires LLM)
  router.post("/:id/draft", (req, res) => {
    res.json({ ok: true, message: "Draft generation requires LLM integration" });
  });

  // POST /api/comms/:id/approve — approve draft
  router.post("/:id/approve", guardedWrite("comms_approve_draft", (req, res) => {
    const db = getDB();
    const wdb = req.writeDB; // Passed by guardedWrite
    const memberId = req.memberId;
    const editedText = req.body.edited_text;

    try {
      const comm = db.prepare("SELECT * FROM ops_comms WHERE id = ?").get(req.params.id);
      if (!comm) {
        return res.status(404).json({ error: "Comm not found" });
      }

      if (!hasChannelAccess(db, memberId, comm.channel)) {
        return res.status(403).json({ error: "No access to this channel" });
      }

      // Check if member can approve drafts
      const access = db.prepare(
        "SELECT can_approve_drafts FROM comms_channel_member_access WHERE member_id = ? AND channel_id = ?"
      ).get(memberId, comm.channel);

      if (!access || !access.can_approve_drafts) {
        return res.status(403).json({ error: "No permission to approve drafts on this channel" });
      }

      const updateFields = ["draft_status = 'approved'"];
      const params = [];

      if (editedText) {
        updateFields.push("draft_response = ?");
        params.push(editedText);
      }

      params.push(req.params.id);

      wdb.prepare(`
        UPDATE ops_comms
        SET ${updateFields.join(', ')}
        WHERE id = ?
      `).run(...params);

      auditLog(wdb, "comms-approve", JSON.stringify({ id: req.params.id, edited: !!editedText }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // POST /api/comms/:id/reject — reject draft
  router.post("/:id/reject", guardedWrite("comms_approve_draft", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;

    try {
      wdb.prepare(`
        UPDATE ops_comms
        SET draft_status = 'rejected'
        WHERE id = ?
      `).run(req.params.id);

      auditLog(wdb, "comms-reject", JSON.stringify({ id: req.params.id }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // POST /api/comms/:id/send — approve + mark as sent
  router.post("/:id/send", guardedWrite("comms_approve_draft", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;

    try {
      wdb.prepare(`
        UPDATE ops_comms
        SET draft_status = 'approved',
            outcome = 'sent',
            responded_at = datetime('now')
        WHERE id = ?
      `).run(req.params.id);

      auditLog(wdb, "comms-send", JSON.stringify({ id: req.params.id }), memberId);

      // TODO: Actual adapter delivery would go here

      res.json({ ok: true, message: "Marked as sent (adapter delivery stub)" });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // POST /api/comms/:id/snooze — set snoozed_until date
  router.post("/:id/snooze", guardedWrite("comms_snooze", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const until = req.body.until || req.query.until;

    if (!until) {
      return res.status(400).json({ error: "until date required (YYYY-MM-DD)" });
    }

    try {
      wdb.prepare(`
        UPDATE ops_comms
        SET snoozed_until = ?
        WHERE id = ?
      `).run(until, req.params.id);

      auditLog(wdb, "comms-snooze", JSON.stringify({ id: req.params.id, until }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // POST /api/comms/:id/archive — set needs_response=0, outcome='handled'
  router.post("/:id/archive", guardedWrite("comms_respond", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;

    try {
      wdb.prepare(`
        UPDATE ops_comms
        SET needs_response = 0,
            outcome = 'handled',
            responded_at = datetime('now')
        WHERE id = ?
      `).run(req.params.id);

      auditLog(wdb, "comms-archive", JSON.stringify({ id: req.params.id }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  return router;
}
