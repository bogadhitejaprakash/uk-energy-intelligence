-- =====================================================================
-- 02_marts.sql  -  analysis-ready tables used by EDA, Power BI and models
-- =====================================================================

-- Grain: one row per half-hour.  THE main table of the project.
--   wa_*  = actual weather (ERA5)          -> EDA and training
--   wf_*  = weather forecast issued 24h ahead -> fair benchmark vs NESO
CREATE OR REPLACE TABLE fact_demand_hh AS
SELECT
    d.ts_utc,
    d.ts_local,
    d.settlement_date,
    d.settlement_period,
    d.nd_mw,
    d.tsd_mw,
    d.england_wales_demand_mw,
    d.embedded_solar_mw,
    d.embedded_wind_mw,
    d.embedded_solar_capacity_mw,
    d.embedded_wind_capacity_mw,
    d.pump_storage_pumping_mw,
    f.neso_forecast_mw,
    f.neso_outturn_mw,
    f.triad_adjustment_mw,
    wa.temperature_2m       AS wa_temperature,
    wa.apparent_temperature AS wa_apparent_temperature,
    wa.relative_humidity_2m AS wa_humidity,
    wa.wind_speed_10m       AS wa_wind_speed,
    wa.cloud_cover          AS wa_cloud_cover,
    wa.shortwave_radiation  AS wa_solar_radiation,
    wa.precipitation        AS wa_precipitation,
    wf.temperature_2m       AS wf_temperature,
    wf.apparent_temperature AS wf_apparent_temperature,
    wf.relative_humidity_2m AS wf_humidity,
    wf.wind_speed_10m       AS wf_wind_speed,
    wf.cloud_cover          AS wf_cloud_cover,
    wf.shortwave_radiation  AS wf_solar_radiation,
    wf.precipitation        AS wf_precipitation
FROM stg_demand AS d
LEFT JOIN stg_neso_forecast AS f  ON f.ts_utc = d.ts_utc
LEFT JOIN stg_weather_gb_hh AS wa ON wa.ts_utc = d.ts_utc AND wa.source = 'actual'
LEFT JOIN stg_weather_gb_hh AS wf ON wf.ts_utc = d.ts_utc AND wf.source = 'forecast'
ORDER BY d.ts_utc;


-- Grain: one row per day.  Handy for Power BI and quick EDA.
CREATE OR REPLACE VIEW v_daily_demand AS
SELECT
    settlement_date,
    COUNT(*)                                   AS n_periods,
    ROUND(AVG(nd_mw))                          AS avg_nd_mw,
    MAX(nd_mw)                                 AS peak_nd_mw,
    MIN(nd_mw)                                 AS min_nd_mw,
    ROUND(SUM(nd_mw) / 2 / 1000.0, 1)          AS energy_gwh,     -- MW x 0.5h -> MWh -> GWh
    ROUND(AVG(wa_temperature), 1)              AS avg_temperature,
    ROUND(SUM(embedded_solar_mw) / 2 / 1000.0, 1) AS embedded_solar_gwh,
    ROUND(AVG(ABS(neso_forecast_mw - nd_mw)))  AS neso_mae_mw
FROM fact_demand_hh
GROUP BY settlement_date
ORDER BY settlement_date;
