#!/usr/bin/env node
/**
 * behavioral_engine.mjs — Dark Prosthetics (Section 5)
 * 
 * Variable-ratio reinforcement, elastic streaks, endowed progress,
 * momentum detection, Zeigarnik hooks.
 * 
 * Pure functions. No database access. Called by server.mjs.
 */

// ═══════════════════════════════════════════════════════════
// VARIABLE-RATIO REINFORCEMENT (Section 5.1)
// ═══════════════════════════════════════════════════════════

const REWARD_SCHEDULE = [
  { prob: 0.60, tier: "simple", messages: [
    "Done.",
    "✓",
    "Logged.",
    "Got it ✓",
    "Checked off ✓"
  ]},
  { prob: 0.25, tier: "warm", messages: [
    "That's momentum.",
    "Solid. Keep rolling.",
    "Nice one.",
    "Another one bites the dust.",
    "You're in a groove.",
    "That's {today} today — nice run."
  ]},
  { prob: 0.10, tier: "celebration", messages: [
    "🎉 Crushing it!",
    "Three in a row!",
    "On fire today.",
    "🏆 {today} done — you're unstoppable.",
    "Streak preserved. Your future self thanks you.",
    "That task had been sitting there {days_old} days. It's finally free. 🦋"
  ]},
  { prob: 0.05, tier: "rare", messages: [
    "🏆 LEGENDARY. You just mass-cleared.",
    "Hall of fame move.",
    "🎰 Holy smokes — {today} tasks in one session. Personal record.",
    "💎 You've been on fire this week. {week} completed. The household runs because of you.",
    "🎉 JACKPOT! You cleared your entire overdue queue. This hasn't happened in {days_since_clear} days!"
  ]}
];

/**
 * Select reward tier and message using variable-ratio schedule.
 * @param {string} memberId 
 * @param {object} task - Completed task
 * @param {object} stats - Completion stats
 * @returns {{ tier: string, message: string }}
 */
export function selectReward(memberId, task, stats) {
  const roll = Math.random();
  let cumulative = 0;
  
  for (const { prob, tier, messages } of REWARD_SCHEDULE) {
    cumulative += prob;
    if (roll <= cumulative) {
      const template = messages[Math.floor(Math.random() * messages.length)];
      
      // Calculate task age
      const daysOld = task.created_at 
        ? Math.floor((Date.now() - new Date(task.created_at)) / 86400000)
        : 0;
      
      const message = template
        .replace('{today}', stats.completions_today || 0)
        .replace('{week}', stats.week_completions || 0)
        .replace('{days_old}', daysOld)
        .replace('{days_since_clear}', stats.days_since_clear || '?');
      
      return { tier, message };
    }
  }
  
  return { tier: "simple", message: "Done ✓" };
}

// ═══════════════════════════════════════════════════════════
// COMPLETION STATS (for reward context)
// ═══════════════════════════════════════════════════════════

/**
 * Get completion statistics for reward selection.
 * @param {object} db - Database connection (better-sqlite3)
 * @param {string} memberId 
 * @returns {object} Stats
 */
export function getCompletionStats(db, memberId) {
  const today = new Date().toISOString().split('T')[0];
  
  // Today's completions
  const todayRow = db.prepare(`
    SELECT completions_today FROM pib_energy_states 
    WHERE member_id = ? AND state_date = ?
  `).get(memberId, today);
  
  // Week completions (last 7 days)
  const weekStart = new Date();
  weekStart.setDate(weekStart.getDate() - 7);
  const weekStartStr = weekStart.toISOString().split('T')[0];
  
  const weekRow = db.prepare(`
    SELECT COUNT(*) as count FROM ops_tasks 
    WHERE assignee = ? AND status = 'done' 
    AND completed_at >= ?
  `).get(memberId, weekStartStr);
  
  // Days since all overdue cleared (simplified)
  const overdueRow = db.prepare(`
    SELECT COUNT(*) as count FROM ops_tasks 
    WHERE assignee = ? AND status NOT IN ('done','dismissed') 
    AND due_date < ?
  `).get(memberId, today);
  
  return {
    completions_today: todayRow?.completions_today || 0,
    week_completions: weekRow?.count || 0,
    days_since_clear: overdueRow?.count === 0 ? 0 : null,
  };
}

// ═══════════════════════════════════════════════════════════
// ELASTIC STREAKS (Section 5.2)
// ═══════════════════════════════════════════════════════════

/**
 * Update streak on task completion. Elastic with grace days.
 * @param {object} db - Database connection (better-sqlite3)
 * @param {string} memberId 
 * @param {string} completionDate - YYYY-MM-DD
 * @returns {object} Streak state
 */
export function updateStreak(db, memberId, completionDate) {
  const streak = db.prepare(`
    SELECT * FROM ops_streaks 
    WHERE member_id = ? AND streak_type = 'daily_completion'
  `).get(memberId);
  
  if (!streak) {
    // First completion — start streak
    db.prepare(`
      INSERT INTO ops_streaks 
      (member_id, streak_type, current_streak, best_streak, last_completion_date, max_grace_days)
      VALUES (?, 'daily_completion', 1, 1, ?, 1)
    `).run(memberId, completionDate);
    
    return { current: 1, best: 1, event: "started" };
  }
  
  const lastDate = new Date(streak.last_completion_date);
  const currentDate = new Date(completionDate);
  const gap = Math.floor((currentDate - lastDate) / 86400000);
  
  if (gap <= 0) {
    // Same day completion
    return { 
      current: streak.current_streak, 
      best: streak.best_streak, 
      event: "same_day" 
    };
  } else if (gap === 1) {
    // Next day — extend streak
    const newStreak = streak.current_streak + 1;
    const newBest = Math.max(newStreak, streak.best_streak);
    
    db.prepare(`
      UPDATE ops_streaks 
      SET current_streak = ?, best_streak = ?, last_completion_date = ?,
          grace_days_used = 0, updated_at = datetime('now')
      WHERE id = ?
    `).run(newStreak, newBest, completionDate, streak.id);
    
    const event = (newStreak === newBest && newStreak > 3) ? "new_record" : "extended";
    return { current: newStreak, best: newBest, event };
    
  } else if (gap === 2 && streak.grace_days_used < streak.max_grace_days) {
    // Grace period — 1 miss doesn't break
    const newStreak = streak.current_streak + 1;
    
    db.prepare(`
      UPDATE ops_streaks 
      SET current_streak = ?, last_completion_date = ?,
          grace_days_used = grace_days_used + 1, updated_at = datetime('now')
      WHERE id = ?
    `).run(newStreak, completionDate, streak.id);
    
    return { 
      current: newStreak, 
      best: streak.best_streak, 
      event: "grace_used",
      grace_days_used: streak.grace_days_used + 1
    };
    
  } else {
    // Streak broken — reset
    db.prepare(`
      UPDATE ops_streaks 
      SET current_streak = 1, last_completion_date = ?,
          grace_days_used = 0, updated_at = datetime('now')
      WHERE id = ?
    `).run(completionDate, streak.id);
    
    const event = (streak.current_streak >= 3) ? "reset_was_long" : "reset";
    return { current: 1, best: streak.best_streak, event };
  }
}

// ═══════════════════════════════════════════════════════════
// ZEIGARNIK HOOK ("One more?" nudge)
// ═══════════════════════════════════════════════════════════

const EFFORT_TEXT = {
  tiny: "2 min",
  small: "5 min",
  medium: "15 min",
  large: "30+ min"
};

/**
 * Generate "one more?" nudge from next task.
 * @param {object} task - Next task from whatNow
 * @returns {string|null}
 */
export function generateOneMoreNudge(task) {
  if (!task) return null;
  
  const effort = EFFORT_TEXT[task.effort] || "5 min";
  return `One more? "${task.title}" — only ${effort}.`;
}

// ═══════════════════════════════════════════════════════════
// ENDOWED PROGRESS (Section 5.5 Console Update)
// ═══════════════════════════════════════════════════════════

/**
 * Get endowed progress items for the day.
 * These are pre-credited dots that start the stream at 2+ instead of 0.
 * @param {string} memberId 
 * @param {string} date - YYYY-MM-DD
 * @returns {array} Endowed stream items
 */
export function getEndowedProgress(memberId, date) {
  return [
    {
      id: `endowed-${date}-wakeup`,
      type: "endowed",
      title: "Woke up",
      label: "Woke up ✓",
      state: "done",
      time: "00:00",
    },
    {
      id: `endowed-${date}-open`,
      type: "endowed",
      title: "Opened PIB",
      label: "Opened PIB ✓",
      state: "done",
      time: "00:01",
    }
  ];
}

// ═══════════════════════════════════════════════════════════
// MOMENTUM DETECTION (Section 5.4 Protocol)
// ═══════════════════════════════════════════════════════════

/**
 * Check if we should show momentum nudge (3+ completions in session).
 * @param {number} completionsToday 
 * @returns {boolean}
 */
export function shouldShowMomentumNudge(completionsToday) {
  return completionsToday >= 3 && completionsToday % 3 === 0;
}

/**
 * Generate momentum check message.
 * @param {number} count 
 * @returns {string}
 */
export function generateMomentumMessage(count) {
  return `That's ${count} completions. Want to ride the momentum or bank it?`;
}
