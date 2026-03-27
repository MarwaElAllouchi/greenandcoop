import pandas as pd 

def is_valid_record(record: dict, required_fields=None) -> bool:
    if not isinstance(record, dict):
        return False

    if required_fields:
        for field in required_fields:
            value = record.get(field)

            # champ absent
            if value is None:
                return False

            # string vide
            if isinstance(value, str) and not value.strip():
                return False

            # datetime invalide
            if field == "datetime_utc":
                try:
                    pd.to_datetime(value)
                except Exception:
                    return False

    return True
