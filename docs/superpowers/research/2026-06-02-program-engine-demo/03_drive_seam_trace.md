# Drive Seam — 7-day projection trace

`policy = silent_absorb` (no re-pacing) so the table shows raw readiness modulation without governor feedback.

| Day | Flag | Intended (intent / throws) | Delivered (intent / throws) | Modulation reason |
|---|---|---|---|---|
| Mon GREEN (idx 0) | `GREEN` | 84% / 63 | 84% / 63 | green |
| Tue GREEN (idx 1) | `GREEN` | — | — | green |
| Wed YELLOW tissue (idx 2) | `YELLOW` | 84% / 63 | 74% / 50 | yellow |
| Thu YELLOW + mod (idx 3) | `YELLOW` | — | — | red |
| Fri RED elbow caution (idx 4) | `RED` | 84% / 63 | 50% / 20 | red |
| Sat GREEN (recovered) (idx 5) | `GREEN` | — | — | green |
| Sun GREEN (idx 6) | `GREEN` | — | — | green |