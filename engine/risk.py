"""Deterministic live-order gate. With no human in the loop, THIS is the law.

Every live order intent passes through gate_live_order() before the execution
bridge is invoked. Any single failed check kills the order. The gate never
raises — it returns (ok, reasons) so the daemon can log and notify.

Layers (all must pass):
  1. Kill switches — HALT file (operator veto), FLOOR_HALT (equity floor tripped)
  2. Circuit breakers — daily loss, peak drawdown, equity floor
  3. Order-level caps — per-trade max loss, live position count, orders/day,
     per-book allocation
  4. Settlement/GFV ledger (buys: cash; sells: GFV guard)
"""
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HALT_FILE = os.path.join(ROOT, "state", "HALT")
FLOOR_FILE = os.path.join(ROOT, "state", "FLOOR_HALT")


def halted():
    return os.path.exists(HALT_FILE) or os.path.exists(FLOOR_FILE)


def gate_live_order(intent, ledger, engine_state, config, prices):
    """intent: {id, side, symbol, notional, book, stop_pct}"""
    r = config["risk"]
    reasons = []
    today = date.fromisoformat(engine_state["date"])

    if os.path.exists(HALT_FILE):
        reasons.append("HALT flag set by operator — no live orders")
    if os.path.exists(FLOOR_FILE):
        reasons.append("FLOOR_HALT active — equity floor was breached; operator must clear")

    equity = round(ledger.total_cash() + ledger.position_value(prices), 2)
    if equity < r["equity_floor"]:
        reasons.append(f"equity {equity:.2f} below floor {r['equity_floor']:.2f}")

    day_start = engine_state.get("day_start_equity") or equity
    if day_start > 0 and intent["side"] == "buy":
        day_pnl = equity / day_start - 1
        if day_pnl <= -r["daily_loss_halt_pct"]:
            reasons.append(f"daily loss {day_pnl:.1%} beyond halt threshold — no new entries today")
    peak = max(engine_state.get("peak_equity", equity), equity)
    if intent["side"] == "buy" and peak > 0 and equity / peak - 1 <= -r["peak_dd_flatten_pct"]:
        reasons.append(f"drawdown from peak {equity / peak - 1:.1%} beyond flatten threshold")

    if intent["side"] == "buy":
        stop_pct = float(intent.get("stop_pct") or 1.0)  # missing stop = assume total loss
        max_loss = intent["notional"] * stop_pct
        if equity > 0 and max_loss / equity > r["per_trade_max_loss_pct"]:
            reasons.append(f"max loss {max_loss:.2f} is {max_loss / equity:.1%} of equity — cap {r['per_trade_max_loss_pct']:.0%}")

        if len(ledger.open_symbols()) >= r["max_live_positions"]:
            reasons.append(f"live position count at cap {r['max_live_positions']}")

        book_cfg = config["books"].get(intent["book"], {})
        alloc = book_cfg.get("live_alloc", 0.0)
        book_open_cost = sum(
            l["cost"] for lots in ledger.data["positions"].values() for l in lots
            if l["book"] == intent["book"]
        )
        if book_open_cost + intent["notional"] > alloc + 0.01:
            reasons.append(f"book '{intent['book']}' allocation {book_open_cost + intent['notional']:.2f} exceeds cap {alloc:.2f}")

        if engine_state.get("live_orders_today", 0) >= r["max_live_orders_per_day"]:
            reasons.append(f"live orders/day at cap {r['max_live_orders_per_day']} (settlement-cadence guard)")

        ok, _funds_settle, why = ledger.plan_buy(intent["notional"], today)
        if not ok:
            reasons.append(why)

    if intent["side"] == "sell":
        ok, why = ledger.can_sell(intent["symbol"], today)
        if not ok:
            reasons.append(why)

    return (len(reasons) == 0), reasons


def trip_floor(note=""):
    os.makedirs(os.path.dirname(FLOOR_FILE), exist_ok=True)
    with open(FLOOR_FILE, "w") as f:
        f.write(note or "equity floor breached")
