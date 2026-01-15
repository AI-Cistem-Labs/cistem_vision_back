# modules/vision/processors/registry.py
from .flow_persons import FlowPersonsProcessor

PROCESSOR_REGISTRY = {
    1: { # ID numérico según Postman
        "class": FlowPersonsProcessor,
        "label": "Flujo de Personas",
        "description": "Detecta y cuenta personas. Recomendación: Cámara a 3m de altura."
    }
}

def get_processor_class(proc_id):
    return PROCESSOR_REGISTRY.get(proc_id, {}).get("class")

def get_available_processors():
    """Formato para el evento available_processors del frontend"""
    return [
        {
            "category_id": 1,
            "label": "Analítica de Flujo",
            "processors": [
                {
                    "processor_id": pid,
                    "label": info["label"],
                    "description": info["description"]
                } for pid, info in PROCESSOR_REGISTRY.items()
            ]
        }
    ]