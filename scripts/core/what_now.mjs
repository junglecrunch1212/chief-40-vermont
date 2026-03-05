#!/usr/bin/env node
/**
 * what_now.mjs — THE ONE FUNCTION
 * 
 * Deterministic. NO LLM. Pure scoring function.
 * Input: member, current time, energy level, medication state, tasks, calendar, custody
 * Output: ONE task with score, micro-script, and rationale
 * 
 * From PIB v5 spec section 4: whatNow() — The single query the entire system exists to answer.
 */

import Database from "better-sqlite3";
import { parseArgs } from "node:util";

const EFFORT_ORDER = { tiny: 0, small: 1, medium: 2, large: 3 };
const ENERGY_LEVELS = { low: 0, medium: 1, high: 2 };

// ═══════════════════════════════════════════════════════════
// MAIN FUNCTION
// ═══════════════════════════════════════════════════════════

/**
 * whatNow() - Layer 1 deterministic task selection
 * @param {string} memberId 
 * @param {object} snapshot - Pre-fetched DB snapshot
 * @param {Date} now 
 * @returns {object} WhatNowResult
 */
function whatNow(memberId, snapshot, now = new Date()) {
  const today = now.toISOString().split('T')[0];
  const member = snapshot.members.find(m => m.id === memberId);
  if (!member) {
    return { error: "Member not found", the_one_task: null };
  }

  // ── 1. CALENDAR FILTER ──
  const currentBlock = findCurrentBlock(snapshot.calendar, now);
  if (currentBlock) {
    return {
      the_one_task: null,
      blocked_until: currentBlock.end_time,
      next_event: currentBlock,
      context: `In: ${currentBlock.title} until ${formatTime(currentBlock.end_time)}`,
      ...fillMeta(snapshot, memberId, today)
    };
  }

  // ── 2. VELOCITY CAP CHECK ──
  const energy = snapshot.energyState;
  const velocityCap = member.velocity_cap || 20;
  const completionsToday = energy?.completions_today || 0;
  
  if (completionsToday >= velocityCap) {
    return {
      the_one_task: breakTask(completionsToday),
      context: `🎉 ${completionsToday} done today! Take a break — you've earned it.`,
      ...fillMeta(snapshot, memberId, today)
    };
  }

  // ── 3. ENERGY MATCHING ──
  const energyLevel = computeEnergyLevel(energy, member, now);
  const energyFilter = getEnergyFilter(energyLevel);

  // ── 4. TASK SCORING (deterministic with all factors from spec) ──
  let candidates = snapshot.tasks.filter(t => 
    t.assignee === memberId &&
    ['next', 'in_progress', 'inbox'].includes(t.status) &&
    !isBlockedByDependency(t, snapshot.tasks) &&
    !isBlockedByCustody(t, snapshot.custodyState, memberId)
  );

  // Apply energy filter if available
  if (energyFilter && candidates.length > 0) {
    const filtered = candidates.filter(energyFilter);
    if (filtered.length > 0) {
      candidates = filtered;
    }
    // If filter removes ALL candidates, show unfiltered with energy note
  }

  // Calculate score for each task using all factors from spec
  for (const task of candidates) {
    task._score = calculateTaskScore(task, {
      today,
      energyLevel,
      energy,
      member,
      now,
      custodyState: snapshot.custodyState,
      streak: snapshot.streak
    });
  }

  // Sort by score (highest first)
  candidates.sort((a, b) => b._score - a._score);

  const theOne = candidates[0] || null;
  const oneMore = candidates[1] || null;

  // ── 5. NEXT EVENT ──
  const nextEvent = findNextEvent(snapshot.calendar, now);
  let timeUntil = null;
  if (nextEvent) {
    const prep = (nextEvent.prep_minutes || 0) + (nextEvent.travel_minutes_to || 0);
    const eventStart = new Date(nextEvent.start_time);
    timeUntil = (eventStart - now) / 60000 - prep; // minutes
  }

  // ── 6. CONTEXT STRING ──
  const contextParts = [];
  const overdueCount = candidates.filter(t => t.due_date && t.due_date < today).length;
  if (overdueCount > 0) {
    contextParts.push(`${overdueCount} overdue`);
  }
  const streak = snapshot.streak || {};
  if ((streak.current_streak || 0) > 0) {
    contextParts.push(`🔥 ${streak.current_streak}-day streak`);
  }
  if (energy?.meds_taken) {
    const phase = getMedicationPhase(energy, member, now);
    contextParts.push(`meds: ${phase}`);
  }
  if (energy?.sleep_quality === 'rough') {
    contextParts.push('rough sleep — easy day');
  }
  if (timeUntil && timeUntil < 60) {
    contextParts.push(`next event in ${Math.floor(timeUntil)}min`);
  }

  return {
    the_one_task: theOne,
    one_more_teaser: oneMore,
    blocked_until: null,
    next_event: nextEvent,
    streak: streak,
    velocity: { 
      today: completionsToday, 
      cap: velocityCap,
      remaining: velocityCap - completionsToday 
    },
    energy_state: {
      level: energyLevel,
      medication_phase: energy?.meds_taken ? getMedicationPhase(energy, member, now) : 'none',
      sleep: energy?.sleep_quality || 'unknown'
    },
    context: contextParts.length > 0 ? contextParts.join(' · ') : 'Clear day ahead'
  };
}

// ═══════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ═══════════════════════════════════════════════════════════

function findCurrentBlock(calendar, now) {
  if (!calendar || calendar.length === 0) return null;
  const nowTime = now.toISOString();
  return calendar.find(e => 
    e.scheduling_impact === 'HARD_BLOCK' &&
    e.start_time <= nowTime && 
    e.end_time > nowTime
  );
}

function findNextEvent(calendar, now) {
  if (!calendar || calendar.length === 0) return null;
  const nowTime = now.toISOString();
  const upcoming = calendar
    .filter(e => e.start_time > nowTime)
    .sort((a, b) => a.start_time.localeCompare(b.start_time));
  return upcoming[0] || null;
}

function computeEnergyLevel(energy, member, now) {
  // If explicit energy_level is set, use it
  if (energy?.energy_level) {
    return energy.energy_level;
  }

  // Rough sleep → cap at low
  if (energy?.sleep_quality === 'rough') {
    return 'low';
  }

  // Medication phase calculation (using medication_config from member)
  if (energy?.meds_taken) {
    try {
      const medConfig = JSON.parse(member.medication_config || '{}');
      if (medConfig.peak_onset_minutes && medConfig.peak_duration_minutes) {
        const medsTakenAt = energy.meds_taken_at; // Time string like "07:45"
        if (medsTakenAt) {
          const medsTakenMinutes = timeToMinutes(medsTakenAt);
          const nowMinutes = timeToMinutes(now.toTimeString().slice(0, 5));
          
          const peakStart = medsTakenMinutes + medConfig.peak_onset_minutes;
          const peakEnd = peakStart + medConfig.peak_duration_minutes;
          const crashStart = medsTakenMinutes + (medConfig.crash_start_minutes || 360);
          
          if (nowMinutes >= peakStart && nowMinutes <= peakEnd) {
            return 'high';
          }
          if (nowMinutes >= crashStart) {
            return 'low';
          }
        }
      }
    } catch (e) {
      // Invalid JSON, skip
    }
  }

  // Time-of-day defaults from member.energy_markers
  try {
    const markers = JSON.parse(member.energy_markers || '{}');
    const hour = now.getHours();
    
    if (markers.peak_hours) {
      for (const range of markers.peak_hours) {
        const [start, end] = range.split('-').map(Number);
        if (hour >= start && hour < end) {
          return 'high';
        }
      }
    }
    
    if (markers.crash_hours) {
      for (const range of markers.crash_hours) {
        const [start, end] = range.split('-').map(Number);
        if (hour >= start && hour < end) {
          return 'low';
        }
      }
    }
  } catch (e) {
    // Invalid JSON, skip
  }

  return 'medium';
}

function getEnergyFilter(level) {
  if (level === 'low') {
    return (t) => ['tiny', 'small'].includes(t.effort) && (!t.energy || t.energy === 'low');
  }
  if (level === 'high') {
    return (t) => !t.energy || ['medium', 'high'].includes(t.energy);
  }
  return null; // Medium: no filter
}

function isBlockedByDependency(task, allTasks) {
  // TODO: Implement dependency checking when ops_dependencies is populated
  return false;
}

function isBlockedByCustody(task, custodyState, memberId) {
  // TODO: Implement custody-aware task blocking
  return false;
}

function breakTask(completions) {
  return {
    id: 'break',
    title: 'Take a break',
    status: 'next',
    micro_script: 'Stand up → walk to kitchen → glass of water → 10 minutes off screens',
    energy: 'low',
    effort: 'tiny',
    notes: `You've done ${completions} things today. That's genuinely impressive. Rest.`
  };
}

function fillMeta(snapshot, memberId, today) {
  const streak = snapshot.streak || {};
  const energy = snapshot.energyState || {};
  const member = snapshot.members.find(m => m.id === memberId) || {};
  
  return {
    streak: {
      current: streak.current_streak || 0,
      best: streak.best_streak || 0,
      grace: streak.grace_days_used || 0
    },
    velocity: {
      today: energy.completions_today || 0,
      cap: member.velocity_cap || 20,
      remaining: (member.velocity_cap || 20) - (energy.completions_today || 0)
    },
    energy_state: {
      level: energy.energy_level || 'medium',
      sleep: energy.sleep_quality || 'unknown'
    }
  };
}

function formatTime(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

function timeToMinutes(timeStr) {
  if (!timeStr) return 0;
  const [h, m] = timeStr.split(':').map(Number);
  return h * 60 + m;
}

// ═══════════════════════════════════════════════════════════
// TASK SCORING — All factors from spec Section 4
// ═══════════════════════════════════════════════════════════

function calculateTaskScore(task, context) {
  let score = 0;
  const { today, energyLevel, energy, member, now, custodyState, streak } = context;
  
  // ── Due Date Urgency ──
  if (task.due_date) {
    if (task.due_date < today) {
      score += 500; // Overdue
    } else if (task.due_date === today) {
      score += 200; // Due today
    } else {
      const daysUntil = Math.floor(
        (new Date(task.due_date) - new Date(today)) / 86400000
      );
      if (daysUntil <= 7) {
        score += 50; // Due this week
      }
    }
  }
  
  // ── Energy Match ──
  if (task.energy) {
    const taskEnergyLevel = ENERGY_LEVELS[task.energy] || 1;
    const currentEnergyLevel = ENERGY_LEVELS[energyLevel] || 1;
    
    if (taskEnergyLevel === currentEnergyLevel) {
      score += 100; // Perfect match
    } else if (Math.abs(taskEnergyLevel - currentEnergyLevel) === 1) {
      score += 30; // Adjacent match
    } else {
      score -= 50; // Mismatch
    }
  }
  
  // ── Effort Match (low energy → small tasks only) ──
  if (energyLevel === 'low') {
    if (['tiny', 'small'].includes(task.effort)) {
      score += 50; // Good for low energy
    } else {
      score -= 100; // Too big for low energy
    }
  } else if (energyLevel === 'high') {
    if (['medium', 'large'].includes(task.effort)) {
      score += 30; // Good use of high energy
    }
  }
  
  // ── Domain Batching Bonus ──
  // TODO: Get last completed task's domain
  // For now, simplified: if domain matches yesterday's most-completed domain
  
  // ── Time-of-Day Fitness ──
  const hour = now.getHours();
  
  // Morning tasks (before noon)
  if (task.title.toLowerCase().includes('morning') || 
      task.title.toLowerCase().includes('breakfast')) {
    score += (hour < 12) ? 40 : -20;
  }
  
  // Afternoon/evening tasks
  if (task.title.toLowerCase().includes('afternoon') || 
      task.title.toLowerCase().includes('evening')) {
    score += (hour >= 12) ? 40 : -20;
  }
  
  // ── Streak Momentum ──
  if (streak && streak.current_streak > 0) {
    score += Math.min(streak.current_streak * 2, 40); // Max +40 for 20-day streak
  }
  
  // ── Medication Window ──
  if (energy?.meds_taken) {
    const medPhase = getMedicationPhase(energy, member, now);
    if (medPhase === 'peak') {
      // During peak: boost focus-requiring tasks
      if (task.energy === 'high' || task.effort === 'large') {
        score += 50;
      }
    } else if (medPhase === 'crash') {
      // During crash: penalize demanding tasks
      if (task.energy === 'high' || task.effort === 'large') {
        score -= 80;
      }
    }
  }
  
  // ── Custody Context ──
  // If Charlie is home, boost child-related tasks
  if (custodyState && task.domain === 'family') {
    score += 30;
  }
  
  // ── Status Priority ──
  const statusBonus = {
    'in_progress': 150, // Already started
    'next': 50,         // Queued
    'inbox': 0          // Not yet triaged
  };
  score += statusBonus[task.status] || 0;
  
  // ── Blocked/Waiting Penalty ──
  if (task.status === 'waiting_on') {
    score = -1000; // Remove from consideration
  }
  
  // ── Smallest First (tie-breaker) ──
  const effortPenalty = EFFORT_ORDER[task.effort || 'small'] || 1;
  score -= effortPenalty * 5; // Small penalty for larger tasks
  
  return score;
}

function getMedicationPhase(energy, member, now) {
  if (!energy?.meds_taken) return 'none';
  
  // Calculate phase from meds_taken_at + medication_config
  try {
    const medConfig = JSON.parse(member?.medication_config || '{}');
    if (!medConfig.peak_onset_minutes) return 'active';
    
    const medsTakenAt = energy.meds_taken_at;
    if (!medsTakenAt) return 'active';
    
    const medsTakenMinutes = timeToMinutes(medsTakenAt);
    const nowMinutes = timeToMinutes(now.toTimeString().slice(0, 5));
    
    const peakStart = medsTakenMinutes + medConfig.peak_onset_minutes;
    const peakEnd = peakStart + (medConfig.peak_duration_minutes || 240);
    const crashStart = medsTakenMinutes + (medConfig.crash_start_minutes || 360);
    
    if (nowMinutes >= peakStart && nowMinutes <= peakEnd) {
      return 'peak';
    }
    if (nowMinutes >= crashStart) {
      return 'crash';
    }
    if (nowMinutes < peakStart) {
      return 'onset';
    }
    
    return 'active';
  } catch (e) {
    return 'active';
  }
}

// ═══════════════════════════════════════════════════════════
// DATA SNAPSHOT LOADER
// ═══════════════════════════════════════════════════════════

function loadSnapshot(db, memberId) {
  const today = new Date().toISOString().split('T')[0];
  
  // Members
  const members = db.prepare("SELECT * FROM common_members WHERE active = 1").all();
  
  // Tasks
  const tasks = db.prepare(`
    SELECT * FROM ops_tasks 
    WHERE assignee = ? AND status NOT IN ('done', 'dismissed')
    ORDER BY due_date, created_at
  `).all(memberId);
  
  // Calendar (today only)
  const calendar = db.prepare(`
    SELECT * FROM cal_classified_events 
    WHERE event_date = ? 
    AND (for_member_ids = '[]' OR for_member_ids LIKE '%' || ? || '%')
    ORDER BY start_time
  `).all(today, memberId);
  
  // Energy state
  const energyState = db.prepare(`
    SELECT * FROM pib_energy_states 
    WHERE member_id = ? AND state_date = ?
  `).get(memberId, today);
  
  // Streak
  const streak = db.prepare(`
    SELECT * FROM ops_streaks 
    WHERE member_id = ? AND streak_type = 'daily_completion'
  `).get(memberId);
  
  // Custody state (simplified)
  const custodyState = null; // TODO: Implement custody state lookup
  
  return {
    members,
    tasks,
    calendar,
    energyState,
    streak,
    custodyState
  };
}

// ═══════════════════════════════════════════════════════════
// CLI INTERFACE
// ═══════════════════════════════════════════════════════════

function main() {
  const { values: args } = parseArgs({
    options: {
      member: { type: "string" },
      json: { type: "boolean", default: false },
      help: { type: "boolean", default: false },
      db: { type: "string" },
    },
    strict: false,
  });

  if (args.help) {
    console.log(`what_now.mjs — Get the single next task for a household member.

Usage: node scripts/core/what_now.mjs --member <id> [options]

Options:
  --member <id>   Member ID (required)
  --db <path>     Database path (default: PIB_DB_PATH env or /opt/pib/data/pib.db)
  --json          Output structured JSON
  --help          Show this help`);
    process.exit(0);
  }

  if (!args.member) {
    console.error("Error: --member <id> is required");
    process.exit(1);
  }

  const dbPath = args.db || process.env.PIB_DB_PATH || "/opt/pib/data/pib.db";
  
  try {
    const db = new Database(dbPath, { readonly: true });
    db.pragma("journal_mode = WAL");
    
    const snapshot = loadSnapshot(db, args.member);
    const result = whatNow(args.member, snapshot);
    
    db.close();
    
    if (args.json) {
      console.log(JSON.stringify(result, null, 2));
    } else {
      if (result.error) {
        console.error(`Error: ${result.error}`);
        process.exit(1);
      }
      
      if (result.the_one_task) {
        console.log(`\n🎯 Next: ${result.the_one_task.title}`);
        if (result.the_one_task.micro_script) {
          console.log(`\n   ${result.the_one_task.micro_script}`);
        }
        console.log(`\n   ${result.context}`);
        
        if (result.one_more_teaser) {
          const effortMap = { tiny: '2 min', small: '5 min', medium: '15 min', large: '30+ min' };
          const effort = effortMap[result.one_more_teaser.effort] || '5 min';
          console.log(`\n   One more? "${result.one_more_teaser.title}" — only ${effort}.`);
        }
      } else {
        console.log(`\n${result.context || 'Nothing pending right now.'}`);
      }
    }
  } catch (err) {
    console.error(`Error: ${err.message}`);
    process.exit(1);
  }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
  main();
}

// Export for use as module
export { whatNow, loadSnapshot };
