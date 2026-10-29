# tests/unit/test_markov_chain.py
"""
Unit tests for 5-state discrete Markov Chain forecasting (`src/etl/transform/markov_chain.py`)
and pipeline routing (`forecast_method="markov"`).
"""
import os
import sys
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.etl.transform.markov_chain import (
    STATES,
    _build_markov_model,
    _classify_state,
    run_markov_chain,
    run_markov_chain_iterations,
)
from src.etl.transform.monte_carlo import (
    run_monte_carlo,
    run_monte_carlo_iterations,
)


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.columns.months = ["Jan", "Feb", "Mar"]
    config.columns.index = "Tahun"
    config.monte_carlo.forecast_years = 2
    config.monte_carlo.random_seed = 42
    config.monte_carlo.num_simulations = 30
    config.runoff.curve_number = 75.0
    config.runoff.river_basin_area = 58.87
    return config


@pytest.fixture
def df_hist():
    """Hardcoded historical DataFrame: 6 years x 3 months with spread across 5 states."""
    df = pd.DataFrame(
        {
            "Jan": [10.0, 20.0, 50.0, 80.0, 120.0, 200.0],
            "Feb": [15.0, 35.0, 60.0, 95.0, 150.0, 250.0],
            "Mar": [5.0,  12.0, 40.0, 70.0, 110.0, 180.0],
        },
        index=[2019, 2020, 2021, 2022, 2023, 2024],
    )
    df.index.name = "Tahun"
    return df


# ==========================================
# Markov Chain — State & Transition Model
# ==========================================

def test_classify_state_percentiles():
    assert _classify_state(5.0, 10.0, 30.0, 60.0, 100.0) == 0
    assert _classify_state(10.0, 10.0, 30.0, 60.0, 100.0) == 0
    assert _classify_state(25.0, 10.0, 30.0, 60.0, 100.0) == 1
    assert _classify_state(45.0, 10.0, 30.0, 60.0, 100.0) == 2
    assert _classify_state(80.0, 10.0, 30.0, 60.0, 100.0) == 3
    assert _classify_state(120.0, 10.0, 30.0, 60.0, 100.0) == 4


def test_build_markov_model_structure(df_hist):
    model = _build_markov_model(df_hist, ["Jan", "Feb", "Mar"])

    assert model["transition_matrix"].shape == (5, 5)
    np.testing.assert_allclose(model["transition_matrix"].sum(axis=1), np.ones(5), rtol=1e-6)
    assert model["last_state"] in STATES
    for m in ("Jan", "Feb", "Mar"):
        assert set(model["pools"][m].keys()) == {0, 1, 2, 3, 4}
        for s in STATES:
            assert len(model["pools"][m][s]) > 0


# ==========================================
# Markov Chain — Single & Iterations Output
# ==========================================

def test_run_markov_chain_single_matches_mc_keys(mock_config, df_hist):
    mk = run_markov_chain(df_hist, config=mock_config)
    mc = run_monte_carlo(df_hist, config=mock_config)

    assert set(mc.keys()).issubset(set(mk.keys()))
    assert mk["df_pred"].shape == (2, 3)
    assert list(mk["df_pred"].index) == [2025, 2026]
    assert mk["transition_matrix"].shape == (5, 5)
    assert mk["p_ext_wet"].shape == (2, 3)
    assert mk["p_ext_dry"].shape == (2, 3)


def test_run_markov_chain_iterations_exact_dict_structure(mock_config, df_hist):
    mk = run_markov_chain_iterations(df_hist, config=mock_config)
    mc = run_monte_carlo_iterations(df_hist, config=mock_config)

    assert set(mc.keys()).issubset(set(mk.keys()))
    assert len(mk["df_pred_all"]) == mock_config.monte_carlo.num_simulations
    assert mk["df_pred_mean"].shape == (2, 3)
    assert mk["df_pred_std"].shape == (2, 3)
    assert mk["df_pred_sample"].shape == (2, 3)
    assert mk["df_combined"].shape == (8, 3)  # 6 hist + 2 pred
    assert len(mk["ts_pred_conn"]) == 1 + 2 * 3
    assert mk["transition_matrix"].shape == (5, 5)
    assert mk["p_ext_wet"].shape == (2, 3)
    assert mk["p_ext_dry"].shape == (2, 3)

    # Verify Climatology Adjustment: seasonal mean of forecast matches historical climatology
    np.testing.assert_allclose(
        mk["df_pred_mean"].mean().values,
        df_hist.mean().values,
        atol=0.05,
    )

    for metric_name in ("MAE", "RMSE", "MAPE"):
        assert isinstance(mk["metrics"][metric_name], float)


def test_run_markov_chain_iterations_deterministic(mock_config, df_hist):
    r1 = run_markov_chain_iterations(df_hist, n_iterations=15, config=mock_config)
    r2 = run_markov_chain_iterations(df_hist, n_iterations=15, config=mock_config)

    pd.testing.assert_frame_equal(r1["df_pred_mean"], r2["df_pred_mean"])
    pd.testing.assert_frame_equal(r1["df_pred_sample"], r2["df_pred_sample"])


def test_pipeline_invalid_forecast_method_raises(mock_config, tmp_path):
    from src.pipeline import run_full_pipeline

    manual = {
        2020: {"Jan": 10.0, "Feb": 100.0, "Mar": 5.0},
        2021: {"Jan": 20.0, "Feb": 200.0, "Mar": 15.0},
        2022: {"Jan": 30.0, "Feb": 300.0, "Mar": 25.0},
    }
    with pytest.raises(ValueError, match="Invalid forecast_method"):
        run_full_pipeline(
            output_dir=str(tmp_path),
            manual_data=manual,
            config=mock_config,
            forecast_method="invalid_algo",
        )
