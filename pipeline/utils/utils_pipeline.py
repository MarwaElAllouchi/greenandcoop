import json 
import pandas as pd
import numpy as np
import unicodedata
from .logger import log_info, log_error
from .s3_utils import list_s3_files,extract_from_csv,extract_from_jsonl
import re
from config import STATIONS_METADATA,STANDARD_COLS,COLUMN_MAPPING,UNIT_CONVERSIONS,UNIT_COLUMNS

def extract_records_from_s3(
    bucket: str,
    prefix: str,
    file_type: str = "auto",  # "csv", "jsonl", "auto"
    airbyte: bool = True
):
    """
    Parcourt un dossier S3 et extrait les données réelles.
    """
    records = []

    files = list_s3_files(bucket, prefix)

    for key in files:
        if key.endswith("/"):
            continue

        if file_type == "auto":
            if key.endswith(".csv"):
                fmt = "csv"
            elif key.endswith(".jsonl") or key.endswith(".json"):
                fmt = "jsonl"
            else:
                continue
        else:
            fmt = file_type

        if fmt == "csv":
            records.extend(extract_from_csv(bucket, key))

        elif fmt == "jsonl":
            records.extend(extract_from_jsonl(bucket, key, airbyte))

    return records
def extract_station_folder(file_key: str) -> str | None:
    """
    Extrait le dossier station depuis un chemin S3
    """
    parts = file_key.split("/")
    for part in parts:
        if "_" in part and part[0].isupper():
            return part
    return None
# -----------------------------
# Ajout métadonnées station
# -----------------------------
def add_station_metadata(df, station_key):
    meta = STATIONS_METADATA.get(station_key, {})
    for k, v in meta.items():
        df[k] = v
    return df

def flatten_dict(d, parent_key="", sep="."):
    """
    Aplatit un dictionnaire imbriqué.

    Exemple :
    {'a': 1, 'b': {'c': 2}} → {'a': 1, 'b.c': 2}
    """
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def flatten_jsonl_file(input_path: str, output_path: str, sep="."):
    """
    Lit un fichier JSONL imbriqué et écrit un JSONL aplati.

    Args:
        input_path: chemin du JSONL d'entrée
        output_path: chemin du JSONL de sortie
        sep: séparateur pour les clés imbriquées
    """
    with open(input_path, "r", encoding="utf-8") as infile, \
         open(output_path, "w", encoding="utf-8") as outfile:
        for line in infile:
            if not line.strip():
                continue
            obj = json.loads(line)
            flat_obj = flatten_dict(obj, sep=sep)
            outfile.write(json.dumps(flat_obj, ensure_ascii=False) + "\n")

def flatten_dict(d, parent_key='', sep='_'):
    """Aplatit un dictionnaire imbriqué."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)

def harmonize_columns(df: pd.DataFrame) -> pd.DataFrame:

    # Normaliser les colonnes : tout en minuscules

    df.columns = df.columns.str.lower()
 
    out = pd.DataFrame()

    for src_col, target_col in COLUMN_MAPPING.items():
        if src_col in df.columns:
            if target_col not in out.columns:
                out[target_col] = df[src_col]
            else:
                out[target_col] = out[target_col].fillna(df[src_col])

    for col in STANDARD_COLS:
        if col not in out.columns:
            out[col] = None

    return out[STANDARD_COLS]

def normalize_units(
    df: pd.DataFrame,
    conversions: dict = UNIT_CONVERSIONS,
    unit_columns: list = UNIT_COLUMNS,
    inplace: bool = False
) -> pd.DataFrame:

    if not inplace:
        df = df.copy()




    for col in unit_columns:
        if col not in df.columns:
            continue

        if df[col].dtype != object:
            continue

    
        series = df[col]

        for unit, func in conversions.items():
            mask = series.str.contains(re.escape(unit), na=False)
            if mask.any():
             

                def convert_value(v):
                    try:
                        num = float(
                            re.findall(r"[-+]?[0-9]*\.?[0-9]+", str(v))[0]
                        )
                        return func(num)
                    except Exception:
                        return None

                df.loc[mask, col] = series[mask].map(convert_value)

        df[col] = pd.to_numeric(df[col], errors="coerce")


    return df

def remove_duplicates_and_nan(
    df: pd.DataFrame,
    dedup_subset=STANDARD_COLS,           # colonnes à considérer pour la déduplication
    required_fields=("station_id", "datetime_utc")
):
    
    df = df.copy()
    
    # 1️⃣ Rejet si les DEUX champs obligatoires sont absents
    mask_valid = pd.Series(True, index=df.index)
    
    # Créer un masque où les deux champs sont manquants
    both_missing_mask = df[required_fields[0]].isna() & df[required_fields[1]].isna()
    mask_valid &= ~both_missing_mask  # True = ligne valide, False = ligne à rejeter
    
    # Conversion datetime si present
    if "datetime_utc" in df.columns:
        parsed = pd.to_datetime(df["datetime_utc"], errors="coerce")
        # les lignes déjà rejetées restent rejetées
        mask_valid &= parsed.notna() | ~both_missing_mask  
        df["datetime_utc"] = parsed

    # Séparer lignes valides et rejetées initiales
    initial_valid_df = df[mask_valid].copy()
    rejected_df = df[~mask_valid].copy()

    # 2️⃣ Rejet doublons exacts (toutes les colonnes)
    before = len(initial_valid_df)
    duplicates_mask = initial_valid_df.duplicated(keep=False)  # True = doublon exact
    rejected_duplicates = initial_valid_df[duplicates_mask].copy()
    valid_df = initial_valid_df[~duplicates_mask].copy()
    after = len(valid_df)

    log_info(f"[CLEAN] Deduplication complète : {before} → {after}")

    # Ajouter doublons exacts aux rejetés
    rejected_df = pd.concat([rejected_df, rejected_duplicates], ignore_index=True)

    return valid_df, rejected_df


def prepare_for_mongo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare un DataFrame pour MongoDB :
    - NaN → None
    - Ne touche pas aux types déjà castés
    """

    df = df.copy()
    for c in df.columns:
        df[c] = df[c].where(pd.notna(df[c]), None)
    return df

def cast_types_from_schema(df: pd.DataFrame, schema: dict) -> pd.DataFrame:
    """
    Cast toutes les colonnes d'un DataFrame selon un schéma configurable.
    - Supporte int, float, string, timestamp (datetime lisible + timestamp ms)
    - Remplace NaN par None pour compatibilité MongoDB

    Arguments :
        df : pd.DataFrame
        schema : dict {colonne: type_str}, type_str ∈ ["int", "float", "string", "timestamp_ms"]
    """
    df = df.copy()

    for col, col_type in schema.items():
        if col not in df.columns:
            continue

        if col_type == "int":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

        elif col_type == "float":
            df[col] = pd.to_numeric(df[col], errors="coerce")

        elif col_type == "string":
            df[col] = df[col].astype(str)
            df[col] = df[col].replace({"nan": None, "NaN": None})  # convertir NaN en None

        elif col_type == "timestamp_ms":
            # Conversion datetime lisible
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
            # Création colonne timestamp en millisecondes
            ts_col = col + "_ts"
            df[ts_col] = df[col].apply(lambda x: x.isoformat() if pd.notnull(x) else None)
       

    # Conversion finale NaN → None pour compatibilité MongoDB
    for c in df.columns:
        df[c] = df[c].where(pd.notna(df[c]), None)

    return df

# -------------------------------------------------
# Normalisation robuste des noms de colonnes
# -------------------------------------------------
def normalize_column(name: str) -> str:
    name = name.lower()

    # Espaces et points → _
    name = re.sub(r"[ .]+", "_", name)

    # Suppression des accents
    name = "".join(
        c for c in unicodedata.normalize("NFD", name)
        if unicodedata.category(c) != "Mn"
    )

    # Suppression caractères spéciaux
    name = re.sub(r"[^a-z0-9_]", "", name)

    # Nettoyage des underscores multiples
    name = re.sub(r"_+", "_", name)

    return name.strip("_")