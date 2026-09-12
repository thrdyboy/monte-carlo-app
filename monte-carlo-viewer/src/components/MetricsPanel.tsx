import type { RunMetrics } from "../types/api";

function fmt(n: number | null | undefined, digits = 2) {
    if (n == null) return "—";
    return n.toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
    });
}

export default function MetricsPanel({ metrics }: { metrics: RunMetrics | null }) {
    if (!metrics) {
        return (
            <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400 text-sm">
                No metrics recorded yet. Trigger a run to populate this panel.
            </div>
        );
    }

    const cards = [
        { label: "MAE", value: fmt(metrics.mae), unit: "mm" },
        { label: "RMSE", value: fmt(metrics.rmse), unit: "mm" },
        { label: "MAPE", value: fmt(metrics.mape), unit: "%" },
        { label: "Sims", value: metrics.num_simulations.toLocaleString() },
        { label: "Horizon", value: `${metrics.forecast_years}y` },
        { label: "CN", value: String(metrics.curve_number) },
        { label: "Area", value: `${metrics.river_basin_area} km²` },
        { label: "Scope", value: metrics.runoff_scope ?? "—" },
    ];

    return (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-baseline justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-700">
                    Metrics — latest run
                </h3>
                <span className="text-xs text-slate-400 font-mono truncate max-w-[60%]">
                    {metrics.run_id}
                </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {cards.map((c) => (
                    <div
                        key={c.label}
                        className="bg-slate-50 rounded-lg px-3 py-2 border border-slate-100"
                    >
                        <div className="text-[11px] uppercase tracking-wide text-slate-500">
                            {c.label}
                        </div>
                        <div className="text-lg font-semibold text-slate-800">
                            {c.value}
                            {c.unit && (
                                <span className="text-xs font-normal text-slate-500 ml-1">
                                    {c.unit}
                                </span>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}