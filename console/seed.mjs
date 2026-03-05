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
    
    // Execute entire file as one block (SQLite handles multiple statements)
    try {
      db.exec(sql);
    } catch (err) {
      // Log errors but continue (some migrations may reference non-existent tables)
      if (!err.message.includes('already exists') && 
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
