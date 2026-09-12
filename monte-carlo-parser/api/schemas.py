# api/schemas.py
from typing import Dict, Optional
from pydantic import BaseModel, Field


class ManualRunRequest(BaseModel):
    """Body for POST /api/runs/from-manual."""
    data: Dict[int, Dict[str, float]] = Field(
        ...,
        description="Year -> month -> rainfall (mm). Example: {2020: {'Jan': 250, ...}}",
    )
    forecast_years: Optional[int] = Field(None, ge=1, le=200)
    num_simulations: Optional[int] = Field(None, ge=1, le=100000)
    random_seed: Optional[int] = None
    curve_number: Optional[float] = Field(None, ge=1, le=100)
    river_basin_area: Optional[float] = Field(None, gt=0)
    runoff_scope: str = Field("forecast", pattern="^(forecast|combined)$")


class RunResponse(BaseModel):
    status: str
    dag_run_id: str
    source: str
    input_path: Optional[str] = None
    conf: dict