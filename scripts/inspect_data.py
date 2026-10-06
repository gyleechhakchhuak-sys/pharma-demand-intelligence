from pathlib import Path
import pandas as pd

# Locate the project folder, then its raw data folder.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"

files = [
    "saleshourly.csv",
    "salesdaily.csv",
    "salesweekly.csv",
    "salesmonthly.csv",
]

for filename in files:
    path = DATA_DIR / filename

    print(f"\n{'=' * 60}")
    print(f"FILE: {filename}")

    if not path.exists():
        print(f"Missing file: {path}")
        continue

    df = pd.read_csv(path)

    print(f"\nRows: {df.shape[0]:,}")
    print(f"Columns: {df.shape[1]}")

    print("\nFirst 5 rows:")
    print(df.head().to_string(index=False))

    print("\nColumn data types:")
    print(df.dtypes)

    print("\nMissing values per column:")
    print(df.isna().sum())

    print(f"\nFully duplicated rows: {df.duplicated().sum()}")