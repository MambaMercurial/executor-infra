"""The Executor engine daemon — always-on Railway worker.

Two loops:
  FAST (this process, every poll): quotes → signals → paper books always;
    live book only through engine/risk.py gates → execution bridge.
  SLOW (invoked by this process): pre-market run (reconcile broker state,
    earnings watch, discretionary pipeline w/ adversarial skeptic), post-market
    run (journal, stats, graduation audit), weekly review (Fri).

The LLM never sits in the fast loop: intraday signal math, risk gating and
settlement accounting are deterministic Python. LLM runs are scheduled or
event-triggered (order execution bridge), each with hard turn/budget caps.

Run: python3 -m engine.daemon
Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (notify+veto), ANTHROPIC_API_KEY
     EXECUTOR_DRY_RUN=1 → simulate live fills without touching the broker.
"""
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import ledger as ledger_mod
from . import notify, quotes, risk
from .paper import PaperBook
from .signals import btctrend, meanrev, tom

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "state")
ET = ZoneInfo("America/New_York")

CONFIG = json.load(open(os.path.join(ROOT, "engine", "config.json")))
ENGINE_STATE_PATH = os.path.join(STATE, "engine_state.json")
OUTBOX = os.path.join(STATE, "orders", "outbox")
RESULTS = os.path.join(STATE, "orders", "results")
DAY_HALT = os.path.join(STATE, "DAY_HALT")
DRY_RUN = os.environ.get("EXECUTOR_DRY_RUN") == "1"


# ---------------------------------------------------------------- calendar --
def now_et():
    return datetime.now(ET)


def is_trading_day(d):
    return d.weekday() < 5 and d.isoformat() not in CONFIG["holidays_2026"]


def session_close(d):
    hhmm = (13, 0) if d.isoformat() in CONFIG["early_close_2026"] else (16, 0)
    return datetime(d.year, d.month, d.day, *hhmm, tzinfo=ET)


def market_open(ts):
    if not is_trading_day(ts.date()):
        return False
    o = ts.replace(hour=9, minute=30, second=0, microsecond=0)
    return o <= ts < session_close(ts.date())


def in_window(ts, window):
    lo = ts.replace(hour=int(window[0][:2]), minute=int(window[0][3:]), second=0)
    hi = ts.replace(hour=int(window[1][:2]), minute=int(window[1][3:]), second=0)
    return lo <= ts <= hi


# ------------------------------------------------------------------- state --
def load_engine_state():
    if os.path.exists(ENGINE_STATE_PATH):
        return json.load(open(ENGINE_STATE_PATH))
    return {"date": None, "day_start_equity": None, "peak_equity": None,
            "live_orders_today": 0, "live_meta": {}, "graduated": {}, "runs_done": {}}


def save_engine_state(s):
    os.makedirs(STATE, exist_ok=True)
    tmp = ENGINE_STATE_PATH + ".tmp"
    json.dump(s, open(tmp, "w"), indent=2)
    os.replace(tmp, ENGINE_STATE_PATH)


# --------------------------------------------------------------- slow loop --
def run_claude(prompt_file, budget, turns, label):
    cmd = [
        "claude", "-p", open(os.path.join(ROOT, prompt_file)).read(),
        "--allowedTools", "Read,Write,Edit,Bash(python3 *),mcp__robinhood__*",
        "--max-turns", str(turns), "--max-budget-usd", str(budget),
        "--output-format", "json",
    ]
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=1800)
        with open(os.path.join(STATE, f"last_{label}.json"), "w") as f:
            f.write(out.stdout or out.stderr or "")
        return out.returncode == 0
    except Exception as e:
        notify.send(f"⚠️ {label} run crashed: {e}")
        return False


# --------------------------------------------------------------- execution --
def execute_live(intent, led, prices):
    """Write intent to outbox, invoke the bridge, apply the result to the ledger."""
    oid = intent["id"]
    os.makedirs(OUTBOX, exist_ok=True)
    os.makedirs(RESULTS, exist_ok=True)
    intent["account_number"] = CONFIG["account_number"]
    with open(os.path.join(OUTBOX, f"{oid}.json"), "w") as f:
        json.dump(intent, f, indent=2)

    today = now_et().date()
    price = prices.get(intent["symbol"])
    if DRY_RUN:
        result = {"status": "filled", "fill_price": price,
                  "qty": (intent["notional"] / price) if (price and intent["side"] == "buy") else intent.get("qty"),
                  "amount": intent["notional"]}
    else:
        try:
            subprocess.run(["bash", os.path.join(ROOT, "scripts", "execute_order.sh"), oid],
                           cwd=ROOT, capture_output=True, text=True, timeout=240)
        except Exception:
            pass
        rf = os.path.join(RESULTS, f"{oid}.json")
        result = json.load(open(rf)) if os.path.exists(rf) else {"status": "no_result"}

    if result.get("status") == "filled":
        if intent["side"] == "buy":
            ok, funds_settle, _ = led.plan_buy(intent["notional"], today)
            if ok:
                led.record_buy(intent["symbol"], result.get("qty") or 0.0,
                               intent["notional"], today, intent["book"], funds_settle)
        else:
            led.record_sell(intent["symbol"], result.get("amount") or 0.0, today)
        notify.send(f"✅ LIVE {intent['side'].upper()} {intent['symbol']} ${intent['notional']:.2f} [{intent['book']}] ({'dry-run' if DRY_RUN else 'filled'})")
        return True
    notify.send(f"❌ LIVE order {oid} {intent['side']} {intent['symbol']} failed: {result.get('status')} — {result.get('error', '')[:200]}")
    return False


def flatten_live(led, prices, es, why):
    for sym in list(led.open_symbols()):
        ok, reason = led.can_sell(sym, now_et().date())
        if not ok:
            notify.send(f"⚠️ FLAT: cannot sell {sym} today ({reason}); will retry next session")
            continue
        meta = es["live_meta"].get(sym, {})
        execute_live({"id": f"flat-{uuid.uuid4().hex[:8]}", "side": "sell", "symbol": sym,
                      "book": meta.get("book", "unknown"), "notional": 0.0,
                      "qty": None, "reason": why}, led, prices)
        es["live_meta"].pop(sym, None)


# ------------------------------------------------------------------ books ---
def _exit_reason(book, sym, meta_or_pos, last, age_days, ts, history, params):
    if book == "meanrev":
        return meanrev.exit_signal(sym, history.get(sym, []), last, meta_or_pos["entry"], age_days, params)
    if book == "btctrend":
        return btctrend.exit_signal(ts.date(), history.get(sym, []), last, meta_or_pos["entry"], params)
    opened = datetime.fromisoformat(meta_or_pos["opened"]).astimezone(ET).date()
    return tom.exit_signal(ts.date(), opened, set(CONFIG["holidays_2026"]), params, last, meta_or_pos["entry"])


def process_book(book, cfg, pb, led, es, prices, history, ts):
    params = cfg["params"]
    live_enabled = (cfg.get("live") or es["graduated"].get(book)) and not risk.halted() and not os.path.exists(DAY_HALT)

    # exits — paper
    for sym in list(pb.data["positions"].keys()):
        pos = pb.data["positions"][sym]
        age = pb.age_days(sym, datetime.now(tz=ZoneInfo("UTC")))
        last = prices.get(sym)
        why = _exit_reason(book, sym, pos, last, age, ts, history, params)
        if why and last:
            t = pb.close_position(sym, last, why)
            if t:
                print(f"[paper:{book}] closed {sym} {why} {t['ret_bps']}bps", flush=True)

    # exits — live (positions this book owns)
    for sym, meta in list(es["live_meta"].items()):
        if meta.get("book") != book:
            continue
        last = prices.get(sym)
        age = (ts - datetime.fromisoformat(meta["opened"])).total_seconds() / 86400.0
        why = _exit_reason(book, sym, meta, last, age, ts, history, params)
        if why:
            ok, reason = led.can_sell(sym, ts.date())
            if ok:
                if execute_live({"id": f"x-{uuid.uuid4().hex[:8]}", "side": "sell", "symbol": sym,
                                 "book": book, "notional": 0.0, "reason": why}, led, prices):
                    es["live_meta"].pop(sym, None)
            elif "stop" in why:
                notify.send(f"🚨 {sym} at stop but settlement-locked today ({reason}). Exits at next legal session.")

    # entries
    if not in_window(ts, params["entry_window_et"]):
        return
    candidates = []
    if book == "meanrev":
        for sym in cfg.get("universe", CONFIG["universe"]):
            sig = meanrev.entry_signal(sym, history.get(sym, []), prices.get(sym), params)
            if sig:
                candidates.append(sig)
        candidates.sort(key=lambda s: s["z"])  # deepest dislocation first
    elif book == "btctrend":
        sig = btctrend.entry_signal(ts.date(), history.get(params["symbol"], []),
                                    prices.get(params["symbol"]), params)
        if sig:
            candidates.append(sig)
    else:  # tom
        sig = tom.entry_signal(ts.date(), set(CONFIG["holidays_2026"]), params,
                               prices.get(params["symbol"]))
        if sig:
            candidates.append(sig)

    for sig in candidates:
        sym = sig["symbol"]
        if len(pb.data["positions"]) < cfg["max_open"] and sym not in pb.data["positions"]:
            if pb.open_position(sym, cfg["paper_notional"], prices[sym],
                                params["stop_pct"], params.get("time_stop_days", params.get("hold_days", 5)),
                                meta=sig):
                print(f"[paper:{book}] opened {sym} {sig}", flush=True)

        if live_enabled and sym not in es["live_meta"] and sym not in led.open_symbols():
            intent = {"id": f"o-{uuid.uuid4().hex[:8]}", "side": "buy", "symbol": sym,
                      "notional": cfg["live_notional"], "book": book,
                      "stop_pct": params["stop_pct"], "signal": sig}
            es["date"] = ts.date().isoformat()
            ok, reasons = risk.gate_live_order(intent, led, es, CONFIG, prices)
            if ok:
                if execute_live(intent, led, prices):
                    es["live_orders_today"] = es.get("live_orders_today", 0) + 1
                    es["live_meta"][sym] = {"book": book, "entry": prices[sym],
                                            "opened": ts.isoformat(), "stop_pct": params["stop_pct"]}
            else:
                print(f"[gate] blocked {sym}: {reasons}", flush=True)


# ------------------------------------------------------------------- main ---
def main():
    # Railway sends SIGTERM on redeploy (then SIGKILL after drainingSeconds).
    # Exit cleanly so state is saved and no order is left half-tracked.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    for d in (OUTBOX, RESULTS, os.path.join(STATE, "paper"), os.path.join(STATE, "pending")):
        os.makedirs(d, exist_ok=True)
    led = ledger_mod.Ledger(holidays=CONFIG["holidays_2026"])
    # Bootstrap seed: an empty ledger reads $0 equity and (correctly) trips the
    # floor gate on everything. Seed from positions.json — last broker-verified
    # snapshot — so the engine is never blind; the premarket reconcile trues it
    # against the live broker every trading day.
    if not led.data["cash_lots"] and not led.data["positions"]:
        try:
            pos = json.load(open(os.path.join(STATE, "positions.json")))
            seed = float(pos.get("dry_powder") or pos.get("account_value") or 0)
            if seed > 0:
                led.seed_cash(seed, now_et().date())
                led.save()
                notify.send(f"🌱 Ledger seeded ${seed:.2f} settled from positions.json "
                            "(premarket reconcile will true against the broker)")
        except Exception:
            pass
    es = load_engine_state()
    books = {name: PaperBook(name, cfg["paper_start_cash"], CONFIG["spread_bps"])
             for name, cfg in CONFIG["books"].items()}
    history, history_ts = {}, 0.0
    notify.send(f"🟢 Executor engine online ({'DRY-RUN' if DRY_RUN else 'live-capable'}). Books: "
                + ", ".join(f"{n}({'LIVE' if (c.get('live') or es['graduated'].get(n)) else 'paper'})"
                            for n, c in CONFIG["books"].items()))

    while True:
        try:
            ts = now_et()
            today = ts.date().isoformat()

            # day rollover
            if es.get("date") != today:
                es["date"] = today
                es["live_orders_today"] = 0
                es["day_start_equity"] = None
                es["runs_done"] = {}
                if os.path.exists(DAY_HALT):
                    os.remove(DAY_HALT)

            # operator veto channel
            for cmd in notify.poll_commands():
                if cmd == "HALT":
                    open(risk.HALT_FILE, "w").write(ts.isoformat())
                    notify.send("🛑 HALT set — live trading stopped (paper continues). RESUME to clear.")
                elif cmd == "RESUME":
                    for p in (risk.HALT_FILE, risk.FLOOR_FILE, DAY_HALT):
                        if os.path.exists(p):
                            os.remove(p)
                    notify.send("▶️ RESUMED — live gates re-armed.")
                elif cmd == "FLAT":
                    prices = quotes.last_prices(CONFIG["universe"])
                    flatten_live(led, prices, es, "operator FLAT")
                    open(risk.HALT_FILE, "w").write(ts.isoformat())
                    notify.send("🛑 Flattened what was legal to sell; HALT set.")
                elif cmd == "STATUS":
                    prices = quotes.last_prices(CONFIG["universe"])
                    eq = led.total_cash() + led.position_value(prices)
                    lines = [f"equity ${eq:.2f} · cash ${led.total_cash():.2f} (settled ${led.settled_cash(ts.date()):.2f})",
                             f"live: {', '.join(led.open_symbols()) or 'flat'}"]
                    for n, b in books.items():
                        lines.append(f"{n}: {json.dumps(b.stats())}")
                    notify.send("📊 " + "\n".join(lines))

            # scheduled slow-loop runs
            if is_trading_day(ts.date()):
                pm = CONFIG["runs"]["premarket_et"]
                if ts.strftime("%H:%M") >= pm and not es["runs_done"].get("premarket"):
                    es["runs_done"]["premarket"] = True
                    save_engine_state(es)
                    run_claude("prompts/premarket.md", 1.50, 35, "premarket")
                    led = ledger_mod.Ledger(holidays=CONFIG["holidays_2026"])  # reload post-reconcile
                po = CONFIG["runs"]["postmarket_et"]
                if ts.strftime("%H:%M") >= po and not es["runs_done"].get("postmarket"):
                    es["runs_done"]["postmarket"] = True
                    # graduation audit — code decides, the LLM only narrates
                    for n, b in books.items():
                        if not (CONFIG["books"][n].get("live") or es["graduated"].get(n)) and b.graduated(CONFIG["graduation"]):
                            es["graduated"][n] = True
                            notify.send(f"🎓 {n} GRADUATED to live (stats: {json.dumps(b.stats())}). "
                                        f"Starts at ${CONFIG['books'][n]['live_notional']:.0f}/trade.")
                    save_engine_state(es)
                    run_claude("prompts/postmarket.md", 1.50, 35, "postmarket")
                    if ts.weekday() == CONFIG["runs"]["weekly_dow"]:
                        run_claude("prompts/weekly_review.md", 2.50, 45, "weekly")

            if not market_open(ts):
                save_engine_state(es)
                time.sleep(60)
                continue

            # fast loop body
            prices = quotes.last_prices(CONFIG["universe"])
            if time.time() - history_ts > 3600:
                h = quotes.daily_history(CONFIG["universe"], days=300)  # 200-SMA needs deep history
                if h:
                    history, history_ts = h, time.time()

            equity = round(led.total_cash() + led.position_value(prices), 2)
            if es["day_start_equity"] is None:
                es["day_start_equity"] = equity
            es["peak_equity"] = max(es.get("peak_equity") or equity, equity)

            # circuit breakers (live only — paper never halts)
            r = CONFIG["risk"]
            if equity < r["equity_floor"] and led.open_symbols():
                notify.send(f"🚨 EQUITY FLOOR: ${equity:.2f} < ${r['equity_floor']:.2f}. Flattening + permanent halt.")
                flatten_live(led, prices, es, "equity floor")
                risk.trip_floor(f"equity {equity:.2f}")
            elif es["day_start_equity"] and equity / es["day_start_equity"] - 1 <= -r["daily_loss_flatten_pct"]:
                if not os.path.exists(DAY_HALT):
                    notify.send(f"🚨 Day loss beyond {r['daily_loss_flatten_pct']:.0%}. Flattening live; halted until tomorrow.")
                    flatten_live(led, prices, es, "daily flatten breaker")
                    open(DAY_HALT, "w").write(today)

            for name, cfg in CONFIG["books"].items():
                process_book(name, cfg, books[name], led, es, prices, history, ts)

            save_engine_state(es)
            time.sleep(CONFIG["poll_seconds"])
        except KeyboardInterrupt:
            raise
        except Exception as e:
            print(f"[daemon] error: {e}", flush=True)
            try:
                notify.send(f"⚠️ engine error (continuing): {str(e)[:200]}")
            except Exception:
                pass
            time.sleep(60)


if __name__ == "__main__":
    sys.exit(main())
