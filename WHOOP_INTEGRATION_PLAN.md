# WHOOP Integration Plan

> Status: Planned. Reference implementation exists in `/Users/landonbrice/Desktop/arm-care-bot/whoop_client.py`

## What This Does

Replaces self-reported sleep (defaulting to 7.0h) with real biometric data from WHOOP: recovery score, HRV (heart rate variability), sleep performance, and strain. This feeds directly into triage accuracy — the system knows how recovered you actually are, not how recovered you think you are.

## Architecture

### Per-Pitcher WHOOP Linking

Unlike the Armcare bot (single user), this system has 12 pitchers. Each needs their own WHOOP OAuth connection.

**Flow:**
1. Pitcher runs `/whoop` in Telegram (or taps "Connect WHOOP" in mini-app Profile page)
2. Bot generates a per-pitcher OAuth URL with PKCE
3. Pitcher opens URL in browser, authorizes on WHOOP
4. WHOOP redirects to callback URL with auth code
5. System exchanges code for tokens, stores per-pitcher in Supabase
6. Daily 6am job pulls biometric data for all linked pitchers

### Callback Handling (Production)

The Armcare bot uses `localhost:8080` for OAuth callback — that won't work on Railway. Options:

**Recommended: FastAPI callback endpoint on the existing API**
- Add `GET /api/whoop/callback?code=...&state=...` to routes.py
- The redirect_uri in WHOOP developer portal points to `https://baseball-production-9d28.up.railway.app/api/whoop/callback`
- State parameter maps back to pitcher_id
- Returns a simple HTML page: "WHOOP connected! You can close this tab."
- No localhost server needed

---

## Supabase Schema

### New table: `whoop_tokens`
```sql
CREATE TABLE whoop_tokens (
  pitcher_id TEXT PRIMARY KEY REFERENCES pitchers(pitcher_id),
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_in INTEGER,
  obtained_at TIMESTAMPTZ DEFAULT now(),
  scopes TEXT DEFAULT 'read:recovery read:sleep read:cycles offline'
);
```

### New table: `whoop_daily`
```sql
CREATE TABLE whoop_daily (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pitcher_id TEXT NOT NULL REFERENCES pitchers(pitcher_id),
  date DATE NOT NULL,
  recovery_score INTEGER,        -- 0-100%
  hrv_rmssd REAL,               -- milliseconds
  sleep_performance INTEGER,     -- 0-100%
  sleep_hours REAL,             -- actual hours from WHOOP (replaces self-reported)
  yesterday_strain REAL,         -- 0-21 scale
  hrv_7day_avg REAL,            -- computed rolling average
  raw_data JSONB DEFAULT '{}',  -- full API response for debugging
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(pitcher_id, date)
);
```

---

## New Files

### `bot/services/whoop.py` (~200 lines)

Adapted from `arm-care-bot/whoop_client.py`. Key changes:
- Token storage: Supabase `whoop_tokens` table instead of filesystem
- All functions take `pitcher_id` parameter
- Cache: Supabase `whoop_daily` table instead of filesystem
- Error handling: `WHOOPAuthRequired` with pitcher_id context

**Functions:**
| Function | Purpose |
|----------|---------|
| `build_auth_url(pitcher_id)` | Generate OAuth URL with PKCE, store state→pitcher_id mapping |
| `exchange_code(code, state)` | Exchange auth code for tokens, store in Supabase |
| `get_access_token(pitcher_id)` | Load tokens, auto-refresh if expired |
| `pull_whoop_data(pitcher_id)` | Pull recovery + sleep + cycles, cache in whoop_daily |
| `get_today_whoop(pitcher_id)` | Return cached data for today (no API call) |
| `get_hrv_7day_avg(pitcher_id)` | Compute rolling HRV average from whoop_daily |
| `is_linked(pitcher_id)` | Check if pitcher has valid WHOOP tokens |

### `bot/services/db.py` additions

```python
# WHOOP Tokens
def get_whoop_tokens(pitcher_id) -> dict | None
def upsert_whoop_tokens(pitcher_id, tokens)
def list_whoop_linked_pitchers() -> list  # pitchers with tokens

# WHOOP Daily
def get_whoop_daily(pitcher_id, date) -> dict | None
def upsert_whoop_daily(pitcher_id, data)
def get_whoop_daily_range(pitcher_id, days=7) -> list
```

---

## Integration Points

### 1. Triage (`bot/services/triage.py`)

Add WHOOP data to triage input. Current signature:
```python
def triage(arm_feel, sleep_hours, pitcher_profile, energy=3)
```

New:
```python
def triage(arm_feel, sleep_hours, pitcher_profile, energy=3, whoop_data=None)
```

**New triage rules (from Armcare bot, adapted):**
- HRV > 15% below 7-day avg → add yellow trigger
- HRV 10-15% below avg → modified_green factor
- Recovery score < 34% → yellow trigger
- Recovery score < 20% → red trigger (override)
- Sleep performance < 50% → yellow trigger
- Sleep performance 50-70% → modified_green factor
- Replace `sleep_hours` default (7.0) with WHOOP actual when available

### 2. Check-in Service (`bot/services/checkin_service.py`)

Before calling `triage()`, pull today's WHOOP data:
```python
whoop_data = None
try:
    from bot.services.whoop import get_today_whoop
    whoop_data = get_today_whoop(pitcher_id)
except Exception:
    pass  # WHOOP is optional enhancement, not required

triage_result = triage(arm_feel, sleep_hours, profile, energy, whoop_data=whoop_data)
```

If WHOOP provides `sleep_hours`, use that instead of self-reported/default.

### 3. Plan Generator (`bot/services/plan_generator.py`)

Inject WHOOP data into the LLM context:
```
## Biometric Data (WHOOP)
Recovery: 72% | HRV: 45ms (7d avg: 52ms, -13%) | Sleep: 85% (7.2h actual)
Strain yesterday: 12.4
```

### 4. Weekly Narrative (`bot/services/progression.py`)

Include WHOOP trends in `build_week_snapshot()`:
```python
"whoop": {
    "avg_recovery": 68,
    "avg_hrv": 48,
    "hrv_trend": "declining",
    "avg_sleep_performance": 82,
    "days_with_data": 5
}
```

### 5. Morning Notification (`bot/main.py`)

Include WHOOP in morning check-in prompt:
```
Day 3 — Upper Body Pull
WHOOP: Recovery 78% | HRV 52ms | Sleep 88%

How's the arm? (1-5)
```

### 6. Mini-App Home (`mini-app/src/pages/Home.jsx`)

New WHOOP card on Home page showing today's metrics:
- Recovery score (large, color-coded: green >66%, yellow 34-66%, red <34%)
- HRV with 7-day trend sparkline
- Sleep performance percentage
- Yesterday's strain

### 7. Mini-App Profile (`mini-app/src/pages/Profile.jsx`)

"Connect WHOOP" button if not linked. "WHOOP Connected" badge if linked.

---

## Telegram Commands

### `/whoop` — Link or view WHOOP data
- If not linked: generates OAuth URL, sends to pitcher
- If linked: shows today's recovery, HRV, sleep, strain

### `/reauth` — Re-authorize WHOOP (if tokens expired)
- Generates fresh OAuth URL

---

## Scheduled Jobs

### Daily WHOOP Pull — 6:00 AM Chicago
Added to `_schedule_jobs()` in main.py:
```python
job_queue.run_daily(
    _pull_all_whoop,
    time=dt_time(hour=6, minute=0, tzinfo=CHICAGO_TZ),
    name="daily_whoop_pull",
)
```

`_pull_all_whoop()`:
- Queries `list_whoop_linked_pitchers()`
- For each, calls `pull_whoop_data(pitcher_id)`
- Logs success/failure per pitcher
- If auth expired, sends Telegram message to pitcher asking them to re-link

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WHOOP_CLIENT_ID` | yes (for WHOOP) | From WHOOP developer portal |
| `WHOOP_CLIENT_SECRET` | yes (for WHOOP) | From WHOOP developer portal |
| `WHOOP_REDIRECT_URI` | yes (for WHOOP) | `https://baseball-production-9d28.up.railway.app/api/whoop/callback` |

---

## Implementation Order

| Step | What | Effort |
|------|------|--------|
| 1 | Create Supabase tables (whoop_tokens, whoop_daily) | 5 min |
| 2 | Add db.py CRUD functions for WHOOP tables | 15 min |
| 3 | Write `bot/services/whoop.py` (adapted from arm-care-bot) | 30 min |
| 4 | Add `/api/whoop/callback` endpoint to routes.py | 15 min |
| 5 | Add `/whoop` and `/reauth` Telegram commands | 15 min |
| 6 | Wire into triage.py (HRV/recovery thresholds) | 20 min |
| 7 | Wire into checkin_service.py (auto-pull before triage) | 10 min |
| 8 | Wire into plan_generator.py (LLM context injection) | 10 min |
| 9 | Wire into progression.py (weekly narrative data) | 10 min |
| 10 | Add daily 6am pull job to main.py | 10 min |
| 11 | Wire into morning notification (show WHOOP in prompt) | 10 min |
| 12 | Mini-app: WHOOP card on Home | 20 min |
| 13 | Mini-app: Connect WHOOP button on Profile | 15 min |
| 14 | Add env vars to Railway, register redirect URI in WHOOP portal | 10 min |
| 15 | Test end-to-end with landon_brice account | 15 min |

**Total estimate: ~3.5 hours**

---

## Reference

- Armcare bot WHOOP client: `/Users/landonbrice/Desktop/arm-care-bot/whoop_client.py` (269 lines)
- WHOOP Developer Portal: https://developer.whoop.com
- WHOOP API Base: `https://api.prod.whoop.com/developer/v1`
- OAuth endpoints: `/oauth/oauth2/auth` (authorize), `/oauth/oauth2/token` (exchange)
- Scopes needed: `read:recovery read:sleep read:cycles offline`
- PKCE required: S256 challenge method

---

## Risk & Fallback

WHOOP integration is **optional enhancement, never required.** Every code path that uses WHOOP data has a `whoop_data=None` fallback. If a pitcher isn't linked, if tokens expire, or if the WHOOP API is down, the system continues with self-reported data exactly as it does today. No degradation of core functionality.
