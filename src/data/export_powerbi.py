"""
Export analysis-ready tables from DuckDB to CSV for Power BI.

    python -m src.data.export_powerbi

Power BI Desktop cannot read .duckdb files directly, so this writes a small
star schema to dashboards/powerbi/data/:

    dim_date            one row per day (calendar, bank holidays, season)
    fact_daily          one row per day (daily totals and extremes)
    fact_halfhourly     one row per half-hour (profiles, hour-of-day analysis)
    fact_daily_peaks    one row per day (time and size of the daily peak)

All facts join to dim_date on [date].
"""
from __future__ import annotations

import sys

import duckdb

from src.config import DB_PATH, ROOT

OUT_DIR = ROOT / "dashboards" / "powerbi" / "data"

QUERIES = {
    "dim_date": """
        SELECT
            d.settlement_date                         AS date,
            year(d.settlement_date)                   AS year,
            quarter(d.settlement_date)                AS quarter,
            month(d.settlement_date)                  AS month,
            strftime(d.settlement_date, '%b')         AS month_name,
            strftime(d.settlement_date, '%Y-%m')      AS year_month,
            isodow(d.settlement_date)                 AS day_of_week,
            strftime(d.settlement_date, '%a')         AS day_name,
            isodow(d.settlement_date) >= 6            AS is_weekend,
            bh.name IS NOT NULL                       AS is_bank_holiday,
            bh.name                                   AS bank_holiday_name,
            CASE
                WHEN bh.name IS NOT NULL THEN 'Bank holiday'
                WHEN isodow(d.settlement_date) = 6 THEN 'Saturday'
                WHEN isodow(d.settlement_date) = 7 THEN 'Sunday'
                ELSE 'Weekday'
            END                                       AS day_type,
            CASE
                WHEN month(d.settlement_date) IN (12, 1, 2) THEN 'Winter'
                WHEN month(d.settlement_date) IN (3, 4, 5)  THEN 'Spring'
                WHEN month(d.settlement_date) IN (6, 7, 8)  THEN 'Summer'
                ELSE 'Autumn'
            END                                       AS season,
            CASE
                WHEN month(d.settlement_date) IN (12, 1, 2) THEN 1
                WHEN month(d.settlement_date) IN (3, 4, 5)  THEN 2
                WHEN month(d.settlement_date) IN (6, 7, 8)  THEN 3
                ELSE 4
            END                                       AS season_order
        FROM (SELECT DISTINCT settlement_date FROM fact_demand_hh) AS d
        LEFT JOIN dim_bank_holiday AS bh
               ON CAST(bh.date AS DATE) = d.settlement_date
        ORDER BY date
    """,
    "fact_daily": """
        SELECT
            settlement_date                                  AS date,
            COUNT(*)                                         AS periods,
            ROUND(AVG(nd_mw))                                AS avg_nd_mw,
            MAX(nd_mw)                                       AS peak_nd_mw,
            MIN(nd_mw)                                       AS min_nd_mw,
            ROUND(SUM(nd_mw) / 2 / 1000.0, 2)                AS nd_energy_gwh,
            ROUND(SUM(underlying_demand_mw) / 2 / 1000.0, 2) AS underlying_energy_gwh,
            ROUND(SUM(embedded_solar_mw) / 2 / 1000.0, 2)    AS embedded_solar_gwh,
            ROUND(SUM(embedded_wind_mw) / 2 / 1000.0, 2)     AS embedded_wind_gwh,
            MAX(embedded_solar_capacity_mw)                  AS solar_capacity_mw,
            ROUND(AVG(wa_temperature), 1)                    AS avg_temperature_c,
            ROUND(MIN(wa_temperature), 1)                    AS min_temperature_c,
            ROUND(MAX(wa_temperature), 1)                    AS max_temperature_c
        FROM v_fact_enriched
        GROUP BY settlement_date
        ORDER BY date
    """,
    "fact_halfhourly": """
        SELECT
            settlement_date                     AS date,
            ts_local,
            settlement_period,
            hour_local,
            CAST(floor(hour_local) AS INTEGER)  AS hour,
            nd_mw,
            underlying_demand_mw,
            embedded_solar_mw,
            embedded_wind_mw,
            ROUND(wa_temperature, 1)            AS temperature_c,
            neso_forecast_mw,
            neso_error_mw,
            ABS(neso_error_mw)                  AS neso_abs_error_mw,
            ROUND(100.0 * ABS(neso_error_mw) / nd_mw, 3) AS neso_ape_pct,
            CASE
                WHEN embedded_solar_mw < 2000  THEN '0-2 GW'
                WHEN embedded_solar_mw < 4000  THEN '2-4 GW'
                WHEN embedded_solar_mw < 6000  THEN '4-6 GW'
                WHEN embedded_solar_mw < 8000  THEN '6-8 GW'
                WHEN embedded_solar_mw < 10000 THEN '8-10 GW'
                ELSE '10+ GW'
            END                                 AS solar_band,
            CAST(LEAST(floor(embedded_solar_mw / 2000), 5) AS INTEGER) AS solar_band_order
        FROM v_fact_enriched
        ORDER BY ts_local
    """,
    "fact_daily_peaks": """
        SELECT
            settlement_date AS date,
            peak_time_local,
            peak_hour_local,
            peak_nd_mw,
            ROUND(temperature_at_peak, 1) AS temperature_at_peak_c,
            neso_peak_error_mw
        FROM v_daily_peaks
        ORDER BY date
    """,
}


def main() -> int:
    if not DB_PATH.exists():
        print("No database. Run: python -m src.data.build_database")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_PATH), read_only=True)
    for name, sql in QUERIES.items():
        df = con.sql(sql).df()
        path = OUT_DIR / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  {name:<18} {len(df):>8,} rows  ->  {path.relative_to(ROOT)}")
    con.close()
    print("\nNext: open Power BI Desktop and follow dashboards/powerbi/README.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
