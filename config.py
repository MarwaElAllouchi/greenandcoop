import os

# =========================
# Global configuration
# =========================

# S3
S3_BUCKET = os.getenv("S3_BUCKET", "greenandcoop-meteo")
# Paths
RAW_BASE_PATH = "raw"
STAGING_BASE_PATH = "staging"
CURATED_BASE_PATH = "curated"
CURATED_REJECTED_PATH="curated/rejected/"
STAGING_PATH_A_FUSION="staging"
FUSION_PATH = "fusion"
FUSED_FILENAME ="fused_global"
STAGING_PREFIX="staging/"
TRANSFORM_PREFIX="transform/fusion/_merged_all_stations/"
# dossier où écrire fichiers nettoyés
DATA_INPUT_PATHS = ["transform"] # Tu peux ajouter d'autres chemins ici

#Varriables
AIRBYTE = True
VALIDATORS_FIELD="" 
MERGE_KEY = "id_station" 
FLATTEN_KEYS = ["license"]
pipeline_name="pipeline_greenandcoop"

# =========================
# Processing rules
# =========================

# If True, the pipeline processes only the latest available date
PROCESS_LATEST_ONLY = True

# Force a specific date (format: YYYY-MM-DD), e.g. "2025-12-20"
# If None, the latest date will be selected automatically
FORCE_PROCESSING_DATE = None
# =========================
# Sources configuration
# =========================

SOURCES = {
    "weatherunderground": {
        "raw_path": f"{RAW_BASE_PATH}/weatherunderground"
      
    },
    "infoclimat": {
        "raw_path": f"{RAW_BASE_PATH}/infoclimat"
       
    }
}
STATIONS_METADATA = {
    "Weather_Underground_La_Madeleine_FR": {
        "weather_station_id": "ILAMAD25",
        "station_name": "La Madeleine",
        "latitude": 50.659,
        "longitude": 3.07,
        "elevation": 23,
        "city": "La Madeleine",
        "state": "-/-",
        "hardware": "other",
        "software": "EasyWeatherPro_V5.1.6"
    },
    "Weather_Underground_Ichtegem_BE": {
        "weather_station_id": "IICHTE19",
        "station_name": "WeerstationBS",
        "latitude": 51.092,
        "longitude": 2.999,
        "elevation": 15,
        "city": "Ichtegem",
        "state": "-/-",
        "hardware": "other",
        "software": "EasyWeatherV1.6.6"
    }
} 
#Colonnes métier de référence pour la fusion CSV homogènes
# Colonnes finales voulues
STANDARD_COLS = [
    # Identité station
    "station_id",
    "station_name",
    "latitude",
    "longitude",
    "elevation",
    "city",
    "state",

    # Temps
    "datetime_utc",


    # Mesures météo
    "temperature",
    "pression",
    "humidite",
    "point_de_rosee",
    "vent_moyen",
    "vent_rafales",
    "vent_direction",
    "pluie_1h",
    "pluie_3h",

    # Métadonnées techniques
    "hardware",
    "software",

    # Licence
    "license",
    "license_source",
    "license_url"
]


# Mapping multi-sources → colonne standard
COLUMN_MAPPING = {
    # Station ID
    "station_id": "station_id",
    "weather_station_id": "station_id",

    # Nom station
    "station_name": "station_name",

    # Date / heure
    "dh_utc": "datetime_utc",
    "datetime_utc": "datetime_utc",
    "time": "datetime_utc",

    # Localisation
    "latitude": "latitude",
    "longitude": "longitude",
    "elevation": "elevation",
    "city": "city",
    "state": "state",

    # Température
    "temperature": "temperature",
    "Temperature": "temperature",

    # Pression
    "pression": "pression",
    "Pressure": "pression",
    "pressure": "pression",

    # Humidité
    "humidity": "humidite",

    # Point de rosée
    "point_de_rosee": "point_de_rosee",
    "dew point": "point_de_rosee",

    # Vent
    "vent_moyen": "vent_moyen",
    "speed": "vent_moyen",

    "vent_rafales": "vent_rafales",
    "gust": "vent_rafales",

    "vent_direction": "vent_direction",
    "wind": "vent_direction",

    # Pluie
    "pluie_1h": "pluie_1h",
    "precip. rate.": "pluie_1h",

    "pluie_3h": "pluie_3h",
    "precip. accum.": "pluie_3h",

    # Matériel / logiciel
    "hardware": "hardware",
    "software": "software",

    # Licence
    "license": "license",
    "license_source": "license_source",
    "license_url": "license_url"
}

# =========================
# Metadata configuration
# =========================

SOURCES_WITH_STATION_METADATA = ["Weather_Underground_La_Madeleine_FR","weatherunderground",
                                 "Weather_Underground_Ichtegem_BE"]


#dictionnaire de conversions d'unité  configurable

UNIT_CONVERSIONS = {
    "°F": lambda x: (x - 32) * 5/9,        # Fahrenheit → Celsius
    "mph": lambda x: x * 1.60934,          # Miles/h → km/h
    "in": lambda x: x * 25.4,              # Inch → mm
    "%": lambda x: x,                       # Pourcentages, on peut normaliser si besoin
}
#les colonnes contient des unités : 
UNIT_COLUMNS = [
    "temperature",
    "humidite",
    "pression",
    "vent_direction",
    "vent_rafales"
]
MONGO_LOAD_JOBS = [
    {
        "s3_key": "curated/_merged_all_stations/",
        "collection": "meteo",
       "format": "jsonl",
      "required_columns": ["station_id", "datetime_utc"]
    }
    
]
COLUMN_SCHEMA = {
    # Identité station
    "station_id": "string",
    "station_name": "string",
    "city": "string",
    "state": "string",

    # Géographie
    "latitude": "float",
    "longitude": "float",
    "elevation": "int",

    # Temps (UTC → timestamp millisecondes pour Mongo)
    "datetime_utc": "timestamp_ms",

    # Mesures météo
    "temperature": "float",
    "pression": "float",
    "humidite": "int",
    "point_de_rosee": "float",
    "vent_moyen": "float",
    "vent_rafales": "float",
    "vent_direction": "int",
    "pluie_1h": "float",
    "pluie_3h": "float",

    # Métadonnées techniques
    "hardware": "string",
    "software": "string",

    # Licence
    "license": "string",
    "license_source": "string",
    "license_url": "string",
}
