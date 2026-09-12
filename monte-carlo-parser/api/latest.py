import io
import os
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from api.dependencies import get_warehouse_engine, get_s3_client

router = APIRouter(prefix="/api/latest", tags=["latest"])


def _get_latest_run_id() -> str:
    """Return the run_id of the most recently registered artifact."""
    engine = get_warehouse_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT run_id FROM artifacts ORDER BY id DESC LIMIT 1")
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No artifacts registered yet")
    return row[0]


def _fetch_artifacts(run_id: str, artifact_type: str) -> list:
    """Return all artifacts of a given type for a run."""
    engine = get_warehouse_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT id, bucket, object_key, file_size_bytes
                FROM artifacts
                WHERE run_id = :run_id AND artifact_type = :artifact_type
                ORDER BY id
            """),
            {"run_id": run_id, "artifact_type": artifact_type},
        ).mappings().all()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────────────
# Plots (PNG gallery)
# ─────────────────────────────────────────────────────────────────────

@router.get("/plots")
def list_latest_plots(run_id: Optional[str] = Query(None)):
    """Return every PNG plot from the latest (or specified) run.

    Frontend usage:
        const { run_id, plots } = await fetch('/api/latest/plots').then(r => r.json());
        plots.map(p => <img src={p.view_url} />);
    """
    if run_id is None:
        run_id = _get_latest_run_id()

    rows = _fetch_artifacts(run_id, "png")
    if not rows:
        raise HTTPException(status_code=404, detail=f"No plots found for run {run_id}")

    return {
        "run_id": run_id,
        "count": len(rows),
        "plots": [
            {
                "id": r["id"],
                "name": os.path.basename(r["object_key"]),
                "size_bytes": r["file_size_bytes"],
                "view_url": f"/api/artifacts/{r['id']}/view",
                "download_url": f"/api/artifacts/{r['id']}/download",
            }
            for r in rows
        ],
    }


# ─────────────────────────────────────────────────────────────────────
# Tables (parquet -> JSON preview)
# ─────────────────────────────────────────────────────────────────────

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


@router.get("/tables")
def list_latest_tables(
    run_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
):
    """Return every parquet table from the latest (or specified) run,
    with the first `limit` rows as a JSON preview.

    Frontend usage:
        const { run_id, tables } = await fetch('/api/latest/tables').then(r => r.json());
        tables.map(t => <DataTable columns={t.columns} rows={t.rows} />);
    """
    if run_id is None:
        run_id = _get_latest_run_id()

    rows = _fetch_artifacts(run_id, "parquet")
    if not rows:
        raise HTTPException(status_code=404, detail=f"No tables found for run {run_id}")

    s3 = get_s3_client()
    tables = []

    for r in rows:
        name = os.path.basename(r["object_key"])
        try:
            obj = s3.get_object(Bucket=r["bucket"], Key=r["object_key"])
            buf = io.BytesIO(obj["Body"].read())
            df = pd.read_parquet(buf)

            tables.append({
                "id": r["id"],
                "name": name,
                "size_bytes": r["file_size_bytes"],
                "total_rows": int(len(df)),
                "total_columns": int(len(df.columns)),
                "returned_rows": int(min(limit, len(df))),
                "columns": list(df.columns),
                "rows": _df_to_json_safe_records(df, limit),
                "download_url": f"/api/artifacts/{r['id']}/download",
            })
        except Exception as e:
            # Include the failure inline so one bad parquet doesn't kill the whole response
            tables.append({
                "id": r["id"],
                "name": name,
                "size_bytes": r["file_size_bytes"],
                "error": str(e),
            })

    return {
        "run_id": run_id,
        "count": len(tables),
        "tables": tables,
    }

# ─────────────────────────────────────────────────────────────────────
# Bundle the whole latest run into a single Excel workbook
# ─────────────────────────────────────────────────────────────────────

def _safe_sheet_name(name: str, used: set) -> str:
    """Excel sheet names: max 31 chars, cannot contain : \\ / ? * [ ]"""
    import re
    cleaned = re.sub(r"[:\\/?*\[\]]", "_", name)[:31] or "Sheet"
    final, i = cleaned, 1
    while final in used:
        suffix = f"_{i}"
        final = cleaned[:31 - len(suffix)] + suffix
        i += 1
    return final


@router.get("/excel")
def download_latest_as_excel(run_id: Optional[str] = Query(None)):
    """Bundle all parquet tables from a run into ONE Excel file.

    Each parquet becomes a sheet. Also adds a "Metadata" sheet listing
    what was bundled.

    Frontend usage:
        <a href="/api/latest/excel" download>Download all as Excel</a>
    """
    if run_id is None:
        run_id = _get_latest_run_id()

    rows = _fetch_artifacts(run_id, "parquet")
    if not rows:
        raise HTTPException(status_code=404, detail=f"No parquet tables for run {run_id}")

    s3 = get_s3_client()
    xlsx_buf = io.BytesIO()

    with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
        # Metadata sheet first
        meta = pd.DataFrame([
            {"key": "run_id",       "value": run_id},
            {"key": "table_count",  "value": str(len(rows))},
            {"key": "tables",       "value": ", ".join(
                os.path.basename(r["object_key"]).replace(".parquet", "") for r in rows
            )},
        ])
        meta.to_excel(writer, sheet_name="Metadata", index=False)

        used = {"Metadata"}
        for r in rows:
            name = os.path.basename(r["object_key"]).replace(".parquet", "")
            sheet_name = _safe_sheet_name(name, used)
            used.add(sheet_name)

            obj = s3.get_object(Bucket=r["bucket"], Key=r["object_key"])
            df = pd.read_parquet(io.BytesIO(obj["Body"].read()))
            df.to_excel(writer, sheet_name=sheet_name, index=False)

    xlsx_buf.seek(0)
    filename = f"{run_id}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(
        xlsx_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )