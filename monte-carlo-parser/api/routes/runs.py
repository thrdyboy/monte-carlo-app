import json
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from api.airflow_client import trigger_dag
from api.dependencies import get_s3_client, get_warehouse_engine
from api.schemas import ManualRunRequest, RunResponse

router = APIRouter(prefix="/api/runs", tags=["runs"])


# api/routes/runs.py

_TABLE_MISSING_HINT = (
    "No pipeline runs yet. Trigger one via POST /api/runs/from-manual "
    "or POST /api/runs/from-excel."
)


# ─────────────────────────────────────────────────────────────────────
# Trigger runs
# ─────────────────────────────────────────────────────────────────────

@router.post("/from-manual", response_model=RunResponse)
def run_from_manual(body: ManualRunRequest):
    """Upload manual JSON to MinIO, then trigger the Airflow DAG."""
    job_id = uuid.uuid4().hex[:8]
    object_key = f"inputs/manual_{job_id}.json"

    # JSON requires string keys — convert int year keys
    json_safe = {str(y): months for y, months in body.data.items()}
    payload = json.dumps(json_safe, indent=2).encode("utf-8")

    # ── Upload to MinIO ──
    s3 = get_s3_client()
    try:
        s3.put_object(
            Bucket="mc-parquet",                 
            Key=object_key,
            Body=payload,
            ContentType="application/json",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MinIO upload failed: {e}")

    # ── Build DAG config ──
    conf = {
        "source": "manual",
        "manual_data_s3_bucket": "mc-parquet",
        "manual_data_s3_key": object_key,
        "runoff_scope": body.runoff_scope,
        "forecast_method": body.forecast_method or "monte_carlo",
    }
    for k in ("forecast_years", "num_simulations", "random_seed",
              "curve_number", "river_basin_area"):
        v = getattr(body, k, None)
        if v is not None:
            conf[k] = v

    result = trigger_dag(conf)
    return RunResponse(
        status="triggered",
        dag_run_id=result.get("dag_run_id", "unknown"),
        source="manual",
        input_path=f"s3://mc-parquet/{object_key}",
        conf=conf,
    )


@router.post("/from-excel", response_model=RunResponse)
async def run_from_excel(
    file: UploadFile = File(...),
    forecast_years: int = Form(None),
    num_simulations: int = Form(None),
    random_seed: int = Form(None),
    curve_number: float = Form(None),
    river_basin_area: float = Form(None),
    runoff_scope: str = Form("forecast"),
    forecast_method: str = Form("monte_carlo"),
):
    """Upload Excel to MinIO, then trigger the Airflow DAG."""
    if runoff_scope not in ("forecast", "forecast_mean", "combined", "combined_mean"):
        raise HTTPException(status_code=400, detail="Invalid runoff_scope")
    if forecast_method not in ("monte_carlo", "markov"):
        raise HTTPException(status_code=400, detail="Invalid forecast_method")

    job_id = uuid.uuid4().hex[:8]
    original = file.filename or "upload.xlsx"
    safe_name = original.replace(" ", "_").replace("/", "_").replace("\\", "_")
    object_key = f"inputs/excel_{job_id}_{safe_name}"

    content = await file.read()

    # ── Upload to MinIO ──
    s3 = get_s3_client()
    try:
        s3.put_object(
            Bucket="mc-parquet",
            Key=object_key,
            Body=content,
            ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"MinIO upload failed: {e}")

    # ── Build DAG config ──
    conf = {
        "source": "file",
        "input_file_s3_bucket": "mc-parquet",
        "input_file_s3_key": object_key,
        "runoff_scope": runoff_scope,
        "forecast_method": forecast_method,
    }
    if forecast_years is not None:
        conf["forecast_years"] = forecast_years
    if num_simulations is not None:
        conf["num_simulations"] = num_simulations
    if random_seed is not None:
        conf["random_seed"] = random_seed
    if curve_number is not None:
        conf["curve_number"] = curve_number
    if river_basin_area is not None:
        conf["river_basin_area"] = river_basin_area

    result = trigger_dag(conf)
    return RunResponse(
        status="triggered",
        dag_run_id=result.get("dag_run_id", "unknown"),
        source="file",
        input_path=f"s3://mc-parquet/{object_key}",
        conf=conf,
    )


# ─────────────────────────────────────────────────────────────────────
# Run metrics
# ─────────────────────────────────────────────────────────────────────

@router.get("/metrics")
def list_run_metrics(limit: int = Query(50, ge=1, le=500)):
    engine = get_warehouse_engine()
    sql = text("""
        SELECT id, run_id, dag_run_id, forecast_years, num_simulations,
               random_seed, curve_number, river_basin_area, runoff_scope,
               forecast_method, mae, rmse, mape, created_at
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
               forecast_method, mae, rmse, mape, created_at
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
