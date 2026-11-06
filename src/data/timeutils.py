"""Convert GB settlement periods to real timestamps."""
import pandas as pd

UK_TZ = "Europe/London"


def settlement_to_utc(settlement_date: pd.Series, settlement_period: pd.Series) -> pd.Series:
    """
    Start time (UTC, timezone-naive) of each half-hour settlement period.

    Settlement period 1 starts at local midnight, and periods count ELAPSED
    half-hours from there. So a spring clock-change day has 46 periods and an
    autumn one has 50 - converting via UTC handles both without special cases.
    """
    dates = pd.to_datetime(settlement_date).dt.normalize()
    midnight_utc = dates.dt.tz_localize(UK_TZ).dt.tz_convert("UTC").dt.tz_localize(None)
    return midnight_utc + pd.to_timedelta((settlement_period.astype(int) - 1) * 30, unit="min")


def utc_to_local(ts_utc: pd.Series) -> pd.Series:
    """UTC (naive) -> UK local wall-clock time (naive). Used for calendar features."""
    return ts_utc.dt.tz_localize("UTC").dt.tz_convert(UK_TZ).dt.tz_localize(None)
