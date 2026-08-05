"""BTC Slow Trend, Banded — long/flat, weekly evaluation, the one crypto
strategy that survived the cost research (docs/05, part F).

Robinhood crypto round trip ≈ 100bps on BTC — only weeks-to-months trend
holds an edge bigger than that toll. Asymmetric band: hard to enter (20-day
breakout AND above 100-SMA), slow to exit (below 100-SMA AND 40-SMA), so
turnover stays at 3–8 round trips/year. Evaluated once a week; the 60–90s
data delay is irrelevant at this cadence by design.
"""
import statistics


def entry_signal(today, closes, last, params):
    if today.weekday() != params["eval_dow"]:
        return None
    if not closes or len(closes) < params["sma_slow"] + 5 or not last:
        return None
    breakout_high = max(closes[-params["breakout_days"]:])
    sma_slow = statistics.fmean(closes[-params["sma_slow"]:])
    if last > breakout_high and last > sma_slow:
        return {"symbol": params["symbol"], "breakout_20d": True,
                "vs_sma_slow": round(last / sma_slow - 1, 4)}
    return None


def exit_signal(today, closes, last, entry_price, params):
    if not last:
        return None
    if last <= entry_price * (1 - params["stop_pct"]):
        return "disaster_stop"
    if today.weekday() != params["eval_dow"]:
        return None  # weekly cadence: trend exits only on evaluation day
    if not closes or len(closes) < params["sma_slow"]:
        return None
    sma_slow = statistics.fmean(closes[-params["sma_slow"]:])
    sma_fast = statistics.fmean(closes[-params["sma_fast"]:])
    if last < sma_slow and last < sma_fast:
        return "trend_exit"
    return None
