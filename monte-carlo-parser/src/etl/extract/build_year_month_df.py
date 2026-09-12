import os
import sys
import pandas as pd
from typing import Dict, Any, Optional

# Settle the Path with Three Layers
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.config.settings import load_config


def build_year_month_df(
    manual_data: Dict[str, Any],
    config: Optional[Any] = None,
) -> pd.DataFrame:
    """Convert manual_data into expected wide format.

    Expected manual_data shape:
    {
      <year>: {"Jan": x, "Feb": y, ...}
      ...
    }

    IMPORTANT: this keeps every year the user provided, exactly as
    provided. Extraction must NEVER trim or pad historical rows based on
    forecast_years -- forecast_years only controls how many *future*
    years transform() simulates. Mixing the two silently throws away
    real historical years (or fabricates fake ones) whenever
    forecast_years doesn't happen to match the number of years entered.

    Args:
        manual_data: Dict keyed by year with month values.
        config: Optional pre-loaded config. If None, load_config() is called.

    Returns:
        DataFrame with years as index (reset to a column) and month columns.
    """
    if config is None:
        config = load_config()

    df = pd.DataFrame.from_dict(manual_data, orient="index")

    # Normalize columns to config months if possible
    months = list(config.columns.months)
    if len(months) == df.shape[1] and all(c in df.columns for c in months):
        df = df[months]
    else:
        # If manual_data keys match months but order differs, try to reorder.
        existing_months = [m for m in months if m in df.columns]
        if len(existing_months) != df.shape[1]:
            # Fall back to current behavior if manual_data doesn't match month names.
            df.columns = months[: df.shape[1]]
        else:
            df = df[existing_months]

        # If there are fewer month columns than expected, pad with NaN columns.
        if df.shape[1] < len(months):
            for m in months:
                if m not in df.columns:
                    df[m] = pd.NA
            df = df[months]

    # Ensure ordering by year
    df.index.name = config.columns.index
    df = df.sort_index()

    return df