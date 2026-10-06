import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import (
    create_engine, text, URL, DateTime, Float, String
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

TABLES = {
    "sales_hourly": "data/processed/sales_hourly.csv",
    "sales_daily": "data/processed/sales_daily.csv",
    "sales_daily_analysis": "data/processed/sales_daily_analysis.csv",
    "class_summary": "reports/class_summary.csv",
    "weekday_pattern": "reports/weekday_pattern.csv",
    "monthly_trend": "reports/monthly_trend.csv",
    "forecast_validation": "reports/forecast_validation.csv",
    "forecast_metrics": "reports/forecast_metrics.csv",
    "forecast_holdout": "reports/forecast_holdout.csv",
    "forecast_next_28_days": "reports/forecast_next_28_days.csv",
    "inventory_scenarios": "reports/inventory_scenarios.csv",
    "allocated_class_forecasts": "reports/allocated_class_forecasts.csv",
    "hourly_daily_reconciliation": "reports/hourly_daily_reconciliation.csv",
}

DATE_COLUMNS = {
    "timestamp", "date", "training_end",
    "train_end", "test_start", "test_end",
}


def main():
    if not os.getenv("DB_PASSWORD"):
        raise ValueError("Set DB_PASSWORD in your project's .env file")

    # URL.create handles special characters in your password.
    connection_url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER", "postgres"),
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "pharma_demand"),
    )

    # Read all files before starting database changes.
    frames = {}

    for table, relative_path in TABLES.items():
        df = pd.read_csv(PROJECT_ROOT / relative_path)

        for column in DATE_COLUMNS.intersection(df.columns):
            df[column] = pd.to_datetime(df[column], errors="raise")

        frames[table] = df

    engine = create_engine(connection_url, pool_pre_ping=True)

    try:
        # Commit all table loads together; roll back if anything fails.
        with engine.begin() as connection:
            database = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

            print(f"Connected to: {database}")

            for table, df in frames.items():
                column_types = {
                    column: DateTime()
                    for column in DATE_COLUMNS.intersection(df.columns)
                }

                if table in (
                    "sales_hourly", "sales_daily", "sales_daily_analysis"
                ):
                    column_types.update({
                        "drug_class": String(5),
                        "sales": Float(),
                    })

                df.to_sql(
                    name=table,
                    con=connection,
                    schema="public",
                    if_exists="fail",
                    index=False,
                    chunksize=5000,
                    dtype=column_types,
                )

                # Table names come only from our fixed TABLES dictionary.
                stored_rows = connection.execute(
                    text(f'SELECT COUNT(*) FROM public."{table}"')
                ).scalar_one()

                if stored_rows != len(df):
                    raise ValueError(f"Row count mismatch for {table}")

                print(f"Loaded {table}: {stored_rows:,} rows")

            # Enforce uniqueness and valid sales on the main data tables.
            for table in (
                "sales_hourly", "sales_daily", "sales_daily_analysis"
            ):
                connection.execute(text(f'''
                    ALTER TABLE public."{table}"
                    ADD PRIMARY KEY ("timestamp", drug_class),
                    ALTER COLUMN sales SET NOT NULL,
                    ADD CHECK (sales >= 0)
                '''))

        print("\nAll tables committed successfully.")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()