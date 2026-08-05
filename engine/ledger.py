"""Settlement + good-faith-violation ledger for the live cash account.

This is a CHECKS-AND-BALANCES component: deterministic code, no model discretion.
It answers two questions before any live order:
  - buy:  is there cash for this, and when will the cash used settle?
  - sell: would selling this position now be a good-faith violation?

Rules encoded (T+1 cash account, Robinhood semantics — researched 2026-08-05):
  - BUYS SPEND SETTLED CASH ONLY. Robinhood cash accounts cannot trade with
    unsettled funds at all ("wait 1 trading day to trade with funds from
    sales") — so the ledger mirrors the broker: unsettled proceeds are never
    buying power. This also makes GFVs structurally impossible.
  - Sale proceeds settle (become buying power) the NEXT business day, NYSE
    calendar — never weekday arithmetic.
  - A lot bought with settled cash may be sold any time, same day included —
    that is never a violation. The funds_settle lot-marking below is
    defense-in-depth in case broker behavior ever changes.
  - Practical ceiling this implies for a ~$200 account: the whole bankroll
    cycles once per business day (~5 round trips/tranche/week).
"""
import json
import os
from datetime import date, datetime, timedelta

STATE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state")
LEDGER_PATH = os.path.join(STATE, "ledger.json")


def next_business_day(d, holidays=()):
    n = d + timedelta(days=1)
    while n.weekday() >= 5 or n.isoformat() in holidays:
        n += timedelta(days=1)
    return n


class Ledger:
    def __init__(self, path=LEDGER_PATH, holidays=()):
        self.path = path
        self.holidays = set(holidays)
        if os.path.exists(path):
            with open(path) as f:
                self.data = json.load(f)
        else:
            self.data = {"cash_lots": [], "positions": {}, "gfv_blocks": 0}

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    # -- cash --------------------------------------------------------------
    def seed_cash(self, amount, today):
        """Initialize/overwrite cash as fully settled (used at reconciliation)."""
        self.data["cash_lots"] = [{"amount": round(amount, 2), "settles": today.isoformat()}]

    def settled_cash(self, today):
        t = today.isoformat()
        return round(sum(l["amount"] for l in self.data["cash_lots"] if l["settles"] <= t), 2)

    def total_cash(self):
        return round(sum(l["amount"] for l in self.data["cash_lots"]), 2)

    # -- buys --------------------------------------------------------------
    def plan_buy(self, amount, today):
        """Return (ok, funds_settle_date, reason). SETTLED cash only — Robinhood
        cash accounts have no unsettled buying power, and neither do we."""
        if amount < 1.0:
            return False, None, "below $1 fractional-order minimum"
        settled = self.settled_cash(today)
        if amount > settled + 0.005:
            return False, None, (f"insufficient SETTLED cash: need {amount:.2f}, "
                                 f"settled {settled:.2f} (total {self.total_cash():.2f})")
        return True, today, ""

    def record_buy(self, symbol, qty, amount, today, book, funds_settle):
        t = today.isoformat()
        remaining = amount
        lots = sorted(self.data["cash_lots"], key=lambda l: l["settles"])
        for lot in lots:
            if lot["settles"] > t:
                continue  # unsettled — never spendable
            take = min(lot["amount"], remaining)
            lot["amount"] = round(lot["amount"] - take, 2)
            remaining -= take
            if remaining <= 0.005:
                break
        self.data["cash_lots"] = [l for l in lots if l["amount"] > 0.005]
        self.data["positions"].setdefault(symbol, []).append({
            "qty": qty, "cost": amount, "opened": today.isoformat(),
            "funds_settle": funds_settle.isoformat(), "book": book,
        })
        self.save()

    # -- sells -------------------------------------------------------------
    def can_sell(self, symbol, today):
        """(ok, reason). Blocks GFV: selling shares whose purchase cash hasn't settled."""
        lots = self.data["positions"].get(symbol, [])
        if not lots:
            return False, f"no live position in {symbol}"
        t = today.isoformat()
        for lot in lots:
            if lot["funds_settle"] > t:
                self.data["gfv_blocks"] += 1
                self.save()
                return False, (f"GFV guard: {symbol} lot bought with funds settling "
                               f"{lot['funds_settle']} — selling today would be a good-faith violation")
        return True, ""

    def record_sell(self, symbol, proceeds, today):
        self.data["positions"].pop(symbol, None)
        self.data["cash_lots"].append({
            "amount": round(proceeds, 2),
            "settles": next_business_day(today, self.holidays).isoformat(),
        })
        self.save()

    # -- views -------------------------------------------------------------
    def open_symbols(self, book=None):
        out = []
        for sym, lots in self.data["positions"].items():
            if book is None or any(l["book"] == book for l in lots):
                out.append(sym)
        return out

    def position_value(self, prices):
        v = 0.0
        for sym, lots in self.data["positions"].items():
            px = prices.get(sym)
            if px:
                v += sum(l["qty"] * px for l in lots)
            else:
                v += sum(l["cost"] for l in lots)  # stale fallback: cost basis
        return round(v, 2)
