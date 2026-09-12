// src/types/api.ts
//
// Type definitions matching the FastAPI responses.
// Keep these in sync with:
//   - api/schemas.py
//   - api/runs.py
//   - api/latest.py
//   - src/config/settings.py (AppSettings)

// ─────────────────────────────────────────────────────────────────────
// Shared / common
// ─────────────────────────────────────────────────────────────────────

export type RunoffScope =
    | "forecast"
    | "forecast_mean"
    | "combined"
    | "combined_mean";

export type RunSource = "file" | "manual" | "both";

// ─────────────────────────────────────────────────────────────────────
// POST /api/runs/from-manual
// ─────────────────────────────────────────────────────────────────────

/** Year -> month -> rainfall (mm). Example: { "2020": { Jan: 250, ... } } */
export type ManualRainfallData = Record<string, Record<string, number>>;

export interface ManualRunBody {
    data: ManualRainfallData;
    forecast_years?: number;
    num_simulations?: number;
    random_seed?: number;
    curve_number?: number;
    river_basin_area?: number;
    runoff_scope?: RunoffScope;
}

// ─────────────────────────────────────────────────────────────────────
// POST /api/runs/from-excel  (multipart/form-data)
// ─────────────────────────────────────────────────────────────────────
// Handled via FormData in the service. Fields:
//   file:            File (required)
//   forecast_years?: number
//   num_simulations?: number
//   random_seed?: number
//   curve_number?: number
//   river_basin_area?: number
//   runoff_scope?: RunoffScope

export interface ExcelRunFormOptions {
    forecast_years?: number;
    num_simulations?: number;
    random_seed?: number;
    curve_number?: number;
    river_basin_area?: number;
    runoff_scope?: RunoffScope;
}

// ─────────────────────────────────────────────────────────────────────
// Run response (shared by both POST endpoints)
// ─────────────────────────────────────────────────────────────────────

export interface RunTriggeredResponse {
    status: "triggered";
    dag_run_id: string;
    source: RunSource;
    input_path?: string;
    conf: Record<string, unknown>;
}

// ─────────────────────────────────────────────────────────────────────
// GET /api/runs/metrics
// GET /api/runs/metrics/{run_id}
// ─────────────────────────────────────────────────────────────────────

export interface RunMetrics {
    id: number;
    run_id: string;
    dag_run_id: string | null;
    forecast_years: number;
    num_simulations: number;
    random_seed: number;
    curve_number: number;
    river_basin_area: number;
    runoff_scope: RunoffScope | null;
    mae: number;
    rmse: number;
    mape: number;
    created_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// GET /api/latest/plots
// ─────────────────────────────────────────────────────────────────────

export interface PlotItem {
    id: number;
    name: string;
    size_bytes: number;
    /** e.g. "/api/artifacts/15/view" — use directly in <img src> */
    view_url: string;
    /** e.g. "/api/artifacts/15/download" — use in <a href download> */
    download_url: string;
}

export interface LatestPlotsResponse {
    run_id: string;
    count: number;
    plots: PlotItem[];
}

// ─────────────────────────────────────────────────────────────────────
// GET /api/latest/tables
// ─────────────────────────────────────────────────────────────────────

export type TableRow = Record<string, string | number | boolean | null>;

export interface TablePreview {
    id: number;
    name: string;
    size_bytes: number;
    total_rows: number;
    total_columns: number;
    returned_rows: number;
    columns: string[];
    rows: TableRow[];
    download_url: string;
    /** Present only when the parquet could not be read */
    error?: string;
}

export interface LatestTablesResponse {
    run_id: string;
    count: number;
    tables: TablePreview[];
}

// ─────────────────────────────────────────────────────────────────────
// GET /api/artifacts/{id}/view | /download
// (usually you won't call these directly — the URLs come from PlotItem /
// TablePreview — but the type is useful if you build an artifact browser)
// ─────────────────────────────────────────────────────────────────────

export interface ArtifactMeta {
    id: number;
    run_id: string;
    artifact_type: "parquet" | "png" | "json" | string;
    bucket: string | null;
    object_key: string | null;
    s3_uri: string | null;
    local_path: string | null;
    file_size_bytes: number | null;
    created_at: string | null;
}

// ─────────────────────────────────────────────────────────────────────
// Error shape (produced by the axios response interceptor)
// ─────────────────────────────────────────────────────────────────────

export interface ApiError {
    status: number;
    message: string;
    raw?: unknown;
}