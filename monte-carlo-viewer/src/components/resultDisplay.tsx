// src/components/ResultsDisplay.tsx
import { useEffect, useState } from "react";
import { getData } from "../services/api";
import type { DataResponse } from "../types/api";
import { GetImageUrl } from "../utils/getImageUrl";


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

    const downloadImage = (url: string, filename: string) => {
    
        const link = document.createElement("a");
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
    };

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
                    src={`${GetImageUrl(data.plot_urls.timeseries)}?=t${refreshKey}`}
                    alt="Time Series"
                    className="w-full border rounded"
                />
                <button
                    onClick={() => downloadImage(data.plot_urls.timeseries, "timeseries_plot.png")}
                    className="mt-2 bg-blue-600 hover:bg-blue-700 text-white py-2 px-4 rounded"
                >
                    Download Timeseries
                </button>
            </div>

            {/* Heatmap */}
            <div className="bg-white p-4 rounded shadow">
                <h3 className="text-lg font-semibold">Heatmap</h3>
                <img
                    src={`${GetImageUrl(data.plot_urls.heatmap)}?=t${refreshKey}`}
                    alt="Heatmap"
                    className="w-full border rounded"
                />
                <button
                    onClick={() => downloadImage(data.plot_urls.heatmap, "heatmap_plot.png")}
                    className="mt-2 bg-green-600 hover:bg-green-700 text-white py-2 px-4 rounded"
                >
                    Download Heatmap
                </button>
            </div>

            {/* Refresh button */}
            <button
                onClick={fetchData}
                className="bg-gray-600 hover:bg-gray-700 text-white py-2 px-4 rounded"
            >
                Refresh Data
            </button>
        </div>
    )
}