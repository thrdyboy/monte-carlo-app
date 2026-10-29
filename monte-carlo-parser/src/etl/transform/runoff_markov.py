import os
import sys
from typing import Optional, List, Any

import numpy as np
import pandas as pd
from scipy.stats import gamma as _gamma

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config
from src.etl.transform.runoff_measurement_scs_cn import JUMLAH_HARI

DEFAULT_CN = 80.0
LAMBDA_IA = 0.05
SHAPE_GAMMA = 0.7
A_HARI = 2.0
B_HARI = 0.07
N_HARI_MAX = 25


def scs_event(d: Any, cn: float = DEFAULT_CN, lam: float = LAMBDA_IA) -> np.ndarray:
    """SCS-CN untuk satu kejadian hujan (mm) -> limpasan langsung (mm)."""
    S = (25400.0 / cn) - 254.0
    Ia = lam * S
    d_arr = np.asarray(d, dtype=float)
    return np.where(d_arr > Ia, ((d_arr - Ia) ** 2) / (d_arr - Ia + S), 0.0)


def runoff_bulanan(p: float, cn: float = DEFAULT_CN) -> float:
    """SCS-CN berbasis kejadian: CH bulanan dipecah menjadi N hari hujan
    (sebaran gamma, deterministik), SCS-CN dihitung per hari lalu dijumlahkan.
    """
    if pd.isna(p) or p <= 0:
        return 0.0
    p_val = float(p)
    n = int(np.clip(round(A_HARI + B_HARI * p_val), 1, N_HARI_MAX))
    w = _gamma.ppf((np.arange(1, n + 1) - 0.5) / n, SHAPE_GAMMA)
    w = w / w.sum()
    return float(scs_event(p_val * w, cn=cn).sum())


def runoff_matrix(M: Any, cn: float = DEFAULT_CN) -> np.ndarray:
    """Vectorized event-based SCS-CN over a matrix or array of monthly rainfall values."""
    M_arr = np.asarray(M, dtype=float)
    return np.vectorize(lambda x: runoff_bulanan(x, cn=cn), otypes=[float])(M_arr)


def scs_lumped(p: Any, cn: float = DEFAULT_CN) -> np.ndarray:
    """Cara lama (SCS-CN langsung pada total bulanan) - pembanding."""
    return scs_event(p, cn=cn)


def calculate_runoff_details_markov(
    df_rainfall: pd.DataFrame,
    config: Optional[Any] = None,
    jumlah_hari: Optional[List[int]] = None,
) -> pd.DataFrame:
    """Long-format Event-Based SCS-CN runoff table for Markov Chain forecasts."""
    if config is None:
        config = load_config()
    if jumlah_hari is None:
        jumlah_hari = JUMLAH_HARI

    months = list(config.columns.months)
    index_col = config.columns.index

    cn = float(config.runoff.curve_number)
    luas_km2 = float(config.runoff.river_basin_area)
    luas_m2 = luas_km2 * 1_000_000.0

    df_sorted = df_rainfall.sort_index()

    rows = []
    for yr in df_sorted.index:
        for i, m in enumerate(months):
            P = df_sorted.loc[yr, m]
            q_mm = runoff_bulanan(P, cn=cn)

            volume_m3 = (q_mm / 1000.0) * luas_m2
            detik_bulan = jumlah_hari[i] * 24 * 3600
            debit_m3s = volume_m3 / detik_bulan
            koef = (q_mm / float(P)) if (not pd.isna(P) and float(P) > 0) else 0.0

            rows.append({
                index_col: yr,
                "Bulan": m,
                "No_Bulan": i + 1,
                "Curah_Hujan_mm": P,
                "Runoff_mm": q_mm,
                "Volume_m3": volume_m3,
                "Debit_m3_per_s": debit_m3s,
                "Koefisien_Limpasan": koef,
            })

    return pd.DataFrame(rows)



def add_kategori_column(
    df_details: pd.DataFrame,
    thr_wet: float,
    thr_dry: float,
    rain_col: str = "Curah_Hujan_mm",
) -> pd.DataFrame:
    """Return a copy of `df_details` with a legacy-style `Kategori` column.

    Matches the legacy Excel classification:
        P >= thr_wet  -> "EKSTREM BASAH"
        P <= thr_dry  -> "KERING"
        otherwise     -> "NORMAL"
    """
    out = df_details.copy()
    p = pd.to_numeric(out[rain_col], errors="coerce")
    out["Kategori"] = np.select(
        [p >= thr_wet, p <= thr_dry],
        ["EKSTREM BASAH", "KERING"],
        default="NORMAL",
    )
    return out
