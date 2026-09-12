import { useMemo, useState } from "react";
import {
    triggerRunFromManual,
    triggerRunFromExcel,
    toApiError,
} from "../services/api";
import type {
    ManualRainfallData,
    RunoffScope,
    RunTriggeredResponse,
} from "../types/api";
import { pushToast } from "./Toast";

const MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
    "Jul", "Agu", "Sep", "Okt", "Nov", "Des",
];

const RUNOFF_SCOPES: RunoffScope[] = [
    "forecast",
    "forecast_mean",
    "combined",
    "combined_mean",
];

interface Row {
    year: string;
    months: Record<string, string>;
}

function emptyRow(year: number): Row {
    return {
        year: String(year),
        months: Object.fromEntries(MONTHS.map((m) => [m, ""])),
    };
}

// ─────────────────────────────────────────────────────────────────────
// Paste helpers
// ─────────────────────────────────────────────────────────────────────

/** Split pasted text into a 2D grid of strings. Handles tabs, multi-space,
 *  and normalizes line endings. Empty lines are dropped. */
function parseTabular(text: string): string[][] {
    return text
        .replace(/\r/g, "")
        .split("\n")
        .filter((line) => line.trim().length > 0)
        .map((line) => line.split(/\t| {2,}/));
}

function normalizeNumber(s: string): string {
    const v = s.trim();
    if (!v) return "";

    const lastComma = v.lastIndexOf(",");
    const lastDot = v.lastIndexOf(".");

    if (lastComma > lastDot) {
        // Comma is decimal (Indonesian / European style)
        return v.replace(/\./g, "").replace(",", ".");
    }
    if (lastDot > lastComma) {
        // Dot is decimal; comma is thousands separator
        return v.replace(/,/g, "");
    }
    if (lastComma >= 0) {
        // Only commas present
        return v.replace(",", ".");
    }
    return v;
}

function looksLikeYear(s: string): boolean {
    const n = parseInt(s.trim(), 10);
    return Number.isInteger(n) && n >= 1900 && n <= 2200;
}


interface Props {
    onTriggered: (res: RunTriggeredResponse) => void;
}

export default function NewRunPanel({ onTriggered }: Props) {
    const [mode, setMode] = useState<"manual" | "excel">("manual");

    const [forecastYears, setForecastYears] = useState(10);
    const [numSimulations, setNumSimulations] = useState(1000);
    const [curveNumber, setCurveNumber] = useState(75);
    const [riverBasinArea, setRiverBasinArea] = useState(58.87);
    const [runoffScope, setRunoffScope] = useState<RunoffScope>("forecast");

    const [rows, setRows] = useState<Row[]>([emptyRow(2020), emptyRow(2021), emptyRow(2022)]);
    const [file, setFile] = useState<File | null>(null);
    const [submitting, setSubmitting] = useState(false);

    const manualData: ManualRainfallData = useMemo(() => {
        const out: ManualRainfallData = {};
        for (const row of rows) {
            const yr = row.year.trim();
            if (!yr) continue;
            const months: Record<string, number> = {};
            for (const m of MONTHS) {
                const v = parseFloat(normalizeNumber(row.months[m]));
                months[m] = Number.isFinite(v) ? v : 0;
            }
            out[yr] = months;
        }
        return out;
    }, [rows]);

    const handleRun = async () => {
        setSubmitting(true);
        try {
            let res: RunTriggeredResponse;
            if (mode === "manual") {
                if (Object.keys(manualData).length === 0) {
                    pushToast("error", "Add at least one year of manual data.");
                    return;
                }
                res = await triggerRunFromManual({
                    data: manualData,
                    forecast_years: forecastYears,
                    num_simulations: numSimulations,
                    curve_number: curveNumber,
                    river_basin_area: riverBasinArea,
                    runoff_scope: runoffScope,
                });
            } else {
                if (!file) {
                    pushToast("error", "Choose an Excel file first.");
                    return;
                }
                res = await triggerRunFromExcel(file, {
                    forecast_years: forecastYears,
                    num_simulations: numSimulations,
                    curve_number: curveNumber,
                    river_basin_area: riverBasinArea,
                    runoff_scope: runoffScope,
                });
            }
            pushToast("success", `Triggered: ${res.dag_run_id}`);
            onTriggered(res);
        } catch (err) {
            pushToast("error", toApiError(err).message);
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
            <div className="flex border-b border-slate-200">
                {(["manual", "excel"] as const).map((m) => (
                    <button
                        key={m}
                        onClick={() => setMode(m)}
                        className={`px-5 py-3 text-sm font-medium transition-colors ${mode === m
                                ? "text-indigo-600 border-b-2 border-indigo-600"
                                : "text-slate-500 hover:text-slate-800"
                            }`}
                    >
                        {m === "manual" ? "✏️ Manual Input" : "📁 Upload Excel"}
                    </button>
                ))}
            </div>

            <div className="p-6 space-y-6">
                {/* Parameters */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <label className="flex flex-col gap-1 text-sm">
                        <span className="text-slate-600 font-medium">Forecast years</span>
                        <input
                            type="number" min={1} max={200}
                            value={forecastYears}
                            onChange={(e) => setForecastYears(Number(e.target.value))}
                            className="border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                        />
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                        <span className="text-slate-600 font-medium">Num simulations</span>
                        <input
                            type="number" min={2} max={100000}
                            value={numSimulations}
                            onChange={(e) => setNumSimulations(Number(e.target.value))}
                            className="border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                        />
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                        <span className="text-slate-600 font-medium">Curve Number</span>
                        <input
                            type="number" min={1} max={99} step={1}
                            value={curveNumber}
                            onChange={(e) => setCurveNumber(Number(e.target.value))}
                            className="border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                        />
                    </label>
                    <label className="flex flex-col gap-1 text-sm">
                        <span className="text-slate-600 font-medium">River basin area (km²)</span>
                        <input
                            type="number" min={0.0001} step={0.01}
                            value={riverBasinArea}
                            onChange={(e) => setRiverBasinArea(Number(e.target.value))}
                            className="border border-slate-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-400"
                        />
                    </label>
                    <label className="flex flex-col gap-1 text-sm md:col-span-2">
                        <span className="text-slate-600 font-medium">Runoff scope</span>
                        <select
                            value={runoffScope}
                            onChange={(e) => setRunoffScope(e.target.value as RunoffScope)}
                            className="border border-slate-300 rounded-md px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
                        >
                            {RUNOFF_SCOPES.map((s) => (
                                <option key={s} value={s}>{s}</option>
                            ))}
                        </select>
                    </label>
                </div>

                {mode === "manual" ? (
                    <ManualTable rows={rows} setRows={setRows} />
                ) : (
                    <ExcelDropzone file={file} setFile={setFile} />
                )}

                <div className="flex justify-end pt-2">
                    <button
                        onClick={handleRun}
                        disabled={submitting}
                        className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-400 text-white font-medium px-6 py-2.5 rounded-lg shadow-sm transition-colors"
                    >
                        {submitting ? "Triggering…" : "Run Pipeline"}
                    </button>
                </div>
            </div>
        </div>
    );
}

function ManualTable({
    rows,
    setRows,
}: {
    rows: Row[];
    setRows: (r: Row[]) => void;
}) {
    const updateYear = (i: number, year: string) => {
        const next = [...rows];
        next[i] = { ...next[i], year };
        setRows(next);
    };

    const updateMonth = (i: number, m: string, v: string) => {
        const next = [...rows];
        next[i] = { ...next[i], months: { ...next[i].months, [m]: v } };
        setRows(next);
    }

    const addRow = () => {
        const last = rows[rows.length - 1];
        const yr = last ? parseInt(last.year, 10) + 1 : new Date().getFullYear();
        setRows([...rows, emptyRow(yr)]);
    }

    const removeRow = (i: number) =>
        setRows(rows.filter((_, idx) => idx !== i));

    const clearAll = () => {
        if (confirm("Clear all manual rows?")) {
            setRows([emptyRow(new Date().getFullYear())]);
        }
    }

    const handlePaste = (
        e: React.ClipboardEvent<HTMLInputElement>,
        startRow: number,
        startCol: number,
    ) => {
        const text = e.clipboardData.getData("text/plain");
        if (!text.trim()) return;

        const grid = parseTabular(text);
        if (grid.length === 0) return;

        // ── Single-cell paste → normalize in place, then let it land ──
        if (grid.length === 1 && grid[0].length === 1) {
            const raw = grid[0][0];
            const normalized = normalizeNumber(raw);
            if (normalized !== raw) {
                e.preventDefault();
                if (startCol === 0) updateYear(startRow, normalized);
                else updateMonth(startRow, MONTHS[startCol - 1], normalized);
            }
            // If nothing changed, default paste proceeds (fine)
            return;
        }

        // ── Multi-cell paste → intercept and distribute ──
        e.preventDefault();

        // Does this paste include a year column?
        let hasYearColumn = false;
        if (startCol === 0) {
            const firstCol = grid.map((r) => r[0]).filter((v) => v && v.trim());
            if (firstCol.length > 0 && firstCol.every(looksLikeYear)) {
                hasYearColumn = true;
            }
        }

        // Expand rows if the paste needs more than currently exist
        const requiredRows = startRow + grid.length;
        const next = [...rows];
        while (next.length < requiredRows) {
            const prevYear =
                next.length > 0
                    ? parseInt(next[next.length - 1].year, 10) || new Date().getFullYear()
                    : new Date().getFullYear();
            next.push(emptyRow(prevYear + 1));
        }

        // Map paste columns to grid columns
        let pasteStartCol = 0;
        let uiStartCol = startCol;
        if (hasYearColumn) {
            pasteStartCol = 1;
            uiStartCol = 1;
        } else if (startCol === 0) {
            // Pasted into the year column but no year-looking values → assume months from Jan
            uiStartCol = 1;
        }

        // Fill the grid
        grid.forEach((values, r) => {
            const targetRow = startRow + r;
            if (targetRow >= next.length) return;

            const row = { ...next[targetRow], months: { ...next[targetRow].months } };

            if (hasYearColumn && values.length > 0) {
                row.year = values[0].trim();
            }

            for (let c = pasteStartCol; c < values.length; c++) {
                const uiCol = uiStartCol + (c - pasteStartCol);
                if (uiCol < 1 || uiCol > 12) continue;
                const monthName = MONTHS[uiCol - 1];
                row.months[monthName] = normalizeNumber(values[c] ?? "");
            }

            next[targetRow] = row;
        });

        setRows(next);
        pushToast(
            "success",
            `Pasted ${grid.length} row(s) × ${grid[0].length} column(s).`,
        )
    }

    return (
        <div>
            <div className="flex items-center justify-between mb-3">
                <div>
                    <h3 className="text-sm font-semibold text-slate-700">
                        Historical rainfall (mm) — one row per year
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                        💡 Tip: copy a range from Excel and paste it into any cell — it
                        fills the whole grid automatically.
                    </p>
                </div>
                <div className="flex gap-2">
                    <button
                        onClick={clearAll}
                        className="text-xs text-slate-500 hover:text-rose-600 px-2 py-1"
                    >
                        Clear
                    </button>
                    <button
                        onClick={addRow}
                        className="text-sm text-indigo-600 hover:text-indigo-800 font-medium"
                    >
                        + Add year
                    </button>
                </div>
            </div>

            <div className="overflow-x-auto border border-slate-200 rounded-lg max-h-125 overflow-y-auto">
                <table className="min-w-full text-sm">
                    <thead className="bg-slate-50 text-slate-600 sticky top-0 z-10">
                        <tr>
                            <th className="px-2 py-2 text-left font-medium sticky left-0 bg-slate-50">
                                Year
                            </th>
                            {MONTHS.map((m) => (
                                <th key={m} className="px-2 py-2 text-left font-medium">
                                    {m}
                                </th>
                            ))}
                            <th className="px-2 py-2" />
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row, i) => (
                            <tr key={i} className="border-t border-slate-100">
                                <td className="px-1 py-1 sticky left-0 bg-white">
                                    <input
                                        value={row.year}
                                        onChange={(e) => updateYear(i, e.target.value)}
                                        onPaste={(e) => handlePaste(e, i, 0)}
                                        className="w-20 px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-400"
                                    />
                                </td>
                                {MONTHS.map((m, mi) => (
                                    <td key={m} className="px-1 py-1">
                                        <input
                                            type="text"
                                            inputMode="decimal"
                                            value={row.months[m]}
                                            onChange={(e) => updateMonth(i, m, e.target.value)}
                                            onPaste={(e) => handlePaste(e, i, mi + 1)}
                                            className="w-20 px-2 py-1 border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-indigo-400"
                                        />
                                    </td>
                                ))}
                                <td className="px-2 py-1 text-right">
                                    <button
                                        onClick={() => removeRow(i)}
                                        className="text-rose-500 hover:text-rose-700 text-xs"
                                    >
                                        remove
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    )
}

function ExcelDropzone({
    file,
    setFile,
}: {
    file: File | null;
    setFile: (f: File | null) => void;
}) {
    return (
        <label className="block border-2 border-dashed border-slate-300 hover:border-indigo-400 rounded-xl p-8 text-center cursor-pointer transition-colors">
            <input
                type="file"
                accept=".xlsx,.xls"
                className="hidden"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <div className="text-3xl mb-2">📄</div>
            <div className="text-sm text-slate-700 font-medium">
                {file ? file.name : "Click to choose an Excel file"}
            </div>
            <div className="text-xs text-slate-400 mt-1">
                Expected columns: Tahun, Jan, Feb, …, Des
            </div>
        </label>
    )
}