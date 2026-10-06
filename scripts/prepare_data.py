from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "processed"

DRUG_CLASSES = [
    "M01AB", "M01AE", "N02BA", "N02BE",
    "N05B", "N05C", "R03", "R06",
]

# Explicit formats prevent confusion between month/day and day/month.
DATE_FORMATS = {
    "hourly": "%m/%d/%Y %H:%M",
    "daily": "%m/%d/%Y",
    "weekly": "%m/%d/%Y",
    "monthly": "%Y-%m-%d",
}


def prepare_data(granularity, date_format):
    source = RAW_DIR / f"sales{granularity}.csv"
    df = pd.read_csv(source)

    # Keep only the timestamp and the eight sales columns.
    df = df[["datum"] + DRUG_CLASSES].copy()

    df["datum"] = pd.to_datetime(
        df["datum"],
        format=date_format,
        errors="raise",
    )
    df = df.rename(columns={"datum": "timestamp"})

    # Validate the key: one source row per timestamp.
    if df["timestamp"].isna().any():
        raise ValueError(f"{granularity}: missing timestamps")

    if df["timestamp"].duplicated().any():
        raise ValueError(f"{granularity}: duplicate timestamps")

    # Ensure sales are numeric and contain no missing/infinite values.
    df[DRUG_CLASSES] = df[DRUG_CLASSES].apply(
        pd.to_numeric, errors="raise"
    )

    if not np.isfinite(df[DRUG_CLASSES].to_numpy()).all():
        raise ValueError(f"{granularity}: invalid sales values")

    # Convert drug-class columns into rows.
    long_df = df.melt(
        id_vars="timestamp",
        value_vars=DRUG_CLASSES,
        var_name="drug_class",
        value_name="sales",
    )

    long_df = long_df.sort_values(
        ["timestamp", "drug_class"]
    ).reset_index(drop=True)

    # Flag negatives for investigation; do not silently change them.
    negative_count = int((long_df["sales"] < 0).sum())

    # Check for missing time intervals in hourly/daily files.
    missing_intervals = "not checked"
    if granularity in ("hourly", "daily"):
        frequency = "h" if granularity == "hourly" else "D"
        expected = pd.date_range(
            start=df["timestamp"].min(),
            end=df["timestamp"].max(),
            freq=frequency,
        )
        missing_intervals = len(
            expected.difference(pd.DatetimeIndex(df["timestamp"]))
        )

    destination = OUTPUT_DIR / f"sales_{granularity}.csv"
    long_df.to_csv(destination, index=False)

    print(f"\n{granularity.upper()}")
    print(f"Source rows: {len(df):,}")
    print(f"Processed observations: {len(long_df):,}")
    print(f"Start: {df['timestamp'].min()}")
    print(f"End: {df['timestamp'].max()}")
    print(f"Negative sales values: {negative_count}")
    print(f"Missing time intervals: {missing_intervals}")
    print(long_df.head(8).to_string(index=False))


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for granularity, date_format in DATE_FORMATS.items():
        prepare_data(granularity, date_format)


if __name__ == "__main__":
    main()