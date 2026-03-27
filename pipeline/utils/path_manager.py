from datetime import datetime

class PathManager:
   
    def __init__(self, bucket, list_s3_files_func=None):
        self.bucket = bucket
        self.list_s3_files = list_s3_files_func  # peut être None

    def generate_path(self, raw_key: str, stage: str = "staging", source_name: str = None) -> str:
        # Nom de fichier original
        filename = raw_key.split("/")[-1]

        # Récupérer source_name depuis argument ou raw_key
        if source_name is None:
            segments = raw_key.split("/")
            source_name = segments[1] if len(segments) > 1 else "unknown_source"

        # Récupérer la date depuis le dossier avant le fichier
        segments = raw_key.split("/")
        if len(segments) > 2:
            processing_date = segments[2]  # ex: 2025-12-27
        else:
            processing_date = "unknown_date"

        # Générer le path S3
        stage_prefix = f"{stage}/{source_name}/processing_date={processing_date}/"
        return f"{stage_prefix}{filename}"

    def generate_rejected_path(self, raw_key: str, stage: str = "staging", source_name: str = None) -> str:
        filename = raw_key.split("/")[-1]

        if source_name is None:
            segments = raw_key.split("/")
            source_name = segments[1] if len(segments) > 1 else "unknown_source"

        segments = raw_key.split("/")
        if len(segments) > 2:
            processing_date = segments[2]
        else:
            processing_date = "unknown_date"

        stage_prefix = f"{stage}/{source_name}/rejected/processing_date={processing_date}/"
        return f"{stage_prefix}{filename}"
