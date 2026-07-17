import os
import sys
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config.settings import load_config
from src.etl.extract import extract


def calculate_mape(actual, pred) -> float:
    actual, pred = np.array(actual), np.array(pred)
    mask = actual != 0
    if mask.sum() == 0:
        return 0.0
    return np.mean(np.abs((actual[mask] - pred[mask]) / actual[mask])) * 100


def create_ts(df: pd.DataFrame, months) -> pd.DataFrame:
    series = []
    for yr in df.index:
        for m_idx, m_name in enumerate(months):
            series.append(
                {
                    "Tanggal": pd.to_datetime(f"{yr}-{m_idx + 1}-01"),
                    "Nilai": df.loc[yr, m_name],
                }
            )
    return pd.DataFrame(series)


def _apply_overrides(config, overrides: Optional[Dict[str, Any]]) -> None:
    if not overrides:
        return

    if "monte_carlo" not in overrides:
        return

    new_params = overrides["monte_carlo"]
    for key, value in new_params.items():
        if hasattr(config.monte_carlo, key):
            setattr(config.monte_carlo, key, value)
            print(f"Override: {key} diubah menjadi {value}")


def transform(
    df_hist=None,
    file_path: Optional[str] = None,
    manual_data: Optional[Dict[str, Any]] = None,
    forecast_years: Optional[int] = None,
    overrides: Optional[Dict[str, Any]] = None,
):
    """Monte Carlo Transportation transform.

    Keeps the same Monte Carlo method as current implementation:
    - Seed RNG using config.monte_carlo.random_seed
    - Forecast each future year by sampling each month value from historical month values
    - Combine historical + predicted data
    - Compute MAE/RMSE/MAPE on mean across years (historical means vs forecast means)

    If `df_hist` isn't passed directly, provide `file_path` or `manual_data`
    so extract() has an actual source to read from -- `overrides` only
    carries monte_carlo settings (forecast_years, random_seed, etc.), it is
    not a data source.

    `forecast_years` is a shortcut for overrides={"monte_carlo": {"forecast_years": N}}.
    Pass it directly to pick how many future years to simulate on this call;
    the value in montecarlo.yaml (5) is only the fallback used when neither
    `forecast_years` nor `overrides["monte_carlo"]["forecast_years"]` is given.
    If both are passed, this `forecast_years` argument wins.

    Returns dict with:
      df_combined, df_hist, df_pred, ts_hist, ts_pred, ts_pred_conn, metrics, config
    """

    config = load_config()
    _apply_overrides(config, overrides)

    if forecast_years is not None:
        if forecast_years <= 0:
            raise ValueError("forecast_years must be a positive integer")
        config.monte_carlo.forecast_years = forecast_years
        print(f"Override: forecast_years diubah menjadi {forecast_years}")

    if df_hist is None:
        df_hist = extract(file_path=file_path, manual_data=manual_data)

    # extract() may return dict depending on how it's wired upstream
    if isinstance(df_hist, dict):
        df_hist = df_hist.get("df_hist") or df_hist.get("df") or df_hist.get("data")

    if df_hist is None or (isinstance(df_hist, pd.DataFrame) and df_hist.empty):
        print("Historical data is Empty!")
        return None

    index_col = config.columns.index
    months = config.columns.months

    if index_col in df_hist.columns:
        df_hist = df_hist.set_index(index_col)

    forecast_years = config.monte_carlo.forecast_years
    seed = config.monte_carlo.random_seed

    np.random.seed(seed)

    last_year = int(df_hist.index.max())
    pred_years = list(range(last_year + 1, last_year + 1 + forecast_years))

    pred_list = []
    for _yr in pred_years:
        # Sample each month value from the historical distribution of that month
        row_pred = [round(np.random.choice(df_hist[m].dropna().values), 2) for m in months]
        pred_list.append(row_pred)

    df_pred = pd.DataFrame(pred_list, columns=months, index=pred_years)
    df_pred.index.name = index_col

    df_combined = pd.concat([df_hist, df_pred])

    actual_mean = df_hist[months].mean().values
    predictions = df_pred[months].mean().values

    mae = mean_absolute_error(actual_mean, predictions)
    rmse = np.sqrt(mean_squared_error(actual_mean, predictions))
    mape = calculate_mape(actual_mean, predictions)

    metrics = {"MAE": mae, "RMSE": rmse, "MAPE": mape}

    ts_hist = create_ts(df_hist, months)
    ts_pred = create_ts(df_pred, months)

    # Keep the same output shape: last hist row + all predicted rows
    last_hist = ts_hist.iloc[[-1]]
    ts_pred_conn = pd.concat([last_hist, ts_pred], ignore_index=True)

    return {
        "df_combined": df_combined,
        "df_hist": df_hist,
        "df_pred": df_pred,
        "ts_hist": ts_hist,
        "ts_pred": ts_pred,
        "ts_pred_conn": ts_pred_conn,
        "metrics": metrics,
        "config": config,
    }