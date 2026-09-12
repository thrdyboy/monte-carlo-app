import { useCallback, useEffect, useState } from "react";
import NewRunPanel from "./components/NewRunPanel";
import MetricsPanel from "./components/MetricsPanel";
import PlotsGallery from "./components/PlotsGallery";
import TablesPreview from "./components/TablesPreview";
import { ToastHost, pushToast } from "./components/Toast";
import {
    getLatestMetrics,
    getLatestPlots,
    getLatestTables,
    downloadLatestExcel,
    toApiError,
} from "./services/api";
import type {
    RunMetrics,
    LatestPlotsResponse,
    LatestTablesResponse,
} from "./types/api";

type Tab = "run" | "results";

export default function App() {
    const [tab, setTab] = useState<Tab>("run")

    const [metrics, setMetrics] = useState<RunMetrics | null>(null)
    const [plots, setPlots] = useState<LatestPlotsResponse | null>(null)
    const [tables, setTables] = useState<LatestTablesResponse | null>(null)
    const [loading, setLoading] = useState(false)
    const [downloading, setDownloading] = useState(false)

    const refresh = useCallback(async () => {
        setLoading(true);
        try {
            const [m, p, t] = await Promise.all([
                getLatestMetrics(),
                getLatestPlots(),
                getLatestTables(50),
            ]);
            setMetrics(m);
            setPlots(p);
            setTables(t);
        } catch (err) {
            pushToast("error", toApiError(err).message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
    }, [refresh]);

    const handleTriggered = async () => {
        // A run was just queued — wait a moment, then refresh
        // (Airflow needs a few seconds to actually finish the DAG)
        setTab("results");
        setTimeout(refresh, 3000);
        setTimeout(refresh, 10000);
        setTimeout(refresh, 25000);
    };

    const handleDownloadExcel = async () => {
        setDownloading(true);
        try {
            await downloadLatestExcel();
            pushToast("success", "Excel report downloaded.");
        } catch (err) {
            pushToast("error", toApiError(err).message);
        } finally {
            setDownloading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-100 text-slate-800">
            <ToastHost />

            {/* Header */}
            <header className="bg-white border-b border-slate-200">
                <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-indigo-600 text-white flex items-center justify-center text-lg font-bold">
                            MC
                        </div>
                        <div>
                            <h1 className="text-lg font-semibold leading-tight">
                                Monte Carlo ETL
                            </h1>
                            <p className="text-xs text-slate-500">
                                Rainfall + SCS-CN runoff forecasting
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={refresh}
                            disabled={loading}
                            className="text-sm px-3 py-1.5 rounded-md border border-slate-300 hover:bg-slate-50 disabled:opacity-50"
                        >
                            {loading ? "Refreshing…" : "↻ Refresh"}
                        </button>
                        <button
                            onClick={handleDownloadExcel}
                            disabled={downloading}
                            className="text-sm px-3 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white disabled:opacity-50"
                        >
                            {downloading ? "Preparing…" : "⬇ Download Excel"}
                        </button>
                    </div>
                </div>
            </header>

            {/* Tabs */}
            <div className="max-w-6xl mx-auto px-6 mt-6">
                <div className="flex gap-1 bg-white rounded-lg border border-slate-200 p-1 w-fit">
                    {(["run", "results"] as Tab[]).map((t) => (
                        <button
                            key={t}
                            onClick={() => setTab(t)}
                            className={`text-sm px-4 py-1.5 rounded-md font-medium transition-colors ${tab === t
                                ? "bg-indigo-600 text-white"
                                : "text-slate-600 hover:bg-slate-50"
                                }`}
                        >
                            {t === "run" ? "▶ New Run" : "📊 Latest Results"}
                        </button>
                    ))}
                </div>
            </div>

            {/* Content */}
            <main className="max-w-6xl mx-auto px-6 py-6 space-y-6">
                {tab === "run" && <NewRunPanel onTriggered={handleTriggered} />}

                {tab === "results" && (
                    <>
                        <MetricsPanel metrics={metrics} />
                        <PlotsGallery data={plots} />
                        <TablesPreview data={tables} />
                    </>
                )}
            </main>

            <footer className="max-w-6xl mx-auto px-6 py-8 text-center text-xs text-slate-400">
                FastAPI · Airflow · PostgreSQL · MinIO
            </footer>
        </div>
    )
}