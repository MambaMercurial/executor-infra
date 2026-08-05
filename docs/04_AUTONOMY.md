# 04 — The Autonomy Architecture (charter v4.0)
*How the human approval gate was replaced by a system of checks and balances, per operator directive 2026-08-05. This is the design record.*

---

## The division of labor: what is AI and what is code

| Layer | Who | Why |
|---|---|---|
| Intraday signals, order timing | **Deterministic Python** (`engine/`) | Repeatable, testable, cheap, cannot be talked into anything |
| Risk gating, settlement law, circuit breakers | **Deterministic Python** | The rules that must survive any argument live in code |
| Order placement | **LLM bridge, zero discretion** (haiku, ≤$0.40/run) | The Robinhood MCP is OAuth-bound to Claude; the bridge is a dumb pipe with a 12-turn leash |
| Underwriting, reconciliation, journaling, parameter proposals | **LLM (pre/post-market runs)** | Judgment work, on a schedule, with hard budget caps |
| Killing bad discretionary trades | **Adversarial LLM skeptic** (separate hostile context) | Independent second opinion, structurally biased to REFUTE |
| Vetoes | **Operator via Telegram** (HALT/RESUME/FLAT/STATUS) | Human can always stop it; human never has to act for it to run |

The LLM is **never** in the fast loop. This is both a cost decision (a Claude call per poll would burn ~$40/day) and a Medallion decision: the model trades mechanically; intelligence is spent on research and risk, offline.

## The five independent brakes

1. **`engine/risk.py`** — per-order gate: equity floor, daily-loss halt (−3%), per-trade max loss (≤7% equity), position/order-count caps, per-book allocation caps.
2. **`engine/ledger.py`** — settlement law: settled-cash-only buys, GFV-impossible sells, NYSE-calendar settlement. Mirrors the broker's own enforcement (defense-in-depth).
3. **Circuit breakers in the daemon** — day −5% → flatten live + halt until tomorrow; equity < $150 → flatten + permanent halt pending operator.
4. **Graduation ladder** — no strategy touches real dollars until its paper record proves the *implementation* (≥20 clean events, zero violations); live sizing then assumes the edge is zero.
5. **Pre-registered kill criteria** — the postmarket run pulls a live book's flag when it exceeds 1.5× its prior's drawdown or sits below the zero-edge noise band. Autonomous changes are DE-risk only; UP-risk requires the operator.

## Honest framing, written down so it can't drift

- **"Consistent daily profits" is not a thing any legitimate system delivers** — Medallion's own record is a ~50.75% win rate made invincible only by enormous N and near-zero costs. What this system maximizes instead: positive-expectancy-per-cost trades × cadence × compounding, with ruthless measurement.
- **At $200, live trade cadence is settlement-bounded**: the bankroll cycles once per business day (~5 round trips/tranche/week). "As many trades as possible" is therefore delivered by the PAPER engine (unbounded), which is also the only place a statistical sample can accumulate fast.
- **Paper P&L cannot prove edge at this N** (a 20bps edge needs 400–1,200 trades to detect). Paper proves *implementation quality*; evidence priors justify strategies; live results measure *costs*. All three are stated separately in the journal, never conflated.
- **The infra costs more than the account can earn at $200** (~$5/mo Railway + ~$2–4/day LLM runs on trading days). This is an R&D build: the machine, telemetry, and discipline are the assets that compound when capital does.

## Cost budget (LLM)

| Run | Model | Cap | Frequency |
|---|---|---|---|
| Pre-market | default | $1.50 / 35 turns | each trading day |
| Post-market | default | $1.50 / 35 turns | each trading day |
| Weekly review | default | $2.50 / 45 turns | Fridays |
| Execution bridge | haiku | $0.40 / 12 turns | per live order (≤6/day) |
| Skeptic | default | $0.75 / 15 turns | per discretionary proposal |

Worst-case trading day ≈ $6; typical ≈ $3–4. Fits a $100/mo org spend limit with headroom (~$80 worst-case month); the operator console cap is the final backstop. The daemon itself costs nothing between polls.

## Failure posture

- Quote feed down → no signals, positions still exit on stops via last known prices when the feed returns; never trades blind.
- Bridge fails → order intent logged, Telegram alert, no retry storm (one retry max inside the bridge).
- Daemon crash → Railway `ON_FAILURE` restart (≤10), state reconstructed from the volume; SIGTERM on redeploy saves state cleanly.
- Broker/ledger drift → pre-market reconcile fixes the ledger to match the broker, journals the diff.
- Anything confusing → HALT file + Telegram. Stopped is a safe state; paper keeps measuring while stopped.
