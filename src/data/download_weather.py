"""
Download hourly weather for six GB cities from Open-Meteo (free, no key).

Two modes - the difference matters for a fair comparison with NESO:
  actual    ERA5 reanalysis = what the weather really was (2019 onwards).
            Use for EDA and for training.
  forecast  What the weather model predicted 24 hours ahead (Jan 2024 onwards).
            NESO only had forecasts when it made its day-ahead demand forecast,
            so our model must use these too when we benchmark against NESO.

Usage:
    python -m src.data.download_weather --mode actual
    python -m src.data.download_weather --mode forecast

Files: data/external/weather/<mode>/<city>_<year>.csv  (hourly, UTC)
The current year is always re-downloaded so it stays up to date.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta

import pandas as pd
import requests

from src.config import (CITIES, EXTERNAL_DIR, FORECAST_ARCHIVE_START,
                        OPEN_METEO_ACTUAL_URL, OPEN_METEO_FORECAST_URL, WEATHER_VARS)
from src.data.download_neso import HEADERS

FORECAST_SUFFIX = "_previous_day1"  # value predicted 24 hours before the valid time


def date_ranges(start: date, end: date):
    """Split [start, end] into calendar-year chunks."""
    for year in range(start.year, end.year + 1):
        s = max(start, date(year, 1, 1))
        e = min(end, date(year, 12, 31))
        yield year, s, e


def fetch(mode: str, lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
    if mode == "actual":
        url, variables = OPEN_METEO_ACTUAL_URL, WEATHER_VARS
    else:
        url, variables = OPEN_METEO_FORECAST_URL, [v + FORECAST_SUFFIX for v in WEATHER_VARS]

    params = {
        "latitude": lat, "longitude": lon,
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "hourly": ",".join(variables), "timezone": "UTC",
    }
    for attempt in range(5):
        r = requests.get(url, params=params, headers=HEADERS, timeout=120)
        if r.status_code == 429:  # rate limited - back off and retry
            wait = 30 * (attempt + 1)
            print(f"      rate limited, waiting {wait}s")
            time.sleep(wait)
            continue
        if r.status_code != 200:
            raise RuntimeError(f"Open-Meteo error {r.status_code}: {r.text[:300]}")
        hourly = r.json()["hourly"]
        df = pd.DataFrame(hourly).rename(columns={"time": "time_utc"})
        df.columns = [c.replace(FORECAST_SUFFIX, "") for c in df.columns]
        return df
    raise RuntimeError("Gave up after repeated rate limiting")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["actual", "forecast"], required=True)
    parser.add_argument("--start", default=None, help="YYYY-MM-DD (default: 2019-01-01 actual, 2024-01-01 forecast)")
    parser.add_argument("--force", action="store_true", help="re-download completed years")
    args = parser.parse_args(argv)

    today = date.today()
    if args.mode == "actual":
        start = date.fromisoformat(args.start or "2019-01-01")
        end = today - timedelta(days=7)   # ERA5 is published with a ~5 day delay
    else:
        start = date.fromisoformat(args.start or FORECAST_ARCHIVE_START)
        end = today - timedelta(days=1)

    out_dir = EXTERNAL_DIR / "weather" / args.mode
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Weather mode={args.mode}: {start} to {end}, {len(CITIES)} cities")

    for city, c in CITIES.items():
        for year, s, e in date_ranges(start, end):
            dest = out_dir / f"{city}_{year}.csv"
            if dest.exists() and year != today.year and not args.force:
                continue
            df = fetch(args.mode, c["lat"], c["lon"], s, e)
            df.insert(0, "city", city)
            df.to_csv(dest, index=False)
            null_share = df[WEATHER_VARS].isna().mean().max()
            flag = f"  !! up to {null_share:.0%} missing in a variable" if null_share > 0.01 else ""
            print(f"-> {city} {year}: {len(df):,} hours{flag}")
            time.sleep(1)  # be polite to a free API

    print(f"\nDone. Files saved in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
