import { useState } from 'react';
import { useAuth } from '../App';
import { setNextOuting } from '../api';

const OPTIONS = [
  { label: 'Today', days: 0 },
  { label: 'Tomorrow', days: 1 },
  { label: '2 days', days: 2 },
  { label: '3 days', days: 3 },
  { label: '4 days', days: 4 },
  { label: '5+ days', days: 5 },
];

export default function NextOutingPicker({ profile, onRefresh }) {
  const { pitcherId, initData } = useAuth();
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);

  const nextDays = profile?.active_flags?.next_outing_days;
  const label = nextDays != null
    ? nextDays === 0 ? 'Today' : nextDays === 1 ? 'Tomorrow' : `In ${nextDays} days`
    : 'Set next outing';

  const handleSelect = async (days) => {
    setSaving(true);
    try {
      await setNextOuting(pitcherId, days, initData);
      onRefresh?.();
    } catch {}
    setSaving(false);
    setOpen(false);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        disabled={saving}
        className="text-xs text-accent-blue font-medium disabled:opacity-50"
      >
        Next outing: {label} ▾
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute top-6 right-0 bg-bg-secondary border border-bg-tertiary rounded-xl shadow-lg z-40 py-1 min-w-[140px]">
            {OPTIONS.map(opt => (
              <button
                key={opt.days}
                onClick={() => handleSelect(opt.days)}
                className={`w-full text-left px-4 py-2 text-xs transition-colors hover:bg-bg-tertiary ${
                  nextDays === opt.days ? 'text-accent-blue font-medium' : 'text-text-primary'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
