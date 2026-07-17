import React, { useState } from 'react';
import { runSimulation } from '../services/api';
import type { RunSimulationRequest } from '../types/api';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];

interface ExcelRow {
    year: string;
    monthsData: Record<string, number>;
}

const parseExcelNumber = (val: string): number => {
    let str = val.trim();
    if (!str) return 0;
    
    if (str.includes(',') && str.includes('.')) {
        if (str.lastIndexOf(',') > str.lastIndexOf('.')) {
            str = str.replace(/\./g, '').replace(',', '.');
        } else {
            str = str.replace(/,/g, '');
        }
    } else if (str.includes(',')) {
        str = str.replace(',', '.');
    }
    
    const parsed = parseFloat(str);
    return isNaN(parsed) ? 0 : parsed;
};

const InputManual = () => {
    // Default awal set ke 2007 sesuai request kamu
    const [rows, setRows] = useState<ExcelRow[]>([
        {
            year: "2007",
            monthsData: MONTHS.reduce((acc, m) => ({ ...acc, [m]: 0 }), {})
        }
    ]);
    
    const [forecastYears, setForecastYears] = useState<number>(5);

    // ✨ 1. HANDLER PERUBAHAN TAHUN UTAMA (BASE YEAR) ✨
    // Ketika baris pertama diubah, semua baris di bawahnya otomatis menyesuaikan diri
    const handleBaseYearChange = (value: string) => {
        const parsedBase = parseInt(value);
        
        setRows(prevRows => 
            prevRows.map((row, idx) => ({
                ...row,
                year: value === "" ? "" : (isNaN(parsedBase) ? "" : (parsedBase + idx).toString())
            }))
        );
    };

    const handleCellChange = (rowIndex: number, month: string, value: string) => {
        const updatedRows = [...rows];
        updatedRows[rowIndex] = {
            ...updatedRows[rowIndex],
            monthsData: {
                ...updatedRows[rowIndex].monthsData,
                [month]: parseExcelNumber(value)
            }
        };
        setRows(updatedRows);
    };

    // ✨ 2. TAMBAH BARIS OTOMATIS BERURUTAN ✨
    const addRow = () => {
        setRows(prevRows => {
            const baseYearNum = parseInt(prevRows[0]?.year) || 2007;
            const nextYear = baseYearNum + prevRows.length;
            return [
                ...prevRows,
                {
                    year: nextYear.toString(),
                    monthsData: MONTHS.reduce((acc, m) => ({ ...acc, [m]: 0 }), {})
                }
            ];
        });
    };

    const removeRow = (index: number) => {
        if (rows.length === 1) return; 
        // Setelah dihapus, kita urutkan ulang tahunnya agar tidak ada gap melompat
        setRows(prevRows => {
            const filtered = prevRows.filter((_, i) => i !== index);
            const baseYearNum = parseInt(filtered[0]?.year) || 2007;
            return filtered.map((row, idx) => ({
                ...row,
                year: (baseYearNum + idx).toString()
            }));
        });
    };

    const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>, startRowIndex: number, startColIndex: number) => {
        e.preventDefault(); 
        const pasteData = e.clipboardData.getData('text');
        if (!pasteData) return;

        const pastedLines = pasteData.split(/\r?\n/).filter(line => line.trim() !== '')

        setRows(prevRows => {
            const newRows = prevRows.map(row => ({
                ...row,
                monthsData: { ...row.monthsData }
            }));

            
            let currentBaseYear = parseInt(newRows[0]?.year) || 2007

            if (startColIndex === 0 && pastedLines.length > 0) {
                const firstLineCells = pastedLines[0].split('\t')
                const parsedFirstYear = parseInt(firstLineCells[0].trim())
                if (!isNaN(parsedFirstYear)) {
                    currentBaseYear = parsedFirstYear - startRowIndex
                }
            }

            pastedLines.forEach((pastedRowStr, i) => {
                const targetRowIndex = startRowIndex + i

                // Jika baris kurang saat di-paste, buat baris baru kosong
                if (!newRows[targetRowIndex]) {
                    newRows.push({
                        year: "", // Nanti akan diisi oleh loop sinkronisasi di bawah
                        monthsData: MONTHS.reduce((acc, m) => ({ ...acc, [m]: 0 }), {})
                    });
                }

                const pastedCells = pastedRowStr.split('\t')
                pastedCells.forEach((cellValue, j) => {
                    const targetColIndex = startColIndex + j

                    // Abaikan nilai tahun mentah dari excel, karena kita akan buat dia sequential otomatis
                    if (targetColIndex >= 1 && targetColIndex <= 12) {
                        const monthName = MONTHS[targetColIndex - 1]
                        newRows[targetRowIndex].monthsData[monthName] = parseExcelNumber(cellValue)
                    }
                })
            })

            return newRows.map((row, idx) => ({
                ...row,
                year: (currentBaseYear + idx).toString()
            }))
        })
    }

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formattedData: Record<string, Record<string, number>> = {}
        
        rows.forEach(row => {
            if (row.year.trim() !== "") {
                formattedData[row.year] = { ...row.monthsData }
            }
        })

        const payload: RunSimulationRequest = {
            forecast_years: forecastYears,
            data: formattedData
        }

        try {
            const response = await runSimulation(payload)
            console.log("Simulasi sukses!", response)
            alert("Simulasi berhasil dijalankan!")
        } catch (error: any) {
            console.error("Gagal menjalankan simulasi:", error)
            alert(error.response?.data?.detail || "Terjadi kesalahan pada validator backend.")
        }
    }

    return (
        <form onSubmit={handleSubmit} className="p-6 bg-white border rounded-lg shadow-md max-w-full overflow-x-auto">
            <h2 className="text-xl font-bold mb-2 text-gray-800 flex items-center gap-2">
                📊 Input Manual Mode Spreadsheet (Auto-Sequential Year)
            </h2>
            <p className="text-sm text-gray-500 mb-6">
                🔒 <b>Sistem Proteksi:</b> Cukup edit tahun pada <b>baris pertama</b>, tahun-tahun berikutnya akan mengunci dan berurutan otomatis demi mencegah error grafik flat / heatmap ter-skip di backend.
            </p>
            
            <div className="mb-6 max-w-xs">
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                    Jangka Waktu Prediksi (Forecast Years):
                </label>
                <input 
                    type="number" 
                    value={forecastYears} 
                    onChange={(e) => setForecastYears(Number(e.target.value))}
                    className="border border-gray-300 p-2 w-full rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
            </div>

            <div className="overflow-x-auto border border-gray-200 rounded-lg mb-4">
                <table className="min-w-full border-collapse bg-white text-sm text-left text-gray-700">
                    <thead className="bg-gray-100 text-gray-700 uppercase font-semibold border-b border-gray-200">
                        <tr>
                            <th className="p-3 border-r border-gray-200 text-center bg-gray-200 w-24">Tahun</th>
                            {MONTHS.map(month => (
                                <th key={month} className="p-3 border-r border-gray-200 text-center min-w-20">
                                    {month}
                                </th>
                            ))}
                            <th className="p-3 text-center w-16 bg-gray-50">Aksi</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, rowIndex) => (
                            <tr key={rowIndex} className="border-b border-gray-200 hover:bg-gray-50">
                                {/* Kolom Tahun */}
                                <td className="p-2 border-r border-gray-200 bg-gray-50">
                                    <input
                                        type="number"
                                        value={row.year}
                                        // 🔒 JIKA INDEX > 0 MAKA READONLY & BERI STYLE GRAYED-OUT
                                        readOnly={rowIndex > 0} 
                                        onChange={(e) => handleBaseYearChange(e.target.value)}
                                        onPaste={(e) => handlePaste(e, rowIndex, 0)} 
                                        className={`w-full bg-transparent font-bold text-center p-1 focus:outline-none rounded ${
                                            rowIndex > 0 
                                                ? 'text-gray-400 bg-gray-100 cursor-not-allowed select-none' 
                                                : 'text-gray-800 focus:bg-white focus:ring-1 focus:ring-blue-500'
                                        }`}
                                        placeholder="YYYY"
                                    />
                                </td>
                                
                                {/* Kolom Bulan */}
                                {MONTHS.map((month, monthIndex) => (
                                    <td key={month} className="p-1 border-r border-gray-200">
                                        <input
                                            type="text" 
                                            value={row.monthsData[month]}
                                            onChange={(e) => handleCellChange(rowIndex, month, e.target.value)}
                                            onPaste={(e) => handlePaste(e, rowIndex, monthIndex + 1)}
                                            className="w-full text-right p-1 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 rounded"
                                        />
                                    </td>
                                ))}

                                <td className="p-2 text-center bg-gray-50">
                                    <button
                                        type="button"
                                        onClick={() => removeRow(rowIndex)}
                                        disabled={rows.length === 1}
                                        className="text-red-500 hover:text-red-700 disabled:opacity-30 font-semibold"
                                        title="Hapus baris"
                                    >
                                        ✕
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <div className="flex gap-4">
                <button
                    type="button"
                    onClick={addRow}
                    className="px-4 py-2 border border-dashed border-blue-500 text-blue-600 rounded hover:bg-blue-50 font-medium transition"
                >
                    ➕ Tambah Baris Tahun
                </button>
                
                <button
                    type="submit"
                    className="px-6 py-2 bg-green-600 text-white font-bold rounded hover:bg-green-700 shadow transition ml-auto"
                >
                    🚀 Jalankan Simulasi
                </button>
            </div>
        </form>
    )
}

export default InputManual