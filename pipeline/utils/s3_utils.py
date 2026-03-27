import boto3
import pandas as pd
import io
import time
from .logger import log_info, log_error
from botocore.exceptions import ClientError
import json
from io import StringIO, BytesIO
from pipeline.utils.logger import logger
s3 = boto3.client("s3")

def list_s3_files(bucket: str, prefix: str,
                  force_processing_date: str = None,
                  process_latest_only: bool = False,
                  source_name: str = "source") -> list:
  
    """
    Retourne la liste des keys S3 dans un dossier (prefix), avec contrôle de date.
    """
    keys = []

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            keys.append(obj["Key"])

    # --- Gestion date ---
    if force_processing_date:
        
        target_date = force_processing_date
    elif process_latest_only:
       
        # suppose que la date est dans le 3ème segment du path : prefix/date/...
        dates = sorted({f.split("/")[2] for f in keys if len(f.split("/")) > 2})
        target_date = dates[-1] if dates else None
           
    else:
        target_date = None 
       


    if target_date:
        keys = [f for f in keys if f"/{target_date}/" in f]

    log_info(f"[{source_name}] {len(keys)} fichiers à traiter (date={target_date})")
    return keys

def read_s3_text(bucket: str, key: str) -> str:
    """
    Lit un fichier texte (ex: JSONL) depuis S3 et retourne une string.
    """

    response = s3.get_object(Bucket=bucket, Key=key)
    return response["Body"].read().decode("utf-8")


def read_s3_csv(bucket: str, key: str) -> pd.DataFrame:
    """
    Lit un fichier CSV depuis S3 et retourne un DataFrame pandas.
    """


    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read().decode("utf-8")

    return pd.read_csv(StringIO(content))

def extract_from_csv(bucket, key):
    df = read_s3_csv(bucket, key)
    return df.to_dict(orient="records")

def extract_from_jsonl(bucket, key, airbyte=True):
    records = []
    lines = read_s3_text(bucket, key).splitlines()

    for line in lines:
        if not line.strip():
            continue

        obj = json.loads(line)

        if airbyte:
            data = obj.get("_airbyte_data")
            if data:
                records.append(data)
        else:
            records.append(obj)

    return records

   
def read_s3_json(bucket: str, key: str) -> pd.DataFrame:
    """
    Lit un fichier JSON ou JSONL depuis S3 et retourne un DataFrame pandas.
    Gère les JSON imbriqués ou non uniformes.
    """
    s3 = boto3.client("s3")
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        content = obj['Body'].read()

        # JSONL
        if key.endswith(".jsonl"):
            df = pd.read_json(BytesIO(content), lines=True)
            return df

        # JSON standard
        data = json.loads(content)
        
        # Si c'est un dict avec des sous-dicts ou des listes non uniformes, on normalise
        if isinstance(data, dict):
            # transform dict en DataFrame
            # Ici, on a besoin de "flatten" certaines colonnes si nécessaire
            # Exemple simple : convertir chaque clé en colonne et prendre la liste si existante
            df = pd.json_normalize(data, sep='_')
        elif isinstance(data, list):
            df = pd.json_normalize(data, sep='_')
        else:
            raise ValueError("Format JSON non supporté")

        return df
    except Exception as e:
        log_error(f"❌ Erreur lecture JSON S3 {key} : {e}")
        raise

def write_jsonl(df_or_records, bucket: str, key: str):
    """
    Écrit toutes sortes de données en JSONL sur S3.
    
    Args:
        df_or_records: DataFrame, dict, list[dict], JSON string
        bucket: bucket S3
        key: chemin S3
    """
    # --- Cas DataFrame ---
    if isinstance(df_or_records, pd.DataFrame):
        records = df_or_records.to_dict(orient="records")
    
    # --- Cas liste ---
    elif isinstance(df_or_records, list):
        # vérifier si c'est une liste de DataFrame
        if all(isinstance(x, pd.DataFrame) for x in df_or_records):
            records = []
            for df in df_or_records:
                records.extend(df.to_dict(orient="records"))
        else:
            records = df_or_records
    
    # --- Cas dict ---
    elif isinstance(df_or_records, dict):
        records = [df_or_records]
    
    # --- Cas string JSON ---
    elif isinstance(df_or_records, str):
        parsed = json.loads(df_or_records)
        if isinstance(parsed, dict):
            records = [parsed]
        elif isinstance(parsed, list):
            records = parsed
        else:
            raise TypeError(f"String JSON doit être un dict ou une liste de dicts, reçu: {type(parsed)}")
    
    # --- Cas interdit ---
    else:
        raise TypeError(f"Type de données non supporté : {type(df_or_records)}")

    # --- Conversion en JSONL ---
    jsonl_data = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)

    # --- Écriture sur S3 ---
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=jsonl_data.encode("utf-8")
    )

    log_info(f"✅ JSONL écrit dans s3://{bucket}/{key} ({len(records)} enregistrements)")

def save_jsonl_to_s3(df, bucket, key):
    out_buffer = BytesIO()
    df.to_json(out_buffer, orient="records", lines=True, force_ascii=False)
    out_buffer.seek(0)
    s3.put_object(Bucket=bucket, Key=key, Body=out_buffer.getvalue())
    log_info(f"✅ Sauvegardé: s3://{bucket}/{key}")

def write_s3_csv(df, bucket, key, encoding="utf-8"):
    """
    Écrit un DataFrame Pandas en CSV dans S3
    """
    s3 = boto3.client("s3")

    buffer = StringIO()
    df.to_csv(buffer, index=False, encoding=encoding)

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=buffer.getvalue()
    )
    """Écrit un CSV dans S3"""
    csv_buffer = df.to_csv(index=False)
    s3.put_object(Bucket=bucket, Key=key, Body=csv_buffer)

def write_s3_txt(bucket: str, key: str,text: str):
    """
    Écrit une chaîne de texte dans un fichier S3.
    
    Args:
        text (str): Le contenu à écrire.
        bucket (str): Nom du bucket S3.
        key (str): Chemin complet du fichier S3 (ex: "logs/myfile.txt").
    """
    try:
        s3.put_object(Bucket=bucket, Key=key, Body=text.encode("utf-8"))
        log_info(f"✅ Fichier texte écrit dans s3://{bucket}/{key}")
    except Exception as e:
        log_error(f"❌ Erreur lors de l'écriture sur S3 : {e}")

def save_logs_s3(bucket, path="pipeline_logs/pipeline.log"):
    with open("pipeline.log", "r") as f:
        content = f.read()
    write_s3_txt(bucket, path, content)
    log_info(f"✅ Logs enregistrés sur S3 : {path}")

def upload_file_to_s3(bucket: str, local_path: str, s3_key: str):
    """
    Upload d'un fichier local vers S3.
    - bucket : nom du bucket S3
    - local_path : chemin local du fichier
    - s3_key : chemin dans S3
    """
    try:
        s3.upload_file(Filename=local_path, Bucket=bucket, Key=s3_key)
        log_info(f"✅ Fichier uploadé sur S3 : s3://{bucket}/{s3_key}")
    except ClientError as e:
        log_error(f"❌ Erreur upload S3 : {e}")
        raise e