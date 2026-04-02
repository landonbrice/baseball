/**
 * MorningBriefCard — Structured 2x2 nugget card for the morning brief.
 * Parses JSON morning_brief strings internally.
 * If the brief is plain text or unparseable, renders nothing (caller shows fallback).
 */

const STATUS_COLORS = {
  green: '#1D9E75',
  yellow: '#BA7517',
  red: '#A32D2D',
};

/**
 * Attempt to parse a structured morning brief from a raw value.
 * Returns the parsed object if valid, or null.
 */
export function parseStructuredBrief(raw) {
  if (!raw || typeof raw !== 'string') return null;
  try {
    var obj = JSON.parse(raw);
    if (obj && typeof obj === 'object' && typeof obj.arm_verdict === 'object') {
      return obj;
    }
  } catch (_e) {
    // Not JSON — plain text brief
  }
  return null;
}

export default function MorningBriefCard({ rawBrief, rotationDay, rotationLength }) {
  var brief = parseStructuredBrief(rawBrief);
  if (!brief) return null;

  var todayDate = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', timeZone: 'America/Chicago' });

  var armV = brief.arm_verdict || {};
  var sleepV = brief.sleep_verdict || {};
  var todayF = brief.today_focus || {};
  var watchV = brief.watch_item;

  var nuggets = [
    { key: 'arm', emoji: '\uD83D\uDCAA', heading: 'Arm Feel', value: String(armV.value || ''), verdict: String(armV.label || ''), status: String(armV.status || '') },
    { key: 'sleep', emoji: '\uD83D\uDE34', heading: 'Sleep', value: String(sleepV.value || ''), verdict: String(sleepV.label || ''), status: String(sleepV.status || '') },
    { key: 'today', emoji: '\uD83C\uDFAF', heading: 'Today', value: String(todayF.value || ''), verdict: String(todayF.label || '') },
    watchV
      ? { key: 'watch', emoji: '\u26A1', heading: 'Watch', value: String(watchV.value || ''), verdict: String(watchV.label || ''), status: String(watchV.status || '') }
      : { key: 'watch', emoji: '\u2705', heading: 'Watch', value: 'All clear', verdict: 'No concerns', status: 'green' },
  ];

  var coachNote = brief.coaching_note ? String(brief.coaching_note) : null;

  return (
    <div style={{ background: '#fff', borderRadius: 12, padding: 14 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 10 }}>
        <span style={{ fontSize: 14 }}>{'\u2600\uFE0F'}</span>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#2a1a18' }}>{'Morning Brief'}</span>
        <span style={{ fontSize: 11, color: '#b0a89e', marginLeft: 'auto' }}>
          {'Day '}{String(rotationDay != null ? rotationDay : '?')}{' of '}{String(rotationLength || 7)}{' \u00B7 '}{todayDate}
        </span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: coachNote ? 12 : 0 }}>
        {nuggets.map(function(n) {
          return (
            <div key={n.key} style={{ background: '#f5f1eb', borderRadius: 10, padding: '10px 12px', border: '1px solid #e4dfd8' }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: '#b0a89e', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
                {n.emoji}{' '}{n.heading}
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#2a1a18', lineHeight: 1.2 }}>
                {n.value}
              </div>
              <div style={{ fontSize: 11, marginTop: 2, color: STATUS_COLORS[n.status] || '#6b5f58' }}>
                {n.verdict}
              </div>
            </div>
          );
        })}
      </div>
      {coachNote ? (
        <div style={{ borderLeft: '3px solid #BA7517', background: 'rgba(186,117,23,0.08)', borderRadius: '0 8px 8px 0', padding: '10px 12px' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#BA7517', marginBottom: 4 }}>
            {'\uD83D\uDCA1 Coach\u2019s Note'}
          </div>
          <div style={{ fontSize: 12, color: '#6b5f58', lineHeight: 1.5 }}>
            {coachNote}
          </div>
        </div>
      ) : null}
    </div>
  );
}
