# 03 — Operational Notes
*Hard-won constraints. Read before touching the Robinhood MCP.*

---

## Account state (verified live 2026-08-04)
- **Agentic account:** `692261530` — cash account, **equity only** (`option_level` is empty, no options approval). `agentic_allowed: true` — the connector reaches it.
- The primary account (`949788343`, margin, Level 3 options) has `agentic_allowed: false` — **not accessible to this agent.** Equity and equity-equivalent ETFs only, on the agentic account only.
- **Current book: flat. $198.74 cash, $0 equity, $0 unsettled.** Three opening positions (BRK.B $50 core, XLV $50 core, GDX $13 moonshot) were placed as queued orders and then cancelled before execution at the operator's request. `state/positions.json` reflects the flat book with the live numbers.
- **Logged (executed) trades: 0.** The cancelled queue does not count. Sizing stays maximally suppressed until real history accumulates.

## Robinhood MCP quirks
- **Fractional buys:** dollar-based market orders using the `dollar_amount` parameter with `market_hours: regular_hours` is the correct format. Orders placed after the close queue successfully and execute at the next regular session open.
- **Investor profile gate:** Robinhood requires completion of an investor-profile questionnaire before a **second** trade on a new agentic account. The first order went through; subsequent ones returned `400` until the profile was completed at the provided applink URL. **⚠️ Still outstanding — this blocks trade #2.**
- **Cancellation:** `cancel_equity_order` with `order_id` works reliably for queued-but-unfilled orders. Verify with `get_equity_orders` using a `created_at_gte` date filter — it returns current order state cleanly.
- Always `review_equity_order` before `place_equity_order`.

## Cash-account settlement
Selling shares purchased with unsettled funds risks a **good-faith violation**. Therefore:
- `risk_check.py` includes a `settlement.json` guard that blocks sell proposals against unsettled lots.
- In the first days after a deposit, **do not place standing stop orders**. Treat stop levels as alerts requiring deliberate action.
- T+1 settlement bounds round-trip velocity. The tempo doctrine in the charter works **with** this constraint (loaded pipeline, fast cuts), never around it.

## Check-in cadence (v3.0 tempo)
- **Morning pulse:** every trading day, ~15 min before the open.
- **Midday scan:** every trading day, ~12:30 ET — hunt run over the watch universe; proposals only.
- **Weekly:** one substantive review — score decisions vs outcomes, update the edge estimate, kill dead setups.
- **Immediately:** whenever a price alert fires.

## Division of labor
- **This repo is the eyes** — daily pulses, alerts, one-tap approvals, journaling.
- **The Claude.ai project is the brain** — deep underwriting, weekly reviews, edge tracking, charter amendments.
- Same charter, two surfaces. When the charter changes in one place, change it in both.

## Where to run it
| Option | Trade-off |
|---|---|
| Mac + cron | Free, but sleeps when the lid closes. Fine to start. |
| **Railway cron service** | Always-on, config-as-code (`railway.json` in this repo), ~$5/mo class. **The chosen host.** One-time interactive step needed to complete Robinhood MCP OAuth on the box — see README → Railway. |
| $5/mo generic VPS | Same always-on properties, more hands-on ops. Fallback if the Railway OAuth dance proves brittle. |
| Claude Code cloud routines | Runs with your machine off, but plan-limited runs/day and MCP auth is simpler to reason about on your own box. |

## Guardrails
- `--max-budget-usd 1.50` and `--max-turns 30` cap each run — a runaway loop dies for pocket change.
- `flock` prevents overlapping pulse runs.
- Telegram approvals are accepted **only from your chat ID**. Replies from anyone else are ignored.
- `risk_check.py` ships with `test_risk_check.py` — run it after ANY change to the gate. The gate is the load-bearing wall.
