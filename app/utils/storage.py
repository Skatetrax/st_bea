"""DigitalOcean Spaces (S3-compatible) helpers for audio file storage."""

import os
import boto3
from botocore.exceptions import ClientError

_ENDPOINT = os.environ.get("DO_SPACES_ENDPOINT", "https://nyc3.digitaloceanspaces.com")
_BUCKET = os.environ.get("DO_SPACES_BUCKET", "")
_KEY = os.environ.get("DO_SPACES_KEY", "")
_SECRET = os.environ.get("DO_SPACES_SECRET", "")
_CDN_ENDPOINT = os.environ.get("DO_SPACES_CDN_ENDPOINT", "")


def _client():
    return boto3.client(
        "s3",
        region_name="nyc3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_KEY,
        aws_secret_access_key=_SECRET,
    )


def is_configured():
    return bool(_BUCKET and _KEY and _SECRET)


def upload_file(file_obj, key, content_type="audio/mpeg"):
    client = _client()
    client.upload_fileobj(
        file_obj,
        _BUCKET,
        key,
        ExtraArgs={"ContentType": content_type, "ACL": "public-read"},
    )


def delete_file(key):
    try:
        _client().delete_object(Bucket=_BUCKET, Key=key)
    except ClientError:
        pass


def get_public_url(key):
    if not is_configured():
        return f"/music_dev/{key}"
    if _CDN_ENDPOINT:
        return f"{_CDN_ENDPOINT.rstrip('/')}/{key}"
    return f"{_ENDPOINT.rstrip('/')}/{_BUCKET}/{key}"
