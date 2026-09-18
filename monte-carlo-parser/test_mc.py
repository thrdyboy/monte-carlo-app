# test_mc_metrics.py
"""
Standalone Monte Carlo test — compares Option A (sample-based metrics)
against the current mean-based metrics.

Fully hardcoded. No project imports. No Airflow. No database.

Run:
    conda activate monte-carlo-etl
    python test_mc_metrics.py

Outputs:
    - test_output/mc_metrics_report.txt   (side-by-side comparison)
    - test_output/mc_time_series.png
    - test_output/mc_heatmap.png
    - test_output/mc_heatmap_combined.png
"""
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import mean_absolute_error, mean_squared_error


# ═════════════════════════════════════════════════════════════════════
# 1. HARDCODED INPUT — 25 years (2000–2024)
# ═════════════════════════════════════════════════════════════════════

MONTHS = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
          "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]

HIST_DATA = {
    2000: {"Jan":  83.32, "Feb":  25.15, "Mar": 124.71, "Apr":  86.86, "Mei":  40.38, "Jun":  10.15, "Jul":   2.28, "Agu":   3.80, "Sep":   0.00, "Okt":   1.27, "Nov":  90.17, "Des": 115.32},
    2001: {"Jan": 141.72, "Feb":  37.33, "Mar": 124.97, "Apr":   2.28, "Mei":   0.00, "Jun":   0.76, "Jul":  13.72, "Agu":   0.76, "Sep":   7.36, "Okt":  25.15, "Nov":  23.11, "Des":  78.99},
    2002: {"Jan": 168.14, "Feb": 238.49, "Mar":  39.62, "Apr":  58.93, "Mei":   5.08, "Jun":   1.52, "Jul":  14.99, "Agu":   2.03, "Sep":   3.05, "Okt":   0.00, "Nov":  25.65, "Des": 142.74},
    2003: {"Jan": 297.18, "Feb": 288.80, "Mar":  76.96, "Apr":  18.80, "Mei":  35.05, "Jun":   2.28, "Jul":   0.51, "Agu":   0.00, "Sep":   3.56, "Okt":  21.09, "Nov":  35.30, "Des":  89.92},
    2004: {"Jan":  72.39, "Feb": 220.98, "Mar": 180.34, "Apr":  42.68, "Mei": 114.05, "Jun":   0.00, "Jul":   0.00, "Agu":  20.32, "Sep":  29.98, "Okt":   0.00, "Nov":  67.81, "Des": 117.10},
    2005: {"Jan": 128.78, "Feb": 113.79, "Mar": 170.16, "Apr": 111.26, "Mei":   7.12, "Jun":  26.92, "Jul":   8.64, "Agu":  76.20, "Sep":   0.51, "Okt": 206.26, "Nov": 104.39, "Des": 232.92},
    2006: {"Jan": 129.03, "Feb": 235.45, "Mar": 301.25, "Apr":  34.29, "Mei": 142.23, "Jun":  57.66, "Jul":  28.46, "Agu":   2.03, "Sep":   0.00, "Okt":  19.05, "Nov":   4.07, "Des": 154.17},
    2007: {"Jan": 247.15, "Feb": 257.81, "Mar": 338.84, "Apr": 142.75, "Mei":  24.12, "Jun":  70.10, "Jul":   1.02, "Agu":  33.28, "Sep":   0.51, "Okt":   6.60, "Nov":  30.99, "Des": 100.33},
    2008: {"Jan": 137.66, "Feb": 266.44, "Mar": 251.21, "Apr":  21.08, "Mei":  33.28, "Jun": 162.30, "Jul":   5.59, "Agu":   4.31, "Sep":  13.97, "Okt":  50.30, "Nov":  99.31, "Des": 312.42},
    2009: {"Jan": 345.18, "Feb": 242.56, "Mar":  41.91, "Apr": 172.47, "Mei":  94.50, "Jun":  27.18, "Jul":  30.98, "Agu":   1.27, "Sep":  39.37, "Okt":  39.12, "Nov":  91.44, "Des": 163.85},
    2010: {"Jan": 320.04, "Feb": 112.78, "Mar": 166.61, "Apr": 213.36, "Mei": 171.69, "Jun":  79.24, "Jul":  58.16, "Agu":  28.45, "Sep":  59.17, "Okt": 188.21, "Nov":  28.96, "Des": 127.53},
    2011: {"Jan": 179.83, "Feb":  97.04, "Mar": 117.59, "Apr": 207.51, "Mei": 108.21, "Jun":  13.46, "Jul":  18.29, "Agu":   7.87, "Sep":   0.00, "Okt":  26.92, "Nov":  37.86, "Des": 116.82},
    2012: {"Jan": 254.54, "Feb":  85.86, "Mar":  57.40, "Apr":  16.00, "Mei":  52.59, "Jun":   1.02, "Jul":  32.26, "Agu":   1.02, "Sep":   9.91, "Okt":   0.00, "Nov":  66.81, "Des": 147.59},
    2013: {"Jan": 325.12, "Feb":  94.25, "Mar": 208.29, "Apr": 183.39, "Mei":  77.22, "Jun":  78.21, "Jul":  74.17, "Agu":  11.19, "Sep":   6.61, "Okt":   0.25, "Nov": 183.64, "Des": 145.80},
    2014: {"Jan": 157.72, "Feb": 230.61, "Mar":  30.72, "Apr": 128.01, "Mei":   6.85, "Jun":  12.19, "Jul":  25.91, "Agu":  16.50, "Sep":   0.00, "Okt":   0.00, "Nov":  53.08, "Des": 165.61},
    2015: {"Jan": 149.62, "Feb": 163.32, "Mar": 194.82, "Apr":  48.26, "Mei":  75.19, "Jun":  57.15, "Jul":   0.00, "Agu":   4.31, "Sep":   0.00, "Okt":   0.00, "Nov":   0.00, "Des": 131.82},
    2016: {"Jan": 108.97, "Feb": 229.37, "Mar":  60.20, "Apr":  45.97, "Mei":  61.21, "Jun": 126.75, "Jul":  69.34, "Agu":  91.19, "Sep":  17.27, "Okt":  60.95, "Nov": 100.06, "Des": 256.04},
    2017: {"Jan": 254.26, "Feb": 242.31, "Mar": 173.73, "Apr":  84.32, "Mei": 138.69, "Jun": 142.50, "Jul":  81.53, "Agu":  54.10, "Sep":   1.27, "Okt":  76.71, "Nov": 221.46, "Des": 264.41},
    2018: {"Jan": 462.80, "Feb": 267.46, "Mar": 146.05, "Apr":  25.15, "Mei":   2.03, "Jun":  23.36, "Jul":  91.95, "Agu":  36.81, "Sep":   2.03, "Okt":   0.51, "Nov": 142.75, "Des":  90.17},
    2019: {"Jan": 219.96, "Feb":  69.10, "Mar": 157.22, "Apr": 234.45, "Mei":  13.73, "Jun":  16.01, "Jul":   0.00, "Agu":   3.30, "Sep":   4.06, "Okt":   0.00, "Nov":   2.03, "Des":  11.18},
    2020: {"Jan": 135.62, "Feb": 284.24, "Mar": 209.83, "Apr":  36.58, "Mei": 210.57, "Jun":  61.96, "Jul":  56.89, "Agu":  31.75, "Sep":  69.08, "Okt": 195.32, "Nov":  22.61, "Des": 186.96},
    2021: {"Jan": 242.84, "Feb": 249.16, "Mar": 192.80, "Apr": 182.38, "Mei":  30.23, "Jun": 128.26, "Jul":  62.22, "Agu":  45.21, "Sep":  89.67, "Okt":  59.44, "Nov": 183.14, "Des": 197.34},
    2022: {"Jan": 261.09, "Feb":  80.26, "Mar": 297.94, "Apr":  40.12, "Mei":  25.89, "Jun":  62.23, "Jul":   9.13, "Agu":  26.92, "Sep":  45.98, "Okt": 227.32, "Nov": 279.64, "Des": 142.23},
    2023: {"Jan": 233.94, "Feb": 386.59, "Mar": 204.21, "Apr":  92.97, "Mei":   8.11, "Jun":  38.61, "Jul": 185.93, "Agu":   6.61, "Sep":   3.30, "Okt":   0.00, "Nov":  17.02, "Des":   2.54},
    2024: {"Jan": 152.91, "Feb": 214.89, "Mar": 198.13, "Apr":  86.62, "Mei":   9.64, "Jun":  21.84, "Jul":  40.39, "Agu":   0.76, "Sep":   6.86, "Okt":  59.18, "Nov":  53.85, "Des": 268.72},
}

# Monte Carlo parameters
FORECAST_YEARS  = 10
NUM_SIMULATIONS = 1000
RANDOM_SEED     = 42
OUT_DIR         = "test_output"

# Sample-selection mode for visualization
SAMPLE_MODE     = "typical"    # "random" | "typical" | "weighted"
ALPHA_PARAMS    = 5.0


# ═════════════════════════════════════════════════════════════════════
# 2. METRICS — both flavors
# ═════════════════════════════════════════════════════════════════════

def calculate_mape(actual, pred) -> float:
    actual, pred = np.array(actual), np.array(pred)
    mask = actual != 0
    if mask.sum() == 0:
        return 0.0
    return float(np.mean(np.abs((actual[mask] - pred[mask]) / actual[mask])) * 100)


def compute_metrics(df_hist, df_pred, months):
    """Compare MONTHLY MEANS: historical vs given forecast DataFrame.

    This is the ORIGINAL behavior. When df_pred is the mean of N simulations,
    the metric converges to ~0.
    """
    actual_mean = df_hist[months].mean().values
    predictions = df_pred[months].mean().values
    return {
        "MAE":  float(mean_absolute_error(actual_mean, predictions)),
        "RMSE": float(np.sqrt(mean_squared_error(actual_mean, predictions))),
        "MAPE": calculate_mape(actual_mean, predictions),
    }


def compute_metrics_yearly_totals(df_hist, df_pred, months):
    """Compare YEARLY TOTALS: historical annual rainfall vs forecast annual rainfall.

    Pairs each forecast year with a historical year (up to the shorter length).
    Produces a metric that reflects "how much does an annual total differ",
    which is far more variable and meaningful than monthly means.
    """
    hist_totals = df_hist[months].sum(axis=1).values
    pred_totals = df_pred[months].sum(axis=1).values

    n = min(len(hist_totals), len(pred_totals))
    actual = hist_totals[:n]
    pred   = pred_totals[:n]

    return {
        "MAE":  float(mean_absolute_error(actual, pred)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, pred))),
        "MAPE": calculate_mape(actual, pred),
    }


# ═════════════════════════════════════════════════════════════════════
# 3. MONTE CARLO — block bootstrap
# ═════════════════════════════════════════════════════════════════════

def simulate_once(hist_array, pred_years):
    pred_list = []
    for _ in pred_years:
        idx = np.random.randint(0, len(hist_array))
        pred_list.append(hist_array[idx])
    return pd.DataFrame(pred_list, columns=MONTHS, index=pred_years)


def pick_sample(all_preds, df_mean):
    if SAMPLE_MODE == "random":
        idx = int(np.random.randint(0, len(all_preds)))

    elif SAMPLE_MODE == "typical":
        mean_values = df_mean[MONTHS].values
        distances = [
            float(np.linalg.norm(all_preds[i][MONTHS].values - mean_values))
            for i in range(len(all_preds))
        ]
        idx = int(np.argmin(distances))

    elif SAMPLE_MODE == "weighted":
        w = np.random.gamma(shape=ALPHA_PARAMS, scale=1.0, size=len(all_preds))
        w = w / w.sum()
        idx = int(np.random.choice(len(all_preds), p=w))

    else:
        raise ValueError(f"Unknown SAMPLE_MODE: {SAMPLE_MODE!r}")

    return all_preds[idx], idx


def run_monte_carlo(df_hist):
    last_year  = int(df_hist.index.max())
    pred_years = list(range(last_year + 1, last_year + 1 + FORECAST_YEARS))
    hist_array = df_hist[MONTHS].values

    np.random.seed(RANDOM_SEED)
    all_preds = [simulate_once(hist_array, pred_years)
                 for _ in range(NUM_SIMULATIONS)]

    stacked      = pd.concat(all_preds, keys=range(NUM_SIMULATIONS))
    df_mean      = stacked.groupby(level=1).mean()
    df_std       = stacked.groupby(level=1).std()

    df_sample, sample_idx = pick_sample(all_preds, df_mean)

    return {
        "df_hist":     df_hist,
        "df_mean":     df_mean,
        "df_std":      df_std,
        "df_sample":   df_sample,
        "sample_idx":  sample_idx,
        "n_iterations": NUM_SIMULATIONS,
    }


# ═════════════════════════════════════════════════════════════════════
# 4. PLOTS
# ═════════════════════════════════════════════════════════════════════

def to_ts(df):
    rows = []
    for yr in df.index:
        for i, m in enumerate(MONTHS):
            rows.append({
                "Tanggal": pd.to_datetime(f"{yr}-{i+1}-01"),
                "Nilai": df.loc[yr, m],
            })
    return pd.DataFrame(rows)


def plot_time_series(result, out_path):
    ts_hist   = to_ts(result["df_hist"])
    ts_mean   = to_ts(result["df_mean"])
    ts_std    = to_ts(result["df_std"])
    ts_sample = to_ts(result["df_sample"])

    fig, ax = plt.subplots(figsize=(11, 4.2))

    ax.plot(ts_hist["Tanggal"], ts_hist["Nilai"],
            label="Historical", color="#4C72B0", linewidth=1.2)

    lower = (ts_mean["Nilai"] - ts_std["Nilai"]).clip(lower=0)
    upper = ts_mean["Nilai"] + ts_std["Nilai"]
    ax.fill_between(ts_mean["Tanggal"], lower, upper,
                    color="#C44E52", alpha=0.15,
                    label=f"±1σ ({result['n_iterations']} sims)", zorder=1)

    ax.plot(ts_sample["Tanggal"], ts_sample["Nilai"],
            color="#EF0911", linestyle="--", linewidth=1.0,
            alpha=0.75,
            label=f"Sample simulation (#{result['sample_idx']})", zorder=3)

    ax.axvline(ts_hist["Tanggal"].iloc[-1], color="gray",
               linestyle=":", linewidth=0.8)

    ax.set_xlabel("Tanggal")
    ax.set_ylabel("Curah Hujan (mm)")
    ax.set_title(f"Monte Carlo — Historical vs Forecast Rainfall "
                 f"(sample mode: {SAMPLE_MODE})")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


def plot_heatmap(result, out_path, include_history):
    df_forecast = result["df_sample"]

    if include_history:
        df_plot = pd.concat([result["df_hist"], df_forecast])
        title = "Monte Carlo — Historical + Sample Heatmap"
    else:
        df_plot = df_forecast
        title = "Monte Carlo — Sample Heatmap"

    fig, ax = plt.subplots(figsize=(10, max(2.5, 0.4 * len(df_plot))))
    sns.heatmap(df_plot[MONTHS], annot=True, fmt=".1f", cmap="YlGnBu",
                cbar_kws={"label": "Rainfall (mm)"}, ax=ax)
    ax.set_title(title)
    ax.set_xlabel("Bulan")
    ax.set_ylabel("Tahun")
    fig.tight_layout()
    fig.savefig(out_path, dpi=170)
    plt.close(fig)


# ═════════════════════════════════════════════════════════════════════
# 5. MAIN
# ═════════════════════════════════════════════════════════════════════

def fmt_metrics(name, m):
    return (f"  {name:<28}"
            f"MAE = {m['MAE']:>8.3f}   "
            f"RMSE = {m['RMSE']:>8.3f}   "
            f"MAPE = {m['MAPE']:>8.3f} %")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df_hist = pd.DataFrame.from_dict(HIST_DATA, orient="index")[MONTHS]
    df_hist.index.name = "Tahun"

    print(f"[test] Historical: {len(df_hist)} years "
          f"({df_hist.index.min()}–{df_hist.index.max()})")
    print(f"[test] Forecast years: {FORECAST_YEARS}")
    print(f"[test] Simulations:    {NUM_SIMULATIONS}")
    print()

    result = run_monte_carlo(df_hist)
    print(f"[test] sample mode: {SAMPLE_MODE} → picked iteration "
          f"#{result['sample_idx']}")
    print()

    # ── Compute all four metric combinations ──
    metrics_mean_monthly   = compute_metrics(df_hist, result["df_mean"],   MONTHS)
    metrics_sample_monthly = compute_metrics(df_hist, result["df_sample"], MONTHS)
    metrics_mean_yearly    = compute_metrics_yearly_totals(df_hist, result["df_mean"],   MONTHS)
    metrics_sample_yearly  = compute_metrics_yearly_totals(df_hist, result["df_sample"], MONTHS)

    # ── Print side by side ──
    lines = [
        "════════════════════════════════════════════════════════════════════",
        "  METRICS COMPARISON",
        "════════════════════════════════════════════════════════════════════",
        "",
        "  Each line uses a different (forecast, target) pair:",
        "",
        "  [1] MONTHLY MEANS  × MEAN of simulations",
        "      → Converges to ~0 because mean of 1000 sims ≈ historical mean.",
        "      → This is what the current server computes.",
        "",
        fmt_metrics("[1] mean-of-sims / monthly", metrics_mean_monthly),
        "",
        "  [2] MONTHLY MEANS  × SAMPLE trajectory          ← Option A",
        "      → Meaningful: how far is one plausible forecast from history?",
        "",
        fmt_metrics("[2] sample / monthly", metrics_sample_monthly),
        "",
        "  [3] YEARLY TOTALS  × MEAN of simulations",
        "      → Less convergence because annual totals vary a lot.",
        "",
        fmt_metrics("[3] mean-of-sims / yearly", metrics_mean_yearly),
        "",
        "  [4] YEARLY TOTALS  × SAMPLE trajectory          ← Option A+B",
        "      → Most informative; matches how forecasters usually report.",
        "",
        fmt_metrics("[4] sample / yearly", metrics_sample_yearly),
        "",
        "════════════════════════════════════════════════════════════════════",
        "",
        "  Recommendation: use [2] for a quick fix, or [4] for the most",
        "  meaningful number. The server currently uses [1] which is ~0 by",
        "  mathematical construction.",
        "════════════════════════════════════════════════════════════════════",
    ]
    report = "\n".join(lines)
    print(report)

    report_path = os.path.join(OUT_DIR, "mc_metrics_report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"[test] saved {report_path}")

    # ── Save plots ──
    plot_time_series(result, os.path.join(OUT_DIR, "mc_time_series.png"))
    plot_heatmap(result, os.path.join(OUT_DIR, "mc_heatmap.png"),
                 include_history=False)
    plot_heatmap(result, os.path.join(OUT_DIR, "mc_heatmap_combined.png"),
                 include_history=True)
    print("[test] saved 3 PNGs to test_output/")
    print("[test] done.")


if __name__ == "__main__":
    main()