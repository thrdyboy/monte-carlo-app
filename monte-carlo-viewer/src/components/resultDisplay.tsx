// src/components/ResultsDisplay.tsx
import { useEffect, useState } from "react";
import { DasSimulationRun, getData } from "../services/api";
import type { DataResponse, PostDASParams } from "../types/api";
import { GetImageUrl } from "../utils/getImageUrl";
import { downloadDasSimulationExcel, downloadSimulationExcel } from "../utils/excelUtils";

export const ResultsDisplay = () => {
    const [data, setData] = useState<DataResponse | null>(null)
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null)

    // For Das Form
    const [dasForm, setDasForm] = useState<PostDASParams>({
        cn_value: 75,
        area_km2: 100,
        n_trials: 500
    })

    const [isUpdatingDas, setIsUpdatingDas] = useState<boolean>(false)
    useEffect(() => {
        if (data?.das_parameters) {
            setDasForm({
                cn_value: data.das_parameters.cn_value || 75,
                area_km2: data.das_parameters.luas_das_km2 || 100,
                n_trials: data.das_parameters.iterasi_monte_carlo || 500
            })
        }
    }, [data])

    const handleUpdateDas = async () => {
        setIsUpdatingDas(true);
        try {
            await DasSimulationRun({
                cn_value: Number(dasForm.cn_value),
                area_km2: Number(dasForm.area_km2),
                n_trials: Number(dasForm.n_trials)
            });


            await fetchData()
            alert("Parameter DAS berhasil diperbarui!")
        } catch (err) {
            console.error("Gagal mengupdate DAS", err)
            alert("Gagal menghitung ulang parameter DAS.")
        } finally {
            setIsUpdatingDas(false)
        }
    }

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

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-200">
                    <h3 className="text-lg font-semibold text-gray-800 border-b pb-2 mb-3">Metrics</h3>
                    <ul className="space-y-2 text-gray-700">
                        <li className="flex justify-between">
                            <span><strong>MAE:</strong></span>
                            <span>{data.metrics.MAE?.toFixed(2)}</span>
                        </li>
                        <li className="flex justify-between">
                            <span><strong>RMSE:</strong></span>
                            <span>{data.metrics.RMSE?.toFixed(2)}</span>
                        </li>
                        <li className="flex justify-between">
                            <span><strong>MAPE:</strong></span>
                            <span>{data.metrics.MAPE?.toFixed(2)}%</span>
                        </li>
                        <li className="flex justify-between">
                            <span><strong>Forecast years:</strong></span>
                            <span>{data.forecast_years_used} Tahun</span>
                        </li>
                    </ul>
                </div>

                {data.das_parameters && (
                    <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-200">
                        {/* Parameters DAS */}
                        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                            <h3 className="text-lg font-bold text-gray-800 mb-4 flex items-center gap-2">
                                <svg className="w-5 h-5 text-blue-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
                                </svg>
                                Parameter & Simulasi DAS
                            </h3>

                            {/* Form Input */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                <div>
                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Luas DAS (km²)</label>
                                    <input
                                        type="number"
                                        value={dasForm.area_km2}
                                        onChange={(e) => setDasForm({ ...dasForm, area_km2: Number(e.target.value) })}
                                        className="mt-1 block w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Curve Number (CN)</label>
                                    <input
                                        type="number"
                                        value={dasForm.cn_value}
                                        onChange={(e) => setDasForm({ ...dasForm, cn_value: Number(e.target.value) })}
                                        className="mt-1 block w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Iterasi Simulasi</label>
                                    <input
                                        type="number"
                                        value={dasForm.n_trials}
                                        onChange={(e) => setDasForm({ ...dasForm, n_trials: Number(e.target.value) })}
                                        className="mt-1 block w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-gray-800 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:bg-white transition-colors"
                                    />
                                </div>
                            </div>

                            {/* Hasil Perhitungan Konstan (Read Only) */}
                            <div className="grid grid-cols-2 gap-4 bg-blue-50/50 p-4 rounded-xl border border-blue-100 mb-4">
                                <div>
                                    <p className="text-sm text-gray-500">Potensi Retensi (S)</p>
                                    <p className="font-semibold text-gray-800">{data.das_parameters?.potensi_retensi_maks_s_mm ?? 0} mm</p>
                                </div>
                                <div>
                                    <p className="text-sm text-gray-500">Abstraksi Awal (Ia)</p>
                                    <p className="font-semibold text-gray-800">{data.das_parameters?.abstraksi_awal_ia_mm ?? 0} mm</p>
                                </div>
                            </div>

                            {/* Tombol Eksekusi */}
                            <button
                                onClick={handleUpdateDas}
                                disabled={isUpdatingDas}
                                className={`w-full inline-flex justify-center items-center gap-2 px-4 py-2.5 text-sm font-medium text-white rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 transition-all duration-200 ${isUpdatingDas ? 'bg-blue-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 focus:ring-blue-500 active:scale-95'
                                    }`}
                            >
                                {isUpdatingDas ? (
                                    <>
                                        <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        Menghitung Ulang DAS...
                                    </>
                                ) : (
                                    'Update & Hitung Ulang DAS'
                                )}
                            </button>
                        </div>
                    </div>
                )}
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

            {/* Runoff DAS */}
            {data.plot_urls.das_chart && (
                <div className="bg-white p-4 rounded shadow">
                    <h3 className="text-lg font-semibold">Grafik Konversi Runoff DAS</h3>
                    <img
                        src={`${GetImageUrl(data.plot_urls.das_chart)}?t=${refreshKey}`}
                        alt="Grafik Konversi DAS"
                        className="w-full border rounded mt-2"
                    />
                </div>
            )}

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
                    Export Monte Carlo to Excel
                </button>

                {/* Export DAS to Excel Button */}
                <button
                    onClick={() => downloadDasSimulationExcel()}
                    className="inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-white bg-blue-600 rounded-xl shadow-sm hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-600 transition-all duration-200 active:scale-95"
                >
                    <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Export Monte Carlo DAS to Excel
                </button>
            </div>
        </div>
    )
}