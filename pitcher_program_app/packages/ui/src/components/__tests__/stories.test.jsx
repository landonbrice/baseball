import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { composeStories } from '@storybook/react-vite';

import * as ButtonStories from '../button.stories';
import * as CardStories from '../card.stories';
import * as FlagPillStories from '../flag-pill.stories';

/**
 * Story-driven DOM regression guard. `composeStories` applies the story's args +
 * decorators (incl. preview globals) exactly as Storybook would, then we snapshot
 * the rendered markup. A component changing shape unexpectedly fails the snapshot
 * — the headless equivalent of a visual diff, runnable in CI with no browser.
 *
 * When a change is intentional, update with `vitest -u`. Pixel-level visual
 * regression (Chromatic / Playwright) layers on top of these same stories later
 * with zero rework.
 */
const suites = {
  Button: ButtonStories,
  Card: CardStories,
  FlagPill: FlagPillStories,
};

for (const [group, mod] of Object.entries(suites)) {
  const composed = composeStories(mod);
  describe(`${group} stories`, () => {
    for (const [name, Story] of Object.entries(composed)) {
      it(`renders <${name}> without crashing and matches snapshot`, () => {
        const { container } = render(<Story />);
        expect(container.firstChild).toBeTruthy();
        expect(container).toMatchSnapshot();
      });
    }
  });
}
