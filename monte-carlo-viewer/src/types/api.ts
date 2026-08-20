// Server Status
type ServerResponse = {
    status: 'success' | 'failed'
    message?: string
}

// GET //get-data
export interface DataResponse {
    status: ServerResponse['status'],
    metrics: {
        MAE: number
        RMSE: number
        MAPE: number
    },
    plot_urls: {
        "timeseries": string,
        "heatmap": string,
        "das_chart": string
    },
    "forecast_years_used": string,
    "random_seed_used": string,
    das_parameters?: {
        luas_das_km2: number,
        cn_value: number,
        potensi_retensi_maks_s_mm: number,
        abstraksi_awal_ia_mm: number,
        iterasi_monte_carlo: number
    }
}

// POST /run-simulation body
export interface RunSimulationRequest {
    data: Record<string, Record<string, number>>
    forecast_years?: number | null
}

export interface RunSimulationResponse {
    status: ServerResponse['status']
    message?: ServerResponse['message']
}

// POST /post-das
export interface PostDASParams {
    cn_value: number;
    area_km2: number;
    n_trials: number;
}

// POST /upload-excel
export interface RunFromExcelRequest {
    file: File
    forecast_years?: number | null
}