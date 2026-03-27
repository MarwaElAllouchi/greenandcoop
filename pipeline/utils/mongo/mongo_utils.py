import os
import time
import logging
from pymongo import MongoClient, ReadPreference
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

# -----------------------
# Configuration Logging
# -----------------------
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

# -----------------------
# Singleton MongoClient
# -----------------------
_mongo_client = None

def get_mongo_client(retries=10, delay=5):
    """
    Retourne un client MongoDB connecté au ReplicaSet.
    Retry si MongoDB n'est pas encore prêt.
    """
    global _mongo_client
    if _mongo_client:
        return _mongo_client

    # -----------------------
    # Lecture variables ECS / Secrets Manager
    # -----------------------
    user = os.getenv("MONGO_USER")
    password = os.getenv("MONGO_PASSWORD")
    host1 = os.getenv("MONGO_HOST1")
    host2 = os.getenv("MONGO_HOST2")
    host3 = os.getenv("MONGO_HOST3")
    port = os.getenv("MONGO_PORT_INTERNE")  # default 27017 si oublié
    db_name = os.getenv("MONGO_DB")

    # -----------------------
    # URI MongoDB
    # -----------------------
    uri = (
        f"mongodb://{user}:{password}@"
        f"{host1}:{port},{host2}:{port},{host3}:{port}/"
        f"{db_name}?replicaSet=rs0&authSource=admin"
    )
    

    # -----------------------
    # Retry loop
    # -----------------------
    for attempt in range(1, retries + 1):
        try:
            start = time.time()
            client = MongoClient(uri, serverSelectionTimeoutMS=10000)
            client.admin.command("ping")
            latency_ms = (time.time() - start) * 1000

            # Vérifie PRIMARY pour écriture
            if not client.primary:
                raise ServerSelectionTimeoutError("PRIMARY non élu")

            logging.info(
                f"✅ MongoDB prêt (après {attempt} tentative(s)) | "
                f"Latence: {latency_ms:.2f} ms | PRIMARY: {client.primary}"
            )
            _mongo_client = client
            return client

        except (ServerSelectionTimeoutError, OperationFailure) as e:
            logging.warning(f"⏳ MongoDB non prêt, tentative {attempt}/{retries} – {e}")
            time.sleep(delay)

    raise Exception("❌ MongoDB non disponible après toutes les tentatives")

# -----------------------
# Fonction pour récupérer une collection
# -----------------------
def get_collection(collection_name, db_name_override=None):
    """
    Retourne une collection MongoDB prête à l'emploi
    Écrit toujours sur le PRIMARY
    """
    client = get_mongo_client()
    
    # Partie où tu peux changer de base sans toucher le client
    db_name_to_use = db_name_override if db_name_override else os.getenv("MONGO_DB")
    
    db = client[db_name_to_use]
    return db.get_collection(
        collection_name,
        read_preference=ReadPreference.PRIMARY
    )


