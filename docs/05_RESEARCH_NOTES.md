# 05 — Research Notes (2026-08-05 deep-research sweep)
*Distilled from three parallel research agents: cash-account mechanics, systematic strategy evidence, Medallion operating principles + platform facts. These findings are load-bearing — the engine encodes them.*

---

## A. Cash-account mechanics (encoded in `engine/ledger.py`)

- **Robinhood cash accounts cannot trade with unsettled funds at all** — unsettled sale proceeds are excluded from buying power ("wait 1 trading day to trade with funds from equity and options sales"). This differs from Fidelity/Schwab. Consequence: GFVs are structurally impossible here; the ledger's GFV logic is defense-in-depth.
- A position bought with **settled** cash can be sold **any time, same day included** — never a violation. Cash accounts are PDT-exempt (unlimited day trades; the binding constraint is settled cash).
- Sale proceeds become buying power at the start of the **next business day** (T+1, NYSE calendar — Friday sale settles Monday; holiday-aware).
- **Cadence ceiling at ~$200:** whole bankroll cycles once per business day → ~5 round trips per tranche per week, ~$1,000/week notional velocity, realistically 2–4 tranches of $50–100. There is no per-day order-count regulation; the constraint is settled cash at the open.
- Fractional/dollar-based orders: ≥$1, market orders, **regular hours only**, NMS-listed >$1 price >$25M cap, worked "Not Held" → book fills from execution reports, not intended notional.
- "Limited margin" is IRA-only at Robinhood — not available here. Agentic accounts: assume pure cash semantics (undocumented otherwise). ACH deposits: count as settled only when fully cleared (up to 5 business days); never trade instant-deposit provisional buying power.
- Violation counters kept anyway: 1 GFV = alert; 3 in 12mo = 90-day lockdown industry-standard. Free-riding (one strike = 90-day freeze) prevented by settled-only buys.

## B. Strategy evidence (encoded in `engine/config.json` books)

**Structural facts first:** the ~60s data delay kills the entire intraday-execution class (ORB, VWAP/intraday momentum, gap plays, auction timing). The 5–15bps cost model only holds in liquid ETFs/mega-caps. At $200, a 30bps edge = $0.60/trade — this build is about validated infrastructure, not income.

| Strategy | Verdict | Notes |
|---|---|---|
| **Mean reversion, long-only, index ETFs, 200-SMA filter** | **MARGINAL — best structural fit** | ~10–35bps/trade net post-2018; 60–70% win in normal regimes; close-based signal is delay-immune. **Tight stops demonstrably hurt this class** → wide disaster stop only; the 200-SMA regime filter is the risk control. Buys crashes on the way down — expect clustered −5–10% worst trades. |
| **Turn-of-the-month (SPY)** | **MARGINAL-VIABLE — the sleeper** | Only calendar effect still significant in 1980–2024 samples. Long last ~2 trading days through 3rd of next month; ~65% win, honest 20–50bps/window net; 12 events/yr; runs on the 45-year prior. Don't extend the window or leverage it. |
| Monthly momentum/rotation | Marginal as base allocation | 0–2%/yr wide-error-bar tilt; the discretionary book occupies this role for now. |
| **PEAD** | **DEAD** | Gone in large/tradeable stocks since ~2006 (Martineau, "RIP PEAD"); residual lives in illiquid names our cost model can't touch. Removed from the engine. |
| Overnight harvesting | DEAD | 250 round-trips/yr of costs vs a waning premium; NightShares ETFs (pro execution) liquidated 2023 after −6.9% vs +22% SPX. Also a settlement nightmare in a cash account. |
| Gap fades, ORB, intraday momentum | DEAD for this infra | Need real-time data + stop precision; the paper edges live inside our data delay. |

**Validation doctrine (the statistical truth):** detecting a 20bps edge against 150–250bps per-trade σ needs **400–1,200 trades** — not achievable live at this cadence. Therefore: paper (8–12 weeks) validates *implementation* — slippage vs model (pass: median ≤10bps, p95 ≤30bps), zero rule violations, no missed/duplicate signals. Live-small then measures *real costs* (±3bps after ~30 trades — costs ARE learnable fast). Edge estimates = evidence prior − measured costs, updated Bayesian-style. Kill criteria pre-registered: slippage persistently >25bps, drawdown >1.5× backtest max, or 100-trade rolling mean below −2σ/√100.

**Honest composite outcome, flawless execution:** ~2–6% annualized vs buy-and-hold at current size — dollars, not riches. The deliverables that matter: cost telemetry, discipline, and a machine that scales if/when capital does.

## C. Medallion principles — the transferable doctrine (encoded across the repo)

Transfers: **measurement culture** (log every decision/fill/slippage; judge distributions, not anecdotes) · **hypothesis discipline** (pattern → statistical test → plausibility, before capital) · **cost accounting as first-class** (reject strategies whose edge isn't a multiple of round-trip cost) · **many small bets, none fatal** · **mechanical deleveraging/kill-switches** (protocol, not mood) · **capacity-horizon matching** (at our data quality, only multi-day horizons are real) · **distrust the model** (assume decay; regime checks).

Does NOT transfer, do not cosplay: the edge itself (microstructure/order-flow at tick resolution), 10–20× basket-option leverage, 150k–300k trades/day N, terabyte data breadth, execution research. Renaissance was ~50.75% right at near-zero marginal cost; at retail spreads, high N without edge *guarantees* bleed — which is exactly why live cadence is capped and paper cadence is not.

## D. Platform facts (encoded in `railway.json` + `engine/config.json`)

- Railway cron: 5-min minimum, skips overlapping runs, never kills hung runs → wrong tool. Always-on worker: `restartPolicyType: ON_FAILURE` + `restartPolicyMaxRetries`, `drainingSeconds: 60`, `overlapSeconds: 0` (two live instances = duplicate orders), single replica, no HTTP healthcheck for a pure worker. Handle SIGTERM (done). Hobby plan ≈ $5/mo flat for a small worker.
- NYSE 2026 remainder: closed Sep 7, Nov 26, Dec 25; early close 1pm Nov 27, Dec 24. (July 3 was an early close, not a holiday — calendar corrected.)
