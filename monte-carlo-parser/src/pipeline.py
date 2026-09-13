import os
import sys
from typing import Dict, Any, Optional

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config.settings import load_config
from src.etl.extract.build_from_file import build_from_file
from src.etl.extract.build_year_month_df import build_year_month_df
from src.etl.transform.monte_carlo import run_monte_carlo_iterations
from src.etl.transform.runoff_measurement_scs_cn import (
    calculate_runoff_details,
    build_rekap_tahunan,
    build_rekap_bulanan,
)
from src.etl.load.plot_monte_carlo import plot_mc_time_series, plot_mc_heatmap
from src.etl.load.plot_runoff import (
    plot_runoff_time_series,
    plot_runoff_monthly_avg,
    plot_runoff_discharge,
    plot_runoff_yearly,
)


def run_full_pipeline(
    output_dir: str,
    input_file_path: Optional[str] = None,
    manual_data: Optional[Dict[str, Any]] = None,
    config: Optional[Any] = None,
    runoff_scope: str = "forecast",
) -> str:
    """
    Unified ETL Pipeline: Extract -> Transform -> Load.

    Args:
        runoff_scope:
            "forecast"        -> runoff on ONE sample Monte Carlo trajectory (varied)
            "forecast_mean"   -> runoff on the MEAN across simulations (smooth)
            "combined"        -> runoff on historical + ONE sample trajectory
            "combined_mean"   -> runoff on historical + the MEAN
    """
    if config is None:
        config = load_config()

    # 1. EXTRACT
    print("--- 1. EXTRACT ---")
    if manual_data is not None:
        print("Extracting from manual data dictionary...")
        df_hist = build_year_month_df(manual_data, config)
    elif input_file_path is not None:
        print(f"Extracting from file: {input_file_path}")
        df_hist = build_from_file(input_file_path, config)
    else:
        raise ValueError("You must provide either 'manual_data' or 'input_file_path'")

    print(f"Extracted {len(df_hist)} historical years: "
          f"{df_hist.index.min()}-{df_hist.index.max()}")

    # 2. TRANSFORM — Monte Carlo
    print("--- 2. TRANSFORM (Monte Carlo) ---")
    mc_result = run_monte_carlo_iterations(df_hist, config=config)
    print("Monte Carlo simulation complete.")

    # 3. TRANSFORM — SCS-CN Runoff
    print("--- 3. TRANSFORM (Runoff SCS-CN) ---")

    # What year-window to compute runoff over
    # df_pred_sample = ONE random simulation (varied)
    # df_pred_mean   = mean across all sims (smooth)
    if runoff_scope == "forecast":
        df_for_runoff = mc_result["df_pred_sample"]
        label = "FORECAST (sample simulation)"
    elif runoff_scope == "forecast_mean":
        df_for_runoff = mc_result["df_pred_mean"]
        label = "FORECAST (mean across simulations)"
    elif runoff_scope == "combined":
        import pandas as pd
        df_for_runoff = pd.concat([mc_result["df_hist"], mc_result["df_pred_sample"]])
        label = "HISTORICAL + FORECAST (sample simulation)"
    elif runoff_scope == "combined_mean":
        import pandas as pd
        df_for_runoff = pd.concat([mc_result["df_hist"], mc_result["df_pred_mean"]])
        label = "HISTORICAL + FORECAST (mean across simulations)"
    else:
        raise ValueError(
            f"Invalid runoff_scope: {runoff_scope!r}. "
            "Use 'forecast', 'forecast_mean', 'combined', or 'combined_mean'."
        )

    print(f"Runoff scope: {label} ({len(df_for_runoff)} years: "
          f"{df_for_runoff.index.min()}-{df_for_runoff.index.max()})")

    df_runoff_details = calculate_runoff_details(df_for_runoff, config)
    rekap_tahunan = build_rekap_tahunan(df_runoff_details, config)
    rekap_bulanan = build_rekap_bulanan(df_runoff_details, config)
    print("Runoff calculation complete.")

    # 4. LOAD — Local Parquet Files
    print("--- 4. LOAD (Local Files) ---")
    os.makedirs(output_dir, exist_ok=True)

    df_runoff_details.to_parquet(
        os.path.join(output_dir, "runoff_details.parquet"), index=False
    )
    rekap_tahunan.to_parquet(
        os.path.join(output_dir, "rekap_tahunan.parquet"), index=False
    )
    rekap_bulanan.to_parquet(
        os.path.join(output_dir, "rekap_bulanan.parquet"), index=False
    )
    mc_result["df_combined"].to_parquet(
        os.path.join(output_dir, "mc_combined.parquet")
    )
    print(f"Local files saved to {output_dir}")

    # 5. LOAD — Local PNG Plots
    print("--- 5. LOAD (Plots) ---")
    plots_dir = os.path.join(output_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    plot_mc_time_series(mc_result, os.path.join(plots_dir, "mc_time_series.png"))
    plot_mc_heatmap(
        mc_result, os.path.join(plots_dir, "mc_heatmap.png"),
        config, include_history=False, use_sample=True,
    )
    plot_mc_heatmap(
        mc_result, os.path.join(plots_dir, "mc_heatmap_combined.png"),
        config, include_history=True, use_sample=True,
    )

    runoff_result_dict = {
        "df_details": df_runoff_details,
        "rekap_tahunan": rekap_tahunan,
        "rekap_bulanan": rekap_bulanan,
    }

    plot_runoff_time_series(
        runoff_result_dict, os.path.join(plots_dir, "runoff_ts.png"), config
    )
    plot_runoff_monthly_avg(
        runoff_result_dict, os.path.join(plots_dir, "runoff_monthly.png"), config
    )
    plot_runoff_discharge(
        runoff_result_dict, os.path.join(plots_dir, "runoff_discharge.png"), config
    )
    plot_runoff_yearly(
        runoff_result_dict, os.path.join(plots_dir, "runoff_yearly.png"), config
    )
    print(f"Plots saved to {plots_dir}")

    # 6 & 7. LOAD — PostgreSQL + MinIO
    run_id = os.path.basename(output_dir.rstrip("/\\"))

    try:
        print("--- 6. LOAD (PostgreSQL Warehouse) ---")
        from src.etl.load.load_to_postgres import (
            load_dataframe_to_postgres,
            ensure_artifacts_table,
            register_artifacts,
            ensure_run_metrics_table,
            save_run_metrics
        )

        ensure_artifacts_table(config)
        ensure_run_metrics_table(config)

        load_dataframe_to_postgres(
            mc_result["df_combined"], "mc_combined", config,
            if_exists="replace", index=True,
        )
        load_dataframe_to_postgres(
            df_runoff_details, "runoff_details", config, if_exists="replace"
        )
        load_dataframe_to_postgres(
            rekap_tahunan, "rekap_tahunan", config, if_exists="replace"
        )
        load_dataframe_to_postgres(
            rekap_bulanan, "rekap_bulanan", config, if_exists="replace"
        )

        save_run_metrics(               
            run_id=run_id,
            metrics=mc_result["metrics"],
            config=config,
            runoff_scope=runoff_scope
        )

        print("--- 7. LOAD (MinIO Object Storage) ---")
        from src.etl.load.load_to_minio import upload_run_artifacts

        artifacts = upload_run_artifacts(output_dir, run_id, config)
        register_artifacts(artifacts, run_id, config)
        print(f"[minio] Uploaded {len(artifacts)} files")

    except Exception as e:
        print(f"[ERROR] Warehouse/MinIO load failed: {e}")
        import traceback
        traceback.print_exc()
        raise

    print("--- PIPELINE COMPLETE ---")
    return "Pipeline Completed Successfully"