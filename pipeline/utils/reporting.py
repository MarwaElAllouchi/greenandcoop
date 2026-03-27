# reporting.py
import pandas as pd
import os
import boto3
from pipeline.utils.logger import log_info, log_error
from pathlib import Path
from utils.mongo.mongo_utils import get_collection
from datetime import datetime

def generate_pipeline_report(doc_validity_map, output_file="pipeline_report.csv"):
    """
    Génère un rapport CSV de validité par document et par étape.
    
    doc_validity_map : dict
        {
            "doc_1": {"enrich": True, "fusion": True, "clean": True, "load": True},
            "doc_2": {"enrich": True, "fusion": False, "clean": False, "load": False},
        }
    """
    rows = []
    for doc_id, steps in doc_validity_map.items():
        row = {"document_id": doc_id}
        row.update(steps)
        rows.append(row)

    df_report = pd.DataFrame(rows)
    output_path = Path(output_file)
    df_report.to_csv(output_path, index=False)
    log_info(f"✅ Rapport pipeline généré : {output_path.resolve()}")
    return output_path
 
def save_pipeline_metrics(total_docs, rejected_docs, error_rate, duration, source=None):
    """
    Enregistre les métriques de pipeline dans MongoDB et CloudWatch.

    Parameters
    ----------
    total_docs : int
        Nombre total de documents traités
    rejected_docs : int
        Nombre de documents rejetés
    error_rate : float
        Taux d'erreur (rejet / total)
    duration : float
        Durée totale du pipeline en secondes
    source : str, optional
        Nom ou source du pipeline. Si None, récupère la variable d'environnement PIPELINE_SOURCE ou utilise "pipeline" par défaut.
    """

    # --- Définition de la source ---
    if source is None:
        source = os.getenv("PIPELINE_SOURCE", "pipeline")

    # --- Métriques à stocker ---
    metrics_doc = {
        "timestamp": datetime.utcnow(),
        "total_docs": total_docs,
        "rejected_docs": rejected_docs,
        "error_rate": error_rate,
        "duration_sec": duration,
        "source": source
    }

    # --- 1️⃣ Sauvegarde dans MongoDB ---
    try:
        bd_metrics = os.getenv("BD_METRICS")  # Nom de la base
        collection = get_collection(bd_metrics)  # Récupère collection pipeline_metrics
        collection.insert_one(metrics_doc)
        log_info(f"✅ Métriques pipeline enregistrées dans MongoDB : {metrics_doc}")
    except Exception as e:
        log_error(f"✖ Erreur enregistrement metrics MongoDB : {e}")

    # --- 2️⃣ Publication dans CloudWatch ---
    try:
        cloudwatch = boto3.client('cloudwatch', region_name='eu-west-3')

        cloudwatch.put_metric_data(
            Namespace='GreenCoop/Pipeline',
            MetricData=[
                {
                    'MetricName': 'TotalDocs',
                    'Dimensions': [{'Name': 'Source', 'Value': source}],
                    'Value': total_docs,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'RejectedDocs',
                    'Dimensions': [{'Name': 'Source', 'Value': source}],
                    'Value': rejected_docs,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'ErrorRate',
                    'Dimensions': [{'Name': 'Source', 'Value': source}],
                    'Value': error_rate,
                    'Unit': 'Percent'
                },
                {
                    'MetricName': 'PipelineDuration',
                    'Dimensions': [{'Name': 'Source', 'Value': source}],
                    'Value': duration,
                    'Unit': 'Seconds'
                }
            ]
        )
        log_info("✅ Métriques pipeline publiées dans CloudWatch")
    except Exception as e:
        log_error(f"✖ Erreur publication metrics CloudWatch : {e}")
