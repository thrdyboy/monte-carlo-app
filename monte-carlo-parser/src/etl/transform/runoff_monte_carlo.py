import os
import sys
from typing import Optional, List, Any

import numpy as np
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config
from src.etl.transform.runoff_measurement_scs_cn import (
    JUMLAH_HARI,
    _scs_cn_params,
    hitung_runoff_mm,
)


def calculate_runoff_details_monte_carlo(
    df_rainfall: pd.DataFrame,
    config: Optional[Any] = None,
    n_iterations: int = 100,
    jumlah_hari: Optional[List[int]] = None,
) -> pd.DataFrame:
    """Probabilistic SCS-CN runoff calculation for Monte Carlo forecasts.

    For each rainfall value P, samples the Curve Number from a normal
    distribution N(loc=config.runoff.curve_number, scale=3.0), calculates
    runoff Q for each sample, and takes the mean of Q as `Runoff_mm` and
    standard deviation as `Runoff_Std_Dev`.
    """
    if config is None:
        config = load_config()
    if jumlah_hari is None:
        jumlah_hari = JUMLAH_HARI

    months = list(config.columns.months)
    index_col = config.columns.index

    base_cn = float(config.runoff.curve_number)
    luas_km2 = float(config.runoff.river_basin_area)
    luas_m2 = luas_km2 * 1_000_000.0

    rows = []
    for yr in df_rainfall.index:
        for i, m in enumerate(months):
            P = df_rainfall.loc[yr, m]

            if pd.isna(P) or P <= 0:
                q_mean = 0.0
                q_std = 0.0
            else:
                cn_samples = np.random.normal(loc=base_cn, scale=3.0, size=n_iterations)
                cn_samples = np.clip(cn_samples, 1.0, 99.9)
                q_samples = np.empty(n_iterations, dtype=float)
                for idx, cn_val in enumerate(cn_samples):
                    S, Ia = _scs_cn_params(float(cn_val))
                    q_samples[idx] = hitung_runoff_mm(float(P), Ia, S)
                q_mean = float(np.mean(q_samples))
                q_std = float(np.std(q_samples))

            volume_m3 = (q_mean / 1000.0) * luas_m2
            detik_bulan = jumlah_hari[i] * 24 * 3600
            debit_m3s = volume_m3 / detik_bulan
            koef = (q_mean / P) if (not pd.isna(P) and P > 0) else 0.0

            rows.append({
                index_col: yr,
                "Bulan": m,
                "No_Bulan": i + 1,
                "Curah_Hujan_mm": P,
                "Runoff_mm": q_mean,
                "Runoff_Std_Dev": q_std,
                "Volume_m3": volume_m3,
                "Debit_m3_per_s": debit_m3s,
                "Koefisien_Limpasan": koef,
            })

    return pd.DataFrame(rows)
