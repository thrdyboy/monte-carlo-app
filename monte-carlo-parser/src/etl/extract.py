import os
import sys

import pandas as pd
from typing import Optional, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config.settings import load_config

config = load_config()


def _build_year_month_df(manual_data: Dict[str, Any]) -> pd.DataFrame:
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
    """

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

    return df.reset_index()


def extract(
    file_path: Optional[str] = None,
    manual_data: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Extract historical data from Excel or manual input.

    - If `file_path` is provided: reads the Excel sheet as-is (all rows).
    - If `manual_data` is provided: converts it into a DataFrame as-is
      (all years supplied).

    Historical extraction is intentionally independent of forecast_years.
    forecast_years belongs to the forecasting step (transform.py), not
    to how much history gets loaded.
    """

    if file_path:
        sheet_name = config.data.default_sheet_name
        df = pd.read_excel(file_path, sheet_name=sheet_name)

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

        return df

    if manual_data:
        return _build_year_month_df(manual_data=manual_data)

    raise ValueError("Harus menyediakan file_path atau manual_data!")