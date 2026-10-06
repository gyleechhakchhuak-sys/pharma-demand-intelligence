![Pharmaceutical demand dashboard](docs/dashboard.png)

# Pharmaceutical Demand Intelligence & Supply Planning

A local analytics application for exploring pharmaceutical sales,
evaluating demand forecasts, and comparing inventory planning scenarios.

Built with Python, pandas, statsmodels, SQLAlchemy, PostgreSQL,
FastAPI, React, and Vite.

## Features

- Converts hourly, daily, weekly, and monthly source files into a
  consistent timestamp–drug-class–sales structure.
- Validates timestamps, numeric values, duplicate timestamps,
  and hourly/daily time coverage.
- Reconciles hourly sales with supplied daily totals.
- Analyzes class concentration, daily variability, weekday patterns,
  and monthly trends.
- Compares seasonal-naive and Holt-Winters forecasts using
  rolling-origin validation and a separate holdout.
- Calculates safety-stock and reorder-point scenarios.
- Displays sales KPIs, class shares, forecast metrics, inventory
  scenarios, and reconciliation results through an API-connected dashboard.

## Results

Daily analysis excludes two incomplete boundary days.

| Metric | Result |
|---|---:|
| Hourly timestamp records | 50,532 |
| Hourly timestamp–class observations | 404,256 |
| Drug classes | 8 |
| Complete days analyzed | 2,104 |
| Recorded sales volume over complete days | 127,476.174 |
| Top-three class share | 73.08% |
| Hourly-to-daily pairs reconciled | 16,848 |
| Reconciliation issues at absolute tolerance 0.000001 | 0 |

The three largest classes by recorded volume were N02BE, N05B, and R03.

Sales volume is measured in the source dataset's units; it is not revenue.

## Forecast evaluation

The target is total daily sales across all eight classes.

- Forecast horizon: 28 days.
- Validation: three successive 28-day windows with expanding training data.
- Final holdout: 10 September–7 October 2019.
- Selection metric: pooled validation WAPE.
- Baseline: repeat the last seven observed days.
- Holt-Winters: additive seasonality, a damped additive trend,
  and a seven-day seasonal period.
- Predictions are constrained to be nonnegative.

| Model | Validation WAPE | Holdout WAPE |
|---|---:|---:|
| Seasonal naive | 30.255% | 29.367% |
| Holt-Winters | 22.034% | 30.245% |

Holt-Winters was selected using validation, but the seasonal-naive
baseline performed better on the final holdout. This implementation
does not demonstrate improved holdout performance.

WAPE = sum(abs(actual - forecast)) / sum(abs(actual)) × 100.

After evaluation, the selected model is refitted using all complete
days. The resulting forecasts begin on 8 October 2019.
They are historical demonstrations, not current forecasts.

## Inventory assumptions

Aggregate forecasts are allocated to classes using constant sales
shares from the last 90 complete days.

Safety stock = recent average daily sales × buffer days.

Reorder point = forecast demand during supplier lead time + safety stock.

| Scenario | Lead time | Buffer |
|---|---:|---:|
| Short delivery | 3 days | 2 days |
| Standard delivery | 7 days | 3 days |
| Delayed delivery | 14 days | 7 days |

These are illustrative assumptions, not measured supplier performance.
Reorder points are thresholds, not recommended order quantities.

## Dataset and attribution

Source: **Pharma Sales Data**, provided by Milan Zdravković.

- Original dataset:
  https://www.kaggle.com/datasets/milanzdravkovic/pharma-sales-data
- Download mirror used:
  https://github.com/mcallara/pharma-sales-data

The mirror identifies the dataset license as
Creative Commons Attribution-NonCommercial 4.0:
https://creativecommons.org/licenses/by-nc/4.0/

The data is third-party material and was not collected by this project's
author. Raw data is excluded from this repository.

Download and extract these files into `data/raw/`:

- saleshourly.csv
- salesdaily.csv
- salesweekly.csv
- salesmonthly.csv

## Local setup — Windows PowerShell

### Prerequisites

- Python 3.12
- Node.js compatible with the included Vite version
- npm
- PostgreSQL
- Git

### Python environment

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Database configuration

Create an empty PostgreSQL database named `pharma_demand`.

Copy the example configuration:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your local database credentials:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pharma_demand
DB_USER=postgres
DB_PASSWORD='your_local_password'
```

Never commit `.env`.

The local demonstration uses the installation's database account.
A deployed application should use a dedicated account with restricted
permissions.

### Run the data pipeline

After placing the four source CSVs in `data/raw/`, run these commands
in order. Stop and resolve any error before continuing.

```powershell
.\.venv\Scripts\python.exe scripts\inspect_data.py
.\.venv\Scripts\python.exe scripts\prepare_data.py
.\.venv\Scripts\python.exe scripts\reconcile_data.py
.\.venv\Scripts\python.exe scripts\analyze_sales.py
.\.venv\Scripts\python.exe scripts\forecast_sales.py
.\.venv\Scripts\python.exe scripts\plan_inventory.py
.\.venv\Scripts\python.exe scripts\load_database.py
```

Processed CSVs and reports are generated locally.

The database loader expects its destination tables not to exist.
It deliberately refuses to overwrite existing tables. Rerunning
analysis scripts does not automatically refresh database contents.

### Start the API

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

- Health: http://127.0.0.1:8000/health
- Interactive API documentation: http://127.0.0.1:8000/docs

### Start the frontend

In a second terminal, from the repository root:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --port 5173 --strictPort
```

Open http://localhost:5173.

Keep both frontend and backend servers running.

### Check the frontend build

From the repository root:

```powershell
npm.cmd --prefix frontend run build
```

This creates frontend assets in `frontend/dist`.
It does not deploy the API or database.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `/health` | Check database connectivity |
| `/kpis` | Summary metrics |
| `/classes` | Class sales and variability |
| `/trends/monthly` | Monthly totals and coverage |
| `/patterns/weekday` | Average sales by weekday |
| `/forecast` | Evaluation metrics, holdout predictions, and forecasts |
| `/inventory?scenario=standard_delivery` | Stored inventory scenario |
| `/quality` | Hourly-to-daily reconciliation summary |

## Limitations

- Sales are a proxy for demand; stockouts and lost sales are unknown.
- Forecast evaluation covers a limited historical period.
- Class forecasts use proportional allocation and are not independently
  validated class-level models.
- Buffer-day scenarios do not guarantee a service level.
- Monthly boundary periods are incomplete and require coverage-aware
  interpretation.
- Weekly and monthly files are standardized but have not been reconciled
  against the hourly data.
- Product-level inventory, pack sizes, expiry dates, supplier performance,
  costs, and incoming orders are unavailable.
- ML forecasting, automated anomaly detection, and capacity optimization
  are not implemented.
- This is a local demonstration without application authentication
  or production deployment configuration.