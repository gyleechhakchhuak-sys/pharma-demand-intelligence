from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"

SCENARIOS = [
    ("short_delivery", 3, 2),
    ("standard_delivery", 7, 3),
    ("delayed_delivery", 14, 7),
]


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    daily = pd.read_csv(
        DATA_DIR / "sales_daily_analysis.csv",
        parse_dates=["timestamp"],
    )

    forecast = pd.read_csv(
        REPORT_DIR / "forecast_next_28_days.csv",
        parse_dates=["timestamp", "training_end"],
    ).sort_values("timestamp")

    cutoff = daily["timestamp"].max()

    if not forecast["training_end"].eq(cutoff).all():
        raise ValueError("Forecast and sales data have different cutoffs")

    expected_dates = pd.date_range(
        cutoff + pd.Timedelta(days=1),
        periods=len(forecast),
        freq="D",
    )

    if not pd.DatetimeIndex(forecast["timestamp"]).equals(expected_dates):
        raise ValueError("Forecast dates must be consecutive after cutoff")

    if len(forecast) < max(s[1] for s in SCENARIOS):
        raise ValueError("Forecast is shorter than the supplier lead time")

    # Use the last 90 complete days to estimate the recent sales mix.
    start = cutoff - pd.Timedelta(days=89)
    recent = daily.loc[daily["timestamp"].between(start, cutoff)]

    mix = recent.groupby("drug_class").agg(
        recent_sales=("sales", "sum"),
        average_daily_sales=("sales", "mean"),
        observed_days=("timestamp", "nunique"),
    )

    if not mix["observed_days"].eq(90).all():
        raise ValueError("Each class must have 90 complete daily records")

    total_recent_sales = mix["recent_sales"].sum()

    if total_recent_sales <= 0:
        raise ValueError("Cannot allocate forecasts without recent sales")

    mix["recent_share"] = mix["recent_sales"] / total_recent_sales

    # Allocate the aggregate forecast across drug classes.
    class_forecasts = forecast[["timestamp", "forecast"]].merge(
        mix[["recent_share"]].reset_index(),
        how="cross",
    )

    class_forecasts["class_forecast"] = (
        class_forecasts["forecast"] * class_forecasts["recent_share"]
    )

    allocated_totals = class_forecasts.groupby(
        "timestamp"
    )["class_forecast"].sum()

    if not np.allclose(
        allocated_totals.to_numpy(),
        forecast["forecast"].to_numpy(),
    ):
        raise ValueError("Allocated forecasts do not sum to total forecast")

    rows = []

    for scenario, lead_days, buffer_days in SCENARIOS:
        aggregate_lead_demand = forecast["forecast"].iloc[:lead_days].sum()

        for drug_class, values in mix.iterrows():
            lead_demand = (
                aggregate_lead_demand * values["recent_share"]
            )
            safety_stock = (
                values["average_daily_sales"] * buffer_days
            )

            rows.append({
                "scenario": scenario,
                "drug_class": drug_class,
                "training_end": cutoff,
                "lead_time_days": lead_days,
                "buffer_days": buffer_days,
                "recent_share_pct": values["recent_share"] * 100,
                "average_daily_sales": values["average_daily_sales"],
                "lead_time_demand": lead_demand,
                "safety_stock": safety_stock,
                "reorder_point": lead_demand + safety_stock,
            })

    planning = pd.DataFrame(rows)

    class_forecasts.to_csv(
        REPORT_DIR / "allocated_class_forecasts.csv",
        index=False,
    )

    planning.to_csv(
        REPORT_DIR / "inventory_scenarios.csv",
        index=False,
    )

    standard = planning.loc[
        planning["scenario"] == "standard_delivery",
        [
            "drug_class",
            "average_daily_sales",
            "lead_time_demand",
            "safety_stock",
            "reorder_point",
        ],
    ]

    print(f"Historical planning cutoff: {cutoff.date()}")
    print("Allocation: constant class shares from the last 90 days")
    print("Safety stock: recent daily average × buffer days")

    print("\nSTANDARD DELIVERY: 7-DAY LEAD TIME + 3-DAY BUFFER")
    print(standard.round(3).to_string(index=False))

    print(f"\nSaved {len(planning)} class/scenario combinations.")


if __name__ == "__main__":
    main()