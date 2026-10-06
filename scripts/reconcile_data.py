from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    hourly = pd.read_csv(
        DATA_DIR / "sales_hourly.csv",
        parse_dates=["timestamp"],
    )
    daily = pd.read_csv(
        DATA_DIR / "sales_daily.csv",
        parse_dates=["timestamp"],
    )

    # Convert each hourly timestamp to its calendar date.
    hourly["date"] = hourly["timestamp"].dt.normalize()
    daily["date"] = daily["timestamp"].dt.normalize()

    # Sum hourly sales separately for each date and drug class.
    calculated = (
        hourly.groupby(["date", "drug_class"], as_index=False)
        .agg(
            hourly_total=("sales", "sum"),
            recorded_hours=("timestamp", "nunique"),
        )
    )

    supplied = daily[["date", "drug_class", "sales"]].rename(
        columns={"sales": "daily_total"}
    )

    # Outer join also reveals records missing from either source.
    comparison = calculated.merge(
        supplied,
        on=["date", "drug_class"],
        how="outer",
        validate="one_to_one",
        indicator=True,
    )

    comparison["difference"] = (
        comparison["hourly_total"] - comparison["daily_total"]
    )

    # Allow a tiny tolerance for floating-point arithmetic.
    comparison["matches"] = (
        comparison["_merge"].eq("both")
        & np.isclose(
            comparison["hourly_total"],
            comparison["daily_total"],
            atol=0.000001,
            rtol=0,
        )
    )

    issues = comparison.loc[~comparison["matches"]]

    comparison.to_csv(
        REPORT_DIR / "hourly_daily_reconciliation.csv",
        index=False,
    )

    issues.to_csv(
        REPORT_DIR / "reconciliation_issues.csv",
        index=False,
    )

    print(f"Date/class pairs checked: {len(comparison):,}")
    print(f"Matching pairs: {comparison['matches'].sum():,}")
    print(f"Pairs needing investigation: {len(issues):,}")

    shared = comparison.loc[comparison["_merge"].eq("both")]
    print(
        "Largest absolute difference among shared pairs: "
        f"{shared['difference'].abs().max():.8f}"
    )

    incomplete_days = (
        calculated.loc[
            calculated["recorded_hours"] != 24,
            ["date", "recorded_hours"],
        ]
        .drop_duplicates()
        .sort_values("date")
    )

    print("\nDays with fewer than 24 recorded hours:")
    print(incomplete_days.to_string(index=False))

    if not issues.empty:
        print("\nFirst 10 reconciliation issues:")
        print(issues.head(10).to_string(index=False))
    else:
        print("\nAll hourly sums agree with the supplied daily data.")


if __name__ == "__main__":
    main()