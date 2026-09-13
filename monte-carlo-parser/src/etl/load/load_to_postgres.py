# src/etl/load/load_to_postgres.py
import os
import sys
from typing import Optional, Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from src.config.settings import load_config


def get_warehouse_engine(config: Optional[Any] = None, echo: bool = False) -> Engine:
    """Create a SQLAlchemy engine for the warehouse Postgres."""
    if config is None:
        config = load_config()

    db = config.database
    url = (
        f"postgresql+psycopg2://{db.user}:{db.password}"
        f"@{db.host}:{db.port}/{db.name}"
    )
    return create_engine(url, echo=echo)


def load_dataframe_to_postgres(
    df: pd.DataFrame,
    table_name: str,
    config: Optional[Any] = None,
    if_exists: str = "replace",
    index: bool = False,
) -> None:
    """Load a DataFrame into a warehouse table."""
    if config is None:
        config = load_config()

    engine = get_warehouse_engine(config)

    df_to_save = df.copy()
    if index and df_to_save.index.name:
        df_to_save = df_to_save.reset_index()

    df_to_save.to_sql(
        table_name,
        engine,
        db_schema=config.database.db_schema,
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=1000,
    )
    print(f"[postgres] Loaded {len(df_to_save)} rows → {table_name} ({if_exists})")
    engine.dispose()


def ensure_artifacts_table(config: Optional[Any] = None) -> None:
    """Create the artifacts tracking table if it doesn't exist."""
    if config is None:
        config = load_config()

    engine = get_warehouse_engine(config)
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {config.database.db_schema}.artifacts (
        id SERIAL PRIMARY KEY,
        run_id VARCHAR(128) NOT NULL,
        artifact_type VARCHAR(20) NOT NULL,
        bucket VARCHAR(64),
        object_key TEXT,
        s3_uri TEXT,
        local_path TEXT,
        file_size_bytes BIGINT,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
    engine.dispose()
    print("[postgres] artifacts table ready")


def register_artifacts(
    artifacts: list,
    run_id: str,
    config: Optional[Any] = None,
) -> None:
    """Insert artifact metadata rows into the artifacts table."""
    if config is None:
        config = load_config()

    if not artifacts:
        print("[postgres] No artifacts to register")
        return

    engine = get_warehouse_engine(config)
    df = pd.DataFrame([
        {
            "run_id": run_id,
            "artifact_type": a.get("artifact_type", "unknown"),
            "bucket": a.get("bucket"),
            "object_key": a.get("key"),
            "s3_uri": a.get("s3_uri"),
            "local_path": a.get("local_path"),
            "file_size_bytes": a.get("size_bytes"),
        }
        for a in artifacts
    ])
    df.to_sql(
        "artifacts",
        engine,
        db_schema=config.database.db_schema,
        if_exists="append",
        index=False,
    )
    print(f"[postgres] Registered {len(df)} artifacts")
    engine.dispose()

def ensure_run_metrics_table(config: Optional[Any] = None) -> None:
    """Create the run_metrics tracking table if it doesn't exist."""
    if config is None:
        config = load_config()

    engine = get_warehouse_engine(config)
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {config.database.db_schema}.run_metrics (
        id SERIAL PRIMARY KEY,
        run_id VARCHAR(128) NOT NULL,
        dag_run_id VARCHAR(128),
        forecast_years INT,
        num_simulations INT,
        random_seed INT,
        curve_number DOUBLE PRECISION,
        river_basin_area DOUBLE PRECISION,
        runoff_scope VARCHAR(32),
        mae DOUBLE PRECISION,
        rmse DOUBLE PRECISION,
        mape DOUBLE PRECISION,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
    engine.dispose()
    print("[postgres] run_metrics table ready")


def save_run_metrics(
    run_id: str,
    metrics: dict,
    config: Optional[Any] = None,
    dag_run_id: Optional[str] = None,
    runoff_scope: Optional[str] = None
) -> None:
    """Persist one row of metrics + config metadata."""
    if config is None:
        config = load_config()

    engine = get_warehouse_engine(config)
    df = pd.DataFrame([{
        "run_id": run_id,
        "dag_run_id": dag_run_id,
        "forecast_years": int(config.monte_carlo.forecast_years),
        "num_simulations": int(config.monte_carlo.num_simulations),
        "random_seed": int(config.monte_carlo.random_seed),
        "curve_number": float(config.runoff.curve_number),
        "river_basin_area": float(config.runoff.river_basin_area),
        "runoff_scope": runoff_scope,
        "mae": float(metrics.get("MAE", 0)),
        "rmse": float(metrics.get("RMSE", 0)),
        "mape": float(metrics.get("MAPE", 0)),
    }])
    df.to_sql(
        "run_metrics", engine,
        db_schema=config.database.db_schema,
        if_exists="append", index=False,
    )
    print(f"[postgres] Saved metrics for {run_id}: "
          f"MAE={metrics.get('MAE'):.2f}, RMSE={metrics.get('RMSE'):.2f}, MAPE={metrics.get('MAPE'):.2f}%")
    engine.dispose()