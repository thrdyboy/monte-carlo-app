from fastapi import HTTPException
from src.config.settings import load_config

def validate_simulation_input(data: dict):
    config = load_config()
    expected_months = set(config.columns.months)
    
    for year, month_vals in data.items():
        # Validasi apakah bulan yang diinput sesuai dengan config
        if set(month_vals.keys()) != expected_months:
            raise HTTPException(
                status_code=400,
                detail=f"Tahun {year} harus memiliki bulan yang lengkap: {sorted(expected_months)}"
            )
        
        # Validasi tipe data (semua harus angka)
        for month, value in month_vals.items():
            if not isinstance(value, (int, float)):
                raise HTTPException(
                    status_code=400,
                    detail=f"Nilai untuk {month} di tahun {year} harus berupa angka."
                )
    return True