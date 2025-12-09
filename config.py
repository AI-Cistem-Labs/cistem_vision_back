import os

# --- Configuración de Red ---
PORT = 5000
HOST = "0.0.0.0"

# --- Configuración de Archivos y Rutas ---
# BASE_DIR nos ayuda a encontrar las carpetas sin importar desde dónde ejecutes el script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_FILE = os.path.join(DATA_DIR, "detecciones_log.csv")

# --- Configuración de Modelos ---
DEFAULT_MODEL_NAME = "NixitoS.pt"
MODEL_PATH = os.path.join(MODELS_DIR, DEFAULT_MODEL_NAME)

# --- Configuración de Visión ---
CAMERA_INDEX = 0  # Cambia a 1 si usas una cámara USB externa y no la integrada
CONFIDENCE_THRESHOLD = 0.5