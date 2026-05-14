import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useBackButton } from '../useTelegram';

describe('useBackButton', () => {
  let show;
  let hide;
  let onClick;
  let offClick;

  beforeEach(() => {
    show = vi.fn();
    hide = vi.fn();
    onClick = vi.fn();
    offClick = vi.fn();
    window.Telegram = {
      WebApp: {
        BackButton: { show, hide, onClick, offClick },
      },
    };
  });

  afterEach(() => {
    delete window.Telegram;
  });

  it('shows BackButton and registers onClick on mount', () => {
    const handler = vi.fn();
    renderHook(() => useBackButton(handler));
    expect(show).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(onClick).toHaveBeenCalledWith(handler);
    expect(hide).not.toHaveBeenCalled();
    expect(offClick).not.toHaveBeenCalled();
  });

  it('hides BackButton and unregisters onClick on unmount', () => {
    const handler = vi.fn();
    const { unmount } = renderHook(() => useBackButton(handler));
    unmount();
    expect(offClick).toHaveBeenCalledTimes(1);
    expect(offClick).toHaveBeenCalledWith(handler);
    expect(hide).toHaveBeenCalledTimes(1);
  });
});
