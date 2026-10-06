import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import URL, create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

if not os.getenv("DB_PASSWORD"):
    raise RuntimeError("Set DB_PASSWORD in the project's .env file")

connection_url = URL.create(
    drivername="postgresql+psycopg",
    username=os.getenv("DB_USER", "postgres"),
    password=os.environ["DB_PASSWORD"],
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "5432")),
    database=os.getenv("DB_NAME", "pharma_demand"),
)

engine = create_engine(connection_url, pool_pre_ping=True)


@asynccontextmanager
async def lifespan(app):
    yield
    engine.dispose()


app = FastAPI(
    title="Pharmaceutical Demand Intelligence",
    description="Historical sales analysis and inventory scenarios.",
    lifespan=lifespan,
)

# Allow the local React dashboard to request data from this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def fetch_rows(sql, parameters=None):
    with engine.connect() as connection:
        result = connection.execute(text(sql), parameters or {})
        return [dict(row) for row in result.mappings()]


@app.get("/health")
def health():
    result = fetch_rows("SELECT current_database() AS database")
    return {"status": "ok", "database": result[0]["database"]}


@app.get("/kpis")
def kpis():
    result = fetch_rows("""
        SELECT
            SUM(sales) AS total_sales,
            COUNT(DISTINCT drug_class) AS drug_classes,
            COUNT(DISTINCT timestamp) AS complete_days,
            MIN(timestamp) AS start_date,
            MAX(timestamp) AS end_date
        FROM sales_daily_analysis
    """)[0]

    result["top_three_share_pct"] = fetch_rows("""
        SELECT SUM(share_pct) AS share
        FROM (
            SELECT share_pct
            FROM class_summary
            ORDER BY total_sales DESC
            LIMIT 3
        ) AS top_classes
    """)[0]["share"]

    return result


@app.get("/classes")
def classes():
    return fetch_rows("""
        SELECT *
        FROM class_summary
        ORDER BY total_sales DESC
    """)


@app.get("/trends/monthly")
def monthly_trends():
    return fetch_rows("""
        SELECT *
        FROM monthly_trend
        ORDER BY month
    """)


@app.get("/patterns/weekday")
def weekday_pattern():
    return fetch_rows("""
        SELECT *
        FROM weekday_pattern
        ORDER BY CASE weekday
            WHEN 'Monday' THEN 1
            WHEN 'Tuesday' THEN 2
            WHEN 'Wednesday' THEN 3
            WHEN 'Thursday' THEN 4
            WHEN 'Friday' THEN 5
            WHEN 'Saturday' THEN 6
            WHEN 'Sunday' THEN 7
        END
    """)


@app.get("/forecast")
def forecast():
    return {
        "metrics": fetch_rows("""
            SELECT * FROM forecast_metrics ORDER BY model
        """),
        "holdout": fetch_rows("""
            SELECT * FROM forecast_holdout ORDER BY timestamp
        """),
        "future": fetch_rows("""
            SELECT * FROM forecast_next_28_days ORDER BY timestamp
        """),
    }


@app.get("/inventory")
def inventory(
    scenario: Literal[
        "short_delivery", "standard_delivery", "delayed_delivery"
    ] = "standard_delivery",
):
    return fetch_rows("""
        SELECT *
        FROM inventory_scenarios
        WHERE scenario = :scenario
        ORDER BY reorder_point DESC
    """, {"scenario": scenario})


@app.get("/quality")
def quality():
    result = fetch_rows("""
        SELECT
            COUNT(*) AS checked_pairs,
            COUNT(*) FILTER (
                WHERE matches IS TRUE
            ) AS matching_pairs,
            COUNT(*) FILTER (
                WHERE matches IS NOT TRUE
            ) AS issue_pairs,
            MAX(ABS(difference)) AS max_absolute_difference,
            COUNT(DISTINCT date) FILTER (
                WHERE recorded_hours <> 24
            ) AS incomplete_days
        FROM hourly_daily_reconciliation
    """)[0]

    result["scope"] = "Hourly-to-daily reconciliation"
    return result