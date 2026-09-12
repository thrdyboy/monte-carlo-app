import os
import sys
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

# Add project root to sys.path (up 2 levels: unit → tests → root)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.etl.transform.monte_carlo import (
    run_monte_carlo,
    run_monte_carlo_iterations,
    _calculate_mape,
)
from src.etl.transform.runoff_measurement_scs_cn import (
    hitung_runoff_mm,
    _scs_cn_params,
    calculate_runoff_wide,
    calculate_runoff_details,
    build_rekap_tahunan,
    build_rekap_bulanan,
)


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture
def mock_config():
    """Fake config matching the real structure after our YAML update."""
    config = MagicMock()
    config.columns.months = ["Jan", "Feb", "Mar"]
    config.columns.index = "Tahun"
    config.monte_carlo.forecast_years = 2
    config.monte_carlo.random_seed = 42
    config.monte_carlo.num_simulations = 50  # small for fast tests
    config.runoff.curve_number = 75
    config.runoff.river_basin_area = 58.87
    return config


@pytest.fixture
def df_hist():
    """Small historical DataFrame: 3 years * 3 months, with variance."""
    df = pd.DataFrame(
        {
            "Jan": [10.0, 20.0, 30.0],
            "Feb": [100.0, 200.0, 300.0],
            "Mar": [5.0, 15.0, 25.0],
        },
        index=[2020, 2021, 2022],
    )
    df.index.name = "Tahun"
    return df


# ==========================================
# Monte Carlo — single run
# ==========================================

def test_run_monte_carlo_returns_expected_keys(mock_config, df_hist):
    result = run_monte_carlo(df_hist, config=mock_config)

    assert set(result.keys()) == {
        "df_combined", "df_hist", "df_pred",
        "ts_hist", "ts_pred", "ts_pred_conn",
        "metrics", "config",
    }


def test_run_monte_carlo_pred_years_and_shape(mock_config, df_hist):
    """forecast_years=2 → df_pred has 2 rows, years 2023–2024."""
    result = run_monte_carlo(df_hist, config=mock_config)

    assert result["df_pred"].shape == (2, 3)
    assert list(result["df_pred"].index) == [2023, 2024]
    assert list(result["df_pred"].columns) == ["Jan", "Feb", "Mar"]


def test_run_monte_carlo_combined_shape(mock_config, df_hist):
    """df_combined = 3 hist + 2 pred = 5 rows."""
    result = run_monte_carlo(df_hist, config=mock_config)

    assert result["df_combined"].shape == (5, 3)
    assert list(result["df_combined"].index) == [2020, 2021, 2022, 2023, 2024]


def test_run_monte_carlo_is_deterministic_with_same_seed(mock_config, df_hist):
    """Two calls with same seed → identical df_pred."""
    r1 = run_monte_carlo(df_hist, config=mock_config)
    r2 = run_monte_carlo(df_hist, config=mock_config)

    pd.testing.assert_frame_equal(r1["df_pred"], r2["df_pred"])


def test_run_monte_carlo_metrics_are_floats(mock_config, df_hist):
    result = run_monte_carlo(df_hist, config=mock_config)

    for k in ("MAE", "RMSE", "MAPE"):
        assert k in result["metrics"]
        assert isinstance(result["metrics"][k], float)


def test_run_monte_carlo_ts_pred_conn_length(mock_config, df_hist):
    """ts_pred_conn = last hist row + all pred rows = 1 + 2*3 = 7."""
    result = run_monte_carlo(df_hist, config=mock_config)

    assert len(result["ts_pred_conn"]) == 1 + 2 * 3


# ==========================================
# Monte Carlo — N iterations
# ==========================================

def test_iterations_default_uses_num_simulations(mock_config, df_hist):
    """If n_iterations is None, uses config.monte_carlo.num_simulations."""
    result = run_monte_carlo_iterations(df_hist, config=mock_config)

    assert len(result["df_pred_all"]) == mock_config.monte_carlo.num_simulations


def test_iterations_respects_explicit_count(mock_config, df_hist):
    result = run_monte_carlo_iterations(df_hist, n_iterations=10, config=mock_config)

    assert len(result["df_pred_all"]) == 10


def test_iterations_produce_different_draws(mock_config, df_hist):
    """Regression guard: each iteration must actually resample (not repeat)."""
    result = run_monte_carlo_iterations(df_hist, n_iterations=20, config=mock_config)

    # If all iterations were identical, std would be exactly 0 everywhere.
    # With real randomness, at least some cells should have non-zero std.
    assert (result["df_pred_std"].fillna(0) > 0).any().any()


def test_iterations_mean_shape_matches_single(mock_config, df_hist):
    """df_pred_mean and df_pred_std keep the same shape as df_pred."""
    result = run_monte_carlo_iterations(df_hist, n_iterations=10, config=mock_config)

    assert result["df_pred_mean"].shape == (2, 3)
    assert result["df_pred_std"].shape == (2, 3)
    assert list(result["df_pred_mean"].index) == [2023, 2024]


def test_iterations_combined_uses_mean(mock_config, df_hist):
    """df_combined = df_hist + df_pred_mean."""
    result = run_monte_carlo_iterations(df_hist, n_iterations=10, config=mock_config)

    expected = pd.concat([df_hist, result["df_pred_mean"]])
    pd.testing.assert_frame_equal(result["df_combined"], expected)


# ==========================================
# Helpers
# ==========================================

def test_calculate_mape_handles_zeros():
    assert _calculate_mape([0, 0], [1, 1]) == 0.0
    assert _calculate_mape([100], [110]) == pytest.approx(10.0)


# ==========================================
# Runoff — SCS-CN core
# ==========================================

def test_scs_cn_params_from_cn_75():
    """CN=75 → S≈84.667, Ia≈16.933 (matches your input form)."""
    S, Ia = _scs_cn_params(75)

    assert S == pytest.approx(84.6667, rel=1e-4)
    assert Ia == pytest.approx(16.9333, rel=1e-4)


def test_runoff_zero_when_below_ia():
    """P ≤ Ia → Q = 0."""
    S, Ia = _scs_cn_params(75)
    assert hitung_runoff_mm(10, Ia, S) == 0.0
    assert hitung_runoff_mm(Ia, Ia, S) == 0.0


def test_runoff_formula_matches_scs_cn():
    """P=100 → Q ≈ 41.135 mm with CN=75."""
    S, Ia = _scs_cn_params(75)
    Q = hitung_runoff_mm(100, Ia, S)

    assert Q == pytest.approx(41.135, rel=1e-3)


def test_runoff_handles_nan():
    S, Ia = _scs_cn_params(75)
    assert hitung_runoff_mm(np.nan, Ia, S) == 0.0


# ==========================================
# Runoff — wide output
# ==========================================

def test_calculate_runoff_wide_preserves_shape(mock_config, df_hist):
    df_runoff = calculate_runoff_wide(df_hist, config=mock_config)

    assert df_runoff.shape == df_hist.shape
    assert list(df_runoff.columns) == list(df_hist.columns)
    assert list(df_runoff.index) == list(df_hist.index)


def test_calculate_runoff_wide_values_all_non_negative(mock_config, df_hist):
    df_runoff = calculate_runoff_wide(df_hist, config=mock_config)

    assert (df_runoff >= 0).all().all()


# ==========================================
# Runoff — long output
# ==========================================

def test_calculate_runoff_details_columns(mock_config, df_hist):
    details = calculate_runoff_details(df_hist, config=mock_config)

    expected_cols = {
        "Tahun", "Bulan", "No_Bulan", "Curah_Hujan_mm",
        "Runoff_mm", "Volume_m3", "Debit_m3_per_s", "Koefisien_Limpasan",
    }
    assert set(details.columns) == expected_cols


def test_calculate_runoff_details_row_count(mock_config, df_hist):
    """3 years * 3 months = 9 rows."""
    details = calculate_runoff_details(df_hist, config=mock_config)
    assert len(details) == 9


def test_calculate_runoff_details_koef_limpasan(mock_config, df_hist):
    """C = Q / P (0 when P is 0 or below Ia)."""
    details = calculate_runoff_details(df_hist, config=mock_config)

    # For rows where P > Ia, C should equal Runoff/P
    mask = details["Curah_Hujan_mm"] > 16.9333
    if mask.any():
        expected = (
            details.loc[mask, "Runoff_mm"] / details.loc[mask, "Curah_Hujan_mm"]
        )
        np.testing.assert_allclose(
            details.loc[mask, "Koefisien_Limpasan"].values,
            expected.values,
            rtol=1e-9,
        )

    # Rows where P <= Ia should have C = 0
    mask_zero = details["Curah_Hujan_mm"] <= 16.9333
    assert (details.loc[mask_zero, "Koefisien_Limpasan"] == 0.0).all()


# ==========================================
# Runoff — rekapitulasi
# ==========================================

def test_build_rekap_tahunan_shape(mock_config, df_hist):
    details = calculate_runoff_details(df_hist, config=mock_config)
    rekap = build_rekap_tahunan(details, index_col="Tahun")

    assert len(rekap) == 3  # 3 years
    assert "Total_Hujan_mm" in rekap.columns
    assert "Koefisien_Limpasan_Tahunan" in rekap.columns


def test_build_rekap_bulanan_shape(mock_config, df_hist):
    details = calculate_runoff_details(df_hist, config=mock_config)
    rekap = build_rekap_bulanan(details)

    assert len(rekap) == 3  # 3 months
    assert list(rekap["No_Bulan"]) == [1, 2, 3]


# ==========================================
# Integration: MC → Runoff
# ==========================================

def test_pipeline_mc_then_runoff_shapes_align(mock_config, df_hist):
    """df_combined (rainfall) and df_runoff (runoff) must align exactly."""
    mc = run_monte_carlo_iterations(df_hist, n_iterations=10, config=mock_config)
    df_runoff = calculate_runoff_wide(mc["df_combined"], config=mock_config)

    assert df_runoff.shape == mc["df_combined"].shape
    assert list(df_runoff.index) == list(mc["df_combined"].index)
    assert list(df_runoff.columns) == list(mc["df_combined"].columns)


def test_pipeline_produces_5_hist_plus_pred_rows(mock_config, df_hist):
    """3 hist + 2 pred = 5 rows through the whole pipeline."""
    mc = run_monte_carlo_iterations(df_hist, n_iterations=10, config=mock_config)
    details = calculate_runoff_details(mc["df_combined"], config=mock_config)

    # 5 years × 3 months = 15 long-format rows
    assert len(details) == 5 * 3
    assert sorted(details["Tahun"].unique()) == [2020, 2021, 2022, 2023, 2024]