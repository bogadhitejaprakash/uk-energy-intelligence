"""Central project paths and constants."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"
REFERENCE_DIR = DATA_DIR / "reference"   # small, hand-checked lookup files (committed to git)
FIGURES_DIR = ROOT / "reports" / "figures"
DB_PATH = DATA_DIR / "energy.duckdb"

# NESO Data Portal (CKAN API)
NESO_API = "https://api.neso.energy/api/3/action"
NESO_HISTORIC_DEMAND_PACKAGE = "historic-demand-data"

# Half-hourly settlement periods: 48 on a normal day,
# 46 on the spring clock change, 50 on the autumn clock change.
NORMAL_PERIODS_PER_DAY = 48

# --- NESO day-ahead forecast datasets (CKAN resource IDs) ---
NESO_FORECAST_RESOURCES = {
    # Half-hourly day-ahead forecast vs outturn, April 2021 onwards (our main benchmark)
    "day_ahead_hh_performance": "08e41551-80f8-4e28-a416-ea473a695db9",
    # Day-ahead forecasts at cardinal points (peaks/troughs), 2018 onwards
    "day_ahead_cardinal_points": "9847e7bb-986e-49be-8138-717b25933fbb",
}

# --- Weather (Open-Meteo, free, no API key) ---
OPEN_METEO_ACTUAL_URL = "https://archive-api.open-meteo.com/v1/archive"          # ERA5 reanalysis
OPEN_METEO_FORECAST_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"  # forecasts as issued
FORECAST_ARCHIVE_START = "2024-01-01"  # Previous Runs API archive starts Jan 2024 for most models

WEATHER_VARS = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "wind_speed_10m",
    "cloud_cover",
    "shortwave_radiation",   # drives embedded solar
    "precipitation",
]

# Six population centres spread across GB. Weights are approximate metro-area
# populations (millions) used to build a GB "population-weighted" temperature.
CITIES = {
    "london":     {"lat": 51.5074, "lon": -0.1278, "pop_m": 9.6},
    "birmingham": {"lat": 52.4862, "lon": -1.8904, "pop_m": 2.9},
    "manchester": {"lat": 53.4808, "lon": -2.2426, "pop_m": 2.8},
    "leeds":      {"lat": 53.8008, "lon": -1.5491, "pop_m": 2.3},
    "glasgow":    {"lat": 55.8642, "lon": -4.2518, "pop_m": 1.8},
    "cardiff":    {"lat": 51.4816, "lon": -3.1791, "pop_m": 1.1},
}
