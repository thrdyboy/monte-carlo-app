# Input after Monte Carlo Appear for DAS Calculation
from pydantic import BaseModel
from typing import Optional, Dict

class DASSimulationRequest(BaseModel):
    cn_value: Optional[float] = 75.0
    area_km2: Optional[float] = 100.0
    n_trials: Optional[int] = 500

class SimulationRequest(BaseModel):
    data: Dict[int, Dict[str, float]]
    forecast_years: Optional[int] = None
    das_params: Optional[DASSimulationRequest] = None