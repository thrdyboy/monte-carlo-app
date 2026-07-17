import { useState } from "react";
import { runFromExcel } from "../services/api";
import type { RunFromExcelRequest } from "../types/api";

export const InputExcel = () => {
    const [file, setFile] = useState<File | null>(null)
    const [forecastYears, setForecastYears] = useState<string>("")
    const [loading, setLoading] = useState(false)
    const [message, setMessage] = useState<string>("")

    const onSubmit = async (e: React.SubmitEvent) => {
        e.preventDefault();
        if (!file) {
            setMessage("Pilih file Excel dulu.")
            return
        }

        const payload: RunFromExcelRequest = {
            file,
            forecast_years: forecastYears === "" ? null : Number(forecastYears),
        }

        setLoading(true)
        setMessage("")

        try {
            const res = await runFromExcel(payload)
            if (res.status === "success") {
                setMessage(res.message ?? "Simulasi dari Excel berhasil dijalankan.")
            } else {
                setMessage(res.message ?? "Simulasi dari Excel gagal.")
            }
        } catch (err) {
            console.error(err)
            setMessage("Terjadi error saat menjalankan simulasi dari Excel.")
        } finally {
            setLoading(false)
        }
    }

    return (
        <div className="max-w-lg mx-auto mt-10">
            <div className="bg-white border border-gray-100 rounded-2xl shadow-xl shadow-slate-200/50 p-8">
                <div className="mb-8">
                    <h2 className="text-2xl font-bold text-gray-900">Upload Data</h2>
                    <p className="text-sm text-gray-500 mt-1">
                        Pilih file Excel untuk memulai proses simulasi.
                    </p>
                </div>

                <form onSubmit={onSubmit} className="space-y-6">
                    <div className="space-y-2">
                        <label className="block text-sm font-semibold text-gray-700">
                            File Excel
                        </label>
                        <div className="relative">
                            <input
                                type="file"
                                accept=".xlsx,.xls"
                                onChange={(e) => {
                                    const picked = e.target.files?.[0] ?? null;
                                    setFile(picked);
                                }}
                                className="block w-full text-sm text-gray-500 file:mr-4 file:py-2.5 file:px-4 file:rounded-lg file:border-0 file:font-semibold file:bg-blue-50 hover:file:bg-blue-100 cursor-pointer border-gray-200 transition-all"
                            />
                        </div>
                        {file && (
                            <p className="text-xs font-medium text-blue-600 bg-blue-50 p-2 rounded-md">
                                Terpilih: {file.name}
                            </p>
                        )}
                    </div>

                    <div className="space-y-2">
                        <label className="block text-sm font-semibold text-gray-700">
                            Forecast Years <span className="text-gray-400 font-normal">(opsional)</span>
                        </label>
                        <input
                            type="number"
                            value={forecastYears}
                            onChange={(e) => setForecastYears(e.target.value)}
                            placeholder="Contoh: 5"
                            className="w-full px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-600 outline-none transition-all placeholder:text-gray-400"
                        />
                    </div>

                    {/* Submit Button */}
                    <button
                        type="submit"
                        disabled={!file || loading}
                        className="w-full bg-blue-600 hover:bg-blue-700 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-xl shadow-lg shadow-blue-600/20 transition-all active:scale-[0.98]"
                    >
                        {loading ? "Memproses..." : "Run Simulation"}
                    </button>

                    {/* Feedback Message */}
                    {message && (
                        <div className={`p-4 rounded-xl text-sm font-medium ${message.toLowerCase().includes("berhasil")
                                ? "bg-green-50 text-green-700 border border-green-100"
                                : "bg-red-50 text-red-700 border border-red-100"
                            }`}>
                            {message}
                        </div>
                    )}
                </form>
            </div>
        </div>
    )
}