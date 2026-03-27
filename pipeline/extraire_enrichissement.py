# enrichissement.py
from config import (
    S3_BUCKET,
    SOURCES,
    FORCE_PROCESSING_DATE,
    PROCESS_LATEST_ONLY
)
from .utils.path_manager import PathManager
from .utils.utils_pipeline import add_station_metadata
from .utils.s3_utils import extract_from_csv, extract_from_jsonl, write_jsonl, list_s3_files
from .utils.validators import is_valid_record

pm = PathManager(bucket=S3_BUCKET)


def extraire_enrich_source(source_name: str,
                            airbyte: bool = True,
                            add_metadata: bool = True,
                            required_fields: list = None):
    """
    Parcourt tous les fichiers d'une source, extrait les données,
    ajoute les métadonnées et écrit valides et rejetés sur S3.
    """
    cfg = SOURCES[source_name]
    prefix = cfg["raw_path"]
    bucket = S3_BUCKET

    files = list_s3_files(
        bucket,
        prefix,
        force_processing_date=FORCE_PROCESSING_DATE,
        process_latest_only=PROCESS_LATEST_ONLY,
        source_name=source_name
    )

    all_valid, all_rejected, all_rejected_keys = [], [], []

    for file_key in files:
        if file_key.endswith("/"):
            continue
        station_key = file_key.split("/")[-2]

        fmt = "csv" if file_key.endswith(".csv") else "jsonl"

        records = extract_from_csv(bucket, file_key) if fmt == "csv" else extract_from_jsonl(bucket, file_key, airbyte)

        valid_records, rejected_records = [], []
        for r in records:
            if add_metadata:
                r = add_station_metadata(r, station_key)
            if is_valid_record(r, required_fields):
                valid_records.append(r)
            else:
                rejected_records.append(r)

        # Chemins S3
        if valid_records:
            output_key = pm.generate_path(file_key, stage="staging")
            write_jsonl(valid_records, bucket, output_key)

        rejected_key = None
        if rejected_records:
            rejected_key = pm.generate_rejected_path(file_key, stage="staging/rejected")
            write_jsonl(rejected_records, bucket, rejected_key)

        all_valid.extend(valid_records)
        all_rejected.extend(rejected_records)
        if rejected_key:
            all_rejected_keys.append(rejected_key)

    return all_valid, all_rejected, all_rejected_keys


def run_pipeline(sources=SOURCES):
    total_valid, total_rejected, all_rejected_keys = [], [], []
    for source in sources:
        valid, rejected, rejected_keys = extraire_enrich_source(source)
        total_valid.extend(valid)
        total_rejected.extend(rejected)
        all_rejected_keys.extend(rejected_keys)
    return total_valid, total_rejected, all_rejected_keys


if __name__ == "__main__":
    run_pipeline()
