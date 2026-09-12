import os
import sys
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.etl.extract.build_year_month_df import build_year_month_df
from src.etl.extract.build_from_file import build_from_file


# ==========================================
# Shared Fixture
# ==========================================

@pytest.fixture
def mock_config():
    """Fake config matching montecarlo.yaml (uses 'Tahun')."""
    config = MagicMock()
    config.columns.months = ["Jan", "Feb", "Mar"]
    config.columns.index = "Tahun"
    config.data.default_sheet_name = "Historical"
    return config


# ==========================================
# Tests for build_year_month_df
# ==========================================

def test_manual_data_perfect_match(mock_config):
    """All months present in correct order."""
    manual_data = {
        2020: {"Jan": 10, "Feb": 20, "Mar": 30},
        2021: {"Jan": 15, "Feb": 25, "Mar": 35},
    }
    df = build_year_month_df(manual_data, config=mock_config)

    assert df.shape == (2, 3)                    # ← year is index, not column
    assert df.index.name == "Tahun"
    assert list(df.columns) == ["Jan", "Feb", "Mar"]
    assert df.index.tolist() == [2020, 2021]
    assert df.iloc[0]["Jan"] == 10
    assert df.iloc[1]["Mar"] == 35


def test_manual_data_sorted_by_year(mock_config):
    """Rows should be sorted regardless of input dict order."""
    manual_data = {
        2022: {"Jan": 30, "Feb": 40, "Mar": 50},
        2020: {"Jan": 10, "Feb": 20, "Mar": 30},
        2021: {"Jan": 20, "Feb": 30, "Mar": 40},
    }
    df = build_year_month_df(manual_data, config=mock_config)

    assert df.index.tolist() == [2020, 2021, 2022]   # ← was df["Year"]


def test_manual_data_missing_months_padded_with_na(mock_config):
    """Missing month columns should be padded with pd.NA."""
    manual_data = {2020: {"Jan": 10}}                 # only Jan provided
    df = build_year_month_df(manual_data, config=mock_config)

    assert list(df.columns) == ["Jan", "Feb", "Mar"]   # ← no "Year"
    assert pd.isna(df.iloc[0]["Feb"])
    assert pd.isna(df.iloc[0]["Mar"])


def test_manual_data_reordered_months(mock_config):
    """Out-of-order months should be reordered to config order."""
    manual_data = {
        2020: {"Mar": 30, "Jan": 10, "Feb": 20},
    }
    df = build_year_month_df(manual_data, config=mock_config)

    assert list(df.columns) == ["Jan", "Feb", "Mar"]   # ← no "Year"
    assert df.iloc[0]["Jan"] == 10
    assert df.iloc[0]["Feb"] == 20
    assert df.iloc[0]["Mar"] == 30


def test_manual_data_does_not_trim_history(mock_config):
    """Regression guard: extraction must NEVER trim years."""
    manual_data = {
        2018: {"Jan": 1, "Feb": 2, "Mar": 3},
        2019: {"Jan": 4, "Feb": 5, "Mar": 6},
        2020: {"Jan": 7, "Feb": 8, "Mar": 9},
        2021: {"Jan": 10, "Feb": 11, "Mar": 12},
        2022: {"Jan": 13, "Feb": 14, "Mar": 15},
    }
    df = build_year_month_df(manual_data, config=mock_config)

    assert df.index.tolist() == [2018, 2019, 2020, 2021, 2022]   # ← was df["Year"]
    assert len(df) == 5


@patch('src.etl.extract.build_year_month_df.load_config')
def test_manual_data_loads_config_when_not_provided(mock_load_config, mock_config):
    """If config is None, load_config() should be called."""
    mock_load_config.return_value = mock_config

    manual_data = {2020: {"Jan": 10, "Feb": 20, "Mar": 30}}
    df = build_year_month_df(manual_data)                        # no config passed

    mock_load_config.assert_called_once()
    assert df.shape == (1, 3)                                    # ← was (1, 4)


# ==========================================
# Tests for build_from_file
# ==========================================

@patch('src.etl.extract.build_from_file.pd.read_excel')
def test_file_reads_with_config_sheet_name(mock_read_excel, mock_config):
    """pd.read_excel should be called with the sheet name from config."""
    mock_read_excel.return_value = pd.DataFrame({
        "Tahun": [2020, 2021],
        "Jan": [10, 15],
        "Feb": [20, 25],
        "Mar": [30, 35],
    })

    build_from_file("dummy.xlsx", config=mock_config)

    mock_read_excel.assert_called_once_with("dummy.xlsx", sheet_name="Historical")


@patch('src.etl.extract.build_from_file.pd.read_excel')
def test_file_reorders_and_indexes_columns(mock_read_excel, mock_config):
    """Expected columns → reorder, sort, and set year as index."""
    mock_read_excel.return_value = pd.DataFrame({
        "Mar": [30, 35],
        "Jan": [10, 15],
        "Unused": ["A", "B"],
        "Feb": [20, 25],
        "Tahun": [2021, 2020],     # deliberately out of order
    })

    df = build_from_file("dummy.xlsx", config=mock_config)

    assert list(df.columns) == ["Jan", "Feb", "Mar"]
    assert df.index.name == "Tahun"
    assert df.index.tolist() == [2020, 2021]
    assert df.iloc[0]["Jan"] == 15     # Year 2020
    assert df.iloc[1]["Jan"] == 10     # Year 2021


@patch('src.etl.extract.build_from_file.pd.read_excel')
def test_file_returns_raw_df_when_columns_dont_match(mock_read_excel, mock_config):
    """If expected columns aren't found, return the raw DataFrame as-is."""
    raw = pd.DataFrame({"Something": [1, 2], "Else": [3, 4]})
    mock_read_excel.return_value = raw

    df = build_from_file("dummy.xlsx", config=mock_config)

    pd.testing.assert_frame_equal(df, raw)


@patch('src.etl.extract.build_from_file.load_config')
@patch('src.etl.extract.build_from_file.pd.read_excel')
def test_file_loads_config_when_not_provided(mock_read_excel, mock_load_config, mock_config):
    """If config is None, load_config() should be called."""
    mock_load_config.return_value = mock_config
    mock_read_excel.return_value = pd.DataFrame({
        "Tahun": [2020],
        "Jan": [10], "Feb": [20], "Mar": [30],
    })

    build_from_file("dummy.xlsx")

    mock_load_config.assert_called_once()