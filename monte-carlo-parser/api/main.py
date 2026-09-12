import json
import os

from contextlib import asynccontextmanager
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api import artifacts, latest, runs
from api.airflow_client import trigger_dag
from api.schemas import ManualRunRequest, RunResponse

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


# ─────────────────────────────────────────────────────────────────────
# Trigger from manual JSON data
# ─────────────────────────────────────────────────────────────────────

@app.post("/api/runs/from-manual", response_model=RunResponse)
def run_from_manual(body: ManualRunRequest):
    """Save manual data to a JSON file, then trigger the Airflow DAG."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    filename = "manual_latest.json"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # JSON requires string keys → convert int year keys
    json_safe = {str(y): months for y, months in body.data.items()}
    with open(filepath, "w") as f:
        json.dump(json_safe, f, indent=2)

    relative_path = f"data/raw/uploads/{filename}"

    conf = {
        "source": "manual",
        "manual_data_path": relative_path,
        "runoff_scope": body.runoff_scope,
    }
    if body.forecast_years is not None:
        conf["forecast_years"] = body.forecast_years
    if body.num_simulations is not None:
        conf["num_simulations"] = body.num_simulations
    if body.random_seed is not None:
        conf["random_seed"] = body.random_seed
    if body.curve_number is not None:
        conf["curve_number"] = body.curve_number
    if body.river_basin_area is not None:
        conf["river_basin_area"] = body.river_basin_area

    result = trigger_dag(conf)

    return RunResponse(
        status="triggered",
        dag_run_id=result.get("dag_run_id", "unknown"),
        source="manual",
        input_path=relative_path,
        conf=conf,
    )


# ─────────────────────────────────────────────────────────────────────
# Trigger from Excel upload
# ─────────────────────────────────────────────────────────────────────

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
    """Save the uploaded Excel file, then trigger the Airflow DAG."""
    if runoff_scope not in ("forecast", "combined"):
        raise HTTPException(status_code=400, detail="runoff_scope must be 'forecast' or 'combined'")

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    
    original = file.filename or "upload.xlsx"
    safe_name = original.replace(" ", "_").replace("/", "_").replace("\\", "_")

    ext = os.path.splitext(safe_name)[1].lower() or ".xlsx"
    filename = f"excel_latest{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    relative_path = f"data/raw/uploads/{filename}"

    conf = {
        "source": "file",
        "input_file_path": relative_path,
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
        input_path=relative_path,
        conf=conf,
    )