/**
 * console/brain_routes.mjs
 * Express router for PIB Memory Browser operations
 */

import { Router } from "express";
import crypto from "crypto";

export function createBrainRouter(getDB, auditLog, guardedWrite) {
  const router = Router();

  // GET /api/brain/memory — list memories with filters
  router.get("/memory", (req, res) => {
    const db = getDB();
    const memberId = req.memberId;
    const { category, domain, limit = 50 } = req.query;

    try {
      // Build base query with filters
      let sql = `
        SELECT * FROM mem_long_term 
        WHERE (member_id = ? OR member_id IS NULL)
          AND superseded_by IS NULL
      `;
      const params = [memberId];

      if (category) {
        sql += " AND category = ?";
        params.push(category);
      }

      if (domain) {
        sql += " AND domain = ?";
        params.push(domain);
      }

      sql += " ORDER BY updated_at DESC LIMIT ?";
      params.push(parseInt(limit, 10));

      const memories = db.prepare(sql).all(...params);

      // Get unique categories
      const categories = db.prepare(`
        SELECT DISTINCT category FROM mem_long_term 
        WHERE (member_id = ? OR member_id IS NULL)
          AND superseded_by IS NULL
          AND category IS NOT NULL
        ORDER BY category
      `).all(memberId);

      // Get unique domains
      const domains = db.prepare(`
        SELECT DISTINCT domain FROM mem_long_term 
        WHERE (member_id = ? OR member_id IS NULL)
          AND superseded_by IS NULL
          AND domain IS NOT NULL
        ORDER BY domain
      `).all(memberId);

      res.json({ 
        memories, 
        categories: categories.map(c => c.category),
        domains: domains.map(d => d.domain)
      });
    } catch (e) {
      res.json({ 
        error: e.message, 
        memories: [], 
        categories: [], 
        domains: [] 
      });
    }
  });

  // GET /api/brain/memory/search — FTS5 search
  router.get("/memory/search", (req, res) => {
    const db = getDB();
    const memberId = req.memberId;
    const { q } = req.query;

    try {
      if (!q || q.trim().length === 0) {
        return res.json({ results: [] });
      }

      // Sanitize FTS5 query - strip special chars
      const sanitized = q
        .replace(/[\*\"\(\)]/g, '')
        .replace(/\b(OR|AND|NOT)\b/gi, '')
        .trim();

      if (sanitized.length === 0) {
        return res.json({ results: [] });
      }

      try {
        // Try FTS5 search first
        const results = db.prepare(`
          SELECT m.* 
          FROM mem_long_term m
          INNER JOIN mem_long_term_fts fts ON fts.rowid = m.id
          WHERE fts MATCH ?
            AND (m.member_id = ? OR m.member_id IS NULL)
            AND m.superseded_by IS NULL
          ORDER BY rank
          LIMIT 50
        `).all(sanitized, memberId);

        res.json({ results });
      } catch (ftsError) {
        // Fall back to LIKE search
        const likePattern = `%${sanitized}%`;
        const results = db.prepare(`
          SELECT * FROM mem_long_term
          WHERE (content LIKE ? OR category LIKE ? OR domain LIKE ?)
            AND (member_id = ? OR member_id IS NULL)
            AND superseded_by IS NULL
          ORDER BY updated_at DESC
          LIMIT 50
        `).all(likePattern, likePattern, likePattern, memberId);

        res.json({ results });
      }
    } catch (e) {
      res.json({ error: e.message, results: [] });
    }
  });

  // PUT /api/brain/memory/:id — update memory content
  router.put("/memory/:id", guardedWrite("memory-update", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const memoryId = req.params.id;
    const { content } = req.body;

    if (!content || content.trim().length === 0) {
      return res.status(400).json({ error: "content required" });
    }

    try {
      wdb.prepare(`
        UPDATE mem_long_term 
        SET content = ?, updated_at = datetime('now')
        WHERE id = ?
      `).run(content, memoryId);

      auditLog(wdb, "memory-update", JSON.stringify({
        memory_id: memoryId,
        content_length: content.length,
      }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.json({ error: e.message, ok: false });
    }
  }));

  // POST /api/brain/memory/:id/supersede — supersede with new memory
  router.post("/memory/:id/supersede", guardedWrite("memory-supersede", (req, res) => {
    const db = getDB();
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const memoryId = req.params.id;
    const { new_content } = req.body;

    if (!new_content || new_content.trim().length === 0) {
      return res.status(400).json({ error: "new_content required" });
    }

    try {
      // Read old memory to get category and domain
      const oldMemory = db.prepare(`
        SELECT category, domain, member_id FROM mem_long_term WHERE id = ?
      `).get(memoryId);

      if (!oldMemory) {
        return res.status(404).json({ error: "Memory not found" });
      }

      // Insert new memory
      const result = wdb.prepare(`
        INSERT INTO mem_long_term (
          category, content, domain, member_id, 
          source, reinforcement_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, 'user_stated', 1, datetime('now'), datetime('now'))
      `).run(
        oldMemory.category,
        new_content,
        oldMemory.domain,
        oldMemory.member_id
      );

      const newId = result.lastInsertRowid;

      // Update old memory to mark as superseded
      wdb.prepare(`
        UPDATE mem_long_term 
        SET superseded_by = ?, updated_at = datetime('now')
        WHERE id = ?
      `).run(newId, memoryId);

      auditLog(wdb, "memory-supersede", JSON.stringify({
        old_memory_id: memoryId,
        new_memory_id: newId,
      }), memberId);

      res.json({ ok: true, new_id: newId });
    } catch (e) {
      res.json({ error: e.message, ok: false });
    }
  }));

  // DELETE /api/brain/memory/:id — soft delete (set superseded_by = -1)
  router.delete("/memory/:id", guardedWrite("memory-delete", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const memoryId = req.params.id;

    try {
      wdb.prepare(`
        UPDATE mem_long_term 
        SET superseded_by = -1, updated_at = datetime('now')
        WHERE id = ?
      `).run(memoryId);

      auditLog(wdb, "memory-delete", JSON.stringify({
        memory_id: memoryId,
      }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.json({ error: e.message, ok: false });
    }
  }));

  // GET /api/brain/working — list working context items
  router.get("/working", (req, res) => {
    const db = getDB();
    const memberId = req.memberId;

    try {
      const items = db.prepare(`
        SELECT * FROM mem_working_context
        WHERE member_id = ?
          AND (expires_at IS NULL OR expires_at > datetime('now'))
        ORDER BY created_at DESC
      `).all(memberId);

      res.json({ items });
    } catch (e) {
      // Table may not exist
      res.json({ items: [], error: e.message });
    }
  });

  // POST /api/brain/working — create working context item
  router.post("/working", guardedWrite("working-context-create", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const { content, context_type, expires_at, source } = req.body;

    if (!content || content.trim().length === 0) {
      return res.status(400).json({ error: "content required" });
    }

    try {
      const id = crypto.randomUUID();

      wdb.prepare(`
        INSERT INTO mem_working_context (
          id, content, context_type, member_id, expires_at, source, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
      `).run(
        id,
        content,
        context_type || null,
        memberId,
        expires_at || null,
        source || 'manual'
      );

      auditLog(wdb, "working-context-create", JSON.stringify({
        id,
        context_type,
      }), memberId);

      res.json({ ok: true, id });
    } catch (e) {
      res.json({ error: e.message, ok: false });
    }
  }));

  // DELETE /api/brain/working/:id — delete working context item
  router.delete("/working/:id", guardedWrite("working-context-delete", (req, res) => {
    const wdb = req.writeDB;
    const memberId = req.memberId;
    const itemId = req.params.id;

    try {
      wdb.prepare(`
        DELETE FROM mem_working_context 
        WHERE id = ? AND member_id = ?
      `).run(itemId, memberId);

      auditLog(wdb, "working-context-delete", JSON.stringify({
        id: itemId,
      }), memberId);

      res.json({ ok: true });
    } catch (e) {
      res.json({ error: e.message, ok: false });
    }
  }));

  return router;
}
