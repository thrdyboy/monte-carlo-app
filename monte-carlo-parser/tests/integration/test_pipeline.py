import os
import sys
import pytest
import pandas as pd

# Add project root to sys.path (up 2 levels)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.etl.extract.build_from_file import build_from_file
from src.etl.extract.build_year_month_df import build_year_month_df
from src.etl.transform.monte_carlo import run_monte_carlo_iterations
from src.etl.transform.markov_chain import run_markov_chain_iterations
from src.etl.transform.runoff_monte_carlo import calculate_runoff_details_monte_carlo
from src.etl.transform.runoff_markov import calculate_runoff_details_markov
from src.etl.transform.runoff_measurement_scs_cn import (
    build_rekap_tahunan,
    build_rekap_bulanan,
)
from src.etl.load.plot_forecast import plot_forecast_time_series, plot_forecast_heatmap
from src.etl.load.plot_markov import plot_markov_time_series
from src.etl.load.plot_ch_runoff_curve import plot_ch_runoff_curve
from src.etl.load.plot_runoff import (
    plot_runoff_time_series,
    plot_runoff_monthly_avg,
    plot_runoff_discharge,
    plot_runoff_yearly,
)

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# ==========================================
# Helpers
# ==========================================

def _assert_valid_png(path: str) -> None:
    assert os.path.exists(path), f"PNG missing: {path}"
    assert os.path.getsize(path) > 0, f"PNG empty: {path}"
    with open(path, "rb") as f:
        assert f.read(8) == PNG_MAGIC, f"Not a PNG: {path}"


def _run_full_pipeline(df_hist, config, tmp_path, forecast_method):
    """extract → Forecast (MC or Markov) → runoff → plots."""
    
    # ---- Transform: Forecast ----
    if forecast_method == "monte_carlo":
        forecast_result = run_monte_carlo_iterations(df_hist, config=config)
    elif forecast_method == "markov":
        forecast_result = run_markov_chain_iterations(df_hist, config=config)
    else:
        raise ValueError(f"Unknown forecast_method: {forecast_method}")

    # ---- Transform: Runoff ----
    if forecast_method == "monte_carlo":
        details = calculate_runoff_details_monte_carlo(
            forecast_result["df_combined"],
            config=config,
            n_iterations=config.monte_carlo.num_simulations,
        )
    elif forecast_method == "markov":
        details = calculate_runoff_details_markov(
            forecast_result["df_combined"], config=config
        )
    else:
        raise ValueError(f"Unknown forecast_method: {forecast_method}")

    runoff_result = {
        "df_details": details,
        "rekap_tahunan": build_rekap_tahunan(details, config=config),
        "rekap_bulanan": build_rekap_bulanan(details, config=config),
    }

    # ---- Load: plots ----
    # Using a prefix so we know which method generated the plot
    outputs = {}
    if forecast_method == "monte_carlo":
        outputs["fc_ts"] = plot_forecast_time_series(forecast_result, str(tmp_path / f"{forecast_method}_ts.png"), config=config)
        outputs["fc_hm"] = plot_forecast_heatmap(forecast_result, str(tmp_path / f"{forecast_method}_hm.png"), config=config)
    elif forecast_method == "markov":
        outputs["fc_ts"] = plot_markov_time_series(forecast_result, str(tmp_path / f"{forecast_method}_ts.png"), config=config)
        outputs["fc_curve"] = plot_ch_runoff_curve(config, str(tmp_path / f"{forecast_method}_ch_runoff_curve.png"))

    outputs.update({
        "ro_ts":  plot_runoff_time_series(runoff_result, str(tmp_path / f"{forecast_method}_ro_ts.png"), config=config),
        "ro_avg": plot_runoff_monthly_avg(runoff_result, str(tmp_path / f"{forecast_method}_ro_avg.png"), config=config),
        "ro_dis": plot_runoff_discharge(runoff_result, str(tmp_path / f"{forecast_method}_ro_dis.png"), config=config),
        "ro_yr":  plot_runoff_yearly(runoff_result, str(tmp_path / f"{forecast_method}_ro_yr.png"), config=config),
    })

    return forecast_result, runoff_result, outputs

# ==========================================
# A. Manual data → full pipeline
# ==========================================

# This parametrize decorator runs the test twice: once for MC, once for Markov
@pytest.mark.parametrize("forecast_method", ["monte_carlo", "markov"])
def test_pipeline_from_manual_data(config, tmp_path, forecast_method):
    manual = {
        2020: {"Jan": 10.0, "Feb": 100.0, "Mar": 5.0},
        2021: {"Jan": 20.0, "Feb": 200.0, "Mar": 15.0},
        2022: {"Jan": 30.0, "Feb": 300.0, "Mar": 25.0},
    }
    df_hist = build_year_month_df(manual, config=config)

    forecast_result, runoff, outputs = _run_full_pipeline(df_hist, config, tmp_path, forecast_method)

    # Note: Markov chain forecast shape might differ slightly depending on test config
    # but the combined shape should be (historical years + forecast_years, months)
    assert forecast_result["df_combined"].shape[1] == 3
    standard_cols = {
        "Tahun", "Bulan", "No_Bulan", "Curah_Hujan_mm",
        "Runoff_mm", "Volume_m3", "Debit_m3_per_s", "Koefisien_Limpasan",
    }
    assert standard_cols.issubset(set(runoff["df_details"].columns))
    if forecast_method == "monte_carlo":
        assert "Runoff_Std_Dev" in runoff["df_details"].columns
    elif forecast_method == "markov":
        assert set(runoff["df_details"].columns) == standard_cols
        assert forecast_result["transition_matrix"].shape == (5, 5)
        assert {"thr_wet", "thr_dry", "ro_hist", "ro_df", "p_ext_wet", "p_ext_dry"}.issubset(set(forecast_result.keys()))

    for path in outputs.values():
        _assert_valid_png(path)


# ==========================================
# B. Excel file → full pipeline
# ==========================================

@pytest.fixture
def sample_excel(tmp_path):
    """Write a real .xlsx with a 'Tahun' column (matching config)."""
    df = pd.DataFrame({
        "Tahun": [2020, 2021, 2022],
        "Jan":   [10.0, 20.0, 30.0],
        "Feb":   [100.0, 200.0, 300.0],
        "Mar":   [5.0, 15.0, 25.0],
    })
    path = tmp_path / "hist.xlsx"
    df.to_excel(path, sheet_name="Sheet1", index=False)
    return str(path)


@pytest.mark.parametrize("forecast_method", ["monte_carlo", "markov"])
def test_pipeline_from_excel(config, sample_excel, tmp_path, forecast_method):
    df_hist = build_from_file(sample_excel, config=config)

    # Sanity on extract output first
    assert not df_hist.empty
    assert df_hist.index.name == "Tahun"

    forecast_result, runoff, outputs = _run_full_pipeline(df_hist, config, tmp_path, forecast_method)

    assert forecast_result["df_combined"].shape[1] == 3
    standard_cols = {
        "Tahun", "Bulan", "No_Bulan", "Curah_Hujan_mm",
        "Runoff_mm", "Volume_m3", "Debit_m3_per_s", "Koefisien_Limpasan",
    }
    assert standard_cols.issubset(set(runoff["df_details"].columns))
    if forecast_method == "monte_carlo":
        assert "Runoff_Std_Dev" in runoff["df_details"].columns
    elif forecast_method == "markov":
        assert set(runoff["df_details"].columns) == standard_cols
        assert forecast_result["transition_matrix"].shape == (5, 5)
        assert {"thr_wet", "thr_dry", "ro_hist", "ro_df", "p_ext_wet", "p_ext_dry"}.issubset(set(forecast_result.keys()))

    for path in outputs.values():
        _assert_valid_png(path)


# ==========================================
# C. Cross-check: manual vs Excel agree (Data extraction only)
# ==========================================
# Note: We only test extraction here because random seeds will make MC vs Markov diverge

def test_manual_and_excel_agree(config, sample_excel):
    manual = {
        2020: {"Jan": 10.0, "Feb": 100.0, "Mar": 5.0},
        2021: {"Jan": 20.0, "Feb": 200.0, "Mar": 15.0},
        2022: {"Jan": 30.0, "Feb": 300.0, "Mar": 25.0},
    }
    from_manual = build_year_month_df(manual, config=config)
    from_excel = build_from_file(sample_excel, config=config)

    # The historical extraction should be identical regardless of the forecast method
    pd.testing.assert_frame_equal(from_manual, from_excel)