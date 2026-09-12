# tests/unit/test_load.py
import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.etl.load.plot_monte_carlo import plot_mc_time_series, plot_mc_heatmap
from src.etl.load.plot_runoff import (
    plot_runoff_time_series,
    plot_runoff_monthly_avg,
    plot_runoff_discharge,
    plot_runoff_yearly,
)


PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


# ==========================================
# Fixtures
# ==========================================

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.columns.months = ["Jan", "Feb", "Mar"]
    config.columns.index = "Tahun"          # ← changed from "Year"
    return config


@pytest.fixture
def mc_result():
    ts_hist = pd.DataFrame({
        "Tanggal": pd.to_datetime(["2020-01-01", "2020-02-01", "2020-03-01"]),
        "Nilai": [10.0, 20.0, 30.0],
    })
    ts_pred = pd.DataFrame({
        "Tanggal": pd.to_datetime(["2021-01-01", "2021-02-01", "2021-03-01"]),
        "Nilai": [12.0, 22.0, 32.0],
    })
    df_pred = pd.DataFrame(
        {"Jan": [12.0, 13.0], "Feb": [22.0, 23.0], "Mar": [32.0, 33.0]},
        index=[2021, 2022],
    )
    df_pred.index.name = "Tahun"

    return {"ts_hist": ts_hist, "ts_pred": ts_pred, "df_pred": df_pred}


@pytest.fixture
def runoff_result():
    df_details = pd.DataFrame({
        "Tahun": [2020, 2020, 2020, 2021, 2021, 2021],   # ← "Tahun"
        "Bulan": ["Jan", "Feb", "Mar", "Jan", "Feb", "Mar"],
        "No_Bulan": [1, 2, 3, 1, 2, 3],
        "Curah_Hujan_mm": [100.0, 20.0, 5.0, 120.0, 25.0, 6.0],
        "Runoff_mm": [41.0, 0.5, 0.0, 55.0, 1.0, 0.0],
        "Volume_m3": [2.4e6, 3.0e4, 0.0, 3.2e6, 5.8e4, 0.0],
        "Debit_m3_per_s": [0.9, 0.012, 0.0, 1.2, 0.024, 0.0],
        "Koefisien_Limpasan": [0.41, 0.025, 0.0, 0.46, 0.04, 0.0],
    })

    rekap_tahunan = pd.DataFrame({
        "Tahun": [2020, 2021],                            # ← "Tahun"
        "Total_Hujan_mm": [125.0, 151.0],
        "Total_Runoff_mm": [41.5, 56.0],
        "Total_Volume_m3": [2.43e6, 3.26e6],
        "Rerata_Debit_m3s": [0.304, 0.408],
        "Koefisien_Limpasan_Tahunan": [0.332, 0.371],
    })

    rekap_bulanan = pd.DataFrame({
        "No_Bulan": [1, 2, 3],
        "Bulan": ["Jan", "Feb", "Mar"],
        "Rerata_Hujan_mm": [110.0, 22.5, 5.5],
        "Rerata_Runoff_mm": [48.0, 0.75, 0.0],
        "Rerata_Debit_m3s": [1.05, 0.018, 0.0],
    })

    return {
        "df_details": df_details,
        "rekap_tahunan": rekap_tahunan,
        "rekap_bulanan": rekap_bulanan,
    }


# ==========================================
# Helpers
# ==========================================

def _assert_valid_png(path: str) -> None:
    assert os.path.exists(path), f"PNG not created: {path}"
    assert os.path.getsize(path) > 0, f"PNG is empty: {path}"
    with open(path, "rb") as f:
        assert f.read(8) == PNG_MAGIC, f"Not a valid PNG: {path}"


# ==========================================
# plot_monte_carlo
# ==========================================

def test_plot_mc_time_series_creates_png(mc_result, tmp_path):
    out = tmp_path / "mc_time_series.png"
    returned = plot_mc_time_series(mc_result, str(out))
    assert returned == str(out)
    _assert_valid_png(str(out))


def test_plot_mc_heatmap_creates_png(mc_result, mock_config, tmp_path):
    out = tmp_path / "mc_heatmap.png"
    returned = plot_mc_heatmap(mc_result, str(out), config=mock_config)
    assert returned == str(out)
    _assert_valid_png(str(out))


@patch('src.etl.load.plot_monte_carlo.load_config')
def test_plot_mc_heatmap_loads_config_when_missing(
    mock_load_config, mc_result, mock_config, tmp_path
):
    mock_load_config.return_value = mock_config
    out = tmp_path / "mc_heatmap.png"
    plot_mc_heatmap(mc_result, str(out))
    mock_load_config.assert_called_once()
    _assert_valid_png(str(out))


def test_plot_mc_heatmap_uses_configured_months(mc_result, mock_config, tmp_path):
    mc_result["df_pred"]["Extra"] = [99.0, 99.0]
    out = tmp_path / "mc_heatmap.png"
    plot_mc_heatmap(mc_result, str(out), config=mock_config)
    _assert_valid_png(str(out))


# ==========================================
# plot_runoff
# ==========================================

def test_plot_runoff_time_series_creates_png(runoff_result, mock_config, tmp_path):
    out = tmp_path / "runoff_time_series.png"
    returned = plot_runoff_time_series(runoff_result, str(out), config=mock_config)
    assert returned == str(out)
    _assert_valid_png(str(out))


def test_plot_runoff_monthly_avg_creates_png(runoff_result, mock_config, tmp_path):
    out = tmp_path / "runoff_monthly_avg.png"
    returned = plot_runoff_monthly_avg(runoff_result, str(out), config=mock_config)
    assert returned == str(out)
    _assert_valid_png(str(out))


def test_plot_runoff_discharge_creates_png(runoff_result, mock_config, tmp_path):
    out = tmp_path / "runoff_discharge.png"
    returned = plot_runoff_discharge(runoff_result, str(out), config=mock_config)
    assert returned == str(out)
    _assert_valid_png(str(out))


def test_plot_runoff_yearly_creates_png(runoff_result, mock_config, tmp_path):
    out = tmp_path / "runoff_yearly.png"
    returned = plot_runoff_yearly(runoff_result, str(out), config=mock_config)
    assert returned == str(out)
    _assert_valid_png(str(out))


def test_runoff_time_series_handles_single_year(runoff_result, mock_config, tmp_path):
    single_year = runoff_result.copy()
    single_year["df_details"] = runoff_result["df_details"][
        runoff_result["df_details"]["Tahun"] == 2020
    ].reset_index(drop=True)

    out = tmp_path / "single_year.png"
    plot_runoff_time_series(single_year, str(out), config=mock_config)
    _assert_valid_png(str(out))


def test_all_plots_generate_together(mc_result, runoff_result, mock_config, tmp_path):
    outputs = [
        plot_mc_time_series(mc_result, str(tmp_path / "mc_ts.png")),
        plot_mc_heatmap(mc_result, str(tmp_path / "mc_hm.png"), config=mock_config),
        plot_runoff_time_series(runoff_result, str(tmp_path / "ro_ts.png"), config=mock_config),
        plot_runoff_monthly_avg(runoff_result, str(tmp_path / "ro_avg.png"), config=mock_config),
        plot_runoff_discharge(runoff_result, str(tmp_path / "ro_dis.png"), config=mock_config),
        plot_runoff_yearly(runoff_result, str(tmp_path / "ro_year.png"), config=mock_config),
    ]
    assert len(outputs) == 6
    for p in outputs:
        _assert_valid_png(p)