# saved_plans deprecation audit runbook

Plan 7 A15 added `saved_plans_deprecated_write` WARN logs on every write.
Plan 8 A1 audits the Supabase table directly (no Railway log integration
yet — Guardian Phase 2 will add that).

## Run the audit

```
cd pitcher_program_app
PYTHONPATH=. python -m scripts.verify_saved_plans_deprecated
```

Exit 0 → safe to run Plan 8 B1 (drop migration).
Exit 1 → block on B1, investigate.

## If the audit fails

Find the writer:

```
git log --all --oneline --since='2026-04-30' -S 'insert_saved_plan'
git log --all --oneline --since='2026-04-30' -S 'save_plan'
grep -rn "save_plan\|insert_saved_plan" pitcher_program_app/api pitcher_program_app/bot
```

Plan 7 B16 removed the mini-app caller; the remaining `save_plan` call
inside `api/routes.py:1257` (custom-plan generator path) is the most
likely culprit. Either remove that call or migrate to `favorited_blocks`.
