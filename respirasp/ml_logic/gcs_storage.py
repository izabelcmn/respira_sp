from pathlib import Path
from google.cloud import storage


def upload_file_to_gcs(
    local_path: Path,
    bucket_name: str,
    destination_blob_name: str,
) -> None:
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
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    blobs = list(bucket.list_blobs(prefix=prefix))

    matching_blobs = [
        blob for blob in blobs
        if Path(blob.name).name.startswith(filename_prefix)
        and Path(blob.name).suffix == ".csv"
    ]

    if not matching_blobs:
        raise FileNotFoundError(
            f"No file starting with {filename_prefix} found in gs://{bucket_name}/{prefix}"
        )

    latest_blob = sorted(matching_blobs, key=lambda blob: blob.name)[-1]

    destination_dir.mkdir(parents=True, exist_ok=True)
    local_path = destination_dir / Path(latest_blob.name).name

    latest_blob.download_to_filename(str(local_path))

    return local_path
