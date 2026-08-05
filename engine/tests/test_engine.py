"""Self-test for the autonomous engine's load-bearing walls: the settlement
ledger, the live-order risk gate, the paper book, and the calendar signals.
Run: python3 -m engine.tests.test_engine   (no network, no secrets needed)"""
import json
import os
import sys
import tempfile
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from engine.ledger import Ledger, next_business_day
from engine import risk
from engine.paper import PaperBook
from engine.signals import meanrev, tom

HOLIDAYS = ["2026-09-07"]
PASSED = []


def check(name, cond):
    PASSED.append((name, bool(cond)))
    print(f"  {'ok ' if cond else 'FAIL'} {name}")


def fresh_ledger(tmp, cash=198.74, day=date(2026, 8, 5)):
    led = Ledger(path=os.path.join(tmp, "ledger.json"), holidays=HOLIDAYS)
    led.seed_cash(cash, day)
    return led


def main():
    tmp = tempfile.mkdtemp()
    d0 = date(2026, 8, 5)   # Wednesday
    fri = date(2026, 9, 4)  # Friday before Labor Day

    # --- ledger: settlement mechanics -----------------------------------
    led = fresh_ledger(tmp)
    ok, fs, _ = led.plan_buy(50.0, d0)
    check("buy from settled cash allowed", ok and fs == d0)
    led.record_buy("SPY", 0.08, 50.0, d0, "meanrev", fs)
    check("cash reduced after buy", abs(led.total_cash() - 148.74) < 0.01)
    ok, _ = led.can_sell("SPY", d0)
    check("same-day sell of settled-funded lot allowed (never a GFV)", ok)
    led.record_sell("SPY", 50.5, d0)
    check("proceeds unsettled same day", led.settled_cash(d0) == 148.74)
    check("proceeds settle next business day", led.settled_cash(date(2026, 8, 6)) == 199.24)

    ok, _, why = led.plan_buy(160.0, d0)
    check("buy beyond SETTLED cash blocked (Robinhood semantics)", not ok and "SETTLED" in why)
    ok, _, _ = led.plan_buy(0.5, d0)
    check("sub-$1 fractional order blocked", not ok)
    check("holiday-aware settlement (Fri sale settles Tue over Labor Day)",
          next_business_day(fri, set(HOLIDAYS)) == date(2026, 9, 8))
    ok, why2 = led.can_sell("QQQ", d0)
    check("selling a position we don't hold blocked", not ok)

    # --- risk gate -------------------------------------------------------
    cfg = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")))
    led2 = fresh_ledger(tmp + "2")
    es = {"date": d0.isoformat(), "day_start_equity": 198.74, "peak_equity": 198.74,
          "live_orders_today": 0, "live_meta": {}, "graduated": {}}
    intent = {"id": "t1", "side": "buy", "symbol": "SPY", "notional": 15.0,
              "book": "meanrev", "stop_pct": 0.08}
    ok, reasons = risk.gate_live_order(intent, led2, es, cfg, {"SPY": 630.0})
    check("normal live buy passes gate", ok)

    big = dict(intent, notional=150.0, stop_pct=0.10)
    ok, reasons = risk.gate_live_order(big, led2, es, cfg, {"SPY": 630.0})
    check("per-trade max-loss cap bites", not ok and any("max loss" in r for r in reasons))

    over_alloc = dict(intent, notional=70.0, stop_pct=0.01)
    ok, reasons = risk.gate_live_order(over_alloc, led2, es, cfg, {"SPY": 630.0})
    check("book allocation cap bites", not ok and any("allocation" in r for r in reasons))

    es_burnt = dict(es, live_orders_today=cfg["risk"]["max_live_orders_per_day"])
    ok, reasons = risk.gate_live_order(intent, led2, es_burnt, cfg, {"SPY": 630.0})
    check("orders/day cadence cap bites", not ok)

    es_down = dict(es, day_start_equity=250.0)
    ok, reasons = risk.gate_live_order(intent, led2, es_down, cfg, {"SPY": 630.0})
    check("daily-loss circuit breaker blocks new buys", not ok)

    led_floor = fresh_ledger(tmp + "3", cash=140.0)
    ok, reasons = risk.gate_live_order(intent, led_floor, es, cfg, {"SPY": 630.0})
    check("equity floor blocks trading", not ok and any("floor" in r for r in reasons))

    sell_no_pos = {"id": "t2", "side": "sell", "symbol": "SPY", "notional": 0, "book": "meanrev"}
    ok, reasons = risk.gate_live_order(sell_no_pos, led2, es, cfg, {"SPY": 630.0})
    check("sell without a position blocked", not ok)

    # --- paper book ------------------------------------------------------
    os.environ.setdefault("TMPDIR", tmp)
    import engine.paper as paper_mod
    paper_mod.PAPER_DIR = os.path.join(tmp, "paper")
    pb = PaperBook("testbook", 2000.0, {"default": 6})
    pb.open_position("SPY", 50.0, 630.0, 0.08, 10)
    check("paper fill pays half-spread on entry", pb.data["positions"]["SPY"]["entry"] > 630.0)
    t = pb.close_position("SPY", 640.0, "test")
    check("paper round trip nets spread cost", t is not None and t["ret_bps"] < (640.0 / 630.0 - 1) * 1e4)
    check("paper stats track", pb.stats()["trades"] == 1)
    check("graduation bar enforces min events", not pb.graduated(cfg["graduation"]))

    # --- signals ---------------------------------------------------------
    closes = [100.0 + 0.05 * i for i in range(260)]
    sig = meanrev.entry_signal("SPY", closes, closes[-1] * 0.97, cfg["books"]["meanrev"]["params"])
    check("meanrev fires on sharp dip in uptrend", sig is not None)
    sig2 = meanrev.entry_signal("SPY", closes, closes[-1] * 1.01, cfg["books"]["meanrev"]["params"])
    check("meanrev silent without dislocation", sig2 is None)
    downtrend = [200.0 - 0.3 * i for i in range(260)]
    sig3 = meanrev.entry_signal("SPY", downtrend, downtrend[-1] * 0.97, cfg["books"]["meanrev"]["params"])
    check("meanrev 200-SMA regime filter blocks downtrend dips", sig3 is None)

    hol = set()
    check("TOM entry on last trading day of Aug", tom.is_entry_day(date(2026, 8, 31), hol, 2))
    check("TOM entry on 2nd-to-last trading day", tom.is_entry_day(date(2026, 8, 28), hol, 2))
    check("TOM no entry mid-month", not tom.is_entry_day(date(2026, 8, 18), hol, 2))
    why = tom.exit_signal(date(2026, 9, 3), date(2026, 8, 31), {"2026-09-07"},
                          {"symbol": "SPY", "exit_trading_day_of_month": 3, "stop_pct": 0.05,
                           "entry_days_before_eom": 2}, 630.0, 629.0)
    check("TOM exits on 3rd trading day of new month", why == "tom_exit")

    n_fail = sum(1 for _, ok in PASSED if not ok)
    print(f"\n{len(PASSED) - n_fail}/{len(PASSED)} engine self-test cases passed")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main()
