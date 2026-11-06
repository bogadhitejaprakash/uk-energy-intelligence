-- =====================================================================
-- 03_analysis.sql  -  analytical views for EDA and Power BI
-- Views (not tables) so they always reflect the latest build.
-- =====================================================================

-- Grain: one row per half-hour.  fact_demand_hh + calendar + derived measures.
-- settlement_date is the UK local date, so it joins directly to bank holidays.
CREATE OR REPLACE VIEW v_fact_enriched AS
SELECT
    f.*,
    year(f.ts_local)                                AS year,
    month(f.ts_local)                               AS month,
    hour(f.ts_local) + minute(f.ts_local) / 60.0    AS hour_local,
    isodow(f.ts_local)                              AS day_of_week,     -- 1 = Monday, 7 = Sunday
    isodow(f.ts_local) >= 6                         AS is_weekend,
    bh.date IS NOT NULL                             AS is_bank_holiday,
    CASE
        WHEN month(f.ts_local) IN (12, 1, 2) THEN 'Winter'
        WHEN month(f.ts_local) IN (3, 4, 5)  THEN 'Spring'
        WHEN month(f.ts_local) IN (6, 7, 8)  THEN 'Summer'
        ELSE 'Autumn'
    END                                             AS season,
    -- Demand hidden behind embedded generation is still real consumption
    f.nd_mw + f.embedded_solar_mw + f.embedded_wind_mw AS underlying_demand_mw,
    -- Positive = NESO over-forecast
    f.neso_forecast_mw - f.nd_mw                    AS neso_error_mw
FROM fact_demand_hh AS f
LEFT JOIN dim_bank_holiday AS bh
       ON CAST(bh.date AS DATE) = f.settlement_date;


-- Grain: one row per year.  Window function LAG gives year-on-year change.
CREATE OR REPLACE VIEW v_annual_summary AS
WITH yearly AS (
    SELECT
        year,
        ROUND(COUNT(*) / 48.0)                          AS days,
        ROUND(AVG(nd_mw))                               AS avg_nd_mw,
        MAX(nd_mw)                                      AS peak_nd_mw,
        ROUND(AVG(underlying_demand_mw))                AS avg_underlying_mw,
        MAX(embedded_solar_capacity_mw)                 AS solar_capacity_mw,
        ROUND(SUM(embedded_solar_mw) / 2 / 1000000.0, 2) AS embedded_solar_twh
    FROM v_fact_enriched
    GROUP BY year
)
SELECT
    *,
    ROUND(100.0 * (avg_nd_mw / LAG(avg_nd_mw) OVER (ORDER BY year) - 1), 1) AS nd_yoy_pct
FROM yearly
ORDER BY year;


-- Grain: one row per day.  The single highest-demand half-hour of each day,
-- picked with ROW_NUMBER().  Peaks drive capacity planning.
CREATE OR REPLACE VIEW v_daily_peaks AS
WITH ranked AS (
    SELECT
        settlement_date,
        ts_local,
        hour_local,
        nd_mw,
        wa_temperature,
        neso_forecast_mw,
        ROW_NUMBER() OVER (PARTITION BY settlement_date ORDER BY nd_mw DESC) AS rn
    FROM v_fact_enriched
)
SELECT
    settlement_date,
    ts_local        AS peak_time_local,
    hour_local      AS peak_hour_local,
    nd_mw           AS peak_nd_mw,
    wa_temperature  AS temperature_at_peak,
    neso_forecast_mw - nd_mw AS neso_peak_error_mw
FROM ranked
WHERE rn = 1
ORDER BY settlement_date;


-- Grain: one row per (year, month).  How good is NESO's day-ahead forecast?
CREATE OR REPLACE VIEW v_neso_error_monthly AS
SELECT
    year,
    month,
    COUNT(*)                                            AS periods,
    ROUND(AVG(ABS(neso_error_mw)))                      AS mae_mw,
    ROUND(100 * AVG(ABS(neso_error_mw) / nd_mw), 2)     AS mape_pct,
    ROUND(AVG(neso_error_mw))                           AS bias_mw,
    ROUND(AVG(embedded_solar_mw))                       AS avg_embedded_solar_mw
FROM v_fact_enriched
WHERE neso_forecast_mw IS NOT NULL
GROUP BY year, month
ORDER BY year, month;
