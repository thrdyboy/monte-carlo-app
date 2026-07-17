from pydantic import BaseModel
from typing import List, Union
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
    months: List[str] = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

class AppSettings(BaseModel):
    data: DataConfig
    monte_carlo: MonteCarloConfig
    columns: ColumnConfig

def load_config(path: str = "src/config/montecarlo.yaml") -> AppSettings:
    with open(path, "r") as f:
        config_data = yaml.safe_load(f)
    return AppSettings(**config_data)