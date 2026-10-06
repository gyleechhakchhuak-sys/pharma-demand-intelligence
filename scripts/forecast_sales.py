from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
REPORT_DIR = PROJECT_ROOT / "reports"

HORIZON = 28
MODELS = ["seasonal_naive", "holt_winters"]


def predict(train, steps, model_name):
    if model_name == "seasonal_naive":
        # Repeat the last observed week without using future actuals.
        predictions = np.tile(
            train.iloc[-7:].to_numpy(),
            int(np.ceil(steps / 7)),
        )[:steps]

    elif model_name == "holt_winters":
        fitted = ExponentialSmoothing(
            train,
            trend="add",
            damped_trend=True,
            seasonal="add",
            seasonal_periods=7,
            initialization_method="estimated",
        ).fit(optimized=True)

        predictions = np.asarray(fitted.forecast(steps))

    else:
        raise ValueError(f"Unknown model: {model_name}")

    if not np.isfinite(predictions).all():
        raise ValueError(f"{model_name} produced invalid predictions")

    # Sales forecasts cannot be negative.
    return np.maximum(predictions, 0)


def wape(actual, predicted):
    actual = np.asarray(actual)
    denominator = np.abs(actual).sum()

    if denominator == 0:
        raise ValueError("WAPE is undefined when actual volume is zero")

    return 100 * np.abs(actual - predicted).sum() / denominator


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    daily = pd.read_csv(
        DATA_DIR / "sales_daily_analysis.csv",
        parse_dates=["timestamp"],
    )

    series = (
        daily.groupby("timestamp")["sales"]
        .sum()
        .sort_index()
        .asfreq("D")
    )

    if series.isna().any():
        raise ValueError("Missing daily observations; investigate first")

    if len(series) < 5 * HORIZON:
        raise ValueError("Not enough history for this evaluation")

    development = series.iloc[:-HORIZON]
    holdout = series.iloc[-HORIZON:]

    validation_rows = []
    pooled_actuals = []
    pooled_predictions = {name: [] for name in MODELS}

    # Three expanding training windows, each followed by 28 test days.
    for fold, remaining in enumerate([3, 2, 1], start=1):
        split = len(development) - remaining * HORIZON
        train = development.iloc[:split]
        actual = development.iloc[split:split + HORIZON]

        pooled_actuals.extend(actual.to_numpy())

        for name in MODELS:
            predictions = predict(train, HORIZON, name)
            pooled_predictions[name].extend(predictions)

            validation_rows.append({
                "fold": fold,
                "model": name,
                "train_end": train.index[-1],
                "test_start": actual.index[0],
                "test_end": actual.index[-1],
                "wape_pct": wape(actual, predictions),
            })

    validation = pd.DataFrame(validation_rows)

    scores = {
        name: wape(pooled_actuals, pooled_predictions[name])
        for name in MODELS
    }

    # Select before evaluating the untouched holdout.
    selected_model = min(scores, key=scores.get)

    holdout_results = pd.DataFrame({
        "timestamp": holdout.index,
        "actual": holdout.to_numpy(),
    })

    metrics = []

    for name in MODELS:
        predictions = predict(development, HORIZON, name)
        holdout_results[name] = predictions

        metrics.append({
            "model": name,
            "validation_wape_pct": scores[name],
            "holdout_wape_pct": wape(holdout, predictions),
            "selected": name == selected_model,
        })

    metrics = pd.DataFrame(metrics)

    # After evaluation, refit the selected model on all complete days.
    future_dates = pd.date_range(
        start=series.index[-1] + pd.Timedelta(days=1),
        periods=HORIZON,
        freq="D",
    )

    future = pd.DataFrame({
        "timestamp": future_dates,
        "forecast": predict(series, HORIZON, selected_model),
        "model": selected_model,
        "training_end": series.index[-1],
    })

    validation.to_csv(REPORT_DIR / "forecast_validation.csv", index=False)
    metrics.to_csv(REPORT_DIR / "forecast_metrics.csv", index=False)
    holdout_results.to_csv(
        REPORT_DIR / "forecast_holdout.csv", index=False
    )
    future.to_csv(REPORT_DIR / "forecast_next_28_days.csv", index=False)

    print("\nROLLING-ORIGIN VALIDATION")
    print(validation.round({"wape_pct": 3}).to_string(index=False))

    print("\nMODEL COMPARISON")
    print(metrics.round(3).to_string(index=False))

    print(f"\nSelected using validation: {selected_model}")
    print(
        f"Holdout: {holdout.index[0].date()} "
        f"to {holdout.index[-1].date()}"
    )

    print("\nFIRST 7 FORECAST DAYS")
    print(future.head(7).round({"forecast": 3}).to_string(index=False))


if __name__ == "__main__":
    main()