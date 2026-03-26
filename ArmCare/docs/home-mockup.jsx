import { useState } from "react";

/*
 * Home Page Mockup v3 — Maroon/Cream design language
 * Changes from v2:
 * - Role subtitle under name ("UChicago Baseball · Starter") with contrast
 * - Week strip legend clarifying dot colors
 * - Full prescription detail on exercises ("2×10 each direction RPE 7-8")
 * - Weekly insight with arm feel trend chart above text
 * - Session progress bar (% of today's plan completed)
 * - Consistency streak with visual
 * - Quick Coach access button
 * - Arm feel mini sparkline in header
 */

const c = {
  maroon: "#5c1020", maroonMid: "#7a1a2e", maroonLight: "#8a2a3e",
  roseBlush: "#e8a0aa", roseSoft: "#f0c4cb",
  creamBg: "#f5f1eb", white: "#ffffff",
  creamBorder: "#e4dfd8", creamSubtle: "#ddd8d0",
  inkPrimary: "#2a1a18", inkSecondary: "#6b5f58",
  inkMuted: "#b0a89e", inkFaint: "#c5bfb8",
  flagGreen: "#1D9E75", flagYellow: "#BA7517", flagRed: "#A32D2D",
  blue: "#3B82F6",
};

const MOCK = {
  name: "Preston",
  role: "Starter",
  team: "UChicago Baseball",
  rotationDay: 3,
  rotationLength: 7,
  flagLevel: "green",
  nextOuting: "Friday",
  checkedIn: true,
  armFeel: 4,
  streak: 4,
  sparkline: [3, 3, 4, 3, 2, 3, 4, 4, 3, 4, 3, 2, 3, 4, 4],
  outingDays: [4, 11],
};

const PLAN = {
  arm_care: {
    duration: 15,
    reasoning: "Standard arm care — day 3, building back toward Friday's start",
    exercises: [
      { id: "band_pull_aparts", name: "Band Pull-Aparts", prescription: "3×15 · light band · RPE 5", completed: true, hasVideo: true, priority: false, why: "Scapular stability and posterior shoulder endurance. Safe at any point in rotation — a daily staple in your program." },
      { id: "prone_y_raises", name: "Prone Y Raises", prescription: "3×10 · 5lb · RPE 6", completed: true, hasVideo: true, priority: false, why: "Lower trap activation and scapular upward rotation. Keeps your shoulder tracking clean through the throwing motion." },
      { id: "pronator_curls", name: "Pronator Curls", prescription: "3×12 · 8lb · RPE 7", completed: false, hasVideo: true, priority: true, why: "Strengthens the flexor-pronator mass — your primary UCL dynamic stabilizer. Included because of your 2024 UCL sprain episode (resolved with PRP). Non-negotiable in your program." },
      { id: "wrist_flex_ext", name: "Wrist Flexion/Extension", prescription: "2×15 each direction · RPE 6-7", completed: false, hasVideo: false, priority: false, why: "Forearm endurance work. Supports the pronator group and helps manage the forearm tightness you've reported historically." },
      { id: "sleeper_stretch", name: "Sleeper Stretch", prescription: "2×30s each side", completed: false, hasVideo: true, priority: false, why: "Internal rotation maintenance. Pitchers lose IR over a season — this keeps your glenohumeral range balanced." },
    ],
  },
  lifting: {
    duration: 40,
    type: "Upper Body",
    reasoning: "Upper body — mid-rotation, full intensity cleared",
    exercises: [
      { id: "db_bench", name: "DB Bench Press", prescription: "4×8 · RPE 7-8", completed: false, hasVideo: true, priority: false, why: "Primary horizontal press. Builds anterior shoulder and chest strength for the deceleration phase of throwing." },
      { id: "pullups", name: "Pull-Ups", prescription: "3×8 · bodyweight · RPE 8", completed: false, hasVideo: true, priority: false, why: "Lat and scapular strength. Your lats are the primary decelerator after ball release — this is foundational." },
      { id: "face_pulls", name: "Face Pulls", prescription: "3×15 · light cable · RPE 6", completed: false, hasVideo: true, priority: false, why: "Posterior shoulder and external rotator work. Balances the internal rotation demands of throwing." },
      { id: "farmers_carry", name: "Farmer's Carry", prescription: "3×40yd · heavy · RPE 8", completed: false, hasVideo: false, priority: false, why: "Grip, core, and shoulder stability under load. Builds the trunk stiffness that transfers force from legs to arm." },
    ],
  },
  throwing: {
    duration: 20,
    reasoning: "Flat ground — building volume back toward Friday's start",
    exercises: [
      { id: "flat_ground", name: "Flat Ground Throwing", prescription: "25 throws · build to 75% · mix FB/CH", completed: false, hasVideo: false, priority: false, why: "Progressive intensity buildup. Day 3 — arm should be fresh enough for moderate volume at controlled effort. Focus on feel, not velocity." },
    ],
  },
};

const WEEK = [
  { day: "M", num: 24, armFeel: 3, status: "done", label: "Day 1", outing: false },
  { day: "T", num: 25, armFeel: 4, status: "partial", label: "Day 2", outing: false },
  { day: "W", num: 26, armFeel: 4, status: "today", label: "Day 3", outing: false },
  { day: "T", num: 27, armFeel: null, status: "future", label: "Day 4", outing: false },
  { day: "F", num: 28, armFeel: null, status: "future", label: "Start", outing: true },
  { day: "S", num: 29, armFeel: null, status: "future", label: "Day 0", outing: false },
  { day: "S", num: 30, armFeel: null, status: "future", label: "Day 1", outing: false },
];

const STAFF = [
  { name: "Landon", checkedIn: true, rotation: "Day 5", role: "SP" },
  { name: "Preston", checkedIn: true, rotation: "Day 3", role: "SP" },
  { name: "Wade", checkedIn: true, rotation: "Available", role: "RP" },
  { name: "Carter", checkedIn: true, rotation: "Day 2", role: "RP" },
  { name: "Taran", checkedIn: true, rotation: "Available", role: "RP" },
  { name: "Russell", checkedIn: false, rotation: "Day 4", role: "SP" },
  { name: "Jonathan", checkedIn: true, rotation: "Available", role: "RP" },
  { name: "Lucien", checkedIn: false, rotation: "Available", role: "RP" },
  { name: "Matt", checkedIn: true, rotation: "Day 1", role: "RP" },
  { name: "Mike", checkedIn: false, rotation: "Available", role: "RP" },
  { name: "Wilson", checkedIn: false, rotation: "Available", role: "RP" },
];

const INSIGHT_TEXT = "Arm feel averaged 4.2 this week, up from 3.6 last week. Post-outing recovery faster — bounced back to 4 by day 2 both times. Pronator work consistent at 6/7 days.";
const TREND_DATA = [
  { week: "Wk 1", avg: 3.4, high: 4, low: 2 },
  { week: "Wk 2", avg: 3.6, high: 4, low: 3 },
  { week: "Wk 3", avg: 3.8, high: 5, low: 3 },
  { week: "Wk 4", avg: 4.2, high: 5, low: 3 },
];

/* ---- Utilities ---- */
const armFeelColor = (v) => !v ? c.creamSubtle : v >= 4 ? c.flagGreen : v === 3 ? c.flagYellow : c.flagRed;

/* ---- Components ---- */

function Sparkline({ data, outingDays, width = 120, height = 28 }) {
  const padding = 2;
  const w = width - padding * 2;
  const h = height - padding * 2;
  const step = w / (data.length - 1);
  const scale = (v) => h - ((v - 1) / 4) * h;

  const points = data.map((v, i) => `${padding + i * step},${padding + scale(v)}`).join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline points={points} fill="none" stroke={c.roseBlush} strokeWidth="1.5" strokeLinejoin="round" />
      {data.map((v, i) => (
        <circle key={i} cx={padding + i * step} cy={padding + scale(v)} r={outingDays.includes(i) ? 2.5 : 1.2}
          fill={outingDays.includes(i) ? c.roseBlush : "rgba(255,255,255,0.6)"} />
      ))}
    </svg>
  );
}

function FlagBadge({ level }) {
  const cfg = { green: { bg: `${c.flagGreen}1F`, text: c.flagGreen, label: "Green" }, yellow: { bg: `${c.flagYellow}1F`, text: c.flagYellow, label: "Yellow" }, red: { bg: `${c.flagRed}1F`, text: c.flagRed, label: "Red" } };
  const s = cfg[level];
  return <span style={{ background: s.bg, color: s.text, padding: "2px 10px", borderRadius: 10, fontSize: 10, fontWeight: 600, letterSpacing: 0.5, textTransform: "uppercase" }}>{s.label}</span>;
}

function SessionProgress({ plan }) {
  const all = [...plan.arm_care.exercises, ...plan.lifting.exercises, ...plan.throwing.exercises];
  const done = all.filter(e => e.completed).length;
  const pct = Math.round((done / all.length) * 100);

  return (
    <div style={{ background: c.white, borderRadius: 12, padding: "10px 14px", border: `0.5px solid ${c.creamBorder}`, display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: c.inkMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>Session Progress</span>
          <span style={{ fontSize: 10, fontWeight: 600, color: pct === 100 ? c.flagGreen : c.inkSecondary }}>{done}/{all.length} exercises</span>
        </div>
        <div style={{ height: 4, background: c.creamBorder, borderRadius: 2, overflow: "hidden" }}>
          <div style={{ width: `${pct}%`, height: "100%", background: pct === 100 ? c.flagGreen : c.maroon, borderRadius: 2, transition: "width 0.3s" }} />
        </div>
      </div>
      <div style={{ fontSize: 18, fontWeight: 800, color: pct === 100 ? c.flagGreen : c.maroon, minWidth: 40, textAlign: "right" }}>{pct}%</div>
    </div>
  );
}

function StreakBadge({ count }) {
  const dots = Array.from({ length: 7 }, (_, i) => i < count);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ display: "flex", gap: 3 }}>
        {dots.map((filled, i) => (
          <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: filled ? c.flagGreen : c.creamSubtle }} />
        ))}
      </div>
      <span style={{ fontSize: 10, fontWeight: 600, color: c.flagGreen }}>{count} day streak</span>
    </div>
  );
}

function ExerciseRow({ exercise, onToggle }) {
  const [showWhy, setShowWhy] = useState(false);
  return (
    <div style={{ borderBottom: `0.5px solid ${c.creamBorder}` }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10, padding: "10px 0" }}>
        <button onClick={() => onToggle(exercise.id)} style={{
          width: 20, height: 20, borderRadius: "50%", marginTop: 1,
          border: `1.5px solid ${exercise.completed ? c.flagGreen : exercise.priority ? c.maroon : c.creamSubtle}`,
          background: exercise.completed ? c.flagGreen : "transparent",
          display: "flex", alignItems: "center", justifyContent: "center", cursor: "pointer", flexShrink: 0,
        }}>
          {exercise.completed && <span style={{ color: c.white, fontSize: 11, fontWeight: 700 }}>✓</span>}
        </button>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
            <span style={{ fontSize: 12, fontWeight: 500, color: exercise.completed ? c.inkMuted : c.inkPrimary, textDecoration: exercise.completed ? "line-through" : "none" }}>
              {exercise.name}
            </span>
            {exercise.priority && !exercise.completed && (
              <span style={{ fontSize: 7, fontWeight: 700, color: c.flagRed, background: `${c.flagRed}15`, padding: "1px 5px", borderRadius: 4, letterSpacing: 0.5, textTransform: "uppercase" }}>FPM</span>
            )}
          </div>
          {/* Full prescription on its own line */}
          <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 2 }}>{exercise.prescription}</div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 2, flexShrink: 0, marginTop: 2 }}>
          {exercise.hasVideo && (
            <button style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: c.inkMuted, fontSize: 11 }}>▶</button>
          )}
          <button onClick={() => setShowWhy(!showWhy)} style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: showWhy ? c.maroon : c.inkFaint, fontSize: 12, transition: "color 0.15s" }}>ⓘ</button>
        </div>
      </div>

      {showWhy && (
        <div style={{ padding: "0 0 10px 30px" }}>
          <div style={{ background: c.creamBg, borderRadius: 8, padding: "8px 12px", fontSize: 11, lineHeight: 1.6, color: c.inkSecondary, borderLeft: `2px solid ${c.roseBlush}` }}>
            {exercise.why}
          </div>
        </div>
      )}
    </div>
  );
}

function PlanBlock({ title, emoji, block }) {
  const [exercises, setExercises] = useState(block.exercises);
  const done = exercises.filter(e => e.completed).length;
  const total = exercises.length;
  const toggle = (id) => setExercises(prev => prev.map(e => e.id === id ? { ...e, completed: !e.completed } : e));

  return (
    <div style={{ background: c.white, borderRadius: 12, overflow: "hidden", border: `0.5px solid ${c.creamBorder}` }}>
      <div style={{ padding: "12px 14px", borderBottom: `0.5px solid ${c.creamBorder}` }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 14 }}>{emoji}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: c.inkPrimary }}>{title}</span>
            {block.type && <span style={{ fontSize: 11, color: c.inkMuted }}>— {block.type}</span>}
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 10, color: c.inkMuted }}>{block.duration} min</span>
            <span style={{ fontSize: 10, color: done === total ? c.flagGreen : c.inkMuted, fontWeight: 600 }}>{done}/{total}</span>
          </div>
        </div>
        <div style={{ fontSize: 10, color: c.inkMuted, marginTop: 4, fontStyle: "italic" }}>{block.reasoning}</div>
      </div>
      <div style={{ padding: "0 14px" }}>
        {exercises.map(ex => <ExerciseRow key={ex.id} exercise={ex} onToggle={toggle} />)}
      </div>
    </div>
  );
}

function WeekStrip({ days }) {
  return (
    <div style={{ background: c.white, borderRadius: 12, padding: 14, border: `0.5px solid ${c.creamBorder}` }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        {days.map((d, i) => {
          const isToday = d.status === "today";
          const isOuting = d.outing;
          return (
            <button key={i} style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: 3, padding: "6px 7px", borderRadius: 8, cursor: "pointer", border: "none",
              background: isToday ? c.maroon : "transparent",
            }}>
              <span style={{ fontSize: 9, fontWeight: 600, color: isToday ? c.roseBlush : c.inkMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>{d.day}</span>
              <span style={{ fontSize: 13, fontWeight: 600, color: isToday ? c.white : c.inkPrimary }}>{d.num}</span>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: d.status === "done" ? c.flagGreen : d.status === "partial" ? c.flagYellow : isToday ? c.white : c.creamSubtle }} />
              {isOuting ? (
                <div style={{ width: 7, height: 7, transform: "rotate(45deg)", background: c.roseBlush, borderRadius: 1 }} />
              ) : (
                <span style={{ fontSize: 8, color: isToday ? c.roseBlush : c.inkFaint }}>{d.label}</span>
              )}
            </button>
          );
        })}
      </div>
      {/* Legend */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 10, paddingTop: 8, borderTop: `0.5px solid ${c.creamBorder}` }}>
        {[
          { color: c.flagGreen, label: "Complete" },
          { color: c.flagYellow, label: "Partial" },
          { color: c.creamSubtle, label: "Upcoming" },
        ].map(({ color, label }, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 3 }}>
            <div style={{ width: 5, height: 5, borderRadius: "50%", background: color }} />
            <span style={{ fontSize: 9, color: c.inkMuted }}>{label}</span>
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
          <div style={{ width: 5, height: 5, transform: "rotate(45deg)", background: c.roseBlush, borderRadius: 1 }} />
          <span style={{ fontSize: 9, color: c.inkMuted }}>Outing</span>
        </div>
      </div>
    </div>
  );
}

function TrendChart({ data }) {
  const w = 280, h = 100, padL = 24, padR = 8, padT = 8, padB = 24;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;
  const xStep = plotW / (data.length - 1);
  const yScale = (v) => padT + plotH - ((v - 1) / 4) * plotH;

  const avgLine = data.map((d, i) => `${padL + i * xStep},${yScale(d.avg)}`).join(" ");
  const rangePath = data.map((d, i) => `${padL + i * xStep},${yScale(d.high)}`).join(" ")
    + " " + [...data].reverse().map((d, i) => `${padL + (data.length - 1 - i) * xStep},${yScale(d.low)}`).join(" ");

  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} style={{ display: "block", margin: "0 auto" }}>
      {/* Y-axis gridlines */}
      {[1, 2, 3, 4, 5].map(v => (
        <g key={v}>
          <line x1={padL} y1={yScale(v)} x2={w - padR} y2={yScale(v)} stroke={c.creamBorder} strokeWidth="0.5" />
          <text x={padL - 6} y={yScale(v) + 3} textAnchor="end" fontSize="8" fill={c.inkFaint}>{v}</text>
        </g>
      ))}

      {/* Range band (high-low) */}
      <polygon points={rangePath} fill={c.roseBlush} fillOpacity="0.15" />

      {/* Average line */}
      <polyline points={avgLine} fill="none" stroke={c.maroon} strokeWidth="2" strokeLinejoin="round" />

      {/* Data points */}
      {data.map((d, i) => (
        <g key={i}>
          <circle cx={padL + i * xStep} cy={yScale(d.avg)} r="3.5" fill={c.maroon} />
          <text x={padL + i * xStep} y={yScale(d.avg) - 8} textAnchor="middle" fontSize="9" fontWeight="600" fill={c.inkPrimary}>{d.avg}</text>
          <text x={padL + i * xStep} y={h - 4} textAnchor="middle" fontSize="8" fill={c.inkMuted}>{d.week}</text>
        </g>
      ))}
    </svg>
  );
}

function InsightCard({ text, trendData }) {
  return (
    <div style={{ background: c.white, borderRadius: 12, padding: 14, border: `0.5px solid ${c.creamBorder}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 10 }}>
        <span style={{ fontSize: 12 }}>📈</span>
        <span style={{ fontSize: 10, fontWeight: 600, color: c.maroon, textTransform: "uppercase", letterSpacing: 0.5 }}>Weekly Insight</span>
        <span style={{ fontSize: 9, color: c.inkFaint, marginLeft: "auto" }}>4-week arm feel trend</span>
      </div>

      {/* Chart */}
      <div style={{ background: c.creamBg, borderRadius: 8, padding: "8px 4px", marginBottom: 10 }}>
        <TrendChart data={trendData} />
        <div style={{ display: "flex", justifyContent: "center", gap: 14, marginTop: 6 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 12, height: 2, background: c.maroon, borderRadius: 1 }} />
            <span style={{ fontSize: 8, color: c.inkMuted }}>Avg</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{ width: 12, height: 6, background: c.roseBlush, opacity: 0.3, borderRadius: 1 }} />
            <span style={{ fontSize: 8, color: c.inkMuted }}>High–Low range</span>
          </div>
        </div>
      </div>

      {/* Text insight */}
      <p style={{ fontSize: 12, lineHeight: 1.6, color: c.inkSecondary, margin: 0 }}>{text}</p>
    </div>
  );
}

function StaffPulse({ staff }) {
  const [expanded, setExpanded] = useState(false);
  const checkedIn = staff.filter(s => s.checkedIn).length;

  return (
    <div style={{ background: c.white, borderRadius: 12, padding: 14, border: `0.5px solid ${c.creamBorder}` }}>
      <button onClick={() => setExpanded(!expanded)} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", background: "none", border: "none", cursor: "pointer", padding: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12 }}>⚾</span>
          <span style={{ fontSize: 10, fontWeight: 600, color: c.inkMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>Pitching Staff</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: c.inkPrimary }}>{checkedIn}/{staff.length}</span>
          <span style={{ fontSize: 10, color: c.inkMuted }}>{expanded ? "▾" : "▸"}</span>
        </div>
      </button>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: `0.5px solid ${c.creamBorder}` }}>
          {staff.map((p, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", borderBottom: i < staff.length - 1 ? `0.5px solid ${c.creamBg}` : "none" }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: p.checkedIn ? c.flagGreen : c.creamSubtle, flexShrink: 0 }} />
              <span style={{ fontSize: 11, color: p.checkedIn ? c.inkPrimary : c.inkMuted, fontWeight: 500, flex: 1 }}>{p.name}</span>
              <span style={{ fontSize: 9, color: c.inkFaint, background: c.creamBg, padding: "1px 6px", borderRadius: 4 }}>{p.role}</span>
              <span style={{ fontSize: 9, color: c.inkFaint, minWidth: 50, textAlign: "right" }}>{p.rotation}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function CoachButton() {
  return (
    <button style={{
      position: "fixed", bottom: 68, right: 16, width: 48, height: 48, borderRadius: "50%",
      background: c.maroon, border: "none", cursor: "pointer",
      boxShadow: "0 2px 12px rgba(92,16,32,0.3)",
      display: "flex", alignItems: "center", justifyContent: "center",
      color: c.white, fontSize: 20,
    }}>
      ◉
    </button>
  );
}

/* ---- Main ---- */

export default function HomeMockup() {
  const p = MOCK;
  const totalExercises = PLAN.arm_care.exercises.length + PLAN.lifting.exercises.length + PLAN.throwing.exercises.length;
  const totalDuration = PLAN.arm_care.duration + PLAN.lifting.duration + PLAN.throwing.duration;

  return (
    <div style={{ minHeight: "100vh", background: c.creamBg, fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
      <div style={{ maxWidth: 480, margin: "0 auto" }}>

        {/* Header */}
        <div style={{ background: c.maroon, padding: "16px 16px 14px", color: c.white }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontSize: 20, fontWeight: 800, letterSpacing: -0.3 }}>{p.name}</div>
              <div style={{ fontSize: 10, color: c.roseBlush, marginTop: 2, letterSpacing: 0.3 }}>
                {p.team} · <span style={{ color: c.white, fontWeight: 600 }}>{p.role}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
                <FlagBadge level={p.flagLevel} />
                <span style={{ fontSize: 11, color: c.roseBlush }}>Day {p.rotationDay} of {p.rotationLength}</span>
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1 }}>{p.armFeel}</div>
              <div style={{ fontSize: 8, textTransform: "uppercase", letterSpacing: 1, color: c.roseBlush, marginTop: 2 }}>Arm Feel</div>
              {/* Mini sparkline */}
              <div style={{ marginTop: 4 }}>
                <Sparkline data={p.sparkline} outingDays={p.outingDays} width={100} height={20} />
              </div>
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 10, paddingTop: 8, borderTop: "0.5px solid rgba(255,255,255,0.12)" }}>
            <span style={{ fontSize: 10, color: c.roseBlush }}>
              Next start: <span style={{ color: c.white, fontWeight: 600 }}>{p.nextOuting}</span> · {totalExercises} exercises · ~{totalDuration} min
            </span>
            <StreakBadge count={p.streak} />
          </div>
        </div>

        {/* Content */}
        <div style={{ padding: "12px 12px 100px", display: "flex", flexDirection: "column", gap: 10 }}>

          {/* Session Progress */}
          <SessionProgress plan={PLAN} />

          {/* Week Strip */}
          <WeekStrip days={WEEK} />

          {/* Plan Section Header */}
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 2px 0" }}>
            <span style={{ fontSize: 10, fontWeight: 600, color: c.inkMuted, textTransform: "uppercase", letterSpacing: 0.5 }}>Today's Plan</span>
            <span style={{ fontSize: 9, color: c.inkFaint }}>tap ⓘ for why</span>
          </div>

          <PlanBlock title="Arm Care" emoji="💪" block={PLAN.arm_care} />
          <PlanBlock title="Lifting" emoji="🏋️" block={PLAN.lifting} />
          <PlanBlock title="Throwing" emoji="⚾" block={PLAN.throwing} />

          {/* Insight with Chart */}
          <InsightCard text={INSIGHT_TEXT} trendData={TREND_DATA} />

          {/* Staff Pulse */}
          <StaffPulse staff={STAFF} />
        </div>

        {/* Floating Coach Button */}
        <CoachButton />

        {/* Bottom Nav */}
        <div style={{
          position: "fixed", bottom: 0, left: "50%", transform: "translateX(-50%)",
          width: "100%", maxWidth: 480, height: 56, background: c.white,
          borderTop: `0.5px solid ${c.creamBorder}`,
          display: "flex", alignItems: "center", justifyContent: "space-around",
        }}>
          {[
            { icon: "⌂", label: "Home", active: true },
            { icon: "▥", label: "Program", active: false },
            { icon: "▦", label: "History", active: false },
            { icon: "◯", label: "Profile", active: false },
          ].map((item, i) => (
            <button key={i} style={{
              display: "flex", flexDirection: "column", alignItems: "center", gap: 2,
              background: "none", border: "none", cursor: "pointer", padding: "4px 14px",
              color: item.active ? c.maroon : c.inkMuted, position: "relative",
            }}>
              {item.active && <div style={{ position: "absolute", top: -1, width: 4, height: 4, borderRadius: "50%", background: c.maroon }} />}
              <span style={{ fontSize: 18 }}>{item.icon}</span>
              <span style={{ fontSize: 9, fontWeight: item.active ? 600 : 400 }}>{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
