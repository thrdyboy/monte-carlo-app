# src/etl/transform/markov_chain.py
import os
import sys
from typing import Dict, Any, Optional, List

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

try:
    from src.config.settings import load_config
except ImportError:  # pragma: no cover
    load_config = None

from src.etl.transform.runoff_markov import runoff_matrix, scs_lumped


# ---------------------------------------------------------------------------
# Constants & Helpers
# ---------------------------------------------------------------------------

STATES = (0, 1, 2, 3, 4)
STATE_NAMES = ["Sangat Kering", "Kering", "Normal", "Basah", "Sangat Basah"]
STATE_LABELS = {
    0: "Sangat Kering",
    1: "Kering",
    2: "Normal",
    3: "Basah",
    4: "Sangat Basah",
}
PERCENTILE_EDGES = [0.2, 0.4, 0.6, 0.8]


def _calculate_mape(actual, pred) -> float:
    actual, pred = np.array(actual), np.array(pred)
    mask = actual != 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((actual[mask] - pred[mask]) / actual[mask])) * 100)


def _create_ts(df: pd.DataFrame, months: List[str]) -> pd.DataFrame:
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


def _compute_metrics(df_hist: pd.DataFrame, df_pred: pd.DataFrame, months: List[str]) -> Dict[str, float]:
    actual_mean = df_hist[months].mean().values
    predictions = df_pred[months].mean().values

    mae = float(mean_absolute_error(actual_mean, predictions))
    rmse = float(np.sqrt(mean_squared_error(actual_mean, predictions)))
    mape = _calculate_mape(actual_mean, predictions)
    return {"MAE": mae, "RMSE": rmse, "MAPE": mape}


# ---------------------------------------------------------------------------
# 5-State Discrete Markov Chain Core
# ---------------------------------------------------------------------------

def _classify_state(value: float, p20: float, p40: float, p60: float, p80: float) -> int:
    """Classify a single value into one of 5 states using [P20, P40, P60, P80] thresholds."""
    return int(np.digitize(value, [p20, p40, p60, p80], right=True))


def _build_markov_model(df_hist: pd.DataFrame, months: List[str]) -> Dict[str, Any]:
    """Build 5-state Markov Chain parameters from historical data.

    Matches the legacy research model:
      1. Rank percentiles per month (`rank(pct=True, method="average")`)
         and digitize into 5 states using edges `[0.2, 0.4, 0.6, 0.8]`:
            0 = Sangat Kering (Very Dry, <= P20)
            1 = Kering        (Dry, P20 - P40)
            2 = Normal        (Normal, P40 - P60)
            3 = Basah         (Wet, P60 - P80)
            4 = Sangat Basah  (Very Wet, > P80)
      2. Build 5x5 transition matrix with Laplace smoothing `(C + 0.5)`.
      3. Compute per-month representative state means (`rep[m, s]`) with linear
         interpolation across missing state buckets.
    """
    hist_clean = df_hist[months].dropna(how="all")
    if len(hist_clean) == 0:
        raise ValueError("No historical rows to sample from.")

    K = len(STATES)
    n_months = len(months)

    # Percentile rank per column & digitize into 5 states (0..4)
    pr = hist_clean.rank(pct=True, method="average")
    st = np.digitize(pr.values, PERCENTILE_EDGES, right=True)
    st_df = pd.DataFrame(st, index=hist_clean.index, columns=months)

    # Flattened chronological sequence of states
    valid_mask = ~hist_clean.isna().values.flatten()
    seq = st_df.values.flatten()[valid_mask]
    if len(seq) == 0:
        raise ValueError("No valid historical observations found.")

    # 5x5 transition matrix with +0.5 smoothing
    counts = np.zeros((K, K), dtype=float)
    for s_from, s_to in zip(seq[:-1], seq[1:]):
        counts[int(s_from), int(s_to)] += 1.0
    transition_matrix = (counts + 0.5) / (counts + 0.5).sum(axis=1, keepdims=True)
    transition_df = pd.DataFrame(transition_matrix, index=STATE_NAMES, columns=STATE_NAMES)

    # Representative mean per (month, state) and empirical pools
    rep = np.zeros((n_months, K), dtype=float)
    pools: Dict[str, Dict[int, np.ndarray]] = {}
    fallback_pools: Dict[str, np.ndarray] = {}
    thresholds: Dict[str, Dict[str, float]] = {}

    hist_vals = hist_clean.values.astype(float)
    for m_idx, m_name in enumerate(months):
        col_all = hist_vals[:, m_idx]
        col_valid = col_all[~np.isnan(col_all)]
        if len(col_valid) == 0:
            col_valid = np.array([0.0])
        fallback_pools[m_name] = col_valid

        p20, p40, p60, p80 = np.percentile(col_valid, [20, 40, 60, 80])
        thresholds[m_name] = {
            "P20": float(p20),
            "P40": float(p40),
            "P60": float(p60),
            "P80": float(p80),
        }

        pools[m_name] = {}
        for s in STATES:
            mask_s = (st_df.values[:, m_idx] == s) & (~np.isnan(col_all))
            v = col_all[mask_s]
            rep[m_idx, s] = float(v.mean()) if len(v) > 0 else np.nan
            pools[m_name][s] = v

        # Interpolate missing state means across the 5 states for month m_idx
        rep[m_idx] = pd.Series(rep[m_idx]).interpolate(limit_direction="both").fillna(float(col_valid.mean())).values

        # Populate empty pools with the interpolated representative value
        for s in STATES:
            if len(pools[m_name][s]) == 0:
                pools[m_name][s] = np.array([rep[m_idx, s]], dtype=float)

    # Global thresholds matching legacy script (thr_wet = P90, thr_dry = 60.0)
    all_valid_vals = hist_vals[~np.isnan(hist_vals)]
    thr_wet = float(np.percentile(all_valid_vals, 90))
    thr_dry = 60.0
    thresholds["global"] = {
        "P20": float(np.percentile(all_valid_vals, 20)),
        "P40": float(np.percentile(all_valid_vals, 40)),
        "P60": float(np.percentile(all_valid_vals, 60)),
        "P80": float(np.percentile(all_valid_vals, 80)),
        "P90": thr_wet,
        "thr_wet": thr_wet,
        "thr_dry": thr_dry,
    }

    last_state = int(seq[-1])
    clim = hist_clean.mean().values.astype(float)

    return {
        "transition_matrix": transition_matrix,
        "transition_df": transition_df,
        "thresholds": thresholds,
        "thr_wet": thr_wet,
        "thr_dry": thr_dry,
        "rep": rep,
        "pools": pools,
        "fallback_pools": fallback_pools,
        "last_state": last_state,
        "clim": clim,
        "state_df": st_df,
    }


def _simulate_markov_ensemble(
    df_hist: pd.DataFrame,
    config: Any,
    n_simulations: int,
    model: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run `n_simulations` trajectories, aggregate via Mode state, and apply climatology adjustment."""
    months = list(config.columns.months)
    n_months = len(months)
    index_col = config.columns.index
    forecast_years = int(config.monte_carlo.forecast_years)
    seed = int(config.monte_carlo.random_seed)
    cn = float(config.runoff.curve_number)

    if model is None:
        model = _build_markov_model(df_hist, months)

    P = model["transition_matrix"]
    rep = model["rep"]
    pools = model["pools"]
    clim = model["clim"]
    last_state = model["last_state"]
    K = len(STATES)

    last_year = int(df_hist.index.max())
    pred_years = list(range(last_year + 1, last_year + 1 + forecast_years))
    nm = forecast_years * n_months

    rng = np.random.default_rng(seed)
    sims_state = np.zeros((n_simulations, nm), dtype=int)
    sims_val = np.zeros((n_simulations, nm), dtype=float)

    for i in range(n_simulations):
        s = last_state
        for t in range(nm):
            s = int(rng.choice(K, p=P[s]))
            sims_state[i, t] = s
            m_idx = t % n_months
            m_name = months[m_idx]
            pool = pools[m_name][s]
            sims_val[i, t] = float(rng.choice(pool)) if len(pool) > 0 else float(rep[m_idx, s])

    # Mode aggregation across simulations for each step t
    mode_state = np.array(
        [np.bincount(sims_state[:, t], minlength=K).argmax() for t in range(nm)],
        dtype=int,
    )
    pred = np.array([rep[t % n_months, mode_state[t]] for t in range(nm)], dtype=float)

    # Climatology bias correction: pred = pred * (hist_clim / pred_clim)
    pm = pred.reshape(forecast_years, n_months)
    pred_clim = pm.mean(axis=0)
    scale_factor = clim / np.where(pred_clim == 0, 1.0, pred_clim)
    pm = pm * scale_factor

    df_pred_mode = pd.DataFrame(pm, index=pred_years, columns=months).round(2)
    df_pred_mode.index.name = index_col

    # Event-based runoff matrices for historical and predicted rainfall
    ro_hist = pd.DataFrame(
        runoff_matrix(df_hist[months].values, cn=cn),
        index=df_hist.index,
        columns=months,
    )
    ro_df = pd.DataFrame(
        runoff_matrix(df_pred_mode.values, cn=cn),
        index=df_pred_mode.index,
        columns=months,
    ).round(2)

    # Probability matrices for Very Wet (state 4, > P80) and Very Dry (state 0, <= P20)
    p_ext_wet = (sims_state == 4).mean(axis=0).reshape(forecast_years, n_months)
    p_ext_dry = (sims_state == 0).mean(axis=0).reshape(forecast_years, n_months)

    df_prob_wet = pd.DataFrame(p_ext_wet, index=pred_years, columns=months)
    df_prob_wet.index.name = index_col
    df_prob_dry = pd.DataFrame(p_ext_dry, index=pred_years, columns=months)
    df_prob_dry.index.name = index_col

    # Individual trajectory DataFrames and standard deviation across simulations
    all_preds: List[pd.DataFrame] = []
    for i in range(n_simulations):
        df_i = pd.DataFrame(
            sims_val[i].reshape(forecast_years, n_months),
            index=pred_years,
            columns=months,
        )
        df_i.index.name = index_col
        all_preds.append(df_i)

    std_matrix = sims_val.reshape(n_simulations, forecast_years, n_months).std(
        axis=0, ddof=1 if n_simulations > 1 else 0
    )
    df_pred_std = pd.DataFrame(std_matrix, index=pred_years, columns=months)
    df_pred_std.index.name = index_col

    return {
        "df_pred_mode": df_pred_mode,
        "df_pred_std": df_pred_std,
        "all_preds": all_preds,
        "ro_hist": ro_hist,
        "ro_df": ro_df,
        "p_ext_wet": p_ext_wet,
        "p_ext_dry": p_ext_dry,
        "df_prob_wet": df_prob_wet,
        "df_prob_dry": df_prob_dry,
        "mode_state": mode_state.reshape(forecast_years, n_months),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_markov_chain(
    df_hist: pd.DataFrame,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Single-call Markov Chain forecast using the 5-state model."""
    if config is None:
        config = load_config()

    months = list(config.columns.months)
    n_simulations = getattr(config.monte_carlo, "num_simulations", 5000) or 5000

    model = _build_markov_model(df_hist, months)
    sim_out = _simulate_markov_ensemble(df_hist, config, n_simulations=n_simulations, model=model)

    df_pred = sim_out["all_preds"][0]
    cn = float(config.runoff.curve_number)
    ro_df = pd.DataFrame(
        runoff_matrix(df_pred.values, cn=cn),
        index=df_pred.index,
        columns=months,
    ).round(2)

    df_combined = pd.concat([df_hist, df_pred])
    metrics = _compute_metrics(df_hist, df_pred, months)

    ts_hist = _create_ts(df_hist, months)
    ts_pred = _create_ts(df_pred, months)
    ts_pred_conn = pd.concat([ts_hist.iloc[[-1]], ts_pred], ignore_index=True)

    return {
        "df_combined": df_combined,
        "df_hist": df_hist,
        "df_pred": df_pred,
        "ts_hist": ts_hist,
        "ts_pred": ts_pred,
        "ts_pred_std": None,
        "ts_pred_conn": ts_pred_conn,
        "metrics": metrics,
        "transition_matrix": model["transition_matrix"],
        "transition_df": model["transition_df"],
        "thresholds": model["thresholds"],
        "thr_wet": model["thr_wet"],
        "thr_dry": model["thr_dry"],
        "ro_hist": sim_out["ro_hist"],
        "ro_df": ro_df,
        "p_ext_wet": sim_out["p_ext_wet"],
        "p_ext_dry": sim_out["p_ext_dry"],
        "df_prob_wet": sim_out["df_prob_wet"],
        "df_prob_dry": sim_out["df_prob_dry"],
        "config": config,
    }


def run_markov_chain_iterations(
    df_hist: pd.DataFrame,
    n_iterations: Optional[int] = None,
    config: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run N 5-state Markov Chain simulations, aggregate via Mode state, and apply climatology adjustment."""
    if config is None:
        config = load_config()
    if n_iterations is None:
        n_iterations = config.monte_carlo.num_simulations

    months = list(config.columns.months)
    model = _build_markov_model(df_hist, months)
    sim_out = _simulate_markov_ensemble(df_hist, config, n_simulations=n_iterations, model=model)

    df_pred_std = sim_out["df_pred_std"]
    all_preds = sim_out["all_preds"]
    df_pred_mode = all_preds[0]

    cn = float(config.runoff.curve_number)
    ro_df = pd.DataFrame(
        runoff_matrix(df_pred_mode.values, cn=cn),
        index=df_pred_mode.index,
        columns=months,
    ).round(2)

    df_combined = pd.concat([df_hist, df_pred_mode])
    metrics = _compute_metrics(df_hist, df_pred_mode, months)

    ts_hist = _create_ts(df_hist, months)
    ts_pred = _create_ts(df_pred_mode, months)
    ts_pred_std = _create_ts(df_pred_std, months)
    ts_pred_sample = ts_pred.copy()
    ts_pred_conn = pd.concat([ts_hist.iloc[[-1]], ts_pred], ignore_index=True)

    return {
        "df_hist": df_hist,
        "df_pred": df_pred_mode,
        "df_pred_mean": df_pred_mode,
        "df_pred_std": df_pred_std,
        "df_pred_sample": df_pred_mode,
        "df_pred_all": all_preds,
        "df_combined": df_combined,
        "ts_hist": ts_hist,
        "ts_pred": ts_pred,
        "ts_pred_std": ts_pred_std,
        "ts_pred_sample": ts_pred_sample,
        "ts_pred_conn": ts_pred_conn,
        "metrics": metrics,
        "transition_matrix": model["transition_matrix"],
        "transition_df": model["transition_df"],
        "thresholds": model["thresholds"],
        "thr_wet": model["thr_wet"],
        "thr_dry": model["thr_dry"],
        "ro_hist": sim_out["ro_hist"],
        "ro_df": ro_df,
        "p_ext_wet": sim_out["p_ext_wet"],
        "p_ext_dry": sim_out["p_ext_dry"],
        "df_prob_wet": sim_out["df_prob_wet"],
        "df_prob_dry": sim_out["df_prob_dry"],
        "config": config,
    }
