from pydantic import BaseModel
from typing import List, Union
import os
import yaml

class DataConfig(BaseModel):
    raw_dir: str = "data/raw/"
    processed_path: str = "data/processed/simulations_result.csv"
    default_sheet_name: Union[str, int] = 0

class MonteCarloConfig(BaseModel):
    num_simulations: int = 1000
    forecast_years: int = 5
    random_seed: int = 42

class ColumnConfig(BaseModel):
    index: str = "Tahun"
    months: List[str] = [
        "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
    ]


class RunoffConfig(BaseModel):
    curve_number: float = 75.0
    river_basin_area: float = 58.87


class DatabaseConfig(BaseModel):
    host: str = "warehouse-postgres"
    port: int = 5432
    name: str
    user: str
    password: str
    schema: str = "public"


class MinioConfig(BaseModel):
    endpoint: str = "minio:9000"
    access_key: str
    secret_key: str
    bucket_parquet: str = "mc-parquet"
    bucket_plots: str = "mc-plots"
    secure: bool = False


class AppSettings(BaseModel):
    data: DataConfig
    monte_carlo: MonteCarloConfig
    columns: ColumnConfig
    runoff: RunoffConfig
    database: DatabaseConfig
    minio: MinioConfig


def load_config(path: str = "src/config/montecarlo.yaml") -> AppSettings:
    
    with open(path, "r") as f:
        config_data = yaml.safe_load(f)

    # ─── Ensure sub-dicts exist so we can inject into them ───
    config_data.setdefault("database", {})
    config_data.setdefault("minio", {})

    # ─── Override with env vars (populated by docker-compose from .env) ───
    if os.getenv("WAREHOUSE_DB_USER"):
        config_data["database"]["user"] = os.environ["WAREHOUSE_DB_USER"]
    if os.getenv("WAREHOUSE_DB_PASSWORD"):
        config_data["database"]["password"] = os.environ["WAREHOUSE_DB_PASSWORD"]
    if os.getenv("WAREHOUSE_DB_NAME"):
        config_data["database"]["name"] = os.environ["WAREHOUSE_DB_NAME"]

    if os.getenv("MINIO_ROOT_USER"):
        config_data["minio"]["access_key"] = os.environ["MINIO_ROOT_USER"]
    if os.getenv("MINIO_ROOT_PASSWORD"):
        config_data["minio"]["secret_key"] = os.environ["MINIO_ROOT_PASSWORD"]

    return AppSettings(**config_data)