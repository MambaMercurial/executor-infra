"""Turn-of-the-month on SPY.

Long the last ~2 trading days of the month through the ~3rd trading day of the
next month. The one calendar effect still statistically significant in
1980-2024 samples. 12 events/year — this runs on the 45-year evidence prior;
the live sample can never prove it and we don't pretend otherwise.
"""
from datetime import date, timedelta


def trading_days_of_month(year, month, holidays):
    d = date(year, month, 1)
    out = []
    while d.month == month:
        if d.weekday() < 5 and d.isoformat() not in holidays:
            out.append(d)
        d += timedelta(days=1)
    return out


def is_entry_day(d, holidays, entry_days_before_eom):
    tds = trading_days_of_month(d.year, d.month, holidays)
    return d in tds and d >= tds[-entry_days_before_eom]


def trading_day_index(d, holidays):
    """1-based index of d among its month's trading days (0 if not one)."""
    tds = trading_days_of_month(d.year, d.month, holidays)
    return tds.index(d) + 1 if d in tds else 0


def entry_signal(today, holidays, params, last):
    if not last:
        return None
    if is_entry_day(today, holidays, params["entry_days_before_eom"]):
        return {"symbol": params["symbol"], "window": "tom"}
    return None


def exit_signal(today, opened_date, holidays, params, last, entry_price):
    if not last:
        return None
    if last <= entry_price * (1 - params["stop_pct"]):
        return "disaster_stop"
    if (today.year, today.month) != (opened_date.year, opened_date.month):
        if trading_day_index(today, holidays) >= params["exit_trading_day_of_month"]:
            return "tom_exit"
    return None
