# modules/vision/processors/registry.py
# Importa aquí tus procesadores reales
# from .flow_persons import FlowPersonsProcessor

# Por ahora, si solo tienes el yolo_counter, puedes registrarlo así:
PROCESSOR_REGISTRY = {
    "flow_persons_v1": {
        "label": "Flujo de Entrada - Personas"
        # Aquí iría la clase una vez creada: "class": FlowPersonsProcessor
    }
}

def get_available_processors():
    return [{"id": k, "label": v["label"]} for k, v in PROCESSOR_REGISTRY.items()]

def get_processor_class(processor_id):
    # Por ahora retorna None o una clase por defecto hasta que completes flow_persons.py
    return PROCESSOR_REGISTRY.get(processor_id, {}).get("class")