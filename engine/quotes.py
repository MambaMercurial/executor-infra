"""Quote layer for the fast loop. yfinance: free, ~seconds-delayed, good enough
for hours-to-days horizons. The Robinhood MCP stays the source of truth for
account state (reconciled by the pre-market run); this feeds signal math only.

Failure posture: every function degrades to {} / None. The daemon treats missing
quotes as 'no signal this poll', never as zero."""
import time


def _yf():
    import yfinance  # lazy: not needed for unit tests
    return yfinance


def daily_history(symbols, days=90):
    """{symbol: [closes oldest→newest, most recent `days` bars]} — hourly refresh.
    Always requests 2y (valid yfinance period) and slices; 200-SMA needs depth."""
    try:
        df = _yf().download(
            " ".join(symbols), period="2y", interval="1d",
            auto_adjust=True, progress=False, group_by="ticker", threads=False,
        )
        out = {}
        for s in symbols:
            try:
                closes = df[s]["Close"].dropna().tolist() if len(symbols) > 1 else df["Close"].dropna().tolist()
                if closes:
                    out[s] = closes[-days:]
            except Exception:
                continue
        return out
    except Exception:
        return {}


def last_prices(symbols):
    """{symbol: last_price} via a single batched 1-minute download."""
    try:
        df = _yf().download(
            " ".join(symbols), period="1d", interval="1m",
            auto_adjust=False, progress=False, group_by="ticker", threads=False,
        )
        out = {}
        for s in symbols:
            try:
                series = df[s]["Close"].dropna() if len(symbols) > 1 else df["Close"].dropna()
                if len(series):
                    out[s] = float(series.iloc[-1])
            except Exception:
                continue
        return out
    except Exception:
        return {}
