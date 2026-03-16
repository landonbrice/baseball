Before committing to this Phase 3 plan, make these adjustments:

## Changes to the plan

1. **FastAPI sidecar is fine** — keep that over aiohttp on the bot process. Cleaner separation.

2. **Dev mode auth fallback.** In task R1 (useTelegram.js), the fallback when not running inside Telegram should use a `VITE_TEST_PITCHER_ID` env variable, not just localStorage. Add a `.env.development` file with `VITE_TEST_PITCHER_ID=test_pitcher_001` so the dashboard works during local dev without Telegram initData. The hook should check: Telegram WebApp → URL token → env var fallback, in that order.

3. **Seed data variance.** In task P2 (seed_test_data.py), make sure the 21 days of synthetic data include: arm feel values ranging from 2-5 (not all 4s — the TrendChart needs visible variance), at least one yellow flag day (arm feel 2, low sleep), sleep hours ranging from 5.5-9, and the 3 outings should have different pitch counts (65, 82, 95). This is critical for testing that components render real-looking data.

4. **Add /dashboard command to bot.** This isn't in the current plan — add it. The bot needs a `/dashboard` handler that sends an InlineKeyboardButton with the Mini App web_app URL. This is how pitchers will actually open the dashboard:
   ```
   /dashboard → bot sends:
   "📊 Your dashboard"
   [InlineKeyboardButton(text="Open dashboard", web_app=WebAppInfo(url=MINI_APP_URL))]
   ```
   Add this as task A6 in Step 1, and add the MINI_APP_URL to the bot's config/env.

5. **Build order for Telegram WebApp registration.** Move task S3 (Register Mini App with BotFather, test initData flow) to AFTER S4 (Deploy). You can't test initData without a publicly accessible HTTPS URL. The order should be: S1 → S2 → S4 (deploy) → S3 (register with BotFather and test). Make this explicit so we don't get stuck trying to test Telegram integration against localhost.

6. **Exercise videos open as external links**, not embedded iframes. Confirm this is the approach in ExerciseRow.jsx and ExerciseLibrary.jsx. YouTube iframes are janky inside Telegram's Mini App webview. A simple `<a href={youtube_url} target="_blank">` is more reliable.

## Reference files to review

Before building, re-read these files that were created during the planning phase — they contain design decisions, component specs, and data flow details that should inform your implementation:

- `mini_app_architecture.md` — React component tree, API endpoint specs, Telegram Mini App integration code, design tokens (dark theme colors), and key UX decisions
- `google_form_pipeline.md` — intake pipeline, Telegram username mapping, and the `intake_to_profile.py` script spec
- `bot_intelligence_architecture.md` — how pitcher context files grow over time, the three-tier knowledge system, and example conversation flows
- `MASTER_PROJECT.md` — the full project spec including UI specification section with Telegram message format, notification cadence, onboarding flow, and rotation tracking

These files have specific code examples, color values, component hierarchies, and API patterns that should be followed rather than reinvented.

## Then commit to the plan with these changes and start building Step 1.
