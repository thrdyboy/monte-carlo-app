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
        "heatmap": string
    },
    "forecast_years_used": string,
    "random_seed_used": string
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

// POST /upload-excel
export interface RunFromExcelRequest {
    file: File
    forecast_years?: number | null
}