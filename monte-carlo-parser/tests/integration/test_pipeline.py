# tests/integration/test_pipeline.py
import os
import sys
import pytest
import pandas as pd

# Add project root to sys.path (up 2 levels)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.etl.extract.build_from_file import build_from_file
from src.etl.extract.build_year_month_df import build_year_month_df
from src.etl.transform.monte_carlo import run_monte_carlo_iterations
from src.etl.transform.runoff_measurement_scs_cn import (
    calculate_runoff_details,
    build_rekap_tahunan,
    build_rekap_bulanan,
)
from src.etl.load.plot_monte_carlo import plot_mc_time_series, plot_mc_heatmap
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


def _run_full_pipeline(df_hist, config, tmp_path):
    """extract → MC → runoff → plots, all config-driven."""
    # ---- Transform: Monte Carlo ----
    mc = run_monte_carlo_iterations(df_hist, config=config)

    # ---- Transform: Runoff ----
    details = calculate_runoff_details(mc["df_combined"], config=config)
    runoff_result = {
        "df_details": details,
        "rekap_tahunan": build_rekap_tahunan(details, config=config),
        "rekap_bulanan": build_rekap_bulanan(details, config=config),
    }

    # ---- Load: plots ----
    outputs = {
        "mc_ts":  plot_mc_time_series(mc, str(tmp_path / "mc_ts.png")),
        "mc_hm":  plot_mc_heatmap(mc, str(tmp_path / "mc_hm.png"), config=config),
        "ro_ts":  plot_runoff_time_series(runoff_result, str(tmp_path / "ro_ts.png"), config=config),
        "ro_avg": plot_runoff_monthly_avg(runoff_result, str(tmp_path / "ro_avg.png"), config=config),
        "ro_dis": plot_runoff_discharge(runoff_result, str(tmp_path / "ro_dis.png"), config=config),
        "ro_yr":  plot_runoff_yearly(runoff_result, str(tmp_path / "ro_yr.png"), config=config),
    }

    return mc, runoff_result, outputs


# ==========================================
# A. Manual data → full pipeline
# ==========================================

def test_pipeline_from_manual_data(config, tmp_path):
    manual = {
        2020: {"Jan": 10.0, "Feb": 100.0, "Mar": 5.0},
        2021: {"Jan": 20.0, "Feb": 200.0, "Mar": 15.0},
        2022: {"Jan": 30.0, "Feb": 300.0, "Mar": 25.0},
    }
    df_hist = build_year_month_df(manual, config=config)

    mc, runoff, outputs = _run_full_pipeline(df_hist, config, tmp_path)

    assert mc["df_combined"].shape == (5, 3)          # 3 hist + 2 pred
    assert runoff["df_details"].shape[0] == 5 * 3     # 5 years × 3 months

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


def test_pipeline_from_excel(config, sample_excel, tmp_path):
    df_hist = build_from_file(sample_excel, config=config)

    # Sanity on extract output first
    assert not df_hist.empty
    assert df_hist.index.name == "Tahun"
    assert list(df_hist.columns) == config.columns.months

    mc, runoff, outputs = _run_full_pipeline(df_hist, config, tmp_path)

    assert mc["df_combined"].shape == (5, 3)
    assert runoff["df_details"].shape[0] == 5 * 3

    for path in outputs.values():
        _assert_valid_png(path)


# ==========================================
# C. Cross-check: manual vs Excel agree
# ==========================================

def test_manual_and_excel_agree(config, sample_excel, tmp_path):
    manual = {
        2020: {"Jan": 10.0, "Feb": 100.0, "Mar": 5.0},
        2021: {"Jan": 20.0, "Feb": 200.0, "Mar": 15.0},
        2022: {"Jan": 30.0, "Feb": 300.0, "Mar": 25.0},
    }
    from_manual = build_year_month_df(manual, config=config)
    from_excel = build_from_file(sample_excel, config=config)

    pd.testing.assert_frame_equal(from_manual, from_excel)