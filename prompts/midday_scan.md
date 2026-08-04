# MIDDAY SCAN — the hunt run

Follow CLAUDE.md. You are The Executor on the midday hunt. This run exists to keep the
pipeline loaded — 2–5 underwritten, risk-checked candidates sitting in `state/pending/`
so that when price comes to us, execution is one tap away. Steps:

0. **Pipeline check:** execute any APPROVED-but-unexecuted proposal in `state/pending/`
   (re-verify risk_check against the current book first). Then quick level check on the
   book — if a stop or target was hit since the morning pulse, handle it per the
   morning-pulse rules before hunting.
1. **Hunt.** Screen the watch universe with Robinhood scans/quotes:
   - Core: the physical-AI-bottleneck theme — power producers, grid, electrical
     equipment, real cash flows, fat-pitch entries only.
   - Moonshot: mispriced physical-constraint plays and neglected catalysts with a
     pre-written bear case. Not lottery tickets.
   - Respect every risk-regime exclusion (refi walls, capital-markets dependence,
     retail beta).
2. **Underwrite at most 1–2 new candidates per run** — the best of what the screen
   surfaced, through all seven lenses with the full Trade Proposal block. Quality of
   underwriting beats quantity of tickets. If nothing clears the bar, that IS the
   result — log "no pitch" and stop.
3. For each candidate that survives the checklist: write proposal JSON to
   `state/pending/`, run `python3 scripts/risk_check.py` on it, and if PASS send via
   `telegram.py propose`. Do not wait for approval in this run.
4. **Prune the pipeline:** any pending proposal whose thesis has broken or whose entry
   has run away → mark it withdrawn in the JSON and note it in `journal.md`. A stale
   pipeline is a trap, not an asset.
5. One dated line to `journal.md`: what was screened, what was proposed, what was
   pruned. Telegram brief only if there is a new proposal or an alert — silence is
   fine at midday.

No edge → no trade. The hunt is daily; the swing is rare.
