/**
 * console/channel_routes.mjs
 * Express router for Channel Management operations
 */

import { Router } from "express";
import crypto from "crypto";

export function createChannelRouter(getDB, auditLog, guardedWrite) {
  const router = Router();

  // GET /api/channels/member/:memberId — channels visible to member with access levels
  router.get("/member/:memberId", (req, res) => {
    const db = getDB();
    const memberId = req.params.memberId;

    try {
      const channels = db.prepare(`
        SELECT 
          cc.*,
          cma.access_level,
          cma.can_approve_drafts,
          cma.receives_proactive,
          cma.digest_include,
          cma.notify_on_urgent,
          cma.batch_window as preferred_batch,
          ch.status as health_status,
          ch.last_poll_at,
          ch.consecutive_failures
        FROM comms_channels cc
        LEFT JOIN comms_channel_member_access cma 
          ON cma.channel_id = cc.id AND cma.member_id = ?
        LEFT JOIN comms_channel_health ch 
          ON ch.channel_id = cc.id
        WHERE cma.access_level IS NOT NULL AND cma.access_level != 'none'
        ORDER BY cc.category, cc.sort_order, cc.display_name
      `).all(memberId);

      res.json({ channels });
    } catch (e) {
      res.status(500).json({ error: e.message, channels: [] });
    }
  });

  // GET /api/channels/member/:memberId/sendable — channels member can send on
  router.get("/member/:memberId/sendable", (req, res) => {
    const db = getDB();
    const memberId = req.params.memberId;

    try {
      const channels = db.prepare(`
        SELECT 
          cc.id,
          cc.display_name,
          cc.icon,
          cc.adapter_id,
          cma.access_level
        FROM comms_channels cc
        INNER JOIN comms_channel_member_access cma 
          ON cma.channel_id = cc.id AND cma.member_id = ?
        WHERE cc.enabled = 1 
          AND cma.access_level IN ('write', 'admin')
        ORDER BY cc.sort_order, cc.display_name
      `).all(memberId);

      res.json({ channels });
    } catch (e) {
      res.status(500).json({ error: e.message, channels: [] });
    }
  });

  // POST /api/channels/:id/access — grant member access
  router.post("/:id/access", guardedWrite("channel_grant_access", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const channelId = req.params.id;
    const { target_member_id, access_level, can_approve_drafts, batch_window } = req.body;

    if (!target_member_id || !access_level) {
      return res.status(400).json({ error: "target_member_id and access_level required" });
    }

    if (!['none', 'read', 'write', 'admin'].includes(access_level)) {
      return res.status(400).json({ error: "Invalid access_level" });
    }

    try {
      const accessId = `ca-${crypto.randomUUID()}`;

      wdb.prepare(`
        INSERT INTO comms_channel_member_access (
          id, member_id, channel_id, access_level, can_approve_drafts, batch_window
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(member_id, channel_id) DO UPDATE SET
          access_level = excluded.access_level,
          can_approve_drafts = excluded.can_approve_drafts,
          batch_window = excluded.batch_window,
          updated_at = datetime('now')
      `).run(
        accessId,
        target_member_id,
        channelId,
        access_level,
        can_approve_drafts ? 1 : 0,
        batch_window || null
      );

      auditLog(wdb, "channel-grant-access", JSON.stringify({
        channel_id: channelId,
        target_member_id,
        access_level,
      }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // DELETE /api/channels/:id/access/:memberId — revoke access
  router.delete("/:id/access/:targetMemberId", guardedWrite("channel_revoke_access", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const channelId = req.params.id;
    const targetMemberId = req.params.targetMemberId;

    try {
      wdb.prepare(`
        DELETE FROM comms_channel_member_access 
        WHERE channel_id = ? AND member_id = ?
      `).run(channelId, targetMemberId);

      auditLog(wdb, "channel-revoke-access", JSON.stringify({
        channel_id: channelId,
        target_member_id: targetMemberId,
      }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // POST /api/channels/setup-member — apply role template
  router.post("/setup-member", guardedWrite("channel_setup_member", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const { target_member_id, role_template } = req.body;

    if (!target_member_id || !role_template) {
      return res.status(400).json({ error: "target_member_id and role_template required" });
    }

    try {
      // Role templates (simplified for now)
      const templates = {
        parent_admin: { access_level: 'admin', can_approve_drafts: 1 },
        parent_full: { access_level: 'write', can_approve_drafts: 1 },
        parent_read: { access_level: 'read', can_approve_drafts: 0 },
        child: { access_level: 'none', can_approve_drafts: 0 },
      };

      const template = templates[role_template];
      if (!template) {
        return res.status(400).json({ error: "Invalid role_template" });
      }

      // Get all channels
      const db = getDB();
      const channels = db.prepare("SELECT id FROM comms_channels WHERE enabled = 1").all();

      for (const channel of channels) {
        const accessId = `ca-${crypto.randomUUID()}`;
        wdb.prepare(`
          INSERT INTO comms_channel_member_access (
            id, member_id, channel_id, access_level, can_approve_drafts
          ) VALUES (?, ?, ?, ?, ?)
          ON CONFLICT(member_id, channel_id) DO UPDATE SET
            access_level = excluded.access_level,
            can_approve_drafts = excluded.can_approve_drafts,
            updated_at = datetime('now')
        `).run(
          accessId,
          target_member_id,
          channel.id,
          template.access_level,
          template.can_approve_drafts
        );
      }

      auditLog(wdb, "channel-setup-member", JSON.stringify({
        target_member_id,
        role_template,
        channels_count: channels.length,
      }), memberId);

      res.json({ ok: true, channels_updated: channels.length });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // GET /api/devices — list all devices
  router.get("/devices", (req, res) => {
    const db = getDB();

    try {
      const devices = db.prepare(`
        SELECT 
          cd.*,
          cm.display_name as owner_name
        FROM comms_devices cd
        LEFT JOIN common_members cm ON cm.id = cd.owner_member_id
        WHERE cd.active = 1
        ORDER BY cd.status DESC, cd.display_name
      `).all();

      res.json({ devices });
    } catch (e) {
      res.status(500).json({ error: e.message, devices: [] });
    }
  });

  // POST /api/devices/:id/status — update device status
  router.post("/devices/:id/status", guardedWrite("channel_update", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const deviceId = req.params.id;
    const { status } = req.body;

    if (!status || !['active', 'offline', 'degraded', 'error'].includes(status)) {
      return res.status(400).json({ error: "Invalid status" });
    }

    try {
      wdb.prepare(`
        UPDATE comms_devices 
        SET status = ?, updated_at = datetime('now')
        WHERE id = ?
      `).run(status, deviceId);

      auditLog(wdb, "device-status-update", JSON.stringify({ device_id: deviceId, status }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // GET /api/accounts — list accounts, optional ?member_id filter
  router.get("/accounts", (req, res) => {
    const db = getDB();
    const memberFilter = req.query.member_id;

    try {
      let sql = `
        SELECT 
          ca.*,
          cm.display_name as owner_name
        FROM comms_accounts ca
        LEFT JOIN common_members cm ON cm.id = ca.owner_member_id
        WHERE ca.active = 1
      `;
      const params = [];

      if (memberFilter) {
        sql += " AND ca.owner_member_id = ?";
        params.push(memberFilter);
      }

      sql += " ORDER BY ca.account_type, ca.address";

      const accounts = db.prepare(sql).all(...params);

      res.json({ accounts });
    } catch (e) {
      res.status(500).json({ error: e.message, accounts: [] });
    }
  });

  // POST /api/channels/:id/onboarding/:stepKey/complete — mark wizard step done
  router.post("/:id/onboarding/:stepKey/complete", guardedWrite("channel_update", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const channelId = req.params.id;
    const stepKey = req.params.stepKey;

    try {
      wdb.prepare(`
        UPDATE comms_onboarding_steps 
        SET status = 'completed', 
            completed_at = datetime('now')
        WHERE channel_id = ? AND step_key = ?
      `).run(channelId, stepKey);

      auditLog(wdb, "channel-onboarding-step", JSON.stringify({
        channel_id: channelId,
        step_key: stepKey,
      }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // POST /api/channels/:id/enable — enable channel (only if required onboarding steps done)
  router.post("/:id/enable", guardedWrite("channel_enable", (req, res) => {
    const db = getDB();
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const channelId = req.params.id;

    try {
      // Check if all required onboarding steps are completed
      const incomplete = db.prepare(`
        SELECT COUNT(*) as count 
        FROM comms_onboarding_steps 
        WHERE channel_id = ? AND status != 'completed' AND status != 'skipped'
      `).get(channelId);

      if (incomplete && incomplete.count > 0) {
        return res.status(400).json({ 
          error: "Cannot enable channel: incomplete onboarding steps",
          incomplete_steps: incomplete.count 
        });
      }

      wdb.prepare(`
        UPDATE comms_channels 
        SET enabled = 1, 
            setup_complete = 1, 
            updated_at = datetime('now')
        WHERE id = ?
      `).run(channelId);

      auditLog(wdb, "channel-enable", JSON.stringify({ channel_id: channelId }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  // PATCH /api/channels/:id — update channel settings
  router.patch("/:id", guardedWrite("channel_update", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const channelId = req.params.id;
    const updates = req.body;

    try {
      const allowedFields = [
        'display_name', 'icon', 'privacy_level', 'content_storage',
        'outbound_requires_approval', 'reply_channel_default', 'sort_order'
      ];

      const updateFields = [];
      const params = [];

      for (const field of allowedFields) {
        if (updates[field] !== undefined) {
          updateFields.push(`${field} = ?`);
          params.push(updates[field]);
        }
      }

      if (updateFields.length === 0) {
        return res.status(400).json({ error: "No valid fields to update" });
      }

      // Handle config_json separately
      if (updates.config_json) {
        updateFields.push("config_json = ?");
        params.push(JSON.stringify(updates.config_json));
      }

      params.push(channelId);

      wdb.prepare(`
        UPDATE comms_channels 
        SET ${updateFields.join(', ')}, updated_at = datetime('now')
        WHERE id = ?
      `).run(...params);

      auditLog(wdb, "channel-update", JSON.stringify({
        channel_id: channelId,
        fields: Object.keys(updates),
      }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.status(500).json({ error: e.message });
    }
  }));

  return router;
}
