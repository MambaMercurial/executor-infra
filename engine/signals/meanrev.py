"""Short-term mean reversion, long-only, on liquid index/sector ETFs.

Research-tuned (docs/05_RESEARCH_NOTES.md):
  - Close-proximate entry window (delay-immune: signal is close-based math).
  - REGIME FILTER is the risk control: only buy dips when price > 200-day SMA.
    Tight stops demonstrably hurt this strategy class, so stop_pct is a wide
    DISASTER stop, not a trading stop.
  - Exit on z-score recovery or time stop (~10 trading days).
"""
import statistics


def zscore(closes, last, ret_days, lookback):
    series = closes[-lookback:] + [last]
    rets = [series[i] / series[i - ret_days] - 1 for i in range(ret_days, len(series))]
    if len(rets) < 20:
        return None
    hist, current = rets[:-1], rets[-1]
    mu = statistics.fmean(hist)
    sd = statistics.stdev(hist)
    if sd == 0:
        return None
    return (current - mu) / sd


def entry_signal(symbol, closes, last, params):
    """Deep short-term dislocation in an uptrending ETF. None unless all clear."""
    need = max(params["sma_trend_days"] + 10, params["lookback_days"] + 25)
    if not closes or len(closes) < need or not last:
        return None
    sma_trend = statistics.fmean(closes[-params["sma_trend_days"]:])
    if last <= sma_trend:
        return None  # regime filter: no dip-buying in a downtrend
    z = zscore(closes, last, params["ret_days"], params["lookback_days"])
    if z is None or z > params["z_entry"]:
        return None
    return {"symbol": symbol, "z": round(z, 2), "sma_dist": round(last / sma_trend - 1, 4)}


def exit_signal(symbol, closes, last, entry_price, age_days, params):
    if not last:
        return None
    if last <= entry_price * (1 - params["stop_pct"]):
        return "disaster_stop"
    if age_days >= params["time_stop_days"]:
        return "time"
    z = zscore(closes, last, params["ret_days"], params["lookback_days"]) if closes else None
    if z is not None and z >= params["z_exit"]:
        return "z_recovered"
    return None
