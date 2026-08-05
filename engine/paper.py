"""Paper book — the measurement engine.

Every strategy trades here FIRST, at full cadence, unconstrained by settlement.
Fills are simulated pessimistically (half-spread against us both ways) so the
measured edge is net of modeled costs. A strategy only touches real dollars
after its paper record clears the graduation bar in engine/config.json.

This is where 'as many trades as possible' lives: paper throughput builds the
statistical sample that decides where live dollars go.
"""
import json
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER_DIR = os.path.join(ROOT, "state", "paper")


class PaperBook:
    def __init__(self, book, start_cash, spread_bps):
        self.book = book
        self.spread_bps = spread_bps
        self.path = os.path.join(PAPER_DIR, f"{book}.json")
        if os.path.exists(self.path):
            with open(self.path) as f:
                self.data = json.load(f)
        else:
            self.data = {"cash": start_cash, "positions": {}, "trades": []}

    def save(self):
        os.makedirs(PAPER_DIR, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    def _spread(self, symbol):
        return self.spread_bps.get(symbol, self.spread_bps.get("default", 6)) / 1e4

    def open_position(self, symbol, notional, price, stop_pct, time_stop_days, meta=None):
        if symbol in self.data["positions"] or notional > self.data["cash"]:
            return False
        fill = price * (1 + self._spread(symbol) / 2)
        qty = notional / fill
        self.data["cash"] -= notional
        self.data["positions"][symbol] = {
            "qty": qty, "entry": fill, "notional": notional,
            "opened": datetime.now(timezone.utc).isoformat(),
            "stop": fill * (1 - stop_pct), "time_stop_days": time_stop_days,
            "meta": meta or {},
        }
        self.save()
        return True

    def close_position(self, symbol, price, reason):
        pos = self.data["positions"].pop(symbol, None)
        if not pos:
            return None
        fill = price * (1 - self._spread(symbol) / 2)
        proceeds = pos["qty"] * fill
        pnl = proceeds - pos["notional"]
        trade = {
            "symbol": symbol, "entry": round(pos["entry"], 4), "exit": round(fill, 4),
            "notional": pos["notional"], "pnl": round(pnl, 4),
            "ret_bps": round((fill / pos["entry"] - 1) * 1e4, 2),
            "opened": pos["opened"], "closed": datetime.now(timezone.utc).isoformat(),
            "reason": reason, "meta": pos.get("meta", {}),
        }
        self.data["cash"] += proceeds
        self.data["trades"].append(trade)
        self.save()
        return trade

    def age_days(self, symbol, now_utc):
        pos = self.data["positions"].get(symbol)
        if not pos:
            return 0
        opened = datetime.fromisoformat(pos["opened"])
        return (now_utc - opened).total_seconds() / 86400.0

    def stats(self):
        trades = self.data["trades"]
        n = len(trades)
        if n == 0:
            return {"trades": 0, "win_rate": None, "profit_factor": None, "expectancy_bps": None}
        wins = [t["pnl"] for t in trades if t["pnl"] > 0]
        losses = [-t["pnl"] for t in trades if t["pnl"] < 0]
        pf = (sum(wins) / sum(losses)) if losses else float("inf")
        return {
            "trades": n,
            "win_rate": round(len(wins) / n, 4),
            "profit_factor": round(pf, 3) if pf != float("inf") else None,
            "expectancy_bps": round(sum(t["ret_bps"] for t in trades) / n, 2),
            "total_pnl": round(sum(t["pnl"] for t in trades), 2),
        }

    def graduated(self, grad_cfg):
        """Implementation-proof bar, not an edge-proof bar (see config note):
        enough paper events to trust the plumbing, and expectancy not so
        negative that it screams implementation bug."""
        s = self.stats()
        return (
            s["trades"] >= grad_cfg["min_paper_events"]
            and s["expectancy_bps"] is not None
            and s["expectancy_bps"] >= grad_cfg["sanity_expectancy_bps_floor"]
        )
