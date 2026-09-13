# dags/monte_carlo_dag.py
"""
Airflow DAG for the Monte Carlo + Runoff ETL pipeline.

Trigger with custom config (optional). All keys are optional — anything
omitted falls back to src/config/montecarlo.yaml.

    {
        "source": "file",              # "file" | "manual" | "both"
        "forecast_years": 10,
        "num_simulations": 1000,
        "random_seed": 42,
        "curve_number": 80,            # ← NEW
        "river_basin_area": 100.5      # ← NEW (km²)
    }

Notes:
- Uses `from airflow.operators.python import PythonOperator` for
  Airflow 2.x compatibility (also works in 3.x).
- Imports from `src.*` are done INSIDE task callables, not at module
  top-level. This keeps DAG parsing fast and prevents the DAG from
  vanishing from the UI if `src` has a slow or flaky import.
- XCom only carries primitives (int/str/float). Custom objects like the
  Pydantic AppSettings config are rebuilt inside each task, avoiding
  Airflow's "not in allow list for deserialization" security error.
"""
import os
import sys
import json
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import BranchPythonOperator, PythonOperator  # type: ignore

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Task callables
# ---------------------------------------------------------------------------

def _build_config(**context):
    """Load config, apply overrides from dag_run.conf, push primitives via XCom."""
    from src.config.settings import load_config

    config = load_config()
    dag_conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}

    # ── Monte Carlo overrides ──
    forecast_years = int(
        dag_conf.get("forecast_years", config.monte_carlo.forecast_years)
    )
    num_simulations = int(
        dag_conf.get("num_simulations", config.monte_carlo.num_simulations)
    )
    random_seed = int(
        dag_conf.get("random_seed", config.monte_carlo.random_seed)
    )

    # ── Runoff overrides ──
    curve_number = float(
        dag_conf.get("curve_number", config.runoff.curve_number)
    )
    river_basin_area = float(
        dag_conf.get("river_basin_area", config.runoff.river_basin_area)
    )

    # ── Runoff scope (forecast-only vs combined) ──
    runoff_scope = str(dag_conf.get("runoff_scope", "forecast")).lower()
    if runoff_scope not in ("forecast", "combined"):
        raise ValueError(
            f"Invalid 'runoff_scope' value: {runoff_scope!r}. "
            "Must be 'forecast' or 'combined'."
        )

    # ── Source selection ──
    source = str(dag_conf.get("source", "both")).lower()
    if source not in ("file", "manual", "both"):
        raise ValueError(
            f"Invalid 'source' value: {source!r}. Must be 'file', 'manual', or 'both'."
        )

    # Push all primitives to XCom
    ti = context["ti"]
    ti.xcom_push(key="forecast_years", value=forecast_years)
    ti.xcom_push(key="num_simulations", value=num_simulations)
    ti.xcom_push(key="random_seed", value=random_seed)
    ti.xcom_push(key="curve_number", value=curve_number)
    ti.xcom_push(key="river_basin_area", value=river_basin_area)
    ti.xcom_push(key="runoff_scope", value=runoff_scope)
    ti.xcom_push(key="source", value=source)

    print(f"[config] forecast_years   = {forecast_years}")
    print(f"[config] num_simulations  = {num_simulations}")
    print(f"[config] random_seed      = {random_seed}")
    print(f"[config] curve_number     = {curve_number}")
    print(f"[config] river_basin_area = {river_basin_area} km²")
    print(f"[config] runoff_scope     = {runoff_scope}")
    print(f"[config] source           = {source}")


def _choose_branch(**context):
    """Return the task id(s) to run based on the `source` config."""
    source = context["ti"].xcom_pull(task_ids="build_config", key="source") or "both"

    if source == "file":
        print("[branch] Running only the Excel-file pipeline.")
        return "run_pipeline_from_excel"
    if source == "manual":
        print("[branch] Running only the manual-dict pipeline.")
        return "run_pipeline_from_manual_dict"
    print("[branch] Running both pipelines in parallel.")
    return ["run_pipeline_from_excel", "run_pipeline_from_manual_dict"]


def _rebuild_config(ti):
    """Rebuild a fresh config from YAML + the primitives stored in XCom."""
    from src.config.settings import load_config

    config = load_config()

    config.monte_carlo.forecast_years = (
        ti.xcom_pull(task_ids="build_config", key="forecast_years") or 5
    )
    config.monte_carlo.num_simulations = (
        ti.xcom_pull(task_ids="build_config", key="num_simulations") or 1000
    )
    config.monte_carlo.random_seed = (
        ti.xcom_pull(task_ids="build_config", key="random_seed") or 42
    )
    config.runoff.curve_number = (
        ti.xcom_pull(task_ids="build_config", key="curve_number") or 75.0
    )
    config.runoff.river_basin_area = (
        ti.xcom_pull(task_ids="build_config", key="river_basin_area") or 58.87
    )
    return config


def _get_runoff_scope(ti) -> str:
    return ti.xcom_pull(task_ids="build_config", key="runoff_scope") or "forecast"


def _run_pipeline_from_file(**context):
    """Download Excel from MinIO, run pipeline, upload results."""
    import tempfile
    from src.pipeline import run_full_pipeline
    from src.etl.load.load_to_minio import _get_s3_client

    ti = context["ti"]
    config = _rebuild_config(ti)
    runoff_scope = _get_runoff_scope(ti)
    forecast_years = config.monte_carlo.forecast_years

    dag_conf = (context.get("dag_run").conf or {}) if context.get("dag_run") else {}

    bucket = dag_conf.get("input_file_s3_bucket")
    key = dag_conf.get("input_file_s3_key")
    if not bucket or not key:
        print("[skip] No input_file_s3_bucket/key in dag_run.conf")
        return

    # ── Download from MinIO to a temp file ──
    s3 = _get_s3_client(config)
    suffix = os.path.splitext(key)[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
    s3.download_file(bucket, key, tmp_path)
    print(f"[pipeline] Downloaded s3://{bucket}/{key} → {tmp_path}")

    output_dir = os.path.join(
        PROJECT_ROOT, "data", "warehouse",
        f"airflow_file_{forecast_years}y_{context['ds']}",
    )

    result = run_full_pipeline(
        output_dir=output_dir,
        input_file_path=tmp_path,
        config=config,
        runoff_scope=runoff_scope,
    )
    print(f"[pipeline] Result: {result}")
    os.unlink(tmp_path)

def _run_pipeline_from_manual(**context):
    """Download manual JSON from MinIO, run pipeline, upload results."""
    import json
    from src.pipeline import run_full_pipeline
    from src.etl.load.load_to_minio import _get_s3_client

    ti = context["ti"]
    config = _rebuild_config(ti)
    runoff_scope = _get_runoff_scope(ti)
    forecast_years = config.monte_carlo.forecast_years

    dag_conf = (context.get("dag_run").conf or {})
    bucket = dag_conf.get("manual_data_s3_bucket")
    key = dag_conf.get("manual_data_s3_key")
    if not bucket or not key:
        print("[skip] No manual_data_s3_bucket/key in dag_run.conf")
        return

    s3 = _get_s3_client(config)
    obj = s3.get_object(Bucket=bucket, Key=key)
    raw = json.loads(obj["Body"].read().decode("utf-8"))
    manual_data = {int(y): months for y, months in raw.items()}

    output_dir = os.path.join(
        PROJECT_ROOT, "data", "warehouse",
        f"airflow_manual_{forecast_years}y_{context['ds']}",
    )

    result = run_full_pipeline(
        output_dir=output_dir,
        manual_data=manual_data,
        config=config,
        runoff_scope=runoff_scope,
    )
    print(f"[pipeline] Result: {result}")


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

default_args = {
    "owner": "fahmi",
    "depends_on_past": False,
    "email_on_failure": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}

with DAG(
    dag_id="monte_carlo_etl_pipeline",
    description="Monte Carlo + SCS-CN Runoff ETL pipeline",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["etl", "monte_carlo", "scs-cn", "hydrology"],
) as dag:

    build_config = PythonOperator(
        task_id="build_config",
        python_callable=_build_config,
    )

    choose_branch = BranchPythonOperator(
        task_id="choose_branch",
        python_callable=_choose_branch,
    )

    run_from_file = PythonOperator(
        task_id="run_pipeline_from_excel",
        python_callable=_run_pipeline_from_file,
    )

    run_from_manual = PythonOperator(
        task_id="run_pipeline_from_manual_dict",
        python_callable=_run_pipeline_from_manual,
    )

    build_config >> choose_branch >> [run_from_file, run_from_manual]