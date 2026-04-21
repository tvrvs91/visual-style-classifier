import logging

import boto3
from botocore.client import Config

from .config import settings

log = logging.getLogger(__name__)


def build_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def download_bytes(bucket: str, key: str) -> bytes:
    client = build_client()
    obj = client.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read()
    log.info("Downloaded %s/%s (%d bytes)", bucket, key, len(data))
    return data
