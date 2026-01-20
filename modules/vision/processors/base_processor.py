# modules/vision/processors/base_processor.py
from abc import ABC, abstractmethod
from modules.analytics.specialists.system_logger import system_logger
from modules.analytics.specialists.alerts_engine import alerts_engine


class BaseProcessor(ABC):
    """
    Clase base abstracta para todos los procesadores de IA

    Cada procesador debe:
    1. Heredar de esta clase
    2. Definir PROCESSOR_ID, PROCESSOR_LABEL, PROCESSOR_DESCRIPTION
    3. Implementar process_frame(frame)
    4. Opcionalmente guardar datos en CSV
    """

    PROCESSOR_ID = None
    PROCESSOR_LABEL = "Procesador Base"
    PROCESSOR_DESCRIPTION = "Descripción del procesador"

    def __init__(self, cam_id):
        """
        Args:
            cam_id: ID de la cámara asociada
        """
        self.cam_id = cam_id
        self.frame_count = 0

    @abstractmethod
    def process_frame(self, frame):
        """
        Procesa un frame y retorna el frame con anotaciones

        Args:
            frame: Frame de video (numpy array BGR)

        Returns:
            numpy.ndarray: Frame procesado con anotaciones visuales
        """
        pass

    def log(self, message, level="INFO"):
        """Helper para generar logs"""
        system_logger.log(self.cam_id, f"[{self.PROCESSOR_LABEL}] {message}", level)

    def generate_alert(self, message, level="PRECAUCION", context=None):
        """Helper para generar alertas"""
        alerts_engine.create_alert(self.cam_id, message, level, context)

    def increment_frame_count(self):
        """Incrementa contador de frames procesados"""
        self.frame_count += 1
        return self.frame_count