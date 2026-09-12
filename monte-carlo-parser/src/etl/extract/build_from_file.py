import os
import sys
import pandas as pd
from typing import Optional, Any

# Settle the Path with Three Layers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config


def build_from_file(
    file_path: str,
    config: Optional[Any] = None,
) -> pd.DataFrame:
    """Extract historical data from an Excel file.

    Args:
        file_path: Path to the Excel file.
        config: Optional pre-loaded config. If None, load_config() is called.

    Returns:
        DataFrame with year as index (if expected columns are found).
    """
    if config is None:
        config = load_config()

    sheet_name = config.data.default_sheet_name
    df: pd.DataFrame = pd.read_excel(file_path, sheet_name=sheet_name)

    year_col = config.columns.index
    months = list(config.columns.months)

    # If column order is expected but not guaranteed, attempt to reorder.
    if year_col in df.columns and all(m in df.columns for m in months):
        df = df[[year_col] + months]

        # Sort by year if possible.
        try:
            df = df.sort_values(by=year_col)
        except Exception:
            pass

        df = df.set_index(year_col)
        df[months] = df[months].astype(float)

    return df