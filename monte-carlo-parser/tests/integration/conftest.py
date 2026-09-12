import pytest
from unittest.mock import MagicMock

@pytest.fixture
def config():
    """Real-ish config for integration testing — no patching load_config."""
    cfg = MagicMock()
    cfg.columns.months = ["Jan", "Feb", "Mar"]
    cfg.columns.index = "Tahun"
    cfg.data.default_sheet_name = "Sheet1"
    cfg.monte_carlo.forecast_years = 2
    cfg.monte_carlo.random_seed = 42
    cfg.monte_carlo.num_simulations = 20   # small for speed
    cfg.runoff.curve_number = 75
    cfg.runoff.river_basin_area = 58.87
    return cfg