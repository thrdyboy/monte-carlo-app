import re

import numpy as np
import pandas as pd


def _df_to_json_safe_records(df: pd.DataFrame, limit: int) -> list:
    """Convert the first `limit` rows of a DataFrame to JSON-safe dicts.

    Handles NaN, NaT, Timestamps, numpy scalars — everything FastAPI's
    default JSON encoder would choke on.
    """
    preview = df.head(limit).copy()

    # Convert to object dtype so NaN/NaT become Python None cleanly
    preview = preview.astype(object).where(pd.notnull(preview), None)

    records = []
    for _, row in preview.iterrows():
        rec = {}
        for col, val in row.items():
            # pandas Timestamp → ISO string
            if hasattr(val, "isoformat"):
                val = val.isoformat()
            # numpy scalar → python scalar
            elif isinstance(val, (np.integer,)):
                val = int(val)
            elif isinstance(val, (np.floating,)):
                val = float(val)
            elif isinstance(val, (np.bool_,)):
                val = bool(val)
            rec[col] = val
        records.append(rec)

    return records


def _safe_sheet_name(name: str, used: set) -> str:
    """Excel sheet names: max 31 chars, cannot contain : \\ / ? * [ ]"""
    cleaned = re.sub(r"[:\\/?*\[\]]", "_", name)[:31] or "Sheet"
    final, i = cleaned, 1
    while final in used:
        suffix = f"_{i}"
        final = cleaned[:31 - len(suffix)] + suffix
        i += 1
    return final
