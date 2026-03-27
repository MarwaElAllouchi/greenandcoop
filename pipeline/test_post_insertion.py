# test_post_insertion.py
from dotenv import load_dotenv
import os
import time
from pymongo import MongoClient, ReadPreference
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure
from pipeline.utils.logger import log_info, log_error

load_dotenv()

# --- Configuration via variables d'environnement ---
user = os.getenv("MONGO_USER")
password = os.getenv("MONGO_PASSWORD")
host1 = os.getenv("MONGO_HOST1")
host2 = os.getenv("MONGO_HOST2")
host3 = os.getenv("MONGO_HOST3")
port = os.getenv("MONGO_PORT_INTERNE")
db_name = os.getenv("MONGO_DB")


# --- URI MongoDB avec replica set et auth ---
uri = f"mongodb://{user}:{password}@{host1}:{port},{host2}:{port},{host3}:{port}/{db_name}?replicaSet=rs0&authSource=admin"

def wait_for_primary(uri, retries=15, delay=5):
    """Attente d'un PRIMARY élu avant insertion."""
    for attempt in range(1, retries + 1):
        try:
            start = time.time()
            client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            client.admin.command("ping")
            if client.primary:
                latency_ms = (time.time() - start) * 1000
                log_info(f"✅ PRIMARY élu ({client.primary}) – latence {latency_ms:.2f} ms après {attempt} tentative(s)")
                return client
            else:
                raise ServerSelectionTimeoutError("PRIMARY non élu")
        except (ServerSelectionTimeoutError, OperationFailure) as e:
            print(f"⏳ Attente PRIMARY, tentative {attempt}/{retries} – {e}")
            time.sleep(delay)
    raise Exception("❌ PRIMARY non élu après toutes les tentatives")

def test_replication(collection_name="meteo"):
    """Test d'insertion et réplication sur SECONDARY"""
    client_primary = wait_for_primary(uri)
    db_primary = client_primary[db_name]
    col_primary = db_primary.get_collection(collection_name, read_preference=ReadPreference.PRIMARY)

    # --- 1. Insertion document test ---
    test_doc = {"_test_replication": True, "ts": time.time()}
    col_primary.insert_one(test_doc)
    log_info(f"✅ Document test inséré sur PRIMARY ({col_primary.database.client.primary})")

    # --- 2. Lecture sur SECONDARY ---
    client_secondary = MongoClient(uri, read_preference=ReadPreference.SECONDARY)
    col_secondary = client_secondary[db_name].get_collection(collection_name, read_preference=ReadPreference.SECONDARY)

    # --- 3. Attente et vérification réplication ---
    max_wait = 10  # secondes
    interval = 0.5
    start_time = time.time()
    found = False

    while time.time() - start_time < max_wait:
        doc = col_secondary.find_one({"_test_replication": True})
        if doc:
            found = True
            break
        time.sleep(interval)

    elapsed = time.time() - start_time

    if found:
        log_info(f"✅ Document visible sur SECONDARY après {elapsed:.2f}s → Réplication OK")
    else:
        log_error(f"❌ Document non répliqué après {max_wait}s → Problème de réplication")

    # --- 4. Nettoyage (optionnel) ---
    col_primary.delete_one({"_test_replication": True})
    log_info("🧹 Document test supprimé du PRIMARY")

def run(): 
     test_replication() 
     
if __name__ == "__main__":
    run()
