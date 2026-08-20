import os
import sys
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from etl.transform import transform
from utils.das_monte_carlo import generate_das_report
from utils.schemas import DASSimulationRequest

 
def _is_interactive_backend() -> bool:
    """Backend non-GUI (Agg, pdf, svg, ps, cairo, dst) cuma bisa nulis ke
    file dan nggak bisa munculin window -- plt.show() di backend itu cuma
    keluar warning tanpa efek. Kalau kita deteksi backend non-GUI, skip
    plt.show() dan andalkan file yang disimpan lewat savefig() saja.
    """
    non_interactive = {"agg", "pdf", "svg", "ps", "cairo", "template"}
    return matplotlib.get_backend().lower() not in non_interactive


def load(result=None, file_path=None, manual_data=None, forecast_years=None, overrides=None):
    if result is None:
        result = transform(
            file_path=file_path,
            manual_data=manual_data,
            forecast_years=forecast_years,
            overrides=overrides,
        )

    if not result:
        print("No data to load!")
        return

    config = result['config']
    df_combined = result['df_combined']
    df_pred = result['df_pred']
    ts_hist = result['ts_hist']
    ts_pred = result['ts_pred']
    ts_pred_conn = result['ts_pred_conn']

    output_file = config.data.processed_path
    output_dir = os.path.dirname(os.path.abspath(output_file))
    os.makedirs(output_dir, exist_ok=True)

    show_plots = _is_interactive_backend()

    fig1 = plt.figure(figsize=(16, 7))
    plt.plot(ts_hist['Tanggal'], ts_hist['Nilai'], color='#1f77b4', label='Data Historis', linewidth=1.2)

    plt.plot(ts_pred_conn['Tanggal'], ts_pred_conn['Nilai'], color='#d62728', linestyle='--', label='Prediksi Monte Carlo', linewidth=1.5)

    plt.axvspan(ts_pred['Tanggal'].min(), ts_pred['Tanggal'].max(), color='yellow', alpha=0.1)

    plt.title('Deret Waktu Bulanan: Historis vs Prediksi Monte Carlo', fontsize=14, fontweight='bold')
    plt.xlabel('Tahun')
    plt.ylabel('Nilai Bulanan')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend()
    plt.tight_layout()

    timeseries_path = os.path.join(output_dir, 'timeseries_plot.png')
    fig1.savefig(timeseries_path, dpi=120)
    print(f"Grafik deret waktu disimpan ke '{timeseries_path}'")
    if show_plots:
        plt.show()
    else:
        plt.close(fig1)

    fig2 = plt.figure(figsize=(14, 10))
    sns.heatmap(df_combined, annot=True, fmt=".1f", cmap="YlGnBu", cbar_kws={'label': 'Intensitas Nilai'})
    plt.title('Heatmap Pola Bulanan Historis dan Prediksi', fontsize=14)

    heatmap_path = os.path.join(output_dir, 'heatmap_plot.png')
    fig2.savefig(heatmap_path, dpi=120)
    print(f"Heatmap disimpan ke '{heatmap_path}'")
    if show_plots:
        plt.show()
    else:
        plt.close(fig2)

    das_input_df = df_pred.reset_index()

    das_excel_path = os.path.join(output_dir, 'Konversi_Curah_Hujan_DAS.xlsx')
    das_chart_path = os.path.join(output_dir, 'grafik_konversi_das.png')

    das_params: DASSimulationRequest = None
    
    # Default Numbers
    cn_val = 75.0
    area_val = 100.0
    n_trials_val = 500

    # Jika React mengirim data das_params, timpa nilai defaultnya
    if das_params:
        cn_val = das_params.cn_value
        area_val = das_params.area_km2
        n_trials_val = das_params.n_trials

    try:
        das_hasil = generate_das_report(
            data=das_input_df, 
            cn_value=cn_val,
            area_km2=area_val,
            n_trials=n_trials_val,
            output_excel=das_excel_path,
            output_chart=das_chart_path
        )
        print(f"Laporan & Grafik DAS berhasil dibuat di:\n- {das_excel_path}\n- {das_chart_path}")
    except Exception as e:
        print(f"Gagal membuat laporan DAS: {e}")

    metrics_path = os.path.join(output_dir, 'metrics.json')
    with open(metrics_path, "w") as f:
        json.dump(result['metrics'], f)

    metadata_dict = {
        "forecast_years": config.monte_carlo.forecast_years,
        "random_seed": config.monte_carlo.random_seed
    }

    if das_hasil and 'das_parameters' in das_hasil:
        metadata_dict['das_parameters'] = das_hasil['das_parameters']

    metadata_path = os.path.join(output_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump({
            "forecast_years": config.monte_carlo.forecast_years,
            "random_seed": config.monte_carlo.random_seed,
            "das_parameters": das_hasil['das_parameters']
        }, f)
    if output_file.endswith('.csv'):
        df_combined.to_csv(output_file, index=True)
    else:
        df_combined.to_excel(output_file, index=True)

    pred_output_path = os.path.join(output_dir, 'das_monte_carlo.csv')
    das_input_df.to_csv(pred_output_path, index=False)
    print(f"Data prediksi (Monte Carlo only) disimpan ke '{pred_output_path}'")

    print(f"Finish! File '{output_file}' successfully created.")