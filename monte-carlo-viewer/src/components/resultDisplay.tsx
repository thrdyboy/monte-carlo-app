// src/components/ResultsDisplay.tsx
import { useEffect, useState } from "react";
import { getData } from "../services/api";
import type { DataResponse } from "../types/api";
import { GetImageUrl } from "../utils/getImageUrl";
import { downloadSimulationExcel } from "../utils/excelUtils";

export const ResultsDisplay = () => {
    const [data, setData] = useState<DataResponse | null>(null)
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null)

    const [refreshKey, setRefreshKey] = useState<number>(Date.now())

    const fetchData = async () => {
        setLoading(true)
        setError(null)
        try {
            const result = await getData()
            setData(result);
            setRefreshKey(Date.now())
        } catch (err) {
            setError("Failed to fetch simulation results.")
            console.error(err)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchData()
    }, [])

    if (loading) return <div>Loading results...</div>
    if (error) return <div className="text-red-500">{error}</div>
    if (!data) return <div>No data available. Run a simulation first.</div>

    return (
        <div className="max-w-6xl mx-auto p-6 space-y-8">
            <h2 className="text-2xl font-bold">Simulation Results</h2>

            {/* Metrics */}
            <div className="bg-white p-4 rounded shadow">
                <h3 className="text-lg font-semibold">Metrics</h3>
                <ul className="mt-2 space-y-1">
                    <li><strong>MAE:</strong> {data.metrics.MAE?.toFixed(2)}</li>
                    <li><strong>RMSE:</strong> {data.metrics.RMSE?.toFixed(2)}</li>
                    <li><strong>MAPE:</strong> {data.metrics.MAPE?.toFixed(2)}%</li>
                    <li><strong>Forecast years:</strong> {data.forecast_years_used}</li>
                </ul>
            </div>

            {/* Time series plot */}
            <div className="bg-white p-4 rounded shadow">
                <h3 className="text-lg font-semibold">Time Series Plot</h3>
                <img
                    src={`${GetImageUrl(data.plot_urls.timeseries)}?t=${refreshKey}`}
                    alt="Time Series"
                    className="w-full border rounded"
                />
            </div>

            {/* Heatmap */}
            <div className="bg-white p-4 rounded shadow">
                <h3 className="text-lg font-semibold">Heatmap</h3>
                <img
                    src={`${GetImageUrl(data.plot_urls.heatmap)}?t=${refreshKey}`}
                    alt="Heatmap"
                    className="w-full border rounded"
                />
            </div>

            <div className="flex flex-wrap items-center gap-3">
                {/* Refresh Button */}
                <button
                    onClick={fetchData}
                    className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-xl shadow-sm hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition-all duration-200 active:scale-95"
                >
                    <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Refresh Data
                </button>

                {/* Export to Excel Button */}
                <button
                    onClick={() => downloadSimulationExcel()}
                    className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-emerald-600 rounded-xl shadow-sm hover:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-emerald-500 transition-all duration-200 active:scale-95"
                >
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Export to Excel
                </button>
            </div>
        </div>
    )
}