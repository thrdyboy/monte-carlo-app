from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from api.dependencies import get_warehouse_engine

router = APIRouter(prefix="/api/runs", tags=["runs"])


_TABLE_MISSING_HINT = (
    "run_metrics table does not exist yet. "
    "It is created automatically the first time the pipeline runs, "
    "or you can create it manually with the SQL from the docs."
)

@router.get("/metrics")
def list_run_metrics(limit: int = Query(50, ge=1, le=500)):
    """List every run's metrics, newest first. Returns [] if the table is missing."""
    engine = get_warehouse_engine()
    sql = text("""
        SELECT id, run_id, dag_run_id, forecast_years, num_simulations,
               random_seed, curve_number, river_basin_area, runoff_scope,
               mae, rmse, mape, created_at
        FROM run_metrics
        ORDER BY id DESC
        LIMIT :limit
    """)
    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, {"limit": limit}).mappings().all()
    except ProgrammingError:
        # Table doesn't exist yet — return empty list instead of 500
        return []

    return [
        {**dict(r), "created_at": r["created_at"].isoformat() if r["created_at"] else None}
        for r in rows
    ]


@router.get("/metrics/{run_id}")
def get_run_metrics(run_id: str):
    """Return metrics for one specific run. 404 if the run has no metrics."""
    engine = get_warehouse_engine()
    sql = text("""
        SELECT id, run_id, dag_run_id, forecast_years, num_simulations,
               random_seed, curve_number, river_basin_area, runoff_scope,
               mae, rmse, mape, created_at
        FROM run_metrics
        WHERE run_id = :run_id
        ORDER BY id DESC LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(sql, {"run_id": run_id}).mappings().first()
    except ProgrammingError:
        raise HTTPException(status_code=404, detail=_TABLE_MISSING_HINT)

    if not row:
        raise HTTPException(status_code=404, detail=f"No metrics for run {run_id}")

    r = dict(row)
    r["created_at"] = r["created_at"].isoformat() if r["created_at"] else None
    return r