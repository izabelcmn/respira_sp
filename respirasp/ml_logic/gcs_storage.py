import json
from pathlib import Path
from typing import Any

from google.cloud import storage


def upload_file_to_gcs(
    local_path: Path,
    bucket_name: str,
    destination_blob_name: str,
) -> None:
    """Upload a local file to Google Cloud Storage."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(str(local_path))


def download_latest_matching_file_from_gcs(
    bucket_name: str,
    prefix: str,
    filename_prefix: str,
    destination_dir: Path,
) -> Path:
    """Download the latest matching CSV object from Google Cloud Storage."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    normalized_prefix = prefix.rstrip("/") + "/"
    blobs = list(bucket.list_blobs(prefix=normalized_prefix))

    matching_blobs = [
        blob
        for blob in blobs
        if Path(blob.name).name.startswith(filename_prefix)
        and Path(blob.name).suffix.lower() == ".csv"
    ]

    if not matching_blobs:
        raise FileNotFoundError(
            f"No CSV starting with '{filename_prefix}' was found in "
            f"gs://{bucket_name}/{normalized_prefix}"
        )

    latest_blob = max(matching_blobs, key=lambda blob: blob.name)

    destination_dir.mkdir(parents=True, exist_ok=True)
    local_path = destination_dir / Path(latest_blob.name).name

    latest_blob.download_to_filename(str(local_path))

    return local_path


def upload_json_to_gcs(
    payload: dict[str, Any],
    bucket_name: str,
    destination_blob_name: str,
) -> None:
    """Serialize a dictionary as JSON and upload it to Cloud Storage."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_string(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
        ),
        content_type="application/json; charset=utf-8",
    )


def download_json_from_gcs(
    bucket_name: str,
    blob_name: str,
) -> dict[str, Any]:
    """Download and deserialize a JSON object from Cloud Storage."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    if not blob.exists(client=client):
        raise FileNotFoundError(
            f"Object gs://{bucket_name}/{blob_name} was not found."
        )

    content = blob.download_as_text(encoding="utf-8")
    payload = json.loads(content)

    if not isinstance(payload, dict):
        raise ValueError(
            f"Object gs://{bucket_name}/{blob_name} does not contain "
            "a JSON object."
        )

    return payload
