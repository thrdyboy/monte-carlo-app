# src/etl/transform/monte_carlo.py
import os
import sys
from typing import Dict, Any, Optional

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calculate_mape(actual, pred) -> float:
    actual, pred = np.array(actual), np.array(pred)
    mask = actual != 0
    if mask.sum() == 0:
        return 0.0
    return np.mean(np.abs((actual[mask] - pred[mask]) / actual[mask])) * 100


def _create_ts(df: pd.DataFrame, months) -> pd.DataFrame:
    """Convert a wide year-by-month DataFrame into a long time-series DataFrame."""
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


def _simulate_once(df_hist: pd.DataFrame, config) -> pd.DataFrame:
    """One Monte Carlo draw using BLOCK BOOTSTRAP.

    For each forecast year, we sample ONE historical year at random and reuse
    its full 12-month pattern. This preserves realistic intra-year
    correlations (a wet January comes with a wet February, etc.) instead of
    sampling each month independently.

    NOTE: This function does NOT touch the global RNG seed. The caller is
    responsible for seeding once before the loop.
    """
    months = list(config.columns.months)
    index_col = config.columns.index
    forecast_years = config.monte_carlo.forecast_years

    last_year = int(df_hist.index.max())
    pred_years = list(range(last_year + 1, last_year + 1 + forecast_years))

    # Pre-extract historical rows as a 2D numpy array: shape (n_years, 12)
    hist_values = df_hist[months].dropna(how="all").values

    if len(hist_values) == 0:
        raise ValueError("No historical rows to sample from.")

    pred_list = []
    for _yr in pred_years:
        chosen_idx = np.random.randint(0, len(hist_values))
        pred_list.append(hist_values[chosen_idx])

    df_pred = pd.DataFrame(pred_list, columns=months, index=pred_years)
    df_pred.index.name = index_col
    return df_pred


def _compute_metrics(df_hist: pd.DataFrame, df_pred: pd.DataFrame, months) -> Dict[str, float]:
    actual_mean = df_hist[months].mean().values
    predictions = df_pred[months].mean().values

    mae = mean_absolute_error(actual_mean, predictions)
    rmse = np.sqrt(mean_squared_error(actual_mean, predictions))
    mape = _calculate_mape(actual_mean, predictions)
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_monte_carlo(
    df_hist: pd.DataFrame,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Single Monte Carlo simulation (block bootstrap)."""
    if config is None:
        config = load_config()

    months = list(config.columns.months)
    seed = config.monte_carlo.random_seed

    np.random.seed(seed)
    df_pred = _simulate_once(df_hist, config)

    df_combined = pd.concat([df_hist, df_pred])
    metrics = _compute_metrics(df_hist, df_pred, months)

    ts_hist = _create_ts(df_hist, months)
    ts_pred = _create_ts(df_pred, months)

    last_hist = ts_hist.iloc[[-1]]
    ts_pred_conn = pd.concat([last_hist, ts_pred], ignore_index=True)

    return {
        "df_combined": df_combined,
        "df_hist": df_hist,
        "df_pred": df_pred,
        "ts_hist": ts_hist,
        "ts_pred": ts_pred,
        "ts_pred_std": None,
        "ts_pred_conn": ts_pred_conn,
        "metrics": metrics,
        "config": config,
    }


def run_monte_carlo_iterations(
    df_hist: pd.DataFrame,
    n_iterations: Optional[int] = None,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run N block-bootstrap simulations and aggregate.

    In addition to the mean and std, this returns:
        df_pred_sample  : ONE randomly-chosen iteration (for visualization)
        df_pred_all     : all N iterations (for custom analysis)
        df_combined     : df_hist + df_pred_mean (statistical view)
    """
    if config is None:
        config = load_config()
    if n_iterations is None:
        n_iterations = config.monte_carlo.num_simulations

    months = list(config.columns.months)
    seed = config.monte_carlo.random_seed

    np.random.seed(seed)
    all_preds = [_simulate_once(df_hist, config) for _ in range(n_iterations)]

    # Aggregate
    stacked = pd.concat(all_preds, keys=range(n_iterations))
    df_pred_mean = stacked.groupby(level=1).mean()
    df_pred_std = stacked.groupby(level=1).std()

    # ONE representative iteration for visualization
    alpha_params = 5.0
    weights = np.random.gamma(shape=alpha_params, scale=1, size=n_iterations)
    weights = weights / weights.sum()

    sample_idx = sample_idx = int(np.random.choice(n_iterations, p=weights))
    df_pred_sample = all_preds[sample_idx]

    df_combined = pd.concat([df_hist, df_pred_mean])
    metrics = _compute_metrics(df_hist, df_pred_sample, months)

    ts_hist = _create_ts(df_hist, months)
    ts_pred = _create_ts(df_pred_mean, months)
    ts_pred_std = _create_ts(df_pred_std, months)
    ts_pred_sample = _create_ts(df_pred_sample, months)
    ts_pred_conn = pd.concat([ts_hist.iloc[[-1]], ts_pred], ignore_index=True)

    return {
        "df_hist": df_hist,
        "df_pred_mean": df_pred_mean,
        "df_pred_std": df_pred_std,
        "df_pred_sample": df_pred_sample,       
        "df_pred_all": all_preds,
        "df_combined": df_combined,
        "ts_hist": ts_hist,
        "ts_pred": ts_pred,
        "ts_pred_std": ts_pred_std,
        "ts_pred_sample": ts_pred_sample,
        "ts_pred_conn": ts_pred_conn,
        "metrics": metrics,
        "config": config,
    }