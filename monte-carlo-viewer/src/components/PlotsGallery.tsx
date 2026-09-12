// src/components/PlotsGallery.tsx
import type { LatestPlotsResponse } from "../types/api";

export default function PlotsGallery({ data }: { data: LatestPlotsResponse | null }) {
    if (!data || data.plots.length === 0) {
        return (
            <div className="bg-white border border-slate-200 rounded-xl p-6 text-center text-slate-400 text-sm">
                No plots available.
            </div>
        );
    }

    return (
        <div className="bg-white border border-slate-200 rounded-xl p-5">
            <div className="flex items-baseline justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-700">
                    Plots — {data.count} images
                </h3>
                <span className="text-xs text-slate-400 font-mono truncate max-w-[60%]">
                    {data.run_id}
                </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {data.plots.map((p) => (
                    <figure
                        key={p.id}
                        className="border border-slate-200 rounded-lg overflow-hidden bg-slate-50"
                    >
                        <img
                            src={p.view_url}
                            alt={p.name}
                            loading="lazy"
                            className="w-full h-auto bg-white"
                        />
                        <figcaption className="flex items-center justify-between px-3 py-2 text-xs">
                            <span className="text-slate-600 font-medium truncate">
                                {p.name}
                            </span>
                            <a
                                href={p.download_url}
                                className="text-indigo-600 hover:text-indigo-800"
                                download
                            >
                                download
                            </a>
                        </figcaption>
                    </figure>
                ))}
            </div>
        </div>
    );
}