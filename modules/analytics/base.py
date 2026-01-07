from abc import ABC, abstractmethod

class BaseAnalyticsSpecialist(ABC):
    def __init__(self, comms_module):
        self.comms = comms_module

    @abstractmethod
    def analyze(self, current_processor):
        """Método para procesar datos del script de visión activo"""
        pass