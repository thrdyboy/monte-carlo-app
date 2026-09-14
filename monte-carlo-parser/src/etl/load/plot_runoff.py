import os
import sys
from typing import Any, Dict, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config


def _setup_style():
    plt.rcParams.update({
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
    })


def _resolve_year_col(config: Optional[Any] = None) -> str:
    """Return the configured year column name (e.g. 'Tahun')."""
    if config is None:
        config = load_config()
    return config.columns.index


def plot_runoff_time_series(
    runoff_result: Dict[str, Any],
    out_path: str,
    config: Optional[Any] = None,
) -> str:
    """Rainfall bars + runoff line, full multi-year window."""
    _setup_style()
    year_col = _resolve_year_col(config)
    df = runoff_result["df_details"]
    n_years = df[year_col].nunique()

    fig, ax1 = plt.subplots(figsize=(11, 4.2))
    x = np.arange(len(df))
    ax1.bar(x, df["Curah_Hujan_mm"], color="#4C72B0", label="Curah Hujan (mm)", width=1.0)
    ax1.set_ylabel("Curah Hujan (mm)", color="#4C72B0")
    ax1.tick_params(axis="y", labelcolor="#4C72B0")
    ax1.set_xlabel("Bulan ke- (berurutan)")

    ax2 = ax1.twinx()
    ax2.plot(x, df["Runoff_mm"], color="#FE0D15", linewidth=2.5, label="Runoff (mm)")
    ax2.set_ylabel("Runoff (mm)", color="#FE0D15")
    ax2.tick_params(axis="y", labelcolor="#FE0D15")

    for yr in range(0, n_years + 1, 5):
        ax1.axvline(yr * 12, color="gray", linestyle=":", linewidth=0.6)

    ax1.set_title("Curah Hujan & Runoff Bulanan (SCS-CN)")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


def plot_runoff_monthly_avg(
    runoff_result: Dict[str, Any],
    out_path: str,
    config: Optional[Any] = None
) -> str:
    """Bar chart: average rainfall vs runoff per month."""
    _setup_style()
    rekap_bulanan = runoff_result["rekap_bulanan"]
    bulan_names = rekap_bulanan["Bulan"].tolist()

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    xb = np.arange(len(bulan_names))
    width = 0.38
    ax.bar(xb - width / 2, rekap_bulanan["Rerata_Hujan_mm"], width=width,
           color="#4C72B0", label="Rerata Curah Hujan (mm)")
    ax.bar(xb + width / 2, rekap_bulanan["Rerata_Runoff_mm"], width=width,
           color="#C44E52", label="Rerata Runoff (mm)")
    ax.set_xticks(xb)
    ax.set_xticklabels(bulan_names)
    ax.set_ylabel("Tinggi (mm)")
    ax.set_title("Pola Rerata Bulanan Curah Hujan vs Runoff")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


def plot_runoff_discharge(
    runoff_result: Dict[str, Any],
    out_path: str,
    config: Optional[Any] = None
) -> str:
    """Average monthly discharge (m3/s)."""
    _setup_style()
    rekap_bulanan = runoff_result["rekap_bulanan"]
    bulan_names = rekap_bulanan["Bulan"].tolist()

    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    xb = np.arange(len(bulan_names))
    ax.plot(xb, rekap_bulanan["Rerata_Debit_m3s"], marker="o", color="#55A868", linewidth=2)
    ax.fill_between(xb, rekap_bulanan["Rerata_Debit_m3s"], color="#55A868", alpha=0.15)
    ax.set_xticks(xb)
    ax.set_xticklabels(bulan_names)
    ax.set_ylabel("Debit (m3/s)")
    ax.set_title("Pola Rerata Debit Bulanan Hasil Limpasan")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path


def plot_runoff_yearly(
    runoff_result: Dict[str, Any],
    out_path: str,
    config: Optional[Any] = None,
) -> str:
    """Total rainfall vs total runoff per year."""
    _setup_style()
    year_col = _resolve_year_col(config)
    rekap = runoff_result["rekap_tahunan"]

    fig, ax = plt.subplots(figsize=(10, 4.2))
    xt = rekap[year_col]
    ax.bar(xt - 0.2, rekap["Total_Hujan_mm"], width=0.4, color="#4C72B0", label="Total Hujan (mm)")
    ax.bar(xt + 0.2, rekap["Total_Runoff_mm"], width=0.4, color="#C44E52", label="Total Runoff (mm)")
    ax.set_xlabel(year_col)
    ax.set_ylabel("Tinggi (mm)")
    ax.set_title("Total Curah Hujan vs Total Runoff per Tahun")
    ax.set_xticks(xt)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)
    return out_path