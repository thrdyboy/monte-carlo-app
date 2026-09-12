import os
import sys
from typing import Optional, List, Any

import pandas as pd

# Settle the Path with Three Layers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config

JUMLAH_HARI = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


# ---------------------------------------------------------------------------
# Core SCS-CN
# ---------------------------------------------------------------------------

def _scs_cn_params(curve_number: float) -> tuple:
    """Return (S, Ia) from a Curve Number."""
    S = (25400.0 / curve_number) - 254.0
    Ia = 0.2 * S
    return S, Ia


def hitung_runoff_mm(P: float, Ia: float, S: float) -> float:
    """Direct runoff (mm) for a single rainfall value.

    Q = (P - Ia)^2 / (P - Ia + S)   if P > Ia
    Q = 0                           if P <= Ia
    """
    if pd.isna(P) or P <= Ia:
        return 0.0
    return ((P - Ia) ** 2) / (P - Ia + S)


# ---------------------------------------------------------------------------
# Wide output: same shape as input
# ---------------------------------------------------------------------------

def calculate_runoff_wide(
    df_rainfall: pd.DataFrame,
    config: Optional[Any] = None,
) -> pd.DataFrame:
    """Apply SCS-CN to every cell of a Year × Months rainfall DataFrame."""
    if config is None:
        config = load_config()

    months = list(config.columns.months)
    S, Ia = _scs_cn_params(config.runoff.curve_number)

    data = {
        yr: [hitung_runoff_mm(df_rainfall.loc[yr, m], Ia, S) for m in months]
        for yr in df_rainfall.index
    }

    df_runoff = pd.DataFrame.from_dict(data, orient="index", columns=months)
    df_runoff.index.name = df_rainfall.index.name
    return df_runoff


# ---------------------------------------------------------------------------
# Long output: identical columns to old `df` in the original script
# ---------------------------------------------------------------------------

def calculate_runoff_details(
    df_rainfall: pd.DataFrame,
    config: Optional[Any] = None,
    jumlah_hari: Optional[List[int]] = None,
) -> pd.DataFrame:
    """Long-format runoff table (one row per year-month)."""
    if config is None:
        config = load_config()
    if jumlah_hari is None:
        jumlah_hari = JUMLAH_HARI

    months = list(config.columns.months)
    index_col = config.columns.index

    CN = config.runoff.curve_number
    luas_km2 = config.runoff.river_basin_area
    luas_m2 = luas_km2 * 1_000_000

    S, Ia = _scs_cn_params(CN)

    rows = []
    for yr in df_rainfall.index:
        for i, m in enumerate(months):
            P = df_rainfall.loc[yr, m]
            Q_mm = hitung_runoff_mm(P, Ia, S)

            volume_m3 = (Q_mm / 1000.0) * luas_m2
            detik_bulan = jumlah_hari[i] * 24 * 3600
            debit_m3s = volume_m3 / detik_bulan
            koef = (Q_mm / P) if (not pd.isna(P) and P > 0) else 0.0

            rows.append({
                index_col: yr,
                "Bulan": m,
                "No_Bulan": i + 1,
                "Curah_Hujan_mm": P,
                "Runoff_mm": Q_mm,
                "Volume_m3": volume_m3,
                "Debit_m3_per_s": debit_m3s,
                "Koefisien_Limpasan": koef,
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Rekapitulasi
# ---------------------------------------------------------------------------

def build_rekap_tahunan(
    df_details: pd.DataFrame,
    config: Optional[Any] = None,
    index_col: Optional[str] = None,
) -> pd.DataFrame:
    """Group by the year column (defaults to config.columns.index)."""
    if config is None:
        config = load_config()
    if index_col is None:
        index_col = config.columns.index

    rekap = df_details.groupby(index_col).agg(
        Total_Hujan_mm=("Curah_Hujan_mm", "sum"),
        Total_Runoff_mm=("Runoff_mm", "sum"),
        Total_Volume_m3=("Volume_m3", "sum"),
        Rerata_Debit_m3s=("Debit_m3_per_s", "mean"),
    ).reset_index()

    rekap["Koefisien_Limpasan_Tahunan"] = (
        rekap["Total_Runoff_mm"] / rekap["Total_Hujan_mm"]
    )
    return rekap


def build_rekap_bulanan(
    df_details: pd.DataFrame,
    config: Optional[Any] = None,
) -> pd.DataFrame:
    """Group by month. Config is accepted for API uniformity (not used)."""
    return (
        df_details.groupby(["No_Bulan", "Bulan"], sort=True)
        .agg(
            Rerata_Hujan_mm=("Curah_Hujan_mm", "mean"),
            Rerata_Runoff_mm=("Runoff_mm", "mean"),
            Rerata_Debit_m3s=("Debit_m3_per_s", "mean"),
        )
        .reset_index()
        .sort_values("No_Bulan")
    )