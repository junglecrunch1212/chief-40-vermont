#!/usr/bin/env node
/**
 * seed.mjs — Comprehensive PIB Demo Data
 * 
 * Populates a fresh database with realistic data exercising ALL PIB v5 features:
 * - 4 household members (James, Laura, Charlie, Baby)
 * - 15+ tasks across all domains with micro-scripts
 * - 5+ recurring templates (daily, weekly, monthly)
 * - Active streaks for each member
 * - Energy states with medication tracking
 * - 8+ calendar events including custody handoffs
 * - 3+ shopping lists
 * - Life phases (prep, newborn pending)
 * - Coach protocols
 * - Budget categories with spend data
 * - Scoreboard data
 * - Charlie's chores with star values
 * 
 * Usage: node console/seed.mjs /path/to/pib.db
 */

import Database from "better-sqlite3";
import { readFileSync, readdirSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const MIGRATIONS_DIR = join(ROOT, "migrations");

// ═══════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════

function today() {
  return new Date().toISOString().split('T')[0];
}

function isoNow() {
  return new Date().toISOString().slice(0, 19) + 'Z';
}

function yesterday() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d.toISOString().split('T')[0];
}

function tomorrow() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return d.toISOString().split('T')[0];
}

function nextWeek() {
  const d = new Date();
  d.setDate(d.getDate() + 7);
  return d.toISOString().split('T')[0];
}

function lastWeek() {
  const d = new Date();
  d.setDate(d.getDate() - 7);
  return d.toISOString().split('T')[0];
}

// ═══════════════════════════════════════════════════════════
// MIGRATION RUNNER
// ═══════════════════════════════════════════════════════════

function runMigrations(db) {
  console.log("Running migrations from", MIGRATIONS_DIR);
  
  // Get all .sql files, sorted by number prefix
  const files = readdirSync(MIGRATIONS_DIR)
    .filter(f => f.endsWith('.sql'))
    .sort((a, b) => {
      const aNum = parseInt(a.split('_')[0]);
      const bNum = parseInt(b.split('_')[0]);
      return aNum - bNum;
    });
  
  for (const file of files) {
    const path = join(MIGRATIONS_DIR, file);
    const sql = readFileSync(path, 'utf-8');
    
    console.log(`  Applying ${file}...`);
    
    // Strip DOWN section (rollback SQL) and execute only the UP portion
    const upOnly = sql.split('-- DOWN')[0];
    try {
      db.exec(upOnly);
    } catch (err) {
      if (!err.message.includes('already exists') && 
          !err.message.includes('duplicate column') &&
          !err.message.includes('no such table')) {
        console.error(`    ERROR: ${err.message}`);
      }
    }
  }
  
  console.log("Migrations complete.\n");
}

// ═══════════════════════════════════════════════════════════
// SEED DATA
// ═══════════════════════════════════════════════════════════

function seedData(db) {
  console.log("Seeding demo data...\n");
  
  // Disable foreign keys temporarily (migration 009 leaves dangling project_step_ref)
  db.pragma("foreign_keys = OFF");
  
  // ─── Members ───
  console.log("  Members...");
  
  db.prepare(`
    INSERT INTO common_members (
      id, display_name, role, is_household_member, is_adult, 
      can_be_assigned_tasks, can_receive_messages,
      phone, email, imessage_handle, preferred_channel,
      view_mode, digest_mode, velocity_cap,
      energy_markers, medication_config, active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    'm-james', 'James', 'parent', 1, 1, 1, 1,
    '+14045550100', 'james@example.com', 'james@example.com', 'imessage',
    'carousel', 'full', 15,
    JSON.stringify({ peak_hours: ["9-11", "14-16"], crash_hours: ["13-14", "18-19"] }),
    JSON.stringify({ peak_onset_minutes: 30, peak_duration_minutes: 240, crash_start_minutes: 360 }),
    1
  );
  
  db.prepare(`
    INSERT INTO common_members (
      id, display_name, role, is_household_member, is_adult, 
      can_be_assigned_tasks, can_receive_messages,
      phone, email, imessage_handle, preferred_channel,
      view_mode, digest_mode, velocity_cap, active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    'm-laura', 'Laura', 'parent', 1, 1, 1, 1,
    '+14045550101', 'laura@example.com', 'laura@example.com', 'imessage',
    'compressed', 'compressed', 8, 1
  );
  
  db.prepare(`
    INSERT INTO common_members (
      id, display_name, role, is_household_member, is_adult, 
      can_be_assigned_tasks, can_receive_messages,
      age, school, view_mode, active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    'm-charlie', 'Charlie', 'child', 1, 0, 1, 0,
    6, 'Peachtree Elementary', 'child', 1
  );
  
  db.prepare(`
    INSERT INTO common_members (
      id, display_name, role, is_household_member, is_adult, 
      can_be_assigned_tasks, can_receive_messages,
      expected_arrival, view_mode, active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    'm-baby', 'Baby Girl', 'child', 1, 0, 0, 0,
    '2026-05-15', 'entity', 1
  );
  
  // ─── Tasks ───
  console.log("  Tasks...");
  
  const tasks = [
    // Household domain
    { id: 't-001', title: 'Call roofer about leak estimate', status: 'next', assignee: 'm-james',
      domain: 'household', item_type: 'task', due_date: yesterday(), energy: 'medium', effort: 'small',
      micro_script: 'Pick up phone → search "Dan Roofer" → tap call → ask about Saturday availability for leak inspection',
      points: 3 },
    { id: 't-002', title: 'Replace HVAC filter', status: 'next', assignee: 'm-james',
      domain: 'household', item_type: 'maintenance', due_date: today(), energy: 'low', effort: 'tiny',
      micro_script: 'Walk to utility closet → remove old filter → unwrap new 16x25x1 from shelf → slide in → done',
      points: 2 },
    { id: 't-003', title: 'Schedule handyman for baby room paint', status: 'next', assignee: 'm-james',
      domain: 'household', item_type: 'task', due_date: nextWeek(), energy: 'medium', effort: 'small',
      micro_script: 'Open Contacts → tap "Mike (Handyman)" → text "Available to paint nursery week of March 10?"',
      points: 3 },
    
    // Health domain
    { id: 't-004', title: 'Schedule Charlie dentist appointment', status: 'next', assignee: 'm-laura',
      domain: 'health', item_type: 'appointment', due_date: tomorrow(), energy: 'medium', effort: 'small',
      micro_script: 'Call 404-555-DENT → ask for 6-month checkup for Charlie → pick afternoon slot',
      points: 2 },
    { id: 't-005', title: 'Pick up prescription refill', status: 'done', assignee: 'm-james',
      domain: 'health', item_type: 'task', due_date: yesterday(), energy: 'low', effort: 'tiny',
      micro_script: 'Drive to CVS → give name at counter → pay → done',
      completed_at: isoNow(), completed_by: 'm-james', points: 1 },
    { id: 't-006', title: 'Captain heartworm medication', status: 'next', assignee: 'm-james',
      domain: 'health', item_type: 'maintenance', due_date: today(), energy: 'low', effort: 'tiny',
      micro_script: 'Open kitchen drawer → unwrap pill → hide in cheese → give to Captain → log on calendar',
      points: 1 },
    
    // Finance domain
    { id: 't-007', title: 'Pay electric bill', status: 'done', assignee: 'm-james',
      domain: 'finance', item_type: 'task', due_date: yesterday(), energy: 'low', effort: 'tiny',
      micro_script: 'Open Georgia Power app → tap Pay Now → confirm $147 → done',
      completed_at: isoNow(), completed_by: 'm-james', points: 1 },
    { id: 't-008', title: 'Review March budget spreadsheet', status: 'waiting_on', assignee: 'm-laura',
      domain: 'finance', item_type: 'task', due_date: nextWeek(), energy: 'high', effort: 'medium',
      waiting_on: 'Laura', notes: 'Waiting for Laura to open shared sheet' },
    { id: 't-009', title: 'File receipt for baby crib', status: 'inbox', assignee: 'm-james',
      domain: 'finance', item_type: 'task', energy: 'low', effort: 'tiny',
      micro_script: 'Find receipt in email → forward to receipts@household.com → archive',
      points: 1 },
    
    // Admin domain
    { id: 't-010', title: 'Sign Charlie field trip permission form', status: 'next', assignee: 'm-laura',
      domain: 'admin', item_type: 'decision', due_date: tomorrow(), energy: 'low', effort: 'tiny',
      micro_script: 'Check backpack → find yellow form → sign bottom → put back in folder',
      points: 1 },
    { id: 't-011', title: 'Update emergency contact sheet for school', status: 'deferred', assignee: 'm-james',
      domain: 'admin', item_type: 'task', scheduled_date: nextWeek(), energy: 'medium', effort: 'small',
      micro_script: 'Open school portal → click Forms → update phone numbers → submit',
      points: 2 },
    
    // Family domain
    { id: 't-012', title: 'Plan meals for this week', status: 'next', assignee: 'm-james',
      domain: 'family', item_type: 'task', due_date: today(), energy: 'medium', effort: 'medium',
      micro_script: 'Open Notes → list 5 dinners → add ingredients to grocery list → done',
      points: 3 },
    { id: 't-013', title: 'Research car seats for baby', status: 'inbox', assignee: 'm-laura',
      domain: 'family', item_type: 'research', energy: 'high', effort: 'large',
      micro_script: 'Open Wirecutter → read car seat guide → bookmark top 3 options → email James',
      points: 5 },
    
    // Chores (Charlie)
    { id: 't-014', title: 'Made bed', status: 'done', assignee: 'm-charlie',
      domain: 'family', item_type: 'chore', due_date: today(), energy: 'low', effort: 'tiny',
      micro_script: 'Pull covers up → fluff pillow → smooth blanket',
      completed_at: isoNow(), completed_by: 'm-charlie', points: 2 },
    { id: 't-015', title: 'Put dishes in sink', status: 'done', assignee: 'm-charlie',
      domain: 'family', item_type: 'chore', due_date: today(), energy: 'low', effort: 'tiny',
      micro_script: 'Carry plate and cup to sink → rinse → done',
      completed_at: isoNow(), completed_by: 'm-charlie', points: 1 },
    { id: 't-016', title: 'Put away backpack', status: 'next', assignee: 'm-charlie',
      domain: 'family', item_type: 'chore', due_date: today(), energy: 'low', effort: 'tiny',
      micro_script: 'Pick up backpack → hang on hook by door',
      points: 2 },
    { id: 't-017', title: 'Feed Captain', status: 'next', assignee: 'm-charlie',
      domain: 'family', item_type: 'chore', due_date: today(), energy: 'low', effort: 'tiny',
      micro_script: 'Scoop 1 cup dog food → pour in bowl → fill water bowl',
      points: 3 },
  ];
  
  const insertTask = db.prepare(`
    INSERT INTO ops_tasks (
      id, title, status, assignee, domain, item_type, due_date, scheduled_date,
      energy, effort, micro_script, waiting_on, points, notes, completed_at, completed_by,
      project_step_ref
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
  `);
  
  for (const t of tasks) {
    insertTask.run(
      t.id, t.title, t.status, t.assignee, t.domain, t.item_type,
      t.due_date || null, t.scheduled_date || null,
      t.energy || null, t.effort || null, t.micro_script || '', t.waiting_on || null,
      t.points || 1, t.notes || null, t.completed_at || null, t.completed_by || null
    );
  }
  
  // ─── Recurring ───
  console.log("  Recurring templates...");
  
  const recurring = [
    { id: 'r-001', title: 'Morning medication', type: 'daily', frequency: 'daily', days: null,
      assignee: 'm-james', for_member: 'm-james', domain: 'health',
      next_due: today(), lead_days: 0, effort: 'tiny', energy: 'low',
      micro_script_template: 'Take pill bottle from medicine cabinet → swallow with water → log time in energy state',
      points: 1, active: 1 },
    { id: 'r-002', title: 'Walk Captain (morning)', type: 'daily', frequency: 'daily', days: null,
      assignee: 'm-james', for_member: null, domain: 'household',
      next_due: today(), lead_days: 0, effort: 'small', energy: 'low',
      micro_script_template: 'Leash on Captain → walk around block → 15 minutes → done',
      points: 2, active: 1 },
    { id: 'r-003', title: 'Walk Captain (evening)', type: 'daily', frequency: 'daily', days: null,
      assignee: 'm-james', for_member: null, domain: 'household',
      next_due: today(), lead_days: 0, effort: 'small', energy: 'low',
      micro_script_template: 'Leash on Captain → walk around block → 15 minutes → done',
      points: 2, active: 1 },
    { id: 'r-004', title: 'Meal planning Sunday', type: 'weekly', frequency: 'weekly', days: 'Sunday',
      assignee: 'm-james', for_member: null, domain: 'family',
      next_due: nextWeek(), lead_days: 1, effort: 'medium', energy: 'medium',
      micro_script_template: 'Review calendar → plan 5 dinners → add ingredients to grocery list',
      points: 5, active: 1 },
    { id: 'r-005', title: 'Captain heartworm meds', type: 'monthly', frequency: 'monthly', days: '1',
      assignee: 'm-james', for_member: null, domain: 'health',
      next_due: '2026-04-01', lead_days: 2, effort: 'tiny', energy: 'low',
      micro_script_template: 'Get pill from drawer → hide in cheese → give to Captain → mark calendar',
      points: 1, active: 1 },
    { id: 'r-006', title: 'Replace HVAC filter', type: 'monthly', frequency: 'monthly', days: '15',
      assignee: 'm-james', for_member: null, domain: 'household',
      next_due: '2026-03-15', lead_days: 0, effort: 'tiny', energy: 'low',
      micro_script_template: 'Remove old filter from utility closet → unwrap new 16x25x1 → slide in',
      points: 2, active: 1 },
  ];
  
  const insertRecurring = db.prepare(`
    INSERT INTO ops_recurring (
      id, title, type, frequency, days, assignee, for_member, domain,
      next_due, lead_days, effort, energy, micro_script_template, points, active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const r of recurring) {
    insertRecurring.run(
      r.id, r.title, r.type, r.frequency, r.days, r.assignee, r.for_member,
      r.domain, r.next_due, r.lead_days, r.effort, r.energy,
      r.micro_script_template, r.points, r.active
    );
  }
  
  // ─── Streaks ───
  console.log("  Streaks...");
  
  db.prepare(`
    INSERT INTO ops_streaks (
      member_id, streak_type, current_streak, best_streak, last_completion_date,
      grace_days_used, max_grace_days, custody_pause_enabled
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run('m-james', 'daily_completion', 12, 18, yesterday(), 0, 1, 0);
  
  db.prepare(`
    INSERT INTO ops_streaks (
      member_id, streak_type, current_streak, best_streak, last_completion_date,
      grace_days_used, max_grace_days, custody_pause_enabled
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run('m-laura', 'daily_completion', 8, 14, yesterday(), 1, 1, 0);
  
  db.prepare(`
    INSERT INTO ops_streaks (
      member_id, streak_type, current_streak, best_streak, last_completion_date,
      grace_days_used, max_grace_days, custody_pause_enabled
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `).run('m-charlie', 'daily_completion', 4, 7, yesterday(), 0, 1, 1);
  
  // ─── Energy States ───
  console.log("  Energy states...");
  
  db.prepare(`
    INSERT INTO pib_energy_states (
      member_id, state_date, meds_taken, meds_taken_at,
      sleep_quality, completions_today, energy_level
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run('m-james', today(), 1, '07:32', 'great', 2, 'high');
  
  db.prepare(`
    INSERT INTO pib_energy_states (
      member_id, state_date, meds_taken, meds_taken_at,
      sleep_quality, completions_today, energy_level
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run('m-laura', today(), 0, null, 'okay', 0, 'medium');
  
  // ─── Calendar Events ───
  console.log("  Calendar events...");
  
  const events = [
    { id: 'cal-001', event_date: today(), start_time: '07:30', end_time: '07:45', all_day: 0,
      title: 'Medication window', title_redacted: 'Medication window',
      event_type: 'routine', category: 'health', for_member_ids: '["m-james"]',
      scheduling_impact: 'FYI', privacy: 'full' },
    { id: 'cal-002', event_date: today(), start_time: '09:00', end_time: '10:00', all_day: 0,
      title: 'Work: Partner call', title_redacted: 'Laura — meeting',
      event_type: 'calendar', category: 'work', for_member_ids: '["m-laura"]',
      scheduling_impact: 'HARD_BLOCK', privacy: 'privileged' },
    { id: 'cal-003', event_date: today(), start_time: '12:00', end_time: '12:30', all_day: 0,
      title: 'Lunch prep', title_redacted: 'Lunch prep',
      event_type: 'routine', category: 'family', for_member_ids: '["m-james"]',
      scheduling_impact: 'SOFT_BLOCK', privacy: 'full' },
    { id: 'cal-004', event_date: today(), start_time: '15:30', end_time: '16:00', all_day: 0,
      title: 'Charlie pickup', title_redacted: 'Charlie pickup',
      event_type: 'routine', category: 'family', for_member_ids: '["m-james"]',
      scheduling_impact: 'HARD_BLOCK', privacy: 'full', prep_minutes: 10, travel_minutes_to: 15 },
    { id: 'cal-005', event_date: today(), start_time: '18:00', end_time: '18:30', all_day: 0,
      title: 'Dinner', title_redacted: 'Dinner',
      event_type: 'routine', category: 'family', for_member_ids: '[]',
      scheduling_impact: 'SOFT_BLOCK', privacy: 'full' },
    { id: 'cal-006', event_date: tomorrow(), start_time: '08:15', end_time: '08:30', all_day: 0,
      title: 'Charlie drop-off', title_redacted: 'Charlie drop-off',
      event_type: 'routine', category: 'family', for_member_ids: '["m-james"]',
      scheduling_impact: 'HARD_BLOCK', privacy: 'full', travel_minutes_to: 15 },
    { id: 'cal-007', event_date: tomorrow(), start_time: '14:00', end_time: '16:00', all_day: 0,
      title: 'Work: Depositions', title_redacted: 'Laura — unavailable',
      event_type: 'calendar', category: 'work', for_member_ids: '["m-laura"]',
      scheduling_impact: 'HARD_BLOCK', privacy: 'redacted' },
    { id: 'cal-008', event_date: nextWeek(), start_time: '17:00', end_time: '17:30', all_day: 0,
      title: 'Custody handoff: Mike', title_redacted: 'Custody handoff',
      event_type: 'custody', category: 'family', for_member_ids: '["m-james"]',
      scheduling_impact: 'HARD_BLOCK', privacy: 'full', prep_minutes: 15 },
  ];
  
  const insertEvent = db.prepare(`
    INSERT INTO cal_classified_events (
      id, event_date, start_time, end_time, all_day, title, title_redacted,
      event_type, category, for_member_ids, scheduling_impact, privacy,
      prep_minutes, travel_minutes_to
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const e of events) {
    insertEvent.run(
      e.id, e.event_date, e.start_time, e.end_time, e.all_day,
      e.title, e.title_redacted, e.event_type, e.category, e.for_member_ids,
      e.scheduling_impact, e.privacy, e.prep_minutes || null, e.travel_minutes_to || null
    );
  }
  
  // ─── Lists ───
  console.log("  Shopping lists...");
  
  const lists = [
    { list_name: 'grocery', item_text: 'Whole milk (gallon)', quantity: 1, unit: 'gallon', category: 'dairy', checked: 0, added_by: 'm-james' },
    { list_name: 'grocery', item_text: 'Eggs (18 ct)', quantity: 18, unit: 'count', category: 'dairy', checked: 0, added_by: 'm-james' },
    { list_name: 'grocery', item_text: 'Bananas', quantity: 6, unit: 'count', category: 'produce', checked: 0, added_by: 'm-james' },
    { list_name: 'grocery', item_text: 'Ground beef', quantity: 2, unit: 'lb', category: 'meat', checked: 0, added_by: 'm-james' },
    { list_name: 'grocery', item_text: 'Bread (whole wheat)', quantity: 1, unit: 'loaf', category: 'bakery', checked: 0, added_by: 'm-james' },
    
    { list_name: 'honey-do', item_text: 'Fix leaky faucet in guest bath', category: 'plumbing', checked: 0, added_by: 'm-laura' },
    { list_name: 'honey-do', item_text: 'Replace garage door opener battery', category: 'maintenance', checked: 0, added_by: 'm-laura' },
    { list_name: 'honey-do', item_text: 'Hang curtain rod in nursery', category: 'baby-prep', checked: 0, added_by: 'm-laura' },
    
    { list_name: 'packing', item_text: 'Onesies (6 pack)', quantity: 6, unit: 'pack', category: 'clothing', checked: 0, added_by: 'm-laura' },
    { list_name: 'packing', item_text: 'Diapers (newborn size)', quantity: 2, unit: 'box', category: 'essentials', checked: 0, added_by: 'm-laura' },
    { list_name: 'packing', item_text: 'Wipes', quantity: 3, unit: 'pack', category: 'essentials', checked: 0, added_by: 'm-laura' },
    { list_name: 'packing', item_text: 'Pacifiers', quantity: 4, unit: 'count', category: 'essentials', checked: 0, added_by: 'm-james' },
  ];
  
  const insertList = db.prepare(`
    INSERT INTO ops_lists (list_name, item_text, quantity, unit, category, checked, added_by)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const item of lists) {
    insertList.run(
      item.list_name, item.item_text, item.quantity || null, item.unit || null,
      item.category || null, item.checked, item.added_by
    );
  }
  
  // ─── Life Phases ───
  console.log("  Life phases...");
  
  db.prepare(`
    INSERT INTO common_life_phases (id, name, status, start_date, end_date, description, overrides)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(
    'phase-prep', 'Pre-Baby Prep', 'active', '2026-02-01', '2026-05-15',
    'Nesting mode. Reduced velocity cap, baby-related task prioritization.',
    JSON.stringify({ velocity_cap: 12, suppress_crm_nudges: true })
  );
  
  db.prepare(`
    INSERT INTO common_life_phases (id, name, status, start_date, end_date, description, overrides)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `).run(
    'phase-newborn', 'Newborn Survival', 'pending', '2026-05-15', '2026-08-15',
    'First 3 months. Ultra-low velocity cap, suppress non-critical alerts.',
    JSON.stringify({ velocity_cap: 5, max_proactive: 2 })
  );
  
  // ─── Coach Protocols ───
  console.log("  Coach protocols...");
  
  const protocols = [
    { id: 'cp-001', name: 'Momentum Ride', trigger_condition: '3+ completions in session',
      behavior: 'Ask: want to ride it or bank it?', active: 1 },
    { id: 'cp-002', name: 'Paralysis Detection', trigger_condition: '2h silence during peak hours',
      behavior: 'Gentle check-in with tiniest restart option', active: 1 },
    { id: 'cp-003', name: 'Energy Match', trigger_condition: 'Low energy period',
      behavior: 'Present only tiny/small tasks, validate rest', active: 1 },
  ];
  
  const insertProtocol = db.prepare(`
    INSERT INTO pib_coach_protocols (id, name, trigger_condition, behavior, active)
    VALUES (?, ?, ?, ?, ?)
  `);
  
  for (const p of protocols) {
    insertProtocol.run(p.id, p.name, p.trigger_condition, p.behavior, p.active);
  }
  
  // ─── Budget Categories ───
  console.log("  Budget categories...");
  
  const budget = [
    { category: 'Groceries', monthly_target: 800, is_fixed: 0, is_discretionary: 0, alert_threshold: 0.90 },
    { category: 'Dining', monthly_target: 300, is_fixed: 0, is_discretionary: 1, alert_threshold: 0.80 },
    { category: 'Gas', monthly_target: 200, is_fixed: 0, is_discretionary: 0, alert_threshold: 0.90 },
    { category: 'Entertainment', monthly_target: 150, is_fixed: 0, is_discretionary: 1, alert_threshold: 0.80 },
  ];
  
  const insertBudget = db.prepare(`
    INSERT INTO fin_budget_config (category, monthly_target, is_fixed, is_discretionary, alert_threshold)
    VALUES (?, ?, ?, ?, ?)
  `);
  
  for (const b of budget) {
    insertBudget.run(b.category, b.monthly_target, b.is_fixed, b.is_discretionary, b.alert_threshold);
  }
  
  // Add some spending
  const firstOfMonth = today().slice(0, 8) + '01';
  
  db.prepare(`
    INSERT INTO fin_transactions (transaction_date, merchant_raw, merchant_normalized, amount, category, account)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(today(), 'PUBLIX #1234', 'Publix', -127.45, 'Groceries', 'Chase Checking');
  
  db.prepare(`
    INSERT INTO fin_transactions (transaction_date, merchant_raw, merchant_normalized, amount, category, account)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(yesterday(), 'CHIPOTLE', 'Chipotle', -28.50, 'Dining', 'Chase Checking');
  
  db.prepare(`
    INSERT INTO fin_transactions (transaction_date, merchant_raw, merchant_normalized, amount, category, account)
    VALUES (?, ?, ?, ?, ?, ?)
  `).run(lastWeek(), 'SHELL GAS', 'Shell', -52.00, 'Gas', 'Chase Checking');
  
  // ─── Custody Config ───
  console.log("  Custody configuration...");
  
  db.prepare(`
    INSERT INTO common_custody_configs (
      child_id, schedule_type, anchor_date, anchor_parent, other_parent,
      transition_day, transition_time, midweek_visit_enabled, active, effective_from
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run(
    'm-charlie', 'alternating_weeks', '2026-03-03', 'm-james', 'coparent-mike',
    'Thursday', '17:00', 0, 1, '2026-01-01'
  );
  
  // Add coparent Mike
  db.prepare(`
    INSERT INTO common_members (
      id, display_name, role, is_household_member, is_adult,
      can_be_assigned_tasks, can_receive_messages, phone, active
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `).run('coparent-mike', 'Mike', 'coparent', 0, 1, 0, 1, '+14045550199', 1);
  
  // ─── Config ───
  console.log("  Runtime config...");
  
  db.prepare(`
    INSERT INTO pib_config (key, value, description)
    VALUES (?, ?, ?)
  `).run('anthropic_model_sonnet', 'claude-sonnet-4-5-20250929', 'Routine queries');
  
  db.prepare(`
    INSERT INTO pib_config (key, value, description)
    VALUES (?, ?, ?)
  `).run('anthropic_model_opus', 'claude-opus-4-6', 'Complex queries');
  
  db.prepare(`
    INSERT INTO pib_config (key, value, description)
    VALUES (?, ?, ?)
  `).run('household_timezone', 'America/New_York', 'Atlanta');
  
  // ─── Devices ───
  console.log("  Devices...");
  
  const devices = [
    { id: 'dev-mac-mini', display_name: 'Mac Mini (Home)', device_type: 'mac', status: 'active',
      owner_member_id: 'm-james', location: 'Home office' },
    { id: 'dev-james-iphone', display_name: 'James iPhone', device_type: 'ios', status: 'active',
      owner_member_id: 'm-james' },
    { id: 'dev-laura-iphone', display_name: 'Laura iPhone', device_type: 'ios', status: 'active',
      owner_member_id: 'm-laura' },
  ];
  
  const insertDevice = db.prepare(`
    INSERT INTO comms_devices (id, display_name, device_type, status, owner_member_id, location, config_json, active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const d of devices) {
    insertDevice.run(d.id, d.display_name, d.device_type, d.status, d.owner_member_id, d.location || null, '{}', 1);
  }
  
  // ─── Accounts ───
  console.log("  Accounts...");
  
  const accountsData = [
    { id: 'acc-gmail-james', account_type: 'email', address: 'james@example.com', display_name: 'James Gmail',
      owner_member_id: 'm-james', provider: 'gmail', auth_status: 'active' },
    { id: 'acc-apple-james', account_type: 'phone', address: '+14045550100', display_name: 'James iMessage',
      owner_member_id: 'm-james', provider: 'apple', auth_status: 'active' },
    { id: 'acc-apple-laura', account_type: 'phone', address: '+14045550101', display_name: 'Laura iMessage',
      owner_member_id: 'm-laura', provider: 'apple', auth_status: 'active' },
    { id: 'acc-outlook-laura', account_type: 'email', address: 'laura.smith@lawfirm.com', display_name: 'Laura Work Email',
      owner_member_id: 'm-laura', provider: 'outlook', auth_status: 'active' },
  ];
  
  const insertAccount = db.prepare(`
    INSERT INTO comms_accounts (id, account_type, address, display_name, owner_member_id, provider, auth_status, capabilities_json, config_json, active)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const a of accountsData) {
    insertAccount.run(a.id, a.account_type, a.address, a.display_name, a.owner_member_id, a.provider, a.auth_status, '{}', '{}', 1);
  }
  
  // ─── Channels ───
  console.log("  Channels...");
  
  const channelsData = [
    { id: 'ch-gmail-james', display_name: 'Gmail (James)', icon: '📧', category: 'conversational',
      adapter_id: 'email', enabled: 1, setup_complete: 1,
      privacy_level: 'full', content_storage: 'full', outbound_requires_approval: 1,
      config_json: JSON.stringify({ capabilities: ['in', 'out', 'draft', 'extract'], account_id: 'acc-gmail-james' }) },
    { id: 'ch-imessage-james', display_name: 'iMessage (James)', icon: '💬', category: 'conversational',
      adapter_id: 'imessage', enabled: 1, setup_complete: 1,
      privacy_level: 'full', content_storage: 'full', outbound_requires_approval: 0,
      config_json: JSON.stringify({ capabilities: ['in', 'out'], account_id: 'acc-apple-james', device_id: 'dev-james-iphone' }) },
    { id: 'ch-sms-james', display_name: 'SMS (James)', icon: '💬', category: 'conversational',
      adapter_id: 'sms', enabled: 1, setup_complete: 1,
      privacy_level: 'full', content_storage: 'full', outbound_requires_approval: 1,
      config_json: JSON.stringify({ capabilities: ['in', 'out'], account_id: 'acc-apple-james' }) },
    { id: 'ch-voice-james', display_name: 'Voice Memos (James)', icon: '🎤', category: 'capture',
      adapter_id: 'voice', enabled: 1, setup_complete: 1,
      privacy_level: 'full', content_storage: 'full', outbound_requires_approval: 0,
      config_json: JSON.stringify({ capabilities: ['in', 'extract', 'voice'], device_id: 'dev-james-iphone' }) },
    { id: 'ch-outlook-laura', display_name: 'Outlook (Laura Work)', icon: '📨', category: 'conversational',
      adapter_id: 'email', enabled: 1, setup_complete: 1,
      privacy_level: 'metadata_only', content_storage: 'metadata_only', outbound_requires_approval: 1,
      config_json: JSON.stringify({ capabilities: ['in'], account_id: 'acc-outlook-laura' }) },
  ];
  
  const insertChannel = db.prepare(`
    INSERT INTO comms_channels (id, display_name, icon, category, adapter_id, enabled, setup_complete,
      privacy_level, content_storage, outbound_requires_approval, config_json, sort_order)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const ch of channelsData) {
    insertChannel.run(ch.id, ch.display_name, ch.icon, ch.category, ch.adapter_id, ch.enabled, ch.setup_complete,
      ch.privacy_level, ch.content_storage, ch.outbound_requires_approval, ch.config_json, 100);
  }
  
  // ─── Channel Health ───
  console.log("  Channel health...");
  
  for (const ch of channelsData) {
    db.prepare(`
      INSERT INTO comms_channel_health (channel_id, status, consecutive_failures, last_poll_at, last_successful_at)
      VALUES (?, ?, ?, ?, ?)
    `).run(ch.id, ch.enabled ? 'active' : 'inactive', 0, isoNow(), isoNow());
  }
  
  // ─── Member Channel Access ───
  console.log("  Member channel access...");
  
  const memberAccess = [
    // James admin on most
    { member_id: 'm-james', channel_id: 'ch-gmail-james', access_level: 'admin', can_approve_drafts: 1, batch_window: 'morning' },
    { member_id: 'm-james', channel_id: 'ch-imessage-james', access_level: 'admin', can_approve_drafts: 1, batch_window: 'evening' },
    { member_id: 'm-james', channel_id: 'ch-sms-james', access_level: 'admin', can_approve_drafts: 1, batch_window: 'evening' },
    { member_id: 'm-james', channel_id: 'ch-voice-james', access_level: 'admin', can_approve_drafts: 1, batch_window: null },
    { member_id: 'm-james', channel_id: 'ch-outlook-laura', access_level: 'read', can_approve_drafts: 0, batch_window: null },
    
    // Laura admin on her channels
    { member_id: 'm-laura', channel_id: 'ch-outlook-laura', access_level: 'admin', can_approve_drafts: 1, batch_window: 'midday' },
    { member_id: 'm-laura', channel_id: 'ch-gmail-james', access_level: 'read', can_approve_drafts: 0, batch_window: null },
    { member_id: 'm-laura', channel_id: 'ch-imessage-james', access_level: 'read', can_approve_drafts: 0, batch_window: null },
  ];
  
  const insertAccess = db.prepare(`
    INSERT INTO comms_channel_member_access (id, member_id, channel_id, access_level, can_approve_drafts, batch_window,
      show_in_inbox, receives_proactive, digest_include, notify_on_urgent)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const ma of memberAccess) {
    const id = `ca-${ma.member_id}-${ma.channel_id}`;
    insertAccess.run(id, ma.member_id, ma.channel_id, ma.access_level, ma.can_approve_drafts, ma.batch_window || null,
      1, 1, 1, ma.access_level === 'admin' ? 1 : 0);
  }
  
  // ─── Comms Messages ───
  console.log("  Comms messages...");
  
  const comms = [
    { id: 'comm-001', date: today(), channel: 'ch-gmail-james', direction: 'inbound',
      from_addr: 'contractor@example.com', to_addr: 'james@example.com', member_id: 'm-james',
      subject: 'Re: Baby room painting estimate', summary: 'Contractor confirming Saturday 9am appointment',
      body_snippet: 'Hi James, confirming our appointment this Saturday at 9am to give you an estimate for the nursery painting. Should take about 30 minutes.',
      needs_response: 1, response_urgency: 'timely', batch_window: 'morning', outcome: 'pending' },
    { id: 'comm-002', date: today(), channel: 'ch-imessage-james', direction: 'inbound',
      from_addr: '+14045559999', to_addr: '+14045550100', member_id: 'm-james',
      subject: null, summary: 'Charlie school pickup coordination',
      body_snippet: 'Hey can you grab Charlie today? Running late from meeting.',
      needs_response: 1, response_urgency: 'urgent', batch_window: null, outcome: 'pending' },
    { id: 'comm-003', date: yesterday(), channel: 'ch-gmail-james', direction: 'inbound',
      from_addr: 'newsletter@pottery-barn.com', to_addr: 'james@example.com', member_id: 'm-james',
      subject: 'New baby furniture sale', summary: 'Marketing newsletter',
      body_snippet: 'Save 20% on all nursery furniture this weekend only!',
      needs_response: 0, response_urgency: 'normal', batch_window: 'evening', outcome: 'handled' },
    { id: 'comm-004', date: today(), channel: 'ch-outlook-laura', direction: 'inbound',
      from_addr: 'partner@lawfirm.com', to_addr: 'laura.smith@lawfirm.com', member_id: 'm-laura',
      subject: 'Client deposition rescheduled', summary: '[Privileged] Work calendar update',
      body_snippet: null, needs_response: 0, response_urgency: 'timely', batch_window: 'midday', outcome: 'handled' },
    { id: 'comm-005', date: today(), channel: 'ch-voice-james', direction: 'inbound',
      from_addr: null, to_addr: null, member_id: 'm-james',
      subject: null, summary: 'Voice capture: grocery list additions',
      body_snippet: 'Captured items: bananas, peanut butter, bread',
      needs_response: 0, response_urgency: 'normal', batch_window: null, outcome: 'handled',
      extraction_status: 'completed', extracted_items: JSON.stringify(['bananas', 'peanut butter', 'bread']) },
    { id: 'comm-006', date: today(), channel: 'ch-gmail-james', direction: 'outbound',
      from_addr: 'james@example.com', to_addr: 'roofer@example.com', member_id: 'm-james',
      subject: 'Re: Roof leak estimate', summary: 'Draft reply to roofer',
      body_snippet: null, needs_response: 0, draft_status: 'pending',
      draft_response: 'Hi Dan, Saturday works great. See you at 9am. Thanks!',
      batch_window: 'morning', outcome: 'draft' },
  ];
  
  const insertComm = db.prepare(`
    INSERT INTO ops_comms (id, date, channel, direction, from_addr, to_addr, member_id, item_ref, task_ref,
      thread_id, subject, summary, body_snippet, needs_response, response_urgency, batch_window, batch_date,
      extraction_status, extracted_items, draft_response, draft_status, snoozed_until, outcome)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const c of comms) {
    insertComm.run(
      c.id, c.date, c.channel, c.direction, c.from_addr || null, c.to_addr || null, c.member_id,
      c.item_ref || null, c.task_ref || null, c.thread_id || null, c.subject || null,
      c.summary, c.body_snippet || null, c.needs_response || 0, c.response_urgency || 'normal',
      c.batch_window || null, c.batch_date || c.date, c.extraction_status || 'none',
      c.extracted_items || null, c.draft_response || null, c.draft_status || 'none',
      c.snoozed_until || null, c.outcome || 'pending'
    );
  }
  
  // ─── Captures ───
  console.log("  Capture demo data...");
  
  // Seed notebooks
  const notebooks = [
    { id: 'nb-inbox', member_id: 'm-james', name: 'Inbox', slug: 'inbox', icon: '📥', is_system: 1 },
    { id: 'nb-kitchen', member_id: null, name: 'Kitchen', slug: 'kitchen', icon: '🍽️', is_system: 0 },
    { id: 'nb-ideas', member_id: 'm-james', name: 'Ideas', slug: 'ideas', icon: '💡', is_system: 0 },
    { id: 'nb-reference', member_id: 'm-james', name: 'Reference', slug: 'reference', icon: '📚', is_system: 0 },
    { id: 'nb-kids', member_id: null, name: 'Kids', slug: 'kids', icon: '👶', is_system: 0 },
    { id: 'nb-home', member_id: null, name: 'Home', slug: 'home', icon: '🏠', is_system: 0 },
    { id: 'nb-health', member_id: 'm-james', name: 'Health', slug: 'health', icon: '💊', is_system: 0 },
  ];
  
  const insertNotebook = db.prepare(`
    INSERT INTO cap_notebooks (id, member_id, name, slug, icon, is_system)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  
  for (const nb of notebooks) {
    insertNotebook.run(nb.id, nb.member_id, nb.name, nb.slug, nb.icon, nb.is_system);
  }
  
  // Seed captures
  const captures = [
    // Inbox/unsorted (2)
    {
      id: 'cap-001', member_id: 'm-james', raw_text: 'Voice note: Remember to ask Mike about the custody swap next Thursday. He mentioned possibly switching to Wednesday instead.',
      title: 'Mike custody schedule change', capture_type: 'note', source: 'voice', notebook: 'inbox',
      triage_status: 'raw', created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
    },
    {
      id: 'cap-002', member_id: 'm-james', raw_text: 'Need to research best practices for introducing solid foods to babies. Laura mentioned baby-led weaning.',
      title: 'Baby solid foods research', capture_type: 'note', source: 'chat', notebook: 'inbox',
      triage_status: 'raw', created_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString()
    },
    
    // Kitchen/recipes (2)
    {
      id: 'cap-003', member_id: 'm-james',
      raw_text: 'One-pot chicken and rice: Brown 4 chicken thighs, remove. Sauté onion and garlic, add 2 cups rice, 3 cups broth. Return chicken, simmer 25min covered. Charlie loved it!',
      title: 'One-Pot Chicken and Rice', body: 'Simple weeknight winner. Charlie devoured this.',
      capture_type: 'recipe', source: 'chat', notebook: 'kitchen', triage_status: 'organized',
      recipe_data: JSON.stringify({
        servings: 4,
        prep_min: 10,
        cook_min: 30,
        difficulty: 'Easy',
        meal_type: 'Dinner',
        cuisine: 'Comfort',
        kid_approved: true,
        made_count: 3,
        rating: 5,
        last_made_at: yesterday()
      }),
      created_at: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000).toISOString()
    },
    {
      id: 'cap-004', member_id: 'm-james',
      raw_text: 'Breakfast egg muffins: Beat 8 eggs, add cheese, veggies, pour into muffin tin, bake 20min at 350F. Freezes great for quick mornings.',
      title: 'Make-Ahead Egg Muffins', body: 'Perfect for busy mornings. Can make a batch on Sunday.',
      capture_type: 'recipe', source: 'chat', notebook: 'kitchen', triage_status: 'organized',
      recipe_data: JSON.stringify({
        servings: 6,
        prep_min: 15,
        cook_min: 20,
        difficulty: 'Easy',
        meal_type: 'Breakfast',
        cuisine: 'American',
        kid_approved: true,
        made_count: 0,
        rating: 0
      }),
      created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
    },
    
    // Kids (1)
    {
      id: 'cap-005', member_id: 'm-james',
      raw_text: 'Charlie school note: Spring field trip to zoo on March 18. Need signed permission slip and $15 by Friday. Pack lunch.',
      title: 'Charlie zoo field trip - March 18', capture_type: 'note', source: 'chat', notebook: 'kids',
      triage_status: 'organized', tags: JSON.stringify(['school', 'deadline', 'Charlie']),
      created_at: new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString()
    },
    
    // Home (1)
    {
      id: 'cap-006', member_id: 'm-james',
      raw_text: 'Contractor quote from Dan: Roof leak repair over nursery - $850. Includes flashing replacement and shingle patch. Available next Saturday.',
      title: 'Roof leak quote - $850', capture_type: 'note', source: 'voice', notebook: 'home',
      triage_status: 'organized', tags: JSON.stringify(['contractor', 'home-repair', 'quote']),
      created_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString()
    },
    
    // Health (1)
    {
      id: 'cap-007', member_id: 'm-james',
      raw_text: 'Dr. Stevens instructions: Take medication 30min before breakfast for best absorption. If evening dose causes sleep issues, can switch to morning double dose after consulting.',
      title: 'Medication timing notes from Dr. Stevens', capture_type: 'log', source: 'chat', notebook: 'health',
      triage_status: 'organized', tags: JSON.stringify(['medication', 'doctor', 'instructions']),
      created_at: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000).toISOString()
    },
    
    // Ideas (1 pinned)
    {
      id: 'cap-008', member_id: 'm-james',
      raw_text: 'Blog post idea: "The ADHD Parent\'s Survival Guide to Newborn Sleep Deprivation" - cover energy management, medication timing, partner coordination, when to ask for help.',
      title: 'Blog: ADHD + Newborn Sleep', capture_type: 'idea', source: 'chat', notebook: 'ideas',
      triage_status: 'organized', pinned: 1, tags: JSON.stringify(['blog', 'adhd', 'parenting']),
      created_at: new Date(Date.now() - 6 * 24 * 60 * 60 * 1000).toISOString()
    },
    
    // Reference (1 archived)
    {
      id: 'cap-009', member_id: 'm-james',
      raw_text: 'Captain vet record: Annual checkup Feb 12, 2026. Weight 68lbs (up 2lbs). Heartworm negative. Bordatella booster given. Next appointment Aug 2026.',
      title: 'Captain vet visit - Feb 2026', capture_type: 'reference', source: 'chat', notebook: 'reference',
      triage_status: 'organized', archived: 1, archived_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
      created_at: new Date(Date.now() - 21 * 24 * 60 * 60 * 1000).toISOString()
    },
  ];
  
  const insertCapture = db.prepare(`
    INSERT INTO cap_captures (
      id, member_id, raw_text, title, body, capture_type, source, notebook,
      triage_status, tags, pinned, archived, archived_at, recipe_data, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  
  for (const cap of captures) {
    insertCapture.run(
      cap.id, cap.member_id, cap.raw_text, cap.title, cap.body || null,
      cap.capture_type, cap.source, cap.notebook, cap.triage_status,
      cap.tags || null, cap.pinned || 0, cap.archived || 0, cap.archived_at || null,
      cap.recipe_data || null, cap.created_at
    );
  }
  
  // Re-enable foreign keys
  db.pragma("foreign_keys = ON");
  
  console.log("\n✅ Seed complete!");
}

// ═══════════════════════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════════════════════

function main() {
  const dbPath = process.argv[2];
  
  if (!dbPath) {
    console.error("Usage: node console/seed.mjs /path/to/pib.db");
    process.exit(1);
  }
  
  console.log(`\n🌱 PIB v5 Seed — ${dbPath}\n`);
  
  // Open database
  const db = new Database(dbPath);
  db.pragma("journal_mode = WAL");
  db.pragma("foreign_keys = ON");
  
  try {
    // Run migrations
    runMigrations(db);
    
    // Seed data
    seedData(db);
    
    db.close();
    console.log("\n🎉 Database seeded successfully!\n");
    
  } catch (err) {
    console.error("\n❌ Seed failed:", err.message);
    console.error(err.stack);
    db.close();
    process.exit(1);
  }
}

main();
