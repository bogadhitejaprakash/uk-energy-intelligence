-- =====================================================================
-- 01_staging.sql  -  clean, typed, de-duplicated versions of raw tables
-- Grain of every table is stated in its comment.
-- Note: no semicolons inside comments (the runner splits on them).
-- =====================================================================

-- Grain: one row per half-hour settlement period (UTC start time)
CREATE OR REPLACE TABLE stg_demand AS
SELECT
    ts_utc,
    ts_local,
    CAST(settlement_date AS DATE)            AS settlement_date,
    CAST(settlement_period AS INTEGER)       AS settlement_period,
    CAST(nd AS INTEGER)                      AS nd_mw,
    CAST(tsd AS INTEGER)                     AS tsd_mw,
    CAST(england_wales_demand AS INTEGER)    AS england_wales_demand_mw,
    CAST(embedded_wind_generation AS INTEGER)  AS embedded_wind_mw,
    CAST(embedded_wind_capacity AS INTEGER)    AS embedded_wind_capacity_mw,
    CAST(embedded_solar_generation AS INTEGER) AS embedded_solar_mw,
    CAST(embedded_solar_capacity AS INTEGER)   AS embedded_solar_capacity_mw,
    CAST(pump_storage_pumping AS INTEGER)      AS pump_storage_pumping_mw
FROM raw_demand;


-- Grain: one row per half-hour.  NESO day-ahead forecast (benchmark).
-- Autumn clock-change days are excluded: NESO's file repeats the extra
-- hour under the same period numbers, so periods cannot be aligned reliably.
CREATE OR REPLACE TABLE stg_neso_forecast AS
WITH ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (
            PARTITION BY date, settlement_period
            ORDER BY publish_datetime DESC
        ) AS rn
    FROM raw_neso_forecast
)
SELECT
    ts_utc,
    CAST(date AS DATE)                         AS settlement_date,
    CAST(settlement_period AS INTEGER)         AS settlement_period,
    CAST(demand_forecast AS INTEGER)           AS neso_forecast_mw,
    CAST(demand_outturn AS INTEGER)            AS neso_outturn_mw,
    CAST(triad_avoidance_estimate AS INTEGER)  AS triad_adjustment_mw,
    publish_datetime
FROM ranked
WHERE rn = 1
  AND NOT (month(date) = 10 AND isodow(date) = 7 AND day(date) >= 25);


-- Grain: one row per city.  Approximate metro population used as weights.
-- (dim_city is created from src/config.py by the Python runner.)


-- Grain: one row per (source, hour).  Population-weighted GB weather.
-- source = 'actual' (ERA5) or 'forecast' (issued 24h ahead).
-- Each variable is weighted only over cities where it is not null.
CREATE OR REPLACE TABLE stg_weather_gb_hourly AS
SELECT
    w.source,
    w.time_utc,
    SUM(w.temperature_2m * c.pop_m)       / NULLIF(SUM(CASE WHEN w.temperature_2m       IS NOT NULL THEN c.pop_m END), 0) AS temperature_2m,
    SUM(w.apparent_temperature * c.pop_m) / NULLIF(SUM(CASE WHEN w.apparent_temperature IS NOT NULL THEN c.pop_m END), 0) AS apparent_temperature,
    SUM(w.relative_humidity_2m * c.pop_m) / NULLIF(SUM(CASE WHEN w.relative_humidity_2m IS NOT NULL THEN c.pop_m END), 0) AS relative_humidity_2m,
    SUM(w.wind_speed_10m * c.pop_m)       / NULLIF(SUM(CASE WHEN w.wind_speed_10m       IS NOT NULL THEN c.pop_m END), 0) AS wind_speed_10m,
    SUM(w.cloud_cover * c.pop_m)          / NULLIF(SUM(CASE WHEN w.cloud_cover          IS NOT NULL THEN c.pop_m END), 0) AS cloud_cover,
    SUM(w.shortwave_radiation * c.pop_m)  / NULLIF(SUM(CASE WHEN w.shortwave_radiation  IS NOT NULL THEN c.pop_m END), 0) AS shortwave_radiation,
    SUM(w.precipitation * c.pop_m)        / NULLIF(SUM(CASE WHEN w.precipitation        IS NOT NULL THEN c.pop_m END), 0) AS precipitation,
    COUNT(*) AS n_cities
FROM raw_weather AS w
JOIN dim_city    AS c USING (city)
GROUP BY w.source, w.time_utc;


-- Grain: one row per (source, half-hour).
-- Weather is hourly, demand half-hourly.  For a period starting on the hour
-- we use that hour's value.  For a period starting at :30 we average the
-- hour before and the hour after (linear interpolation).
-- Trick: truncating (ts + 30 min) to the hour gives the SAME hour for :00
-- and the NEXT hour for :30, so one formula covers both.
CREATE OR REPLACE TABLE stg_weather_gb_hh AS
WITH grid AS (
    SELECT source, time_utc AS ts_utc FROM stg_weather_gb_hourly
    UNION ALL
    SELECT source, time_utc + INTERVAL 30 MINUTE FROM stg_weather_gb_hourly
)
SELECT
    g.source,
    g.ts_utc,
    (h0.temperature_2m       + h1.temperature_2m)       / 2 AS temperature_2m,
    (h0.apparent_temperature + h1.apparent_temperature) / 2 AS apparent_temperature,
    (h0.relative_humidity_2m + h1.relative_humidity_2m) / 2 AS relative_humidity_2m,
    (h0.wind_speed_10m       + h1.wind_speed_10m)       / 2 AS wind_speed_10m,
    (h0.cloud_cover          + h1.cloud_cover)          / 2 AS cloud_cover,
    (h0.shortwave_radiation  + h1.shortwave_radiation)  / 2 AS shortwave_radiation,
    (h0.precipitation        + h1.precipitation)        / 2 AS precipitation
FROM grid AS g
LEFT JOIN stg_weather_gb_hourly AS h0
       ON h0.source = g.source AND h0.time_utc = date_trunc('hour', g.ts_utc)
LEFT JOIN stg_weather_gb_hourly AS h1
       ON h1.source = g.source AND h1.time_utc = date_trunc('hour', g.ts_utc + INTERVAL 30 MINUTE);
