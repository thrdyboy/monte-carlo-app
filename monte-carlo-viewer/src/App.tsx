import { useCallback, useEffect, useRef, useState } from "react";
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
    ForecastMethod,
    RunMetrics,
    LatestPlotsResponse,
    LatestTablesResponse,
    RunTriggeredResponse,
} from "./types/api";

type Tab = "run" | "results";

const METHOD_OPTIONS: { value: ForecastMethod; label: string }[] = [
    { value: "monte_carlo", label: "Monte Carlo" },
    { value: "markov", label: "Markov Chain" },
];

export default function App() {
    const [tab, setTab] = useState<Tab>("run")

    const [metrics, setMetrics] = useState<RunMetrics | null>(null)
    const [plots, setPlots] = useState<LatestPlotsResponse | null>(null)
    const [tables, setTables] = useState<LatestTablesResponse | null>(null)
    const [loading, setLoading] = useState(true)
    const [downloading, setDownloading] = useState(false)
    const [method, setMethod] = useState<ForecastMethod>("monte_carlo")

    // Refs so delayed refreshes (setTimeout) always use the *current* method,
    // and so a slow response for an old method can't overwrite a newer one.
    const methodRef = useRef<ForecastMethod>(method)
    const requestIdRef = useRef(0)

    // Fetch results for the current method. Only sets state *after* awaiting,
    // so it is safe to call from the mount effect.
    const load = useCallback(async () => {
        const m = methodRef.current;
        const requestId = ++requestIdRef.current;
        // allSettled: a 404 for one endpoint (e.g. no Markov runs yet)
        // must clear that panel instead of leaving the other method's data.
        const [mr, pr, tr] = await Promise.allSettled([
            getLatestMetrics(m),
            getLatestPlots(m),
            getLatestTables(50, m),
        ]);
        if (requestId !== requestIdRef.current) return; // stale response

        setMetrics(mr.status === "fulfilled" ? mr.value : null);
        setPlots(pr.status === "fulfilled" ? pr.value : null);
        setTables(tr.status === "fulfilled" ? tr.value : null);
        setLoading(false);

        const failed = [mr, pr, tr].find((r) => r.status === "rejected");
        if (failed && failed.status === "rejected") {
            pushToast("error", toApiError(failed.reason).message);
        }
    }, []);

    const refresh = useCallback(() => {
        setLoading(true);
        return load();
    }, [load]);

    useEffect(() => {
        load();
    }, [load]);

    const changeMethod = (m: ForecastMethod) => {
        if (m === methodRef.current) return;
        methodRef.current = m;
        setMethod(m);
        refresh();
    };

    const handleTriggered = async (res: RunTriggeredResponse) => {
        // A run was just queued — wait a moment, then refresh
        // (Airflow needs a few seconds to actually finish the DAG)
        const triggered = res.conf?.forecast_method;
        if (triggered === "monte_carlo" || triggered === "markov") {
            // show results for the method just run
            methodRef.current = triggered;
            setMethod(triggered);
        }
        setTab("results");
        setTimeout(refresh, 3000);
        setTimeout(refresh, 10000);
        setTimeout(refresh, 25000);
    };

    const handleDownloadExcel = async () => {
        setDownloading(true);
        try {
            await downloadLatestExcel(undefined, method);
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
                            <p className="text-xs text-black">
                                Rainfall + SCS-CN runoff forecasting
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <p className="font-sans text-sm text-blue-900 font-bold">
                            Aplikasi Sistem Informasi Prediksi Curah Hujan
                            Stokastik Berbasis Komputasi Monte Carlo dan Algoritma
                            Bootstraping Python
                        </p>
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

            {/* Team/Authors List Section */}
            <div className="bg-white border-b border-slate-200/80 shadow-sm">
                <div className="max-w-6xl mx-auto px-6 py-3 flex flex-col md:flex-row md:items-center gap-2 md:gap-6">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 shrink-0">
                        Tim Peneliti / Anggota:
                    </span>
                    <ol className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 w-full text-xs font-medium text-slate-600">
                        <li className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200/60">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                            M. Yusef Tiansyah
                        </li>
                        <li className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200/60">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                            F. Heru Widodo
                        </li>
                        <li className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200/60">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                            Sunu Tikno
                        </li>
                        <li className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200/60">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                            Samsul Bahri
                        </li>
                        <li className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200/60">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                            Tukiyat
                        </li>
                        <li className="flex items-center gap-1.5 bg-slate-50 px-2.5 py-1 rounded-md border border-slate-200/60">
                            <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                            Muktiyono
                        </li>
                    </ol>
                </div>
            </div>

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
                        {/* Forecast method toggle */}
                        <div className="flex items-center gap-3">
                            <span className="text-sm font-medium text-slate-600">
                                Forecast Method
                            </span>
                            <div className="flex gap-1 bg-white rounded-lg border border-slate-200 p-1 w-fit">
                                {METHOD_OPTIONS.map((opt) => (
                                    <button
                                        key={opt.value}
                                        onClick={() => changeMethod(opt.value)}
                                        className={`text-sm px-4 py-1.5 rounded-md font-medium transition-colors ${method === opt.value
                                            ? "bg-indigo-600 text-white"
                                            : "text-slate-600 hover:bg-slate-50"
                                            }`}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        </div>

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