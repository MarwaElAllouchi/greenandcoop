# load.py
import pandas as pd
from config import S3_BUCKET, MONGO_LOAD_JOBS
from utils.s3_utils import read_s3_csv, read_s3_json, list_s3_files, write_s3_csv
from utils.mongo.mongo_utils import get_collection
from utils.logger import log_info, log_error
import time

def load_one_job(job):
    """
    Charge tous les fichiers d'un dossier S3 pour un job spécifique dans MongoDB.
    Sépare les records valides et rejetés selon les colonnes requises.
    """
    s3_prefix = job["s3_key"]
    collection_name = job["collection"]
    fmt = job["format"]
    required_cols = job.get("required_columns", [])

    files = list_s3_files(S3_BUCKET, s3_prefix)
    all_valid, all_rejected = [], []
    rejected_s3_path = f"curated/rejected/{collection_name}_rejected.csv"

    log_info(f"[LOAD] Traitement job '{collection_name}' avec {len(files)} fichiers")

    for file_key in files:
        if fmt == "csv" and file_key.endswith(".csv"):
            df = read_s3_csv(S3_BUCKET, file_key)
        elif fmt in ["json", "jsonl"] and file_key.endswith((".json", ".jsonl")):
            df = read_s3_json(S3_BUCKET, file_key)
        else:
            continue

        # Validation des colonnes requises
        valid_records, rejected_records = [], []
        for record in df.to_dict(orient="records"):
            if all(record.get(c) is not None for c in required_cols):
                valid_records.append(record)
            else:
                rejected_records.append(record)

        all_valid.extend(valid_records)
        all_rejected.extend(rejected_records)

    # Insertion MongoDB (overwrite)
    if all_valid:
        start_conn = time.time()
        collection = get_collection(collection_name)  # ← Attente automatique du PRIMARY ici
        conn_time = time.time() - start_conn
        log_info(f"[MONGO] Connexion établie en {conn_time:.3f} secondes")

        before_count = collection.count_documents({})
        log_info(f"[MONGO] Documents avant chargement : {before_count}")

        start_insert = time.time()
        collection.delete_many({})
        insert_result = collection.insert_many(all_valid)
        insert_time = time.time() - start_insert

        after_count = collection.count_documents({})
        log_info(f"[MONGO] {len(insert_result.inserted_ids)} documents insérés")
        log_info(f"[MONGO] Documents après chargement : {after_count}")
        log_info(f"[MONGO] Temps d’insertion : {insert_time:.3f} secondes")

    # Écriture fichiers rejetés
    if all_rejected:
        df_rejected = pd.DataFrame(all_rejected)
        write_s3_csv(df_rejected, S3_BUCKET, rejected_s3_path)
        log_info(f"[LOAD] {len(all_rejected)} documents rejetés écrits : s3://{S3_BUCKET}/{rejected_s3_path}")

    return all_valid, all_rejected, rejected_s3_path


def run():
    """
    Parcours tous les jobs définis dans config.MONGO_LOAD_JOBS.
    Retourne un rapport global.
    """
    total_valid, total_rejected, rejected_paths = [], [], []
    for job in MONGO_LOAD_JOBS:
        valid, rejected, rejected_s3 = load_one_job(job)
        total_valid.extend(valid)
        total_rejected.extend(rejected)
        rejected_paths.append(rejected_s3)

    log_info(f"[REPORT] TOTAL → Valides: {len(total_valid)}, Rejetés: {len(total_rejected)}")
    return {
        "total_valid": len(total_valid),
        "total_rejected": len(total_rejected),
        "rejected_paths": rejected_paths
    }


if __name__ == "__main__":
    run()
