from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"

WEEKDAYS = [
    "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday",
]


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    daily = pd.read_csv(
        DATA_DIR / "sales_daily.csv",
        parse_dates=["timestamp"],
    )

    reconciliation = pd.read_csv(
        REPORT_DIR / "hourly_daily_reconciliation.csv",
        parse_dates=["date"],
    )

    # Require successful reconciliation before using daily totals.
    if not reconciliation["_merge"].eq("both").all():
        raise ValueError("Some records are missing from one source.")

    if not reconciliation["difference"].abs().le(0.000001).all():
        raise ValueError("Resolve reconciliation differences first.")

    # Exclude dates with incomplete hourly coverage.
    incomplete_dates = reconciliation.loc[
        reconciliation["recorded_hours"] != 24, "date"
    ].unique()

    analysis = daily.loc[
        ~daily["timestamp"].isin(incomplete_dates)
    ].copy()

    # Summarize each drug class.
    summary = (
        analysis.groupby("drug_class")
        .agg(
            total_sales=("sales", "sum"),
            average_daily_sales=("sales", "mean"),
            daily_std=("sales", "std"),
            peak_daily_sales=("sales", "max"),
        )
        .sort_values("total_sales", ascending=False)
    )

    total_sales = summary["total_sales"].sum()

    summary["share_pct"] = (
        summary["total_sales"] / total_sales * 100
    )

    # Coefficient of variation: fluctuation relative to average sales.
    summary["cv"] = (
        summary["daily_std"]
        / summary["average_daily_sales"].replace(0, float("nan"))
    )

    top_three_share = summary["share_pct"].head(3).sum()

    # One row per day, summed across all classes.
    daily_totals = (
        analysis.groupby("timestamp", as_index=False)
        .agg(total_sales=("sales", "sum"))
    )

    # Average daily total for each weekday.
    daily_totals["weekday"] = daily_totals["timestamp"].dt.day_name()

    weekday_pattern = (
        daily_totals.groupby("weekday")["total_sales"]
        .mean()
        .reindex(WEEKDAYS)
        .rename("average_daily_sales")
    )

    # Monthly totals with coverage counts to identify partial months.
    daily_totals["month"] = (
        daily_totals["timestamp"].dt.to_period("M").astype(str)
    )

    monthly_trend = (
        daily_totals.groupby("month")
        .agg(
            total_sales=("total_sales", "sum"),
            observed_days=("timestamp", "nunique"),
            average_daily_sales=("total_sales", "mean"),
        )
    )

    # Save results for the future API and dashboard.
    analysis.to_csv(DATA_DIR / "sales_daily_analysis.csv", index=False)
    summary.to_csv(REPORT_DIR / "class_summary.csv")
    weekday_pattern.to_csv(REPORT_DIR / "weekday_pattern.csv")
    monthly_trend.to_csv(REPORT_DIR / "monthly_trend.csv")

    print(f"Complete days analyzed: {analysis['timestamp'].nunique():,}")
    print(f"Excluded dates: {len(incomplete_dates)}")
    print(f"Recorded sales volume: {total_sales:,.3f}")
    print(f"Top three classes: {', '.join(summary.head(3).index)}")
    print(f"Top three share: {top_three_share:.2f}%")

    print("\nCLASS SUMMARY")
    print(summary.round(3).to_string())

    print("\nAVERAGE TOTAL SALES BY WEEKDAY")
    print(weekday_pattern.round(3).to_string())

    print("\nFIRST AND LAST MONTHS — CHECK COVERAGE")
    print(monthly_trend.iloc[[0, -1]].round(3).to_string())


if __name__ == "__main__":
    main()