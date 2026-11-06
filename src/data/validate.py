"""
First data-quality checks on the raw NESO demand files.

Usage:
    python -m src.data.validate

Lessons from the raw files (kept here because they matter for the ETL):
- NESO uses THREE date formats across years: 01-JAN-2019, 01-Jan-23, 2025-01-01.
  Parsing them all with one "mixed / dayfirst" rule silently swaps day and month
  for ISO dates (2026-10-12 became 10 Dec 2026), so each file gets an explicit format.
- Columns change over time (SCOTTISH_TRANSFER from 2023, FORECAST_ACTUAL_INDICATOR
  from 2026). Rows flagged "F" are NESO forecasts, not actual demand, and are dropped.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.config import NORMAL_PERIODS_PER_DAY, RAW_DIR

DATE_FORMATS = ["%Y-%m-%d", "%d-%b-%Y", "%d-%b-%y"]  # %b is case-insensitive


def parse_dates(s: pd.Series) -> pd.Series:
    """Parse a date column with the first format that fits EVERY value."""
    s = s.astype(str).str.strip()
    for fmt in DATE_FORMATS:
        parsed = pd.to_datetime(s, format=fmt, errors="coerce")
        if parsed.notna().all():
            return parsed
    raise ValueError(f"Unrecognised date format, e.g. {s.iloc[0]!r}")


def load_raw() -> pd.DataFrame:
    files = sorted((RAW_DIR / "neso").glob("demanddata_*.csv"))
    if not files:
        raise FileNotFoundError("No raw files found. Run: python -m src.data.download_neso")

    frames = []
    for f in files:
        df = pd.read_csv(f, low_memory=False)
        df.columns = [c.strip().upper() for c in df.columns]
        df["SETTLEMENT_DATE"] = parse_dates(df["SETTLEMENT_DATE"])
        df["SOURCE_FILE"] = f.name
        frames.append(df)

    df = pd.concat(frames, ignore_index=True)
    if "FORECAST_ACTUAL_INDICATOR" in df.columns:
        n_forecast = (df["FORECAST_ACTUAL_INDICATOR"] == "F").sum()
        print(f"Dropping {n_forecast} forecast ('F') rows - we only want actuals")
        df = df[df["FORECAST_ACTUAL_INDICATOR"] != "F"]
    return df


def run_checks(df: pd.DataFrame) -> None:
    start, end = df["SETTLEMENT_DATE"].min().date(), df["SETTLEMENT_DATE"].max().date()
    print(f"Rows: {len(df):,}  |  {start} to {end}")
    if end > date.today():
        print("!! Latest date is in the future - date parsing is wrong")

    print("\nColumns that are not in every year:")
    per_file = {name: set(g.dropna(axis=1, how="all").columns)
                for name, g in df.groupby("SOURCE_FILE")}
    common = set.intersection(*per_file.values())
    for col in sorted(set.union(*per_file.values()) - common):
        years = [f[11:15] for f, cols in per_file.items() if col in cols]
        print(f"  {col}: {years[0]}-{years[-1]}")

    dupes = df.duplicated(["SETTLEMENT_DATE", "SETTLEMENT_PERIOD"]).sum()
    print(f"\nDuplicate (date, period) rows: {dupes}")

    print("Missing values in key columns:")
    print(df[["ND", "TSD"]].isna().sum().to_string())

    all_days = pd.date_range(start, end, freq="D")
    missing_days = all_days.difference(df["SETTLEMENT_DATE"].unique())
    print(f"\nCalendar days with no data at all: {len(missing_days)}")

    per_day = df.groupby("SETTLEMENT_DATE")["SETTLEMENT_PERIOD"].nunique()
    odd = per_day[per_day != NORMAL_PERIODS_PER_DAY]
    print(f"Days without {NORMAL_PERIODS_PER_DAY} periods: {len(odd)} "
          "(expect 46 on the last Sunday of March, 50 on the last Sunday of October)")
    unexpected = [d for d, n in odd.items()
                  if not (d.day_of_week == 6 and d.day >= 25 and
                          ((d.month == 3 and n == 46) or (d.month == 10 and n == 50)))]
    print(f"  ...of which NOT explained by clock changes: {len(unexpected)}")
    for d in unexpected:
        print(f"     {d.date()}: {odd[d]} periods")

    print(f"\nRows with ND <= 0: {(df['ND'] <= 0).sum()}")


if __name__ == "__main__":
    run_checks(load_raw())
