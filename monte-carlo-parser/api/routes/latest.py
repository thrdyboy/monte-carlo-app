import io
import os
from typing import Literal, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from api.dependencies import get_warehouse_engine, get_s3_client
from api.utils.formatters import _df_to_json_safe_records, _safe_sheet_name

router = APIRouter(prefix="/api/latest", tags=["latest"])

ForecastMethod = Literal["monte_carlo", "markov"]

def _table_exists(engine, table_name: str) -> bool:
    """Return True if the given table exists in the warehouse DB."""
    from sqlalchemy import text
    sql = text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = :t
        )
    """)
    with engine.connect() as conn:
        return bool(conn.execute(sql, {"t": table_name}).scalar())

def _get_latest_run_id(method: Optional[str] = None) -> str:
    """Return the run_id of the most recent run.

    - If `method` is given and run_metrics has rows, return the newest run
      whose forecast_method matches (and that has registered artifacts).
      404 if there is no run for that method yet.
    - If `method` is None, or run_metrics doesn't exist / is empty, fall back
      to the most recently registered artifact.
    """
    engine = get_warehouse_engine()
    no_runs = "No pipeline runs yet. Trigger one via POST /api/runs/from-manual or /from-excel."

    if not _table_exists(engine, "artifacts"):
        raise HTTPException(status_code=404, detail=no_runs)

    if method is not None and _table_exists(engine, "run_metrics"):
        with engine.connect() as conn:
            has_metrics = conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM run_metrics)")
            ).scalar()
            if has_metrics:
                row = conn.execute(
                    text("""
                        SELECT rm.run_id
                        FROM run_metrics rm
                        WHERE rm.forecast_method = :method
                          AND EXISTS (SELECT 1 FROM artifacts a WHERE a.run_id = rm.run_id)
                        ORDER BY rm.id DESC
                        LIMIT 1
                    """),
                    {"method": method},
                ).fetchone()
                if not row:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No '{method}' runs yet. Trigger one with forecast_method='{method}'.",
                    )
                return row[0]

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT run_id FROM artifacts ORDER BY id DESC LIMIT 1")
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=no_runs)
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
def list_latest_plots(
    run_id: Optional[str] = Query(None),
    method: Optional[ForecastMethod] = Query(None),
):
    """Return every PNG plot from the latest (or specified) run.

    Frontend usage:
        const { run_id, plots } = await fetch('/api/latest/plots').then(r => r.json());
        plots.map(p => <img src={p.view_url} />);
    """
    if run_id is None:
        run_id = _get_latest_run_id(method)

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

@router.get("/tables")
def list_latest_tables(
    run_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    method: Optional[ForecastMethod] = Query(None),
):
    """Return every parquet table from the latest (or specified) run,
    with the first `limit` rows as a JSON preview.

    Frontend usage:
        const { run_id, tables } = await fetch('/api/latest/tables').then(r => r.json());
        tables.map(t => <DataTable columns={t.columns} rows={t.rows} />);
    """
    if run_id is None:
        run_id = _get_latest_run_id(method)

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

@router.get("/excel")
def download_latest_as_excel(
    run_id: Optional[str] = Query(None),
    method: Optional[ForecastMethod] = Query(None),
):
    """Bundle all parquet tables from a run into ONE Excel file.

    Each parquet becomes a sheet. Also adds a "Metadata" sheet listing
    what was bundled.

    Frontend usage:
        <a href="/api/latest/excel" download>Download all as Excel</a>
    """
    if run_id is None:
        run_id = _get_latest_run_id(method)

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
