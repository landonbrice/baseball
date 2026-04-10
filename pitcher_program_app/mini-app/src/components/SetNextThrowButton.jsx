import { useState } from 'react';
import SetThrowModal from './SetThrowModal';

export default function SetNextThrowButton({ onAdd }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        style={{
          fontSize: 10, fontWeight: 600, color: 'var(--color-maroon)',
          background: 'rgba(92,16,32,0.06)',
          border: '1px solid rgba(92,16,32,0.15)',
          borderRadius: 14, padding: '4px 10px', cursor: 'pointer',
        }}
      >
        ＋ Set next throw
      </button>
      {open && (
        <SetThrowModal
          onClose={() => setOpen(false)}
          onSave={async (data) => {
            await onAdd(data);
            setOpen(false);
          }}
        />
      )}
    </>
  );
}
