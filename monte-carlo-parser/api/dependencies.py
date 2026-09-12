import os
from functools import lru_cache

import boto3
from botocore.client import Config as BotoConfig
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

@lru_cache(maxsize=1)
def get_warehouse_engine() -> Engine:
    """SQLAlchemy engine for the warehouse Postgres (cached)."""
    user = os.environ["WAREHOUSE_DB_USER"]
    password = os.environ["WAREHOUSE_DB_PASSWORD"]
    name = os.environ["WAREHOUSE_DB_NAME"]
    host = os.environ.get("WAREHOUSE_DB_HOST", "warehouse-postgres")
    port = int(os.environ.get("WAREHOUSE_DB_PORT", "5432"))

    # Get the URL
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
    return create_engine(url)

@lru_cache(maxsize=1)
def get_s3_client():
    """boto3 S3 client pointed at MinIO (cached)."""
    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    access = os.environ["MINIO_ROOT_USER"]
    secret = os.environ["MINIO_ROOT_PASSWORD"]
    return boto3.client(
        "s3",
        endpoint_url=f"http://{endpoint}",
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",
    )