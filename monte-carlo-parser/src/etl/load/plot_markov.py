# src/etl/load/plot_markov.py
import os
import sys
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config
from src.etl.transform.runoff_markov import scs_lumped, runoff_matrix


def plot_markov_time_series(
    forecast_result: Dict[str, Any],
    out_path: str,
    config: Optional[Any] = None,
) -> str:
    """Generate the 3-stacked subplot figure (Rainfall, Runoff, Coefficient) for Markov Chain."""
    if config is None:
        config = forecast_result.get("config") or load_config()

    cn = config.runoff.curve_number

    hist = forecast_result["df_hist"]
    pred_df = forecast_result.get("df_pred")
    if pred_df is None:
        pred_df = forecast_result.get("df_pred_mean")
    if pred_df is None:
        pred_df = forecast_result["df_pred_sample"]

    ro_hist = forecast_result.get("ro_hist")
    if ro_hist is None:
        ro_hist = pd.DataFrame(
            runoff_matrix(hist.values, cn=cn), index=hist.index, columns=hist.columns
        )

    ro_df = forecast_result.get("ro_df")
    if ro_df is None:
        ro_df = pd.DataFrame(
            runoff_matrix(pred_df.values, cn=cn), index=pred_df.index, columns=pred_df.columns
        ).round(2)

    thr_wet = forecast_result.get("thr_wet")
    if thr_wet is None:
        thr_wet = float(np.percentile(hist.values[~np.isnan(hist.values)], 90))

    thr_dry = forecast_result.get("thr_dry", 60.0)

    hist_vals = hist.values.flatten()
    pred_vals = pred_df.values.flatten()
    ro_hist_vals = ro_hist.values.flatten()
    ro_df_vals = ro_df.values.flatten()

    n_months = hist.shape[1]
    if n_months == 12:
        start_hist = f"{int(hist.index.min())}-01"
        start_pred = f"{int(pred_df.index.min())}-01"
        xh = pd.period_range(start_hist, periods=len(hist_vals), freq="M").to_timestamp()
        xp = pd.period_range(start_pred, periods=len(pred_vals), freq="M").to_timestamp()
    else:
        xh = pd.to_datetime(forecast_result["ts_hist"]["Tanggal"])
        xp = pd.to_datetime(forecast_result["ts_pred"]["Tanggal"])

    hist_start_yr, hist_end_yr = int(hist.index.min()), int(hist.index.max())
    pred_start_yr, pred_end_yr = int(pred_df.index.min()), int(pred_df.index.max())

    fig, ax = plt.subplots(
        3,
        1,
        figsize=(15, 13),
        sharex=True,
        gridspec_kw={"height_ratios": [1.1, 1.1, 0.8]},
    )

    # 1. RAINFALL
    ax[0].plot(
        xh,
        hist_vals,
        color="#1f77b4",
        lw=1.2,
        label=f"Historis {hist_start_yr}-{hist_end_yr}",
    )
    ax[0].plot(
        xp,
        pred_vals,
        color="#d62728",
        lw=1.8,
        marker="o",
        ms=3,
        label=f"Prediksi Markov {pred_start_yr}-{pred_end_yr}",
    )
    ax[0].axhline(
        thr_wet,
        color="navy",
        ls="--",
        lw=0.8,
        label=f"Ambang ekstrem basah ({thr_wet:.0f} mm)",
    )
    ax[0].axhline(
        thr_dry,
        color="orange",
        ls="--",
        lw=0.8,
        label=f"Ambang kering ({thr_dry:.0f} mm)",
    )
    ax[0].set_ylabel("Curah hujan (mm/bulan)")
    ax[0].legend(ncol=2)
    ax[0].grid(alpha=0.3)
    ax[0].set_title("Curah Hujan Bulanan: Historis vs Prediksi Markov Chain")

    # 2. RUNOFF
    ax[1].plot(
        xh,
        scs_lumped(hist.values, cn=cn).flatten(),
        color="gray",
        lw=0.8,
        ls=":",
        label="Cara lama: SCS-CN langsung pada total bulanan (over-estimasi)",
    )
    ax[1].plot(
        xh,
        ro_hist_vals,
        color="#2ca02c",
        lw=1.2,
        label="Run off historis (SCS-CN berbasis kejadian)",
    )
    ax[1].plot(
        xp,
        ro_df_vals,
        color="#9467bd",
        lw=1.8,
        marker="o",
        ms=3,
        label="Run off prediksi",
    )
    ax[1].set_ylabel(f"Run off (mm/bulan), CN={cn:g}")
    ax[1].legend(loc="upper left")
    ax[1].grid(alpha=0.3)
    ax[1].set_title("Run Off Langsung - SCS-CN berbasis kejadian (CH bulanan dipecah ke hari hujan)")

    # 3. COEFFICIENT
    kh = ro_hist_vals / np.where(hist_vals > 0, hist_vals, np.nan) * 100.0
    kp = ro_df_vals / np.where(pred_vals > 0, pred_vals, np.nan) * 100.0
    ax[2].plot(xh, kh, color="#2ca02c", lw=1.0, label="Historis")
    ax[2].plot(xp, kp, color="#9467bd", lw=1.5, marker="o", ms=3, label="Prediksi")
    ax[2].set_ylabel("Koef. run off (%)")
    ax[2].set_ylim(0, 100)
    ax[2].legend()
    ax[2].grid(alpha=0.3)
    ax[2].set_title("Koefisien Run Off = Run off / Curah hujan")

    plt.tight_layout()
    plt.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path
