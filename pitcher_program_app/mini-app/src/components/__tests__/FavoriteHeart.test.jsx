/**
 * FavoriteHeart — Plan 6 / B2.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import FavoriteHeart from '../FavoriteHeart';

vi.mock('../../api', () => ({
  postApi: vi.fn(),
}));

import { postApi } from '../../api';

const BLOCK = {
  exercises: [{ exercise_id: 'ex_1', name: 'Bench', sets: 3, reps: 5 }],
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('FavoriteHeart', () => {
  it('starts unfilled with aria-pressed=false', () => {
    render(
      <FavoriteHeart
        blockType="lifting" sourceEntryDate="2026-05-13"
        blockSnapshot={BLOCK} initData="fake"
      />
    );
    const btn = screen.getByRole('button', { name: /add to favorites/i });
    expect(btn).toHaveAttribute('aria-pressed', 'false');
  });

  it('POSTs /api/favorites with the right payload on click', async () => {
    const user = userEvent.setup();
    postApi.mockResolvedValue({ favorite_id: 'fav-1' });
    render(
      <FavoriteHeart
        blockType="arm_care" sourceEntryDate="2026-05-13"
        blockSnapshot={BLOCK} initData="fake"
      />
    );
    await user.click(screen.getByRole('button'));
    await waitFor(() => expect(postApi).toHaveBeenCalled());
    const [path, body, initData] = postApi.mock.calls[0];
    expect(path).toBe('/api/favorites');
    expect(body).toEqual({
      block_type: 'arm_care',
      source_entry_date: '2026-05-13',
      block_snapshot: BLOCK,
    });
    expect(initData).toBe('fake');
  });

  it('fills optimistically and disables further interaction', async () => {
    const user = userEvent.setup();
    let resolveApi;
    postApi.mockReturnValue(new Promise(r => { resolveApi = r; }));
    render(
      <FavoriteHeart
        blockType="lifting" sourceEntryDate="2026-05-13"
        blockSnapshot={BLOCK} initData="fake"
      />
    );
    await user.click(screen.getByRole('button'));
    // Even mid-flight, the button should be disabled + aria-pressed=true
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'true');
    resolveApi({ favorite_id: 'fav-1' });
    await waitFor(() =>
      expect(screen.getByRole('button')).toHaveAttribute('aria-label', 'Favorited')
    );
  });

  it('reverts the fill on API error', async () => {
    const user = userEvent.setup();
    postApi.mockRejectedValue(new Error('API 500'));
    render(
      <FavoriteHeart
        blockType="lifting" sourceEntryDate="2026-05-13"
        blockSnapshot={BLOCK} initData="fake"
      />
    );
    await user.click(screen.getByRole('button'));
    await waitFor(() =>
      expect(screen.getByRole('button')).toHaveAttribute('aria-pressed', 'false')
    );
  });

  it('disables when there is no snapshot to save', () => {
    render(
      <FavoriteHeart
        blockType="lifting" sourceEntryDate="2026-05-13"
        blockSnapshot={null} initData="fake"
      />
    );
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('disables when snapshot is an empty object', () => {
    render(
      <FavoriteHeart
        blockType="lifting" sourceEntryDate="2026-05-13"
        blockSnapshot={{}} initData="fake"
      />
    );
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('does not double-fire when clicked twice rapidly', async () => {
    const user = userEvent.setup();
    postApi.mockResolvedValue({ favorite_id: 'fav-1' });
    render(
      <FavoriteHeart
        blockType="lifting" sourceEntryDate="2026-05-13"
        blockSnapshot={BLOCK} initData="fake"
      />
    );
    const btn = screen.getByRole('button');
    await user.click(btn);
    await user.click(btn);
    await waitFor(() => expect(postApi).toHaveBeenCalledTimes(1));
  });
});
