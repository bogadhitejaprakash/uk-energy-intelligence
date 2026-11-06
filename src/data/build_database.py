"""
Build the DuckDB warehouse: data/energy.duckdb

    python -m src.data.build_database

Layers:
  raw_*   files loaded as-is (Python handles formats and timestamps)
  stg_*   cleaned and typed            (sql/01_staging.sql)
  fact_*  analysis-ready tables, views (sql/02_marts.sql)
  v_*     analytical views for EDA / Power BI (sql/03_analysis.sql)

The whole database is rebuilt from the raw files every time, so it is
reproducible and never edited by hand.
"""
from __future__ import annotations

import sys

import duckdb
import pandas as pd

from src.config import (CITIES, DB_PATH, EXTERNAL_DIR, RAW_DIR, REFERENCE_DIR, ROOT)
from src.data.timeutils import settlement_to_utc, utc_to_local
from src.data.validate import load_raw

SQL_DIR = ROOT / "sql"


# ---------------------------------------------------------------- raw loaders
def load_demand() -> pd.DataFrame:
    df = load_raw()  # handles NESO's three date formats + forecast rows
    df.columns = [c.lower() for c in df.columns]
    df["ts_utc"] = settlement_to_utc(df["settlement_date"], df["settlement_period"])
    df["ts_local"] = utc_to_local(df["ts_utc"])
    return df


def load_neso_forecast() -> pd.DataFrame:
    df = pd.read_csv(RAW_DIR / "neso_forecasts" / "day_ahead_hh_performance.csv")
    df.columns = [c.lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    df["publish_datetime"] = pd.to_datetime(df["publish_datetime"], utc=True).dt.tz_localize(None)
    # NB: NESO's 'datetime' column is local time despite its 'Z' suffix - not used.
    df["ts_utc"] = settlement_to_utc(df["date"], df["settlement_period"])
    return df.drop(columns=["datetime"])


def load_weather() -> pd.DataFrame:
    frames = []
    for source in ["actual", "forecast"]:
        for f in sorted((EXTERNAL_DIR / "weather" / source).glob("*.csv")):
            df = pd.read_csv(f)
            df["source"] = source
            frames.append(df)
    if not frames:
        raise FileNotFoundError("No weather files. Run: python -m src.data.download_weather --mode actual")
    df = pd.concat(frames, ignore_index=True)
    df["time_utc"] = pd.to_datetime(df["time_utc"])
    return df


def load_cities() -> pd.DataFrame:
    return pd.DataFrame([{"city": k, **v} for k, v in CITIES.items()])


def load_bank_holidays() -> pd.DataFrame:
    """England & Wales bank holidays (source: gov.uk/bank-holidays)."""
    df = pd.read_csv(REFERENCE_DIR / "bank_holidays_england_wales.csv")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


# ---------------------------------------------------------------- sql runner
def run_sql_file(con: duckdb.DuckDBPyConnection, path) -> None:
    """Run every statement in a .sql file (split on ';')."""
    text = path.read_text(encoding="utf-8")
    for stmt in text.split(";"):
        code = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if code:
            con.execute(code)


def main() -> int:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()  # full rebuild every time
    con = duckdb.connect(str(DB_PATH))

    print("Loading raw files...")
    for name, loader in [("raw_demand", load_demand),
                         ("raw_neso_forecast", load_neso_forecast),
                         ("raw_weather", load_weather),
                         ("dim_city", load_cities),
                         ("dim_bank_holiday", load_bank_holidays)]:
        df = loader()
        con.register("tmp_df", df)
        con.execute(f"CREATE TABLE {name} AS SELECT * FROM tmp_df")
        con.unregister("tmp_df")
        print(f"  {name:<20} {len(df):>10,} rows")

    for sql_file in sorted(SQL_DIR.glob("*.sql")):
        print(f"Running {sql_file.name}")
        run_sql_file(con, sql_file)

    print("\nTables:")
    tables = con.execute("""
        SELECT table_name, table_type FROM information_schema.tables
        WHERE table_schema = 'main' ORDER BY table_name
    """).fetchall()
    for name, ttype in tables:
        n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        print(f"  {name:<24} {n:>10,} rows  ({ttype.lower()})")

    print("\nCoverage of fact_demand_hh:")
    print(con.execute("""
        SELECT
            MIN(ts_utc)                                   AS first_period,
            MAX(ts_utc)                                   AS last_period,
            COUNT(*)                                      AS periods,
            ROUND(100 * COUNT(neso_forecast_mw) / COUNT(*), 1) AS pct_with_neso_forecast,
            ROUND(100 * COUNT(wa_temperature)   / COUNT(*), 1) AS pct_with_actual_weather,
            ROUND(100 * COUNT(wf_temperature)   / COUNT(*), 1) AS pct_with_forecast_weather
        FROM fact_demand_hh
    """).df().T.to_string(header=False))

    con.close()
    print(f"\nDone. Database: {DB_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
