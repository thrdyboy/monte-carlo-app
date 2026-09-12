# src/etl/load/load_to_minio.py
import os
import sys
from typing import Optional, Any

import boto3
from botocore.client import Config as BotoConfig

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from src.config.settings import load_config


def _get_s3_client(config: Optional[Any] = None):
    """Build a boto3 S3 client pointed at MinIO."""
    if config is None:
        config = load_config()

    scheme = "https" if config.minio.secure else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{config.minio.endpoint}",
        aws_access_key_id=config.minio.access_key,
        aws_secret_access_key=config.minio.secret_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )


def upload_file_to_minio(
    local_path: str,
    object_key: str,
    bucket: str,
    config: Optional[Any] = None,
) -> dict:
    """Upload a single file and return its metadata."""
    if config is None:
        config = load_config()

    s3 = _get_s3_client(config)
    s3.upload_file(local_path, bucket, object_key)

    return {
        "bucket": bucket,
        "key": object_key,
        "size_bytes": os.path.getsize(local_path),
        "local_path": local_path,
        "s3_uri": f"s3://{bucket}/{object_key}",
    }


def upload_run_artifacts(
    output_dir: str,
    run_id: str,
    config: Optional[Any] = None,
) -> list:
    """Upload all .parquet and .png files from a run directory to MinIO.

    Organizes by run_id prefix:
        mc-parquet/runs/<run_id>/mc_combined.parquet
        mc-plots/runs/<run_id>/mc_heatmap.png
    """
    if config is None:
        config = load_config()

    uploaded = []

    # Parquet files
    for fname in sorted(os.listdir(output_dir)):
        if fname.endswith(".parquet"):
            local = os.path.join(output_dir, fname)
            key = f"runs/{run_id}/{fname}"
            meta = upload_file_to_minio(local, key, config.minio.bucket_parquet, config)
            uploaded.append({**meta, "artifact_type": "parquet"})

    # Plot PNGs
    plots_dir = os.path.join(output_dir, "plots")
    if os.path.isdir(plots_dir):
        for fname in sorted(os.listdir(plots_dir)):
            if fname.endswith(".png"):
                local = os.path.join(plots_dir, fname)
                key = f"runs/{run_id}/{fname}"
                meta = upload_file_to_minio(local, key, config.minio.bucket_plots, config)
                uploaded.append({**meta, "artifact_type": "png"})

    return uploaded