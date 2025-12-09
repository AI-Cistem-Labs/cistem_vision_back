# modules/vision/processors/base.py
from abc import ABC, abstractmethod
import cv2

class BaseVisionProcessor(ABC):
    """
    Clase base abstracta. Todos los algoritmos de visión (conteo, seguridad,
    mapa de calor) deben heredar de esta clase.
    """
    def __init__(self, model_path):
        self.model_path = model_path
        self.load_model()

    @abstractmethod
    def load_model(self):
        """Carga el modelo de IA en memoria."""
        pass

    @abstractmethod
    def process_frame(self, frame):
        """
        Recibe un frame, ejecuta la lógica y retorna:
        1. El frame anotado (para video).
        2. Los datos crudos (para el CSV).
        """
        pass