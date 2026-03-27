# transform.py
import boto3
import json
import pandas as pd
from .utils.utils_pipeline import flatten_dict, harmonize_columns
from  config import S3_BUCKET, STAGING_PREFIX, TRANSFORM_PREFIX, FLATTEN_KEYS
from .utils.s3_utils import save_jsonl_to_s3

s3 = boto3.client("s3")


def flatten_weather_json_readable(data: dict):
    records = []
    top_record = data.copy()
    for fk in FLATTEN_KEYS:
        if fk in top_record and isinstance(top_record[fk], dict):
            top_record.update(flatten_dict(top_record[fk], parent_key=fk))
            del top_record[fk]

    stations = data.get("stations", [])
    for station_id, hours in data.get("hourly", {}).items():
        station_info = next((s for s in stations if s.get("id") == station_id), {})
        for hour_entry in hours:
            if hour_entry is None: continue
            if isinstance(hour_entry, str):
                try:
                    hour_entry = json.loads(hour_entry)
                except json.JSONDecodeError:
                    continue
            if not isinstance(hour_entry, dict): continue

            record = {
                "station_id": hour_entry.get("id_station", station_id),
                "datetime_utc": hour_entry.get("dh_utc")
            }
            for k, v in hour_entry.items():
                if k not in ["id_station", "dh_utc"]:
                    record[k] = v
            record["station_name"] = station_info.get("name")
            record["latitude"] = station_info.get("latitude")
            record["longitude"] = station_info.get("longitude")
            record["elevation"] = station_info.get("elevation")
            record["type"] = station_info.get("type")
            license_info = station_info.get("license", {})
            record["license"] = license_info.get("license")
            record["license_source"] = license_info.get("source")
            record["license_url"] = license_info.get("url")
            records.append(record)
    return pd.DataFrame(records)


def process_json_file(bucket, key, flatten_keys=None):
    obj = s3.get_object(Bucket=bucket, Key=key)
    content = obj["Body"].read().decode("utf-8")
    records = []

    if key.endswith(".jsonl"):
        for line in content.splitlines():
            if not line.strip(): continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "hourly" in row:
                df_line = flatten_weather_json_readable(row)
                records.extend(df_line.to_dict(orient="records"))
            else:
                if flatten_keys:
                    for fk in flatten_keys:
                        if fk in row and isinstance(row[fk], dict):
                            row.update(flatten_dict(row[fk], parent_key=fk))
                            del row[fk]
                records.append(row)
        df = pd.DataFrame(records)
    else:
        data = json.loads(content)
        if isinstance(data, dict) and "hourly" in data:
            df = flatten_weather_json_readable(data)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = pd.json_normalize(data)
    return df


def merge_staging_s3(bucket, prefix, output_prefix, flatten_keys=None):
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
    all_dfs = []
    all_rejected = []
    rejected_s3_path = None

    for obj in resp.get("Contents", []):
        key = obj["Key"]
        if key.endswith((".json", ".jsonl")):
            df = process_json_file(bucket, key, flatten_keys)
            if not df.empty:
                df = harmonize_columns(df)
                all_dfs.append(df)

    if all_dfs:
        merged_df = pd.concat(all_dfs, axis=0, ignore_index=True)
        out_key = key.replace(prefix, output_prefix)
     
        save_jsonl_to_s3(merged_df, bucket, out_key)
        valid_records = merged_df.to_dict(orient="records")
        rejected_records = []  # Pour l’instant, aucun rejet côté fusion
        return valid_records, rejected_records, rejected_s3_path
    return [], [], None


def run():
    return merge_staging_s3(S3_BUCKET, STAGING_PREFIX, TRANSFORM_PREFIX, FLATTEN_KEYS)


if __name__ == "__main__":
    run()
