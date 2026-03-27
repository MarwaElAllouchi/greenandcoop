import logging
from pathlib import Path
import sys

# --- CHEMIN DU FICHIER LOG ---
log_file_path = Path("pipeline.log")

# --- CONFIGURATION DU LOGGER ---
logger = logging.getLogger("pipeline_logger")
logger.setLevel(logging.INFO)

# On enlève tous les handlers existants au cas où
logger.handlers.clear()

# ⚡ IMPORTANT : empêche la propagation vers le logger racine
logger.propagate = False

# --- Handler console ---
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_format = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
console_handler.setFormatter(console_format)
logger.addHandler(console_handler)

# --- Handler fichier ---
log_file_path.parent.mkdir(parents=True, exist_ok=True)  # crée le dossier si nécessaire
file_handler = logging.FileHandler(log_file_path, mode="w", encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(console_format)
logger.addHandler(file_handler)

# --- Fonctions utilitaires ---
def log_info(msg: str):
    """Log niveau INFO, gestion des caractères spéciaux"""
    try:
        logger.info(msg)
    except UnicodeEncodeError:
        safe_msg = msg.encode('cp1252', errors='replace').decode('cp1252')
        logger.info(safe_msg)

def log_error(msg: str):
    """Log niveau ERROR, gestion des caractères spéciaux"""
    try:
        logger.error(msg)
    except UnicodeEncodeError:
        safe_msg = msg.encode('cp1252', errors='replace').decode('cp1252')
        logger.error(safe_msg)
