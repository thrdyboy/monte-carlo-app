# src/etl/load/plot_monte_carlo.py
import os
import sys
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config


def plot_mc_time_series(mc_result: Dict[str, Any], out_path: str) -> str:
    """Historical + forecast with uncertainty band + one sample trajectory.

    - Blue: historical
    - Red solid: forecast mean
    - Red dashed: one random Monte Carlo sample (shows year-to-year variety)
    - Shaded: ±1σ envelope across all iterations
    """
    config = load_config()
    ts_hist = mc_result["ts_hist"]
    ts_pred = mc_result["ts_pred"]
    ts_std = mc_result.get("ts_pred_std")
    ts_sample = mc_result.get("ts_pred_sample")

    fig, ax = plt.subplots(figsize=(11, 4.2))

    # Historical
    ax.plot(ts_hist["Tanggal"], ts_hist["Nilai"],
            label="Historical", color="#4C72B0", linewidth=1.2)

    # One sample trajectory (dashed) — shows realistic year variety
    if ts_sample is not None:
        ax.plot(ts_sample["Tanggal"], ts_sample["Nilai"],
                color="#EF0911", linestyle="--", linewidth=1.0,
                alpha=0.05, label="Sample simulation (Monte Carlo Simulation)", zorder=3)

    ax.axvline(ts_hist["Tanggal"].iloc[-1], color="gray",
               linestyle=":", linewidth=0.8)

    ax.set_xlabel("Tanggal")
    ax.set_ylabel("Curah Hujan (mm)")
    ax.set_title("Monte Carlo — Historical vs Forecast Rainfall")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


def plot_mc_heatmap(
    mc_result: Dict[str, Any],
    out_path: str,
    config: Optional[Any] = None,
    include_history: bool = False,
    use_sample: bool = True,
) -> str:
    """Heatmap of rainfall: rows = years, cols = months.

    Args:
        use_sample: If True (default), plot ONE random Monte Carlo iteration
                    (varied, realistic-looking). If False, plot the mean
                    across iterations (statistically smooth, flat-looking).
    """
    if config is None:
        config = load_config()

    # Choose which forecast DataFrame to render
    if use_sample:
        df_forecast = mc_result.get("df_pred_sample")
        if df_forecast is None:
            df_forecast = mc_result.get("df_pred_mean")
        subtitle = "Sample Simulation"
    else:
        df_forecast = mc_result.get("df_pred_mean")
        if df_forecast is None:
            df_forecast = mc_result.get("df_pred")
        subtitle = "Mean Forecast"

    if df_forecast is None:
        raise KeyError("mc_result must contain 'df_pred_sample', 'df_pred_mean', or 'df_pred'")

    if include_history:
        df_hist = mc_result.get("df_hist")
        if df_hist is None:
            raise KeyError("include_history=True but 'df_hist' not found in mc_result")
        import pandas as pd
        df_plot = pd.concat([df_hist, df_forecast])
        title = f"Monte Carlo — Historical + {subtitle} Heatmap"
    else:
        df_plot = df_forecast
        title = f"Monte Carlo — {subtitle} Heatmap"

    months = list(config.columns.months)

    fig, ax = plt.subplots(figsize=(10, max(2.5, 0.4 * len(df_plot))))
    sns.heatmap(
        df_plot[months],
        annot=True,
        fmt=".1f",
        cmap="YlGnBu",
        cbar_kws={"label": "Rainfall (mm)"},
        ax=ax,
    )
    ax.set_title(title)
    ax.set_xlabel("Bulan")
    ax.set_ylabel(config.columns.index)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path