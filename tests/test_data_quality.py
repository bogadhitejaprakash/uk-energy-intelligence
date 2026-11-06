"""
Data-quality tests on the built warehouse. Run after build_database:

    python -m pytest -v
"""
import pytest

duckdb = pytest.importorskip("duckdb")
from src.config import DB_PATH  # noqa: E402

pytestmark = pytest.mark.skipif(not DB_PATH.exists(), reason="run src.data.build_database first")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB_PATH), read_only=True)
    yield c
    c.close()


def one(con, sql):
    return con.execute(sql).fetchone()[0]


def test_one_row_per_half_hour(con):
    assert one(con, "SELECT COUNT(*) - COUNT(DISTINCT ts_utc) FROM fact_demand_hh") == 0


def test_no_gaps_in_time_series(con):
    gaps = one(con, """
        SELECT COUNT(*) FROM (
            SELECT ts_utc - LAG(ts_utc) OVER (ORDER BY ts_utc) AS step FROM fact_demand_hh
        ) WHERE step <> INTERVAL 30 MINUTE
    """)
    assert gaps == 0


def test_demand_is_present_and_plausible(con):
    assert one(con, "SELECT COUNT(*) FROM fact_demand_hh WHERE nd_mw IS NULL") == 0
    lo, hi = con.execute("SELECT MIN(nd_mw), MAX(nd_mw) FROM fact_demand_hh").fetchone()
    assert 5_000 < lo and hi < 60_000, (lo, hi)


def test_actual_weather_complete(con):
    # ERA5 lags ~1 week, so only check periods up to the last weather hour
    missing = one(con, """
        SELECT COUNT(*) FROM fact_demand_hh
        WHERE wa_temperature IS NULL
          AND ts_utc < (SELECT MAX(time_utc) FROM raw_weather WHERE source = 'actual')
    """)
    assert missing == 0


def test_forecast_weather_complete_in_benchmark_window(con):
    missing = one(con, """
        SELECT COUNT(*) FROM fact_demand_hh
        WHERE wf_temperature IS NULL
          AND ts_utc >= TIMESTAMP '2024-03-07'
          AND ts_utc <  (SELECT MAX(time_utc) FROM raw_weather WHERE source = 'forecast')
    """)
    assert missing == 0


def test_neso_outturn_matches_our_demand(con):
    # Confirms the timestamp alignment of the two NESO sources (ND within ~1%)
    mae = one(con, """
        SELECT AVG(ABS(neso_outturn_mw - nd_mw)) FROM fact_demand_hh
        WHERE neso_outturn_mw IS NOT NULL
    """)
    assert mae < 200, mae


def test_population_weighted_temperature_is_sensible(con):
    lo, hi = con.execute("SELECT MIN(wa_temperature), MAX(wa_temperature) FROM fact_demand_hh").fetchone()
    assert -20 < lo < 0 and 25 < hi < 42, (lo, hi)


def test_enriched_view_does_not_duplicate_rows(con):
    # A bad join to the bank-holiday table would multiply rows
    assert one(con, "SELECT COUNT(*) FROM v_fact_enriched") == one(con, "SELECT COUNT(*) FROM fact_demand_hh")


def test_bank_holidays_are_flagged(con):
    # Christmas Day 2024: all 48 periods flagged
    assert one(con, """
        SELECT COUNT(*) FROM v_fact_enriched
        WHERE settlement_date = DATE '2024-12-25' AND is_bank_holiday
    """) == 48


def test_one_peak_per_day(con):
    assert one(con, "SELECT COUNT(*) FROM v_daily_peaks") == one(
        con, "SELECT COUNT(DISTINCT settlement_date) FROM fact_demand_hh")
