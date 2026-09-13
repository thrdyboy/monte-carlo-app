import json
import uuid

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api import artifacts, latest, runs
from api.airflow_client import trigger_dag
from api.schemas import ManualRunRequest, RunResponse
from api.dependencies import get_s3_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run on startup: make sure warehouse tables exist."""
    try:
        from src.etl.load.load_to_postgres import (
            ensure_artifacts_table,
            ensure_run_metrics_table,
        )
        ensure_artifacts_table()
        ensure_run_metrics_table()
        print("[startup] warehouse tables ready")
    except Exception as e:
        # Don't crash the API if warehouse is temporarily unreachable
        print(f"[startup] warning: could not ensure warehouse tables: {e}")
    yield

app = FastAPI(
    title="Monte Carlo ETL API",
    description="Trigger the Monte Carlo + SCS-CN pipeline via Airflow",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(artifacts.router)
app.include_router(latest.router)
app.include_router(runs.router)

UPLOAD_DIR = "/app/data/raw/uploads"


# ─────────────────────────────────────────────────────────────────────
# Health & root
# ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "OK"}


@app.get("/")
def root():
    return {
        "service": "monte-carlo-api",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "manual": "POST /api/runs/from-manual",
            "excel":  "POST /api/runs/from-excel",
        },
    }

@app.post("/api/runs/from-manual", response_model=RunResponse)
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


@app.post("/api/runs/from-excel", response_model=RunResponse)
async def run_from_excel(
    file: UploadFile = File(...),
    forecast_years: int = Form(None),
    num_simulations: int = Form(None),
    random_seed: int = Form(None),
    curve_number: float = Form(None),
    river_basin_area: float = Form(None),
    runoff_scope: str = Form("forecast"),
):
    """Upload Excel to MinIO, then trigger the Airflow DAG."""
    if runoff_scope not in ("forecast", "forecast_mean", "combined", "combined_mean"):
        raise HTTPException(status_code=400, detail="Invalid runoff_scope")

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