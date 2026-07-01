#!/usr/bin/env python3
"""
risk_check.py — deterministic pre-trade validator. The LLM proposes; this code decides
whether the proposal is even eligible for human approval. Hard caps live HERE, not in
prompts, so they cannot be talked around.

Usage:  python3 scripts/risk_check.py state/pending/<id>.json
Exit 0 + "PASS" if eligible; exit 1 + reasons if not.

Proposal JSON schema:
{
  "id": "t004",
  "symbol": "XYZ",
  "sleeve": "core" | "moonshot",
  "side": "buy" | "sell",
  "notional": 50.00,          # dollars
  "entry": 100.0,             # reference price
  "stop": 90.0,               # required for buys
  "target": 130.0,
  "thesis": "one-liner",
  "max_loss": 5.00            # agent-computed; recomputed & verified here
}
Reads state/positions.json for account context:
{ "account_value": 200.0, "peak_value": 200.0, "day_start_value": 200.0,
  "moonshot_sleeve_value": 40.0, "logged_trades": 3, "positions": [...] }
"""
import json, sys, os

HARD_PER_TRADE_RISK_PCT = 0.07      # 7% of total account, absolute ceiling
CORE_TARGET_RISK_PCT    = 0.03      # soft ceiling for core; warn above
MOONSHOT_SLEEVE_FRac    = 1/3       # max fraction of moonshot sleeve per shot
DAY_LOSS_HALT_PCT       = 0.20      # -20% on day: no new positions
PEAK_DD_HALT_PCT        = 0.40      # -40% from peak: full halt
SMALL_HISTORY_TRADES    = 50

def fail(reasons):
    print("FAIL")
    for r in reasons: print(f"  - {r}")
    sys.exit(1)

def main():
    if len(sys.argv) != 2: fail(["usage: risk_check.py <proposal.json>"])
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prop = json.load(open(sys.argv[1]))
    state = json.load(open(os.path.join(root, "state", "positions.json")))

    reasons, warns = [], []
    av   = float(state["account_value"])
    peak = float(state.get("peak_value", av))
    day0 = float(state.get("day_start_value", av))

    # Circuit breakers. These gate NEW RISK only — a sell reduces risk, so it is
    # never blocked here. Blocking exits during a drawdown would trap you in a
    # losing book, the opposite of what "halt, review" should mean. Both breakers
    # are therefore buy-scoped.
    if prop["side"] == "buy" and av <= peak * (1 - PEAK_DD_HALT_PCT):
        reasons.append(f"HALT: account {av:.2f} is ≥40% below peak {peak:.2f}. Full review required — no new positions.")
    if prop["side"] == "buy" and av <= day0 * (1 - DAY_LOSS_HALT_PCT):
        reasons.append(f"HALT: down ≥20% today (start {day0:.2f} → {av:.2f}). No new positions.")

    if prop["side"] == "buy":
        for k in ("stop", "entry", "notional", "sleeve"):
            if k not in prop or prop[k] in (None, ""):
                reasons.append(f"missing required field: {k}")
        if reasons: fail(reasons)

        entry, stop, notional = float(prop["entry"]), float(prop["stop"]), float(prop["notional"])
        if stop >= entry:
            reasons.append(f"stop {stop} must be below entry {entry} for a long.")
        # Recompute max loss ourselves — never trust the agent's arithmetic.
        risk_frac_of_position = (entry - stop) / entry
        max_loss = notional * risk_frac_of_position
        risk_pct = max_loss / av
        if abs(max_loss - float(prop.get("max_loss", max_loss))) > 0.05:
            warns.append(f"agent max_loss {prop.get('max_loss')} != computed {max_loss:.2f}; using computed.")
        if risk_pct > HARD_PER_TRADE_RISK_PCT:
            reasons.append(f"risk {risk_pct:.1%} of account exceeds hard cap {HARD_PER_TRADE_RISK_PCT:.0%}.")
        if prop["sleeve"] == "core" and risk_pct > CORE_TARGET_RISK_PCT:
            warns.append(f"core risk {risk_pct:.1%} above 3% target band.")
        if prop["sleeve"] == "moonshot":
            sleeve = float(state.get("moonshot_sleeve_value", av * 0.2))
            if notional > sleeve * MOONSHOT_SLEEVE_FRac + 0.01:
                reasons.append(f"moonshot notional {notional:.2f} exceeds 1/3 of sleeve ({sleeve/3:.2f}).")
        if int(state.get("logged_trades", 0)) < SMALL_HISTORY_TRADES:
            warns.append(f"only {state.get('logged_trades',0)} logged trades — edge estimate is noise; size stays small.")
        # Cash-account settlement guard for sells handled below; buys need cash available
        if notional > av + 0.01:
            reasons.append(f"notional {notional:.2f} exceeds account value {av:.2f}.")

    if prop["side"] == "sell":
        settle_path = os.path.join(root, "state", "settlement.json")
        if os.path.exists(settle_path):
            s = json.load(open(settle_path))
            if s.get("unsettled_symbols") and prop["symbol"] in s["unsettled_symbols"]:
                reasons.append(f"{prop['symbol']} was bought with unsettled funds — selling now risks a good-faith violation.")

    if reasons: fail(reasons)
    print("PASS")
    for w in warns: print(f"  ! {w}")
    sys.exit(0)

if __name__ == "__main__":
    main()
