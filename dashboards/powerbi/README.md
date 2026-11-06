# Power BI dashboard — build guide

Three pages, built from four CSV files exported from the DuckDB warehouse.

| Page | Question it answers |
|---|---|
| 1 · Overview | How much electricity does GB use, and how is it changing? |
| 2 · Demand drivers | What makes demand go up and down? |
| 3 · NESO forecast performance | Where does the industry's day-ahead forecast go wrong? |

---

## Step 1 — Export the data

```powershell
python -m src.data.export_powerbi
```

This writes `dim_date`, `fact_daily`, `fact_halfhourly` and `fact_daily_peaks` to `dashboards/powerbi/data/`
(git-ignored — rerun after every database rebuild, then **Refresh** in Power BI).

## Step 2 — Load the four CSVs

1. Power BI Desktop → **Get data → Text/CSV** → `dim_date.csv` → **Transform Data**.
2. In Power Query, check the column types (icon left of each header):
   - `date` → **Date** · `ts_local`, `peak_time_local` → **Date/Time**
   - `is_weekend`, `is_bank_holiday` → **True/False**
   - all `_mw`, `_gwh`, `_c`, `_pct` columns → **Decimal number**
3. **Home → New Source → Text/CSV** for the other three files, same checks.
4. **Close & Apply**.

## Step 3 — Model (star schema)

In **Model view**:

1. Drag `dim_date[date]` onto `date` in each fact table → three **one-to-many** relationships, single direction.
2. Select `dim_date` → **Table tools → Mark as date table** → column `date`.
3. Sort-by-column (select the column → **Column tools → Sort by column**):
   - `dim_date[month_name]` by `month` · `dim_date[day_name]` by `day_of_week`
   - `dim_date[season]` by `season_order` · `fact_halfhourly[solar_band]` by `solar_band_order`
4. Hide the `date` column in the three fact tables (right-click → **Hide in report view**) so every visual uses `dim_date`.

```
            ┌──────────────┐
            │   dim_date   │
            └──────┬───────┘
         1 ┌───────┼────────┐ 1
           ▼ *     ▼ *      ▼ *
   fact_daily  fact_halfhourly  fact_daily_peaks
```

## Step 4 — Measures and theme

1. **Home → Enter data** → name the table `_Measures` → **Load**.
2. Add each measure from [`measures.dax`](measures.dax) (**New measure**, paste one block at a time).
   Format: `… (GW)` → 1 decimal · `… %` → Percentage, 1 decimal · `(MW)` → whole number with thousands separator.
3. **View → Themes → Browse for themes** → `theme.json` (same colour-blind-safe palette as the notebook charts).

## Step 5 — Build the pages

Put a **Year** slicer (`dim_date[year]`) and a **Season** slicer (`dim_date[season]`) at the top of every page
(**View → Sync slicers** to share them).

### Page 1 · Overview
| Visual | Fields |
|---|---|
| 5 × Card | Avg Demand (GW) · Peak Demand (GW) · Grid Energy (TWh) · Avg Demand YoY % · Hidden Demand % |
| Line chart | X: `dim_date[year_month]` · Y: Avg Demand (GW), Avg Underlying Demand (GW) |
| Column chart | X: `dim_date[year]` · Y: Solar Capacity (GW) |
| Text box | *"Grid demand fell 11.6% since 2019 but consumption only 5.7% — rooftop solar hides the rest."* |

### Page 2 · Demand drivers
| Visual | Fields | Filter |
|---|---|---|
| Line chart | X: `fact_halfhourly[hour_local]` · Y: Avg Demand (GW) · Legend: `dim_date[season]` | `day_type` = Weekday |
| Bar chart | Y: `dim_date[day_type]` · X: Avg Demand (GW) | — |
| Scatter | X: `fact_daily[avg_temperature_c]` · Y: `fact_daily[avg_nd_mw]` · Values: `dim_date[date]` | `day_type` = Weekday |
| Line chart | X: `fact_halfhourly[solar_band]` · Y: Avg Demand (GW), Avg Underlying Demand (GW) | `month` 5–8, `hour` 12–13, Weekday |

### Page 3 · NESO forecast performance
| Visual | Fields | Filter |
|---|---|---|
| 3 × Card | NESO MAPE % · NESO MAE (MW) · NESO Bias (MW) | — |
| Matrix (heatmap) | Rows: `month_name` · Columns: `year` · Values: NESO MAPE % | Year ≥ 2021 |
| Line chart | X: `fact_halfhourly[hour]` · Y: NESO MAE (MW) · Legend: `dim_date[year]` | Year = 2022, 2025 |
| Column chart | X: `fact_halfhourly[solar_band]` · Y: NESO Bias (MW) | `month` 4–9, `hour` 9–17 |
| Text box | *"NESO's error has grown at sunny middays: it expects too little solar on sunny days and too much on dull ones."* |

**Heatmap:** select the matrix → **Format → Cell elements → Background color → fx** → Gradient, lowest = light blue `#cde2fb`, highest = dark blue `#0d366b`.
**Bias chart:** **Format → Columns → Color → fx** → Rules: value < 0 → blue `#2a78d6`, value ≥ 0 → red `#e34948`.

The numbers should match `notebooks/01_eda.ipynb` (e.g. 2025 NESO MAPE ≈ 2.7%).

## Step 6 — Save and screenshot

1. Save as `dashboards/powerbi/uk_energy_dashboard.pbix`.
2. Screenshot each page into `reports/figures/powerbi_overview.png`, `powerbi_drivers.png`, `powerbi_neso.png`
   (they appear in the main README for anyone without Power BI).
