import os
import time
from datetime import datetime
from pymongo.errors import PyMongoError
import boto3
from utils.mongo.mongo_utils import get_mongo_client  # ← ta fonction existante
from pipeline.utils.logger import log_info, log_error

# -----------------------
# CloudWatch client
# -----------------------
cloudwatch = boto3.client("cloudwatch", region_name="eu-west-3")

NAMESPACE = "GreenCoop/MongoDB"

def send_replica_lag_metrics():
    """
    Envoie les métriques Replica Lag de chaque nœud du ReplicaSet vers CloudWatch.
    """
    try:
        client = get_mongo_client()
        status = client.admin.command("replSetGetStatus")

        primary_optime = None
        # Identifier le PRIMARY pour calcul du lag
        for member in status["members"]:
            if member["stateStr"] == "PRIMARY":
                primary_optime = member["optime"]["ts"]
                break

        if primary_optime is None:
            log_error("❌ Aucun PRIMARY trouvé pour calcul du Replica Lag")
            return

        # Parcours des membres pour calculer le lag
        for member in status["members"]:
            if member["stateStr"] != "PRIMARY":
                lag_sec = (primary_optime.time - member["optime"]["ts"].time)
                metric_name = f"ReplicaLag_{member['name']}"
                cloudwatch.put_metric_data(
                    Namespace=NAMESPACE,
                    MetricData=[
                        {
                            "MetricName": metric_name,
                            "Dimensions": [
                                {"Name": "ReplicaSet", "Value": status["set"]}
                            ],
                            "Timestamp": datetime.utcnow(),
                            "Value": lag_sec,
                            "Unit": "Seconds",
                        }
                    ],
                )
                #log_info(f"✔ {metric_name} = {lag_sec:.2f}s envoyé à CloudWatch")

    except PyMongoError as e:
        log_error(f"✖ Erreur MongoDB Replica Lag : {e}")
    except Exception as e:
        log_error(f"✖ Erreur générale Replica Lag : {e}")
