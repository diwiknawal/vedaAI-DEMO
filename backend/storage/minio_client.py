"""
Veda AI — MinIO Storage Client
S3-compatible object storage running locally via Docker.

Object key conventions:
  uploads/{job_id}/original.{ext}
  processed/{job_id}/transcoded.mp4
  thumbnails/{job_id}/scene_{n}.jpg
  clips/{job_id}/{clip_id}_{platform}.mp4
  transcripts/{job_id}/transcript.json
"""
import boto3
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Optional
import logging

from config import settings

logger = logging.getLogger(__name__)


def _make_client():
    return boto3.client(
        "s3",
        endpoint_url=f"{'https' if settings.minio_secure else 'http'}://{settings.minio_endpoint}",
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=BotoConfig(signature_version="s3v4"),
        region_name="us-east-1",   # MinIO ignores this but boto3 requires it
    )


_client = None


def get_client():
    global _client
    if _client is None:
        _client = _make_client()
    return _client


_public_client = None


def get_public_client():
    """Returns a client configured with the public URL for presigned generation."""
    global _public_client
    if _public_client is None:
        if settings.minio_public_url:
            _public_client = boto3.client(
                "s3",
                endpoint_url=settings.minio_public_url,
                aws_access_key_id=settings.minio_access_key,
                aws_secret_access_key=settings.minio_secret_key,
                config=BotoConfig(signature_version="s3v4"),
                region_name="us-east-1",
            )
        else:
            _public_client = get_client()
    return _public_client


def ensure_bucket():
    """Create the bucket if it doesn't already exist."""
    client = get_client()
    try:
        client.head_bucket(Bucket=settings.minio_bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            client.create_bucket(Bucket=settings.minio_bucket)
            logger.info(f"Created MinIO bucket: {settings.minio_bucket}")
        else:
            raise


def upload_file(local_path: str | Path, object_key: str) -> str:
    """
    Upload a local file to MinIO.
    Returns the object key (use `get_presigned_url` to serve it).
    """
    client = get_client()
    client.upload_file(str(local_path), settings.minio_bucket, object_key)
    logger.info(f"Uploaded {local_path} → minio://{settings.minio_bucket}/{object_key}")
    return object_key


def download_file(object_key: str, local_path: str | Path) -> Path:
    """Download an object from MinIO to a local path."""
    client = get_client()
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    client.download_file(settings.minio_bucket, object_key, str(local_path))
    logger.info(f"Downloaded minio://{settings.minio_bucket}/{object_key} → {local_path}")
    return Path(local_path)


def upload_bytes(data: bytes, object_key: str, content_type: str = "application/octet-stream") -> str:
    """Upload raw bytes directly to MinIO (useful for JSON/text files)."""
    import io
    client = get_client()
    client.upload_fileobj(
        io.BytesIO(data),
        settings.minio_bucket,
        object_key,
        ExtraArgs={"ContentType": content_type},
    )
    return object_key


def get_presigned_url(object_key: str, expires_in: int = 3600) -> str:
    """Generate a pre-signed URL for temporary public access."""
    client = get_public_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": object_key},
        ExpiresIn=expires_in,
    )


def delete_object(object_key: str):
    """Delete a single object."""
    client = get_client()
    client.delete_object(Bucket=settings.minio_bucket, Key=object_key)


def object_exists(object_key: str) -> bool:
    client = get_client()
    try:
        client.head_object(Bucket=settings.minio_bucket, Key=object_key)
        return True
    except ClientError:
        return False


# ── Convenience key builders ──────────────────────────────────────────────────

def upload_key(job_id: str, ext: str) -> str:
    return f"uploads/{job_id}/original.{ext}"

def processed_key(job_id: str) -> str:
    return f"processed/{job_id}/transcoded.mp4"

def transcript_key(job_id: str) -> str:
    return f"transcripts/{job_id}/transcript.json"

def thumbnail_key(job_id: str, scene_index: int) -> str:
    return f"thumbnails/{job_id}/scene_{scene_index:04d}.jpg"

def clip_key(job_id: str, clip_id: str, platform: str) -> str:
    return f"clips/{job_id}/{clip_id}_{platform}.mp4"
