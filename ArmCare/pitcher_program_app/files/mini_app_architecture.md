# Mini App Architecture Spec

## Data API: Option D — Lightweight HTTP Endpoints on Bot Process

Add aiohttp web server running alongside the Telegram bot in the same process.
This is the simplest option: one process, one server, direct file access.

### Implementation

```python
# In main.py or a separate api_server.py imported by main.py

from aiohttp import web
import json
import os

DATA_DIR = "data/pitchers"
EXERCISE_LIB = "data/knowledge/exercise_library.json"

async def get_profile(request):
    pitcher_id = request.match_info['pitcher_id']
    path = f"{DATA_DIR}/{pitcher_id}.json"
    if not os.path.exists(path):
        return web.json_response({"error": "not found"}, status=404)
    with open(path) as f:
        return web.json_response(json.load(f))

async def get_plan(request):
    """Returns today's protocol based on rotation day + profile."""
    pitcher_id = request.match_info['pitcher_id']
    # Load profile, calculate rotation day, generate plan
    # (reuse plan_generator.py logic)
    profile_path = f"{DATA_DIR}/{pitcher_id}.json"
    if not os.path.exists(profile_path):
        return web.json_response({"error": "not found"}, status=404)
    with open(profile_path) as f:
        profile = json.load(f)
    # Return today's plan from the most recent log entry or generate fresh
    log_path = f"{DATA_DIR}/{pitcher_id}_log.json"
    with open(log_path) as f:
        log = json.load(f)
    today_entry = log["entries"][-1] if log["entries"] else None
    return web.json_response(today_entry or {"message": "No plan generated yet. Check in with the bot."})

async def get_log(request):
    pitcher_id = request.match_info['pitcher_id']
    path = f"{DATA_DIR}/{pitcher_id}_log.json"
    if not os.path.exists(path):
        return web.json_response({"error": "not found"}, status=404)
    with open(path) as f:
        return web.json_response(json.load(f))

async def get_exercises(request):
    """Returns exercise library, optionally filtered by category."""
    category = request.query.get('category', None)
    with open(EXERCISE_LIB) as f:
        library = json.load(f)
    if category:
        library["exercises"] = [e for e in library["exercises"] if e["category"] == category]
    return web.json_response(library)

async def post_arm_feel(request):
    """Log arm feel from the dashboard."""
    pitcher_id = request.match_info['pitcher_id']
    data = await request.json()
    # Append to log, same logic as bot logging
    # ...
    return web.json_response({"status": "ok"})

def setup_api(app_runner=None):
    """Create and return the aiohttp web app."""
    app = web.Application()
    
    # CORS middleware for Mini App / PWA access
    # Add cors headers to all responses
    
    app.router.add_get('/api/pitcher/{pitcher_id}/profile', get_profile)
    app.router.add_get('/api/pitcher/{pitcher_id}/plan', get_plan)
    app.router.add_get('/api/pitcher/{pitcher_id}/log', get_log)
    app.router.add_get('/api/pitcher/{pitcher_id}/exercises', get_exercises)
    app.router.add_post('/api/pitcher/{pitcher_id}/arm-feel', post_arm_feel)
    
    return app

# In main.py, run both bot and API:
# async def main():
#     api_app = setup_api()
#     api_runner = web.AppRunner(api_app)
#     await api_runner.setup()
#     site = web.TCPSite(api_runner, '0.0.0.0', 8080)
#     await site.start()
#     
#     application = Application.builder().token(BOT_TOKEN).build()
#     # ... set up handlers ...
#     await application.run_polling()
```

### API Endpoints Summary

| Method | Path | Returns | Used By |
|--------|------|---------|---------|
| GET | /api/pitcher/{id}/profile | Pitcher profile JSON | Home, Profile pages |
| GET | /api/pitcher/{id}/plan | Today's protocol + rotation day | Home page |
| GET | /api/pitcher/{id}/log | Full log history | Home (trends), Log History page |
| GET | /api/pitcher/{id}/exercises?category=X | Exercise library (filterable) | Exercise Library page |
| POST | /api/pitcher/{id}/arm-feel | Log arm feel from dashboard | Home page quick-log |

### CORS
The Mini App will be hosted on Vercel (different origin than the bot server).
Add CORS headers allowing requests from the Mini App domain.

### Auth for Mini App
When opened inside Telegram, the Mini App receives initData from Telegram containing user info.
Parse this to get the Telegram user ID, look up the pitcher_id, and pass it to API calls.

When opened as standalone PWA, use a simple token system:
- Bot sends a unique URL: `https://your-app.vercel.app?token=abc123`
- Token maps to pitcher_id on the server side
- Token expires after 30 days, bot can generate a new one

---

## React Component Architecture

### Routing (react-router-dom v6)
```
/                    → Home.jsx (week view + today's plan + trend)
/exercises           → ExerciseLibrary.jsx
/exercises/:id       → ExerciseDetail.jsx (single exercise deep-dive)
/log                 → LogHistory.jsx (calendar)
/log/:date           → LogDay.jsx (single day detail)
/profile             → Profile.jsx
```

### Component Tree
```
App.jsx
├── NavBar.jsx (bottom tab bar: Home, Exercises, Log, Profile)
├── pages/
│   ├── Home.jsx
│   │   ├── FlagBadge.jsx (Green/Yellow/Red pill)
│   │   ├── WeekStrip.jsx (7-day rotation strip)
│   │   │   └── DayCell.jsx (single day in strip — color-coded)
│   │   ├── DailyCard.jsx (today's exercises)
│   │   │   └── ExerciseRow.jsx (checkbox + name + video link)
│   │   ├── ArmFeelInput.jsx (1-5 button row for quick logging)
│   │   └── TrendChart.jsx (arm feel line chart)
│   │
│   ├── ExerciseLibrary.jsx
│   │   ├── CategoryFilter.jsx (pill buttons: All, FPM, Shoulder, etc.)
│   │   ├── SearchBar.jsx
│   │   └── ExerciseCard.jsx (name, muscles, protocol summary)
│   │       └── → links to ExerciseDetail.jsx
│   │
│   ├── ExerciseDetail.jsx
│   │   ├── VideoEmbed.jsx (YouTube iframe)
│   │   ├── ProtocolTable.jsx (sets × reps by mode)
│   │   └── RotationUsage.jsx (which days to use/avoid)
│   │
│   ├── LogHistory.jsx
│   │   ├── CalendarGrid.jsx (month view, color-coded by arm feel)
│   │   └── → tap day links to LogDay.jsx
│   │
│   ├── LogDay.jsx
│   │   ├── ArmFeelDisplay.jsx
│   │   ├── PrescribedList.jsx (what bot prescribed)
│   │   └── CompletedList.jsx (what pitcher actually did)
│   │
│   └── Profile.jsx
│       ├── ProfileInfo.jsx (name, role, injury history)
│       ├── RotationDisplay.jsx (current day, last outing)
│       └── PreferencesForm.jsx (notification time, etc.)
│
└── shared/
    ├── api.js (fetch wrapper for all API calls)
    ├── usePitcher.js (React hook: loads profile + caches)
    └── theme.js (color constants matching Telegram dark theme)
```

### Data Flow
```
App mounts
  → reads Telegram initData (if in Mini App) OR URL token (if PWA)
  → resolves pitcher_id
  → stores in React context (PitcherProvider)
  → all child components access pitcher_id via usePitcher() hook
  → API calls include pitcher_id in URL path
```

### api.js Pattern
```javascript
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export async function fetchProfile(pitcherId) {
  const res = await fetch(`${API_BASE}/api/pitcher/${pitcherId}/profile`);
  if (!res.ok) throw new Error('Failed to fetch profile');
  return res.json();
}

export async function fetchPlan(pitcherId) {
  const res = await fetch(`${API_BASE}/api/pitcher/${pitcherId}/plan`);
  if (!res.ok) throw new Error('Failed to fetch plan');
  return res.json();
}

export async function fetchLog(pitcherId) {
  const res = await fetch(`${API_BASE}/api/pitcher/${pitcherId}/log`);
  if (!res.ok) throw new Error('Failed to fetch log');
  return res.json();
}

export async function fetchExercises(category = null) {
  const url = category 
    ? `${API_BASE}/api/pitcher/exercises?category=${category}`
    : `${API_BASE}/api/pitcher/exercises`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to fetch exercises');
  return res.json();
}

export async function logArmFeel(pitcherId, armFeel) {
  const res = await fetch(`${API_BASE}/api/pitcher/${pitcherId}/arm-feel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ arm_feel: armFeel, timestamp: new Date().toISOString() })
  });
  return res.json();
}
```

### Telegram Mini App Integration
```javascript
// In App.jsx
import { useEffect, useState } from 'react';

function App() {
  const [pitcherId, setPitcherId] = useState(null);
  
  useEffect(() => {
    // Check if running inside Telegram Mini App
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp;
      tg.ready();
      tg.expand(); // Full screen
      
      // Get user from Telegram
      const user = tg.initDataUnsafe?.user;
      if (user) {
        // Look up pitcher_id from Telegram user_id
        fetch(`${API_BASE}/api/resolve-user?tg_id=${user.id}`)
          .then(r => r.json())
          .then(data => setPitcherId(data.pitcher_id));
      }
    } else {
      // Standalone PWA — get pitcher_id from URL token
      const params = new URLSearchParams(window.location.search);
      const token = params.get('token');
      if (token) {
        fetch(`${API_BASE}/api/resolve-token?token=${token}`)
          .then(r => r.json())
          .then(data => setPitcherId(data.pitcher_id));
      }
    }
  }, []);
  
  if (!pitcherId) return <div>Loading...</div>;
  
  return (
    <PitcherProvider pitcherId={pitcherId}>
      <Router>
        {/* routes */}
      </Router>
      <NavBar />
    </PitcherProvider>
  );
}
```

### Design Tokens (matching dark theme from manifest)
```javascript
// theme.js — matches PWA manifest dark theme #1a1a2e / #16213e
export const colors = {
  bg: {
    primary: '#1a1a2e',    // main background
    secondary: '#16213e',  // cards, surfaces
    tertiary: '#0f3460',   // elevated elements
  },
  text: {
    primary: '#e8e8e8',
    secondary: '#a0a0b0',
    muted: '#6c6c7e',
  },
  accent: {
    blue: '#378ADD',
    green: '#4ade80',
    yellow: '#facc15',
    red: '#ef4444',
  },
  flag: {
    green: { bg: '#064e3b', text: '#4ade80', border: '#065f46' },
    yellow: { bg: '#713f12', text: '#facc15', border: '#854d0e' },
    red: { bg: '#7f1d1d', text: '#ef4444', border: '#991b1b' },
  }
};
```

### Key UX Decisions
1. **Bottom tab navigation** (not hamburger menu) — 4 tabs: Home, Exercises, Log, Profile
2. **Pull-to-refresh on Home** — re-fetches today's plan and arm feel
3. **Exercise videos open in YouTube** (external link) rather than embedded iframe — simpler, works better in Telegram Mini App container
4. **Arm feel can be logged from both Telegram AND the dashboard** — both write to the same log
5. **Offline-first for exercise library** — cache exercises in localStorage so they load even without network. Profile and logs always fetch fresh.
6. **Minimal animations** — the Telegram Mini App webview can be laggy. Keep it snappy with no transitions or fancy effects.
