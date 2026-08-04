# EXECUTOR JOURNAL

Append-only log. Every pulse writes one dated line; every executed trade writes a
block. Never trust mental arithmetic — sizing and P&L are computed via `python3`
and the numbers shown here are those computed values. This file is the audit trail:
if it isn't written down, it didn't happen.

## Format
- **Pulse line:** `YYYY-MM-DD HH:MM ET · acct $X (day ±$Y / ±Z%) · <per-position status vs levels> · dry powder $D · action: <none|...>`
- **Trade block:** proposal id, risk_check verdict, approval (who/when), fill, and the
  pre-committed stop + target that were in force at entry.

---

## 2026-07-02 — book seeded
Opening book queued at open (see `state/positions.json`): BRK.B $50 core (stop 440),
XLV $50 core (stop 143.60), GDX $13 moonshot (stop 60, target 95). Account $200,
moonshot sleeve $40, dry powder $87, 3 logged trades. No orders placed yet — all
entries still require risk_check PASS + Telegram APPROVED per the charter.

## 2026-08-04 — charter v3.0 (sicko mode) + book trued up + Railway prep
Master document imported (`docs/00_MASTER_2026-08-04.md`); charter upgraded to v3.0:
tempo doctrine added (morning pulse + midday hunt, loaded pipeline of 2–5 pre-approved-
ready proposals, fast cuts), DRL overlay and all seven lenses carried in. **No hard rail
changed** — caps, quarter-Kelly, circuit breakers, and the two-gate protocol are intact
by design. Book verified flat against live portfolio: $198.74 cash, $0 equity; the three
July queued orders were cancelled pre-fill, so logged_trades reset to 0 and sizing stays
suppressed. Railway deploy layer added (Dockerfile, railway.json, railway_pulse.sh).
Open blockers: investor-profile questionnaire (blocks trade #2), standalone repo split,
Railway OAuth one-timer.
