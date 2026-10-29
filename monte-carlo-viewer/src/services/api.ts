// src/services/api.ts
import axiosInstance from "./axios_service";
import type {
    RunTriggeredResponse,
    ManualRunBody,
    ExcelRunFormOptions,
    ForecastMethod,
    RunMetrics,
    LatestPlotsResponse,
    LatestTablesResponse,
    ApiError,
} from "../types/api";

// ─────────────────────────────────────────────────────────────────────
// 1. POST /api/runs/from-manual
// ─────────────────────────────────────────────────────────────────────

export async function triggerRunFromManual(
    body: ManualRunBody,
): Promise<RunTriggeredResponse> {
    const { data } = await axiosInstance.post<RunTriggeredResponse>(
        "/runs/from-manual",
        body,
    );
    return data;
}

// ─────────────────────────────────────────────────────────────────────
// 2. POST /api/runs/from-excel
// ─────────────────────────────────────────────────────────────────────

export async function triggerRunFromExcel(
    file: File,
    options: ExcelRunFormOptions = {},
): Promise<RunTriggeredResponse> {
    const form = new FormData();
    form.append("file", file);

    // Only append fields that are actually set.
    // Do NOT set Content-Type — axios adds the multipart boundary automatically.
    if (options.forecast_years != null)
        form.append("forecast_years", String(options.forecast_years));
    if (options.num_simulations != null)
        form.append("num_simulations", String(options.num_simulations));
    if (options.random_seed != null)
        form.append("random_seed", String(options.random_seed));
    if (options.curve_number != null)
        form.append("curve_number", String(options.curve_number));
    if (options.river_basin_area != null)
        form.append("river_basin_area", String(options.river_basin_area));
    if (options.runoff_scope != null)
        form.append("runoff_scope", options.runoff_scope);
    if (options.forecast_method != null)
        form.append("forecast_method", options.forecast_method);

    const { data } = await axiosInstance.post<RunTriggeredResponse>(
        "/runs/from-excel",
        form,
    );
    return data;
}

// ─────────────────────────────────────────────────────────────────────
// 3. GET /api/runs/metrics
//    Returns an array, newest first. The latest entry is index [0].
// ─────────────────────────────────────────────────────────────────────

export async function listRunMetrics(limit = 50): Promise<RunMetrics[]> {
    const { data } = await axiosInstance.get<RunMetrics[]>(
        `/runs/metrics?limit=${limit}`,
    );
    return data;
}

/** Convenience: fetch the newest metrics row (optionally for one forecast
 *  method), or null if none exist. */
export async function getLatestMetrics(
    method?: ForecastMethod,
): Promise<RunMetrics | null> {
    if (!method) {
        const rows = await listRunMetrics(1);
        return rows.length > 0 ? rows[0] : null;
    }
    const rows = await listRunMetrics(500);
    return rows.find((r) => r.forecast_method === method) ?? null;
}

// ─────────────────────────────────────────────────────────────────────
// 4. GET /api/latest/plots
// ─────────────────────────────────────────────────────────────────────

export async function getLatestPlots(
    method?: ForecastMethod,
    runId?: string,
): Promise<LatestPlotsResponse> {
    const { data } = await axiosInstance.get<LatestPlotsResponse>(
        "/latest/plots",
        {
            params: {
                ...(method ? { method } : {}),
                ...(runId ? { run_id: runId } : {}),
            },
        },
    );
    return data;
}

// ─────────────────────────────────────────────────────────────────────
// 5. GET /api/latest/tables
// ─────────────────────────────────────────────────────────────────────

export async function getLatestTables(
    limit = 100,
    method?: ForecastMethod,
    runId?: string,
): Promise<LatestTablesResponse> {
    const { data } = await axiosInstance.get<LatestTablesResponse>(
        "/latest/tables",
        {
            params: {
                limit,
                ...(method ? { method } : {}),
                ...(runId ? { run_id: runId } : {}),
            },
        },
    );
    return data;
}

// ─────────────────────────────────────────────────────────────────────
// 6. GET /api/latest/excel  (browser file download)
//    Not JSON — the response is a binary .xlsx.
// ─────────────────────────────────────────────────────────────────────

export async function downloadLatestExcel(
    runId?: string,
    method?: ForecastMethod,
): Promise<void> {
    const res = await axiosInstance.get("/latest/excel", {
        responseType: "blob",
        params: {
            ...(runId ? { run_id: runId } : {}),
            ...(method ? { method } : {}),
        },
    });

    // Extract filename from Content-Disposition if present, else fallback.
    const cd = res.headers["content-disposition"] as string | undefined;
    const match = cd?.match(/filename="?([^"]+)"?/);
    const filename = match?.[1] ?? `report_${Date.now()}.xlsx`;

    const url = URL.createObjectURL(res.data);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
}

// ─────────────────────────────────────────────────────────────────────
// Helper — normalize errors thrown by axios into ApiError
// ─────────────────────────────────────────────────────────────────────

export function toApiError(err: unknown): ApiError {
    if (
        err &&
        typeof err === "object" &&
        "status" in err &&
        "message" in err
    ) {
        return err as ApiError;
    }
    return { status: 0, message: String(err), raw: err };
}