import os
import sys
from typing import Dict, Any, Optional

import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config.settings import load_config
from src.etl.extract.build_from_file import build_from_file
from src.etl.extract.build_year_month_df import build_year_month_df
from src.etl.transform.monte_carlo import run_monte_carlo_iterations
from src.etl.transform.markov_chain import run_markov_chain_iterations
from src.etl.transform.runoff_monte_carlo import calculate_runoff_details_monte_carlo
from src.etl.transform.runoff_markov import (
    calculate_runoff_details_markov,
    add_kategori_column,
)
from src.etl.transform.runoff_measurement_scs_cn import (
    build_rekap_tahunan,
    build_rekap_bulanan,
)
from src.etl.load.plot_forecast import plot_forecast_time_series, plot_forecast_heatmap
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
    forecast_method: str = "monte_carlo",
) -> str:
    """
    Unified ETL Pipeline: Extract -> Transform -> Load.

    Args:
        runoff_scope:
            "forecast"        -> runoff on ONE sample forecast trajectory (varied)
            "forecast_mean"   -> runoff on the MEAN across simulations (smooth)
            "combined"        -> runoff on historical + ONE sample trajectory
            "combined_mean"   -> runoff on historical + the MEAN
        forecast_method:
            "monte_carlo"     -> Block Bootstrap simulation
            "markov"          -> Discrete-state Markov Chain simulation
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

    # 2. TRANSFORM — Forecasting (Monte Carlo or Markov Chain)
    method = (forecast_method or "monte_carlo").lower()
    if method == "markov":
        print("--- 2. TRANSFORM (Markov Chain) ---")
        forecast_result = run_markov_chain_iterations(df_hist, config=config)
        print("Markov Chain simulation complete.")
    elif method == "monte_carlo":
        print("--- 2. TRANSFORM (Monte Carlo) ---")
        forecast_result = run_monte_carlo_iterations(df_hist, config=config)
        print("Monte Carlo simulation complete.")
    else:
        raise ValueError(
            f"Invalid forecast_method: {forecast_method!r}. "
            "Use 'monte_carlo' or 'markov'."
        )

    # 3. TRANSFORM — SCS-CN Runoff
    print("--- 3. TRANSFORM (Runoff SCS-CN) ---")

    if runoff_scope == "forecast":
        df_for_runoff = forecast_result["df_pred_sample"]
        label = "FORECAST (sample simulation)"
    elif runoff_scope == "forecast_mean":
        df_for_runoff = forecast_result["df_pred_mean"]
        label = "FORECAST (mean across simulations)"
    elif runoff_scope == "combined":
        df_for_runoff = pd.concat([forecast_result["df_hist"], forecast_result["df_pred_sample"]])
        label = "HISTORICAL + FORECAST (sample simulation)"
    elif runoff_scope == "combined_mean":
        df_for_runoff = pd.concat([forecast_result["df_hist"], forecast_result["df_pred_mean"]])
        label = "HISTORICAL + FORECAST (mean across simulations)"
    else:
        raise ValueError(
            f"Invalid runoff_scope: {runoff_scope!r}. "
            "Use 'forecast', 'forecast_mean', 'combined', or 'combined_mean'."
        )

    print(f"Runoff scope: {label} ({len(df_for_runoff)} years: "
          f"{df_for_runoff.index.min()}-{df_for_runoff.index.max()})")

    if method == "monte_carlo":
        df_runoff_details = calculate_runoff_details_monte_carlo(
            df_for_runoff, config, n_iterations=config.monte_carlo.num_simulations
        )
    elif method == "markov":
        df_runoff_details = calculate_runoff_details_markov(df_for_runoff, config)
        # Legacy Excel parity: EKSTREM BASAH / KERING / NORMAL per month
        df_runoff_details = add_kategori_column(
            df_runoff_details,
            thr_wet=forecast_result["thr_wet"],
            thr_dry=forecast_result["thr_dry"],
        )
    else:
        raise ValueError(f"Unknown forecast method: {forecast_method}")

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
    forecast_result["df_combined"].to_parquet(
        os.path.join(output_dir, "mc_combined.parquet")
    )

    if method == "markov":
        # Extra Markov outputs matching the legacy Excel sheets.
        # Row labels are moved into real columns because the API previews
        # and Excel export drop the DataFrame index.
        months = list(config.columns.months)
        year_col = config.columns.index
        pred_index = forecast_result["df_pred"].index

        forecast_result["transition_df"].rename_axis("Dari_State").reset_index().to_parquet(
            os.path.join(output_dir, "matriks_transisi.parquet"), index=False
        )
        pd.DataFrame(
            forecast_result["p_ext_wet"], columns=months, index=pred_index
        ).rename_axis(year_col).reset_index().to_parquet(
            os.path.join(output_dir, "prob_sangat_basah.parquet"), index=False
        )
        pd.DataFrame(
            forecast_result["p_ext_dry"], columns=months, index=pred_index
        ).rename_axis(year_col).reset_index().to_parquet(
            os.path.join(output_dir, "prob_sangat_kering.parquet"), index=False
        )
    print(f"Local files saved to {output_dir}")

    # 5. LOAD — Local PNG Plots
    print("--- 5. LOAD (Plots) ---")
    plots_dir = os.path.join(output_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    if method == "monte_carlo":
        # Generate standard MC plots (3 files)
        plot_forecast_time_series(
            forecast_result, os.path.join(plots_dir, "mc_time_series.png"), config=config
        )
        plot_forecast_heatmap(
            forecast_result, os.path.join(plots_dir, "mc_heatmap.png"),
            config, include_history=False, use_sample=True,
        )
        plot_forecast_heatmap(
            forecast_result, os.path.join(plots_dir, "mc_heatmap_combined.png"),
            config, include_history=True, use_sample=True,
        )
    elif method == "markov":
        # Generate Markov specific plots matching legacy visualizations
        from src.etl.load.plot_markov import plot_markov_time_series
        from src.etl.load.plot_ch_runoff_curve import plot_ch_runoff_curve

        plot_markov_time_series(
            forecast_result, os.path.join(plots_dir, "markov_time_series.png"), config=config
        )
        plot_ch_runoff_curve(
            config, os.path.join(plots_dir, "kurva_ch_runoff.png")
        )

    # ALWAYS generate Runoff plots (4 files) for BOTH methods
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
            forecast_result["df_combined"], "mc_combined", config,
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
            metrics=forecast_result["metrics"],
            config=config,
            runoff_scope=runoff_scope,
            forecast_method=method,
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
