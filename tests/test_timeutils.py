"""Unit tests for settlement-period -> timestamp conversion (no database needed)."""
import pandas as pd

from src.data.timeutils import settlement_to_utc, utc_to_local


def _utc(date, periods):
    s = settlement_to_utc(pd.Series([date] * len(periods)), pd.Series(periods))
    return [str(t) for t in s]


def test_winter_day_period_1_is_midnight_utc():
    assert _utc("2024-01-15", [1, 48]) == ["2024-01-15 00:00:00", "2024-01-15 23:30:00"]


def test_summer_day_is_one_hour_behind():
    # BST = UTC+1, so local midnight is 23:00 UTC the previous day
    assert _utc("2024-07-01", [1, 48]) == ["2024-06-30 23:00:00", "2024-07-01 22:30:00"]


def test_spring_clock_change_has_46_continuous_periods():
    ts = pd.to_datetime(_utc("2024-03-31", list(range(1, 47))))
    assert ts[0] == pd.Timestamp("2024-03-31 00:00")
    assert ts[-1] == pd.Timestamp("2024-03-31 22:30")            # 23:30 BST
    assert (pd.Series(ts).diff().dropna() == pd.Timedelta("30min")).all()


def test_autumn_clock_change_has_50_continuous_periods():
    ts = pd.to_datetime(_utc("2024-10-27", list(range(1, 51))))
    assert ts[0] == pd.Timestamp("2024-10-26 23:00")             # 00:00 BST
    assert ts[-1] == pd.Timestamp("2024-10-27 23:30")            # 23:30 GMT
    assert (pd.Series(ts).diff().dropna() == pd.Timedelta("30min")).all()


def test_local_time_round_trip_on_autumn_day():
    ts = settlement_to_utc(pd.Series(["2024-10-27"] * 50), pd.Series(range(1, 51)))
    local = utc_to_local(ts)
    # 01:00-01:30 local happens twice on the autumn clock-change day
    assert (local.dt.strftime("%H:%M") == "01:00").sum() == 2
