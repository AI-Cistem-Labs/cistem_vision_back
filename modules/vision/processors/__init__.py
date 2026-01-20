# modules/vision/processors/__init__.py
import os
import importlib
import inspect
from .base_processor import BaseProcessor

# Diccionario de procesadores disponibles
AVAILABLE_PROCESSORS = {}


def register_processor(processor_class):
    """Registra un procesador en el sistema"""
    if hasattr(processor_class, 'PROCESSOR_ID') and processor_class.PROCESSOR_ID is not None:
        AVAILABLE_PROCESSORS[processor_class.PROCESSOR_ID] = {
            'class': processor_class,
            'label': processor_class.PROCESSOR_LABEL,
            'description': processor_class.PROCESSOR_DESCRIPTION
        }
        print(f"✅ Procesador registrado: {processor_class.PROCESSOR_LABEL} (ID: {processor_class.PROCESSOR_ID})")


def load_processors():
    """Carga automáticamente todos los procesadores en la carpeta"""
    processors_dir = os.path.dirname(__file__)

    for filename in os.listdir(processors_dir):
        if filename.endswith('_processor.py') and filename != 'base_processor.py':
            module_name = filename[:-3]

            try:
                module = importlib.import_module(f'modules.vision.processors.{module_name}')

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, BaseProcessor) and
                            obj != BaseProcessor and
                            hasattr(obj, 'PROCESSOR_ID') and
                            obj.PROCESSOR_ID is not None):
                        register_processor(obj)

            except Exception as e:
                print(f"❌ Error cargando procesador {module_name}: {str(e)}")


def get_available_processors():
    """Retorna diccionario de procesadores disponibles"""
    return {
        proc_id: {
            'label': info['label'],
            'description': info['description']
        }
        for proc_id, info in AVAILABLE_PROCESSORS.items()
    }


def get_processor_class(processor_id):
    """Obtiene la clase de un procesador por su ID"""
    if processor_id in AVAILABLE_PROCESSORS:
        return AVAILABLE_PROCESSORS[processor_id]['class']
    return None


# Cargar procesadores al importar
load_processors()

__all__ = ['BaseProcessor', 'get_available_processors', 'get_processor_class', 'AVAILABLE_PROCESSORS']