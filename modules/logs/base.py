from abc import ABC, abstractmethod

class BaseLogSpecialist(ABC):
    def __init__(self, device_name):
        self.device_name = device_name

    @abstractmethod
    def update(self, status_data):
        """Méodo que ejecutarán los especialistas en cada ciclo"""
        pass