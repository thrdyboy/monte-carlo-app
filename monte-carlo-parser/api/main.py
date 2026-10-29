import os

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import artifacts, latest, runs

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
        print(f"[startup] warning: could not ensure warehouse tables: {e}")
    yield

app = FastAPI(
    title="Monte Carlo ETL API",
    description="Trigger the Monte Carlo + SCS-CN pipeline via Airflow",
    version="0.1.0",
    lifespan=lifespan
)


def _get_allowed_origins() -> list:
    """Read ALLOWED_ORIGINS (comma-separated) from env; fallback to ["*"].

    Example: ALLOWED_ORIGINS="https://app.example.com,http://localhost:5173"
    """
    raw = os.environ.get("ALLOWED_ORIGINS", "")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(artifacts.router)
app.include_router(latest.router)
app.include_router(runs.router)


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
