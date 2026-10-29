import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from api.dependencies import get_warehouse_engine, get_s3_client

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])

CHUNK_SIZE = 64 * 1024  # 64 KB streaming chunks


# Content-type mapping for serving files
_EXT_TO_CONTENT_TYPE = {
    ".png":     "image/png",
    ".jpg":     "image/jpeg",
    ".jpeg":    "image/jpeg",
    ".parquet": "application/octet-stream",
    ".json":    "application/json",
    ".csv":     "text/csv",
    ".xlsx":    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _fetch_artifact_row(artifact_id: int) -> dict:
    """Load one row from the artifacts table (current schema, no content_type)."""
    engine = get_warehouse_engine()
    sql = text("""
        SELECT id, bucket, object_key, artifact_type,
               file_size_bytes, run_id, s3_uri, local_path
        FROM artifacts
        WHERE id = :id
    """)
    with engine.connect() as conn:
        row = conn.execute(sql, {"id": artifact_id}).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found")

    return dict(row)


def _guess_content_type(object_key: str) -> str:
    """Infer content type from file extension."""
    ext = os.path.splitext(object_key or "")[1].lower()
    return _EXT_TO_CONTENT_TYPE.get(ext, "application/octet-stream")


def _stream_s3_object(bucket: str, key: str):
    """Yield chunks from a MinIO object."""
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
    except s3.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail=f"Object not found in storage: {key}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")

    body = obj["Body"]

    def _iterator():
        try:
            while True:
                chunk = body.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk
        finally:
            body.close()

    return _iterator()


@router.get("/{artifact_id}/view")
def view_artifact(artifact_id: int):
    """Serve the artifact inline. Works for <img src=...> with PNGs."""
    row = _fetch_artifact_row(artifact_id)
    if not row["bucket"] or not row["object_key"]:
        raise HTTPException(status_code=404, detail="Artifact has no bucket/object_key")

    content_type = _guess_content_type(row["object_key"])
    filename = os.path.basename(row["object_key"])
    headers = {"Content-Disposition": f'inline; filename="{filename}"'}

    return StreamingResponse(
        _stream_s3_object(row["bucket"], row["object_key"]),
        media_type=content_type,
        headers=headers,
    )


@router.get("/{artifact_id}/download")
def download_artifact(artifact_id: int):
    """Serve the artifact as a download attachment."""
    row = _fetch_artifact_row(artifact_id)
    if not row["bucket"] or not row["object_key"]:
        raise HTTPException(status_code=404, detail="Artifact has no bucket/object_key")

    content_type = _guess_content_type(row["object_key"])
    filename = os.path.basename(row["object_key"])
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(
        _stream_s3_object(row["bucket"], row["object_key"]),
        media_type=content_type,
        headers=headers,
    )

@router.get("/{artifact_id}/excel")
def download_artifact_as_excel(artifact_id: int):
    """Convert a .parquet artifact to .xlsx and stream it as a download.

    Works for any parquet artifact (mc_combined, runoff_details, rekap_tahunan,
    rekap_bulanan). The Excel file has two sheets:
        - "Data"     : the full parquet contents
        - "Metadata" : source info (artifact id, run_id, row/column counts)

    Raises 400 for non-parquet artifacts (PNG, JSON, etc.) — those should
    use /download instead.
    """
    import io
    import pandas as pd

    row = _fetch_artifact_row(artifact_id)
    if not row["bucket"] or not row["object_key"]:
        raise HTTPException(status_code=404, detail="Artifact has no bucket/object_key")

    object_key = row["object_key"]
    if not object_key.lower().endswith(".parquet"):
        raise HTTPException(
            status_code=400,
            detail=f"Only .parquet artifacts can be converted to Excel (got: {object_key})",
        )

    # ── Fetch parquet from MinIO ──
    s3 = get_s3_client()
    try:
        obj = s3.get_object(Bucket=row["bucket"], Key=object_key)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Storage error: {e}")

    parquet_buf = io.BytesIO(obj["Body"].read())
    df = pd.read_parquet(parquet_buf)

    # ── Build the Excel in memory ──
    xlsx_buf = io.BytesIO()
    with pd.ExcelWriter(xlsx_buf, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Data", index=False)

        meta = pd.DataFrame([
            {"key": "source_artifact_id", "value": str(row["id"])},
            {"key": "source_object_key",  "value": object_key},
            {"key": "source_run_id",      "value": str(row.get("run_id", ""))},
            {"key": "row_count",          "value": str(len(df))},
            {"key": "column_count",       "value": str(len(df.columns))},
        ])
        meta.to_excel(writer, sheet_name="Metadata", index=False)

    xlsx_buf.seek(0)

    base = os.path.splitext(os.path.basename(object_key))[0]
    filename = f"{base}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(
        xlsx_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )