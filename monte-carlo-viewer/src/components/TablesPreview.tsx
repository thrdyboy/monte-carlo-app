import { useState } from "react";
import type { LatestTablesResponse, TablePreview } from "../types/api";

export default function TablesPreview({ data }: { data: LatestTablesResponse | null }) {
    const [activeIdx, setActiveIdx] = useState(0);

    if (!data || data.tables.length === 0) {
        return (
            <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400 text-sm">
                No tables available.
            </div>
        );
    }

    const active = data.tables[activeIdx];

    return (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-baseline justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-700">
                    Tables — {data.count} files
                </h3>
                <span className="text-xs text-slate-400 font-mono truncate max-w-[60%]">
                    {data.run_id}
                </span>
            </div>

            {/* Tab bar */}
            <div className="flex flex-wrap gap-1 border-b border-slate-200 mb-4">
                {data.tables.map((t, i) => (
                    <button
                        key={t.id}
                        onClick={() => setActiveIdx(i)}
                        className={`text-xs px-3 py-2 -mb-px border-b-2 transition-colors ${i === activeIdx
                                ? "border-indigo-500 text-indigo-600 font-medium"
                                : "border-transparent text-slate-500 hover:text-slate-800"
                            }`}
                    >
                        {t.name.replace(".parquet", "")}
                    </button>
                ))}
            </div>

            <TableBody table={active} />
        </div>
    );
}

function TableBody({ table }: { table: TablePreview }) {
    if (table.error) {
        return (
            <div className="bg-rose-50 border border-rose-200 text-rose-700 text-sm rounded-lg p-3">
                Failed to load: {table.error}
            </div>
        );
    }

    return (
        <div>
            <div className="flex items-center justify-between text-xs text-slate-500 mb-2">
                <span>
                    Showing {table.returned_rows} of {table.total_rows} rows ·{" "}
                    {table.total_columns} columns
                </span>
                <a
                    href={table.download_url}
                    className="text-indigo-600 hover:text-indigo-800"
                    download
                >
                    download .parquet
                </a>
            </div>

            <div className="overflow-x-auto border border-slate-200 rounded-lg">
                <table className="min-w-full text-xs">
                    <thead className="bg-slate-50 text-slate-600 sticky top-0">
                        <tr>
                            {table.columns.map((c) => (
                                <th key={c} className="px-3 py-2 text-left font-medium whitespace-nowrap">
                                    {c}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {table.rows.map((row, i) => (
                            <tr
                                key={i}
                                className={i % 2 === 0 ? "bg-white" : "bg-slate-50/50"}
                            >
                                {table.columns.map((c) => {
                                    const v = row[c];
                                    const display =
                                        typeof v === "number" && !Number.isInteger(v)
                                            ? v.toFixed(3)
                                            : String(v ?? "");
                                    return (
                                        <td
                                            key={c}
                                            className="px-3 py-1.5 text-slate-700 whitespace-nowrap"
                                        >
                                            {display}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}