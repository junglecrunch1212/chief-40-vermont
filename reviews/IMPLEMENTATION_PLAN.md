# PIB v5 Console — Implementation Plan
**Based on:** COMPREHENSIVE_GAP_ANALYSIS.md  
**Execution:** Phased rollout, API-first, test-covered

---

## Phase 1: Financial Domain (P0) — 2-3 days

### API Endpoints (add to server.mjs)

```javascript
// ─── Financial Transactions ───
app.get("/api/financial/transactions", requireMember, (req, res) => {
  const d = getDB();
  const { from, to, category, merchant, limit = 100 } = req.query;
  
  let sql = "SELECT * FROM fin_transactions WHERE 1=1";
  const params = [];
  
  if (from) {
    sql += " AND transaction_date >= ?";
    params.push(from);
  }
  if (to) {
    sql += " AND transaction_date <= ?";
    params.push(to);
  }
  if (category) {
    sql += " AND category = ?";
    params.push(category);
  }
  if (merchant) {
    sql += " AND merchant_normalized LIKE ?";
    params.push(`%${merchant}%`);
  }
  
  sql += " ORDER BY transaction_date DESC, posted_date DESC LIMIT ?";
  params.push(parseInt(limit, 10));
  
  const transactions = d.prepare(sql).all(...params);
  res.json({ transactions });
});

app.get("/api/financial/transactions/:id", requireMember, (req, res) => {
  const d = getDB();
  const txn = d.prepare("SELECT * FROM fin_transactions WHERE id = ?").get(req.params.id);
  if (!txn) return res.status(404).json({ error: "Transaction not found" });
  res.json({ transaction: txn });
});

app.post("/api/financial/transactions/:id/categorize", requireMember, guardedWrite("financial_categorize", (req, res) => {
  const wdb = req.writeDB;
  const { category, subcategory } = req.body;
  
  if (!category) {
    return res.status(400).json({ error: "category required" });
  }
  
  wdb.prepare(`
    UPDATE fin_transactions 
    SET category = ?, subcategory = ?, needs_review = 0
    WHERE id = ?
  `).run(category, subcategory || null, req.params.id);
  
  auditLog(wdb, "transaction-categorize", JSON.stringify({ id: req.params.id, category, subcategory }), req.memberId);
  
  res.json({ ok: true });
}));

// ─── Merchant Rules ───
app.get("/api/financial/merchant-rules", requireMember, (req, res) => {
  const d = getDB();
  const rules = d.prepare(
    "SELECT * FROM fin_merchant_rules WHERE active = 1 ORDER BY priority, id"
  ).all();
  res.json({ rules });
});

app.post("/api/financial/merchant-rules", requireMember, guardedWrite("financial_rule_add", (req, res) => {
  const wdb = req.writeDB;
  const { pattern, match_type, category, subcategory, normalized_name, priority } = req.body;
  
  if (!pattern || !category) {
    return res.status(400).json({ error: "pattern and category required" });
  }
  
  wdb.prepare(`
    INSERT INTO fin_merchant_rules (pattern, match_type, category, subcategory, normalized_name, priority)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(pattern, match_type || 'contains', category, subcategory || null, normalized_name || null, priority || 100);
  
  auditLog(wdb, "merchant-rule-add", JSON.stringify({ pattern, category }), req.memberId);
  
  res.json({ ok: true });
}));

app.patch("/api/financial/merchant-rules/:id", requireMember, guardedWrite("financial_rule_update", (req, res) => {
  const wdb = req.writeDB;
  const updates = req.body;
  const allowed = ['pattern', 'match_type', 'category', 'subcategory', 'normalized_name', 'priority'];
  
  const fields = [];
  const params = [];
  
  for (const field of allowed) {
    if (updates[field] !== undefined) {
      fields.push(`${field} = ?`);
      params.push(updates[field]);
    }
  }
  
  if (fields.length === 0) {
    return res.status(400).json({ error: "No valid fields to update" });
  }
  
  params.push(req.params.id);
  
  wdb.prepare(`UPDATE fin_merchant_rules SET ${fields.join(', ')} WHERE id = ?`).run(...params);
  auditLog(wdb, "merchant-rule-update", JSON.stringify({ id: req.params.id, ...updates }), req.memberId);
  
  res.json({ ok: true });
}));

app.delete("/api/financial/merchant-rules/:id", requireMember, guardedWrite("financial_rule_delete", (req, res) => {
  const wdb = req.writeDB;
  wdb.prepare("UPDATE fin_merchant_rules SET active = 0 WHERE id = ?").run(req.params.id);
  auditLog(wdb, "merchant-rule-delete", JSON.stringify({ id: req.params.id }), req.memberId);
  res.json({ ok: true });
}));

// ─── Capital Expenses ───
app.get("/api/financial/capital-expenses", requireMember, (req, res) => {
  const d = getDB();
  const expenses = d.prepare(
    "SELECT * FROM fin_capital_expenses WHERE status != 'cancelled' ORDER BY target_date"
  ).all();
  res.json({ expenses });
});

app.post("/api/financial/capital-expenses", requireMember, guardedWrite("financial_capital_add", (req, res) => {
  const wdb = req.writeDB;
  const { id, title, target_amount, target_date, monthly_contribution } = req.body;
  
  if (!id || !title || !target_amount) {
    return res.status(400).json({ error: "id, title, and target_amount required" });
  }
  
  wdb.prepare(`
    INSERT INTO fin_capital_expenses (id, title, target_amount, target_date, monthly_contribution)
    VALUES (?, ?, ?, ?, ?)
  `).run(id, title, target_amount, target_date || null, monthly_contribution || null);
  
  auditLog(wdb, "capital-expense-add", JSON.stringify({ id, title, target_amount }), req.memberId);
  
  res.json({ ok: true, id });
}));

app.patch("/api/financial/capital-expenses/:id", requireMember, guardedWrite("financial_capital_update", (req, res) => {
  const wdb = req.writeDB;
  const updates = req.body;
  const allowed = ['target_amount', 'target_date', 'monthly_contribution', 'accumulated', 'status'];
  
  const fields = [];
  const params = [];
  
  for (const field of allowed) {
    if (updates[field] !== undefined) {
      fields.push(`${field} = ?`);
      params.push(updates[field]);
    }
  }
  
  if (fields.length === 0) {
    return res.status(400).json({ error: "No valid fields to update" });
  }
  
  params.push(req.params.id);
  
  wdb.prepare(`UPDATE fin_capital_expenses SET ${fields.join(', ')}, updated_at = datetime('now') WHERE id = ?`).run(...params);
  auditLog(wdb, "capital-expense-update", JSON.stringify({ id: req.params.id, ...updates }), req.memberId);
  
  res.json({ ok: true });
}));

// ─── Recurring Bills ───
app.get("/api/financial/bills", requireMember, (req, res) => {
  const d = getDB();
  const bills = d.prepare(
    "SELECT * FROM fin_recurring_bills WHERE active = 1 ORDER BY next_due"
  ).all();
  res.json({ bills });
});

app.post("/api/financial/bills", requireMember, guardedWrite("financial_bill_add", (req, res) => {
  const wdb = req.writeDB;
  const { title, amount, category, due_day, frequency, next_due } = req.body;
  
  if (!title || !amount || !category || !next_due) {
    return res.status(400).json({ error: "title, amount, category, next_due required" });
  }
  
  wdb.prepare(`
    INSERT INTO fin_recurring_bills (title, amount, category, due_day, frequency, next_due)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(title, amount, category, due_day || null, frequency || 'monthly', next_due);
  
  auditLog(wdb, "bill-add", JSON.stringify({ title, amount, category }), req.memberId);
  
  res.json({ ok: true });
}));

app.patch("/api/financial/bills/:id", requireMember, guardedWrite("financial_bill_update", (req, res) => {
  const wdb = req.writeDB;
  const updates = req.body;
  const allowed = ['title', 'amount', 'category', 'due_day', 'frequency', 'auto_pay', 'next_due', 'active'];
  
  const fields = [];
  const params = [];
  
  for (const field of allowed) {
    if (updates[field] !== undefined) {
      fields.push(`${field} = ?`);
      params.push(updates[field]);
    }
  }
  
  if (fields.length === 0) {
    return res.status(400).json({ error: "No valid fields to update" });
  }
  
  params.push(req.params.id);
  
  wdb.prepare(`UPDATE fin_recurring_bills SET ${fields.join(', ')} WHERE id = ?`).run(...params);
  auditLog(wdb, "bill-update", JSON.stringify({ id: req.params.id, ...updates }), req.memberId);
  
  res.json({ ok: true });
}));

// ─── Budget Config ───
app.post("/api/financial/budget", requireMember, guardedWrite("financial_budget_update", (req, res) => {
  const wdb = req.writeDB;
  const { category, monthly_target, is_fixed, is_discretionary, alert_threshold } = req.body;
  
  if (!category || monthly_target === undefined) {
    return res.status(400).json({ error: "category and monthly_target required" });
  }
  
  wdb.prepare(`
    INSERT INTO fin_budget_config (category, monthly_target, is_fixed, is_discretionary, alert_threshold)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(category) DO UPDATE SET
      monthly_target = excluded.monthly_target,
      is_fixed = excluded.is_fixed,
      is_discretionary = excluded.is_discretionary,
      alert_threshold = excluded.alert_threshold
  `).run(category, monthly_target, is_fixed || 0, is_discretionary || 1, alert_threshold || 0.9);
  
  auditLog(wdb, "budget-config-update", JSON.stringify({ category, monthly_target }), req.memberId);
  
  res.json({ ok: true });
}));
```

### UI Implementation (add to index.html)

```javascript
// Add to NAV array
{ id:'finance', icon:'dollar-sign', label:'Finance' },

// Add to ICONS
'dollar-sign': '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',

// Add finance page renderer
async function renderFinance() {
  const m = document.getElementById('main');
  const tab = new URLSearchParams(window.location.hash.slice(1)).get('tab') || 'transactions';
  
  let h = `
    <div class="fi">
      <h1 class="page-title">💰 Finance</h1>
      <div class="pill-tabs">
        <div class="pill ${tab==='transactions'?'active':''}" onclick="window.location.hash='#tab=transactions';renderPage()">Transactions</div>
        <div class="pill ${tab==='budget'?'active':''}" onclick="window.location.hash='#tab=budget';renderPage()">Budget</div>
        <div class="pill ${tab==='bills'?'active':''}" onclick="window.location.hash='#tab=bills';renderPage()">Bills</div>
        <div class="pill ${tab==='rules'?'active':''}" onclick="window.location.hash='#tab=rules';renderPage()">Merchant Rules</div>
        <div class="pill ${tab==='capital'?'active':''}" onclick="window.location.hash='#tab=capital';renderPage()">Capital Expenses</div>
      </div>
      <div id="finance-tab-content"></div>
    </div>
  `;
  
  m.innerHTML = h;
  
  if (tab === 'transactions') await renderFinanceTransactions();
  else if (tab === 'budget') await renderFinanceBudget();
  else if (tab === 'bills') await renderFinanceBills();
  else if (tab === 'rules') await renderFinanceMerchantRules();
  else if (tab === 'capital') await renderFinanceCapitalExpenses();
}

async function renderFinanceTransactions() {
  const container = document.getElementById('finance-tab-content');
  container.innerHTML = loading('Loading transactions...');
  
  try {
    const data = await GET('/api/financial/transactions?limit=50');
    const txns = data.transactions || [];
    
    let h = `
      <div style="margin-bottom:20px;display:flex;gap:12px;flex-wrap:wrap">
        <input type="date" id="txn-from" placeholder="From" style="width:auto">
        <input type="date" id="txn-to" placeholder="To" style="width:auto">
        <input type="text" id="txn-merchant" placeholder="Merchant" style="width:200px">
        <button class="btn-s btn-sm" onclick="filterTransactions()">Filter</button>
      </div>
      
      <div class="card-flat">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Merchant</th>
              <th>Amount</th>
              <th>Category</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
    `;
    
    for (const txn of txns) {
      const warn = txn.needs_review ? ' style="background:var(--warn-bg)"' : '';
      h += `
        <tr${warn}>
          <td>${esc(txn.transaction_date)}</td>
          <td>${esc(txn.merchant_normalized || txn.merchant_raw)}</td>
          <td style="font-family:var(--mono);${txn.amount < 0 ? 'color:var(--err)' : ''}">$${Math.abs(txn.amount).toFixed(2)}</td>
          <td><span class="badge badge-info">${esc(txn.category)}</span></td>
          <td>
            ${txn.needs_review ? `<button class="btn-s btn-sm" onclick="recategorizeTxn(${txn.id})">Categorize</button>` : '—'}
          </td>
        </tr>
      `;
    }
    
    h += `
          </tbody>
        </table>
      </div>
    `;
    
    container.innerHTML = h;
  } catch (e) {
    container.innerHTML = `<div class="card" style="color:var(--err)">Error: ${esc(e.message)}</div>`;
  }
}

async function renderFinanceBudget() {
  const container = document.getElementById('finance-tab-content');
  container.innerHTML = loading('Loading budget...');
  
  try {
    const data = await GET('/api/financial/summary');
    const categories = data.categories || [];
    
    let h = `
      <div class="card-flat">
        <div style="margin-bottom:16px;display:flex;justify-content:space-between;align-items:center">
          <div class="section-label">Monthly Budget</div>
          <button class="btn-s btn-sm" onclick="addBudgetCategory()">+ Add Category</button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Category</th>
              <th>Target</th>
              <th>Spent</th>
              <th>Remaining</th>
              <th>% Used</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
    `;
    
    for (const cat of categories) {
      const pct = cat.target ? (cat.spent / cat.target * 100).toFixed(0) : 0;
      const pctColor = pct > 90 ? 'var(--err)' : pct > 80 ? 'var(--warn)' : 'var(--grn)';
      
      h += `
        <tr>
          <td>${cat.icon || '💰'} ${esc(cat.cat)}</td>
          <td style="font-family:var(--mono)">$${cat.target.toFixed(2)}</td>
          <td style="font-family:var(--mono)">$${cat.spent.toFixed(2)}</td>
          <td style="font-family:var(--mono)">$${(cat.target - cat.spent).toFixed(2)}</td>
          <td>
            <div style="display:flex;align-items:center;gap:8px">
              <div style="flex:1;height:8px;background:var(--bd);border-radius:4px;overflow:hidden">
                <div style="width:${Math.min(100, pct)}%;height:100%;background:${pctColor};transition:width .3s"></div>
              </div>
              <span style="font-size:12px;font-family:var(--mono);color:${pctColor}">${pct}%</span>
            </div>
          </td>
          <td>
            <button class="btn-s btn-sm" onclick="editBudgetCategory('${esc(cat.cat)}')">Edit</button>
          </td>
        </tr>
      `;
    }
    
    h += `
          </tbody>
        </table>
      </div>
    `;
    
    container.innerHTML = h;
  } catch (e) {
    container.innerHTML = `<div class="card" style="color:var(--err)">Error: ${esc(e.message)}</div>`;
  }
}

// Add remaining tabs: Bills, Merchant Rules, Capital Expenses
// (Implementation follows same pattern)
```

Add governance gates to config/governance.yaml:

```yaml
action_gates:
  financial_categorize: true
  financial_rule_add: confirm
  financial_rule_update: true
  financial_rule_delete: confirm
  financial_capital_add: confirm
  financial_capital_update: true
  financial_bill_add: confirm
  financial_bill_update: true
  financial_budget_update: confirm
```

---

## Phase 2: Captures Domain (P0) — 3-4 days

Full implementation of Capture domain with FTS5 search, notebooks, deep organizer, and triage flow.

*(Implementation details to follow in separate patch file)*

---

## Phase 3: Projects Domain (P1) — 4-5 days

Autonomous project execution engine with phases, steps, gates, and research.

*(Implementation details to follow in separate patch file)*

---

## Testing Strategy

Each endpoint must have:
1. **Happy path test** (200 OK)
2. **Auth test** (401/403)
3. **Validation test** (400 bad request)
4. **Governance test** (gate enforcement)

Example test structure:

```javascript
// tests/api/financial.test.mjs
import { describe, it, expect } from 'vitest';
import request from 'supertest';
import app from '../console/server.mjs';

describe('Financial API', () => {
  it('GET /api/financial/transactions returns list', async () => {
    const res = await request(app)
      .get('/api/financial/transactions')
      .set('X-PIB-Member', 'm-james');
    expect(res.status).toBe(200);
    expect(res.body.transactions).toBeInstanceOf(Array);
  });
  
  it('POST /api/financial/transactions/:id/categorize requires category', async () => {
    const res = await request(app)
      .post('/api/financial/transactions/1/categorize')
      .set('X-PIB-Member', 'm-james')
      .send({});
    expect(res.status).toBe(400);
  });
  
  // ... more tests
});
```

---

## Deployment Checklist

- [ ] Run migration if schema changes
- [ ] Seed default data (protocols, onboarding steps, rules)
- [ ] Update pib-api-contract.md with new endpoints
- [ ] Test all endpoints with Postman/curl
- [ ] UI smoke test (click every tab)
- [ ] Governance gates tested
- [ ] Audit log writes verified
- [ ] Undo log populated for reversible actions
- [ ] Idempotency keys used for all writes
- [ ] Privacy fence tested (Laura can't see James privileged data)

