# --- Base image Python ---
FROM python:3.11-slim

# --- Variables d'environnement ---
ENV PYTHONPATH=/app/pipeline

# --- Créer le dossier de travail ---
WORKDIR /app

# --- Copier les fichiers nécessaires ---
COPY pipeline ./pipeline
COPY main.py ./main.py
COPY config.py ./config.py
COPY requirements.txt ./requirements.txt

# --- Installer les dépendances ---
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# --- Point d'entrée par défaut ---
CMD ["python", "main.py"]
