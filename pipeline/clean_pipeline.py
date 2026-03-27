# clean_pipeline.py
from numpy import datetime_data
import pandas as pd
from config import S3_BUCKET, DATA_INPUT_PATHS, CURATED_BASE_PATH, CURATED_REJECTED_PATH,COLUMN_SCHEMA
from .utils.utils_pipeline import normalize_units, remove_duplicates_and_nan,prepare_for_mongo,cast_types_from_schema
from .utils.s3_utils import save_jsonl_to_s3, list_s3_files, write_s3_csv, read_s3_csv, read_s3_json
from pathlib import Path


def clean_path_pro(bucket: str, input_path_folder: str, output_subfolder: str):
    files = list_s3_files(bucket, input_path_folder)
    cleaned_dfs = []
    rejected_dfs = []
    rejected_keys = []

    for file_key in files:
        if file_key.endswith(("/", ".tmp")):  # ignore dossiers/temp
            continue

        ext = Path(file_key).suffix
        df = read_s3_csv(bucket, file_key) if ext == ".csv" else read_s3_json(bucket, file_key)

       
        # --- Normalisation ---
        df = normalize_units(df)
    
        # --- Validation + Deduplication ---
        valid_df, rejected_df = remove_duplicates_and_nan(df)
       
         # --- Préparation pour Mongo ---
        valid_df = cast_types_from_schema(valid_df, COLUMN_SCHEMA)  # 👈 ICI
     

        # --- Préparation pour Mongo ---
        valid_df = prepare_for_mongo(valid_df)
        if not rejected_df.empty:
            rejected_df = prepare_for_mongo(rejected_df)
       
        # --- Construction des chemins S3 ---
        relative_key = "/".join(file_key.split("/")[2:])
        out_key = f"{output_subfolder}/{relative_key}"

        # --- Écriture valides ---
        if ext in [".json", ".jsonl"]:
            save_jsonl_to_s3(valid_df, bucket, out_key)
        else:
            write_s3_csv(valid_df, bucket, out_key)

        # --- Écriture rejetés ---
        rejected_key = None
        if not rejected_df.empty:
            rejected_key = out_key.replace(CURATED_BASE_PATH, CURATED_REJECTED_PATH)
            save_jsonl_to_s3(rejected_df, bucket, rejected_key)
            rejected_dfs.append(rejected_df)
            rejected_keys.append(rejected_key)

        cleaned_dfs.append(valid_df)

    return cleaned_dfs, rejected_dfs, rejected_keys


def run():
    all_valid, all_rejected, all_rejected_keys = [], [], []
    for input_path_folder in DATA_INPUT_PATHS:
        valid, rejected, rejected_keys = clean_path_pro(S3_BUCKET, input_path_folder, CURATED_BASE_PATH)
        all_valid.extend(valid)
        all_rejected.extend(rejected)
        all_rejected_keys.extend(rejected_keys)
    return all_valid, all_rejected, all_rejected_keys


if __name__ == "__main__":
    run()