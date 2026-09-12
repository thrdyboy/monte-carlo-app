from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from api.dependencies import get_warehouse_engine

router = APIRouter(prefix="/api/runs", tags=["runs"])


# api/runs.py
from sqlalchemy.exc import ProgrammingError

_TABLE_MISSING_HINT = (
    "No pipeline runs yet. Trigger one via POST /api/runs/from-manual "
    "or POST /api/runs/from-excel."
)

@router.get("/metrics")
def list_run_metrics(limit: int = Query(50, ge=1, le=500)):
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
        return []   # graceful empty list

    return [
        {**dict(r), "created_at": r["created_at"].isoformat() if r["created_at"] else None}
        for r in rows
    ]


@router.get("/metrics/{run_id}")
def get_run_metrics(run_id: str):
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