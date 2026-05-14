/**
 * FavoriteHeart — Plan 6 / B2.
 *
 * Small heart button on each block header in DailyCard. Tap → POST
 * /api/favorites with the block snapshot. Optimistically fills; on error
 * shows a brief shake and reverts. After successful favorite the button
 * is non-interactive (no dedup needed on the backend — A2 allows
 * duplicates — but the UI prevents accidental double-writes).
 *
 * Props:
 *   blockType:        'lifting' | 'arm_care' | 'throwing' | 'warmup'
 *   sourceEntryDate:  'YYYY-MM-DD' (today's entry date)
 *   blockSnapshot:    the actual block content (whatever was rendered)
 *   initData:         Telegram initData for the API call
 *   size:             optional pixel size (default 16)
 */
import { useState } from 'react';
import { postApi } from '../api';

export default function FavoriteHeart({
  blockType,
  sourceEntryDate,
  blockSnapshot,
  initData,
  size = 16,
}) {
  const [filled, setFilled]   = useState(false);
  const [busy, setBusy]       = useState(false);
  const [error, setError]     = useState(false);

  const canFavorite = !!(blockType && sourceEntryDate && blockSnapshot &&
    typeof blockSnapshot === 'object' && Object.keys(blockSnapshot).length > 0);

  const handleClick = async (e) => {
    e.stopPropagation();  // don't trigger any parent toggle
    if (filled || busy || !canFavorite) return;
    setBusy(true);
    setError(false);
    // Optimistic fill
    setFilled(true);
    try {
      await postApi('/api/favorites', {
        block_type: blockType,
        source_entry_date: sourceEntryDate,
        block_snapshot: blockSnapshot,
      }, initData);
    } catch (_e) {
      setFilled(false);
      setError(true);
      // Auto-clear error after 1.5s so the heart can be re-tried
      setTimeout(() => setError(false), 1500);
    } finally {
      setBusy(false);
    }
  };

  const color = filled
    ? 'var(--color-maroon)'
    : error
      ? 'var(--color-flag-red, #b3261e)'
      : 'var(--color-ink-muted)';

  // Outlined when not filled, solid when filled
  const path = filled
    ? 'M12 21s-7-4.5-7-10a4 4 0 017-2.6A4 4 0 0119 11c0 5.5-7 10-7 10z'
    : 'M12 20.5l-.9-.8C6.1 14.7 3 11.9 3 8.5 3 6 5 4 7.5 4c1.5 0 2.9.7 3.7 1.9C12 4.7 13.5 4 15 4 17.5 4 19.5 6 19.5 8.5c0 3.4-3.1 6.2-8.1 11.2l-.9.8z';

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={busy || filled || !canFavorite}
      aria-label={filled ? 'Favorited' : 'Add to favorites'}
      aria-pressed={filled}
      data-testid={`favorite-heart-${blockType}`}
      style={{
        background: 'transparent', border: 'none', padding: 4,
        cursor: (filled || busy || !canFavorite) ? 'default' : 'pointer',
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
        opacity: !canFavorite ? 0.35 : 1,
      }}
      title={filled ? 'Favorited' : error ? 'Could not save' : 'Add to favorites'}
    >
      <svg
        width={size} height={size}
        viewBox="0 0 24 24" fill={filled ? color : 'none'}
        stroke={color} strokeWidth={filled ? 0 : 1.6}
        strokeLinecap="round" strokeLinejoin="round"
        aria-hidden="true">
        <path d={path} />
      </svg>
    </button>
  );
}
