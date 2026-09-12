# api/airflow_client.py
import os
from typing import Any, Dict

import requests
from fastapi import HTTPException

AIRFLOW_API_URL = os.environ.get("AIRFLOW_API_URL", "http://airflow-webserver:8080")
DAG_ID = "monte_carlo_etl_pipeline"


def _get_credentials() -> tuple:
    """Read Airflow credentials from env. Fail loudly if missing."""
    user = os.environ.get("AIRFLOW_API_USER")
    password = os.environ.get("AIRFLOW_API_PASSWORD")
    if not user or not password:
        raise RuntimeError(
            "Missing AIRFLOW_API_USER and/or AIRFLOW_API_PASSWORD environment variables. "
            "These must be set in docker-compose.yaml under the 'api' service, sourced from .env. "
            "Run: docker compose up -d --force-recreate api"
        )
    return user, password


def trigger_dag(conf: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger the Monte Carlo DAG via Airflow's REST API.

    Returns Airflow's response JSON, which includes `dag_run_id`.
    """
    user, password = _get_credentials()

    url = f"{AIRFLOW_API_URL}/api/v1/dags/{DAG_ID}/dagRuns"
    payload = {"conf": conf}

    try:
        resp = requests.post(
            url,
            json=payload,
            auth=(user, password),
            timeout=15,
        )
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach Airflow: {e}")

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail=f"Airflow rejected the trigger ({resp.status_code}): {resp.text}",
        )

    return resp.json()