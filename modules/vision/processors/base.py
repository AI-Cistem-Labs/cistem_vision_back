# modules/vision/processors/base.py
from abc import ABC, abstractmethod
import os
import csv
import datetime
import config


class BaseVisionProcessor(ABC):
    def __init__(self, model_filename, csv_prefix):
        self.model_filename = model_filename
        self.csv_prefix = csv_prefix
        self.csv_path = None
        self.model = None

        self._init_csv()
        self.load_model()

    def _init_csv(self):
        """Inicializa el archivo CSV dinámico para este procesador"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.csv_prefix}_{timestamp}.csv"
        # Aseguramos que la carpeta data exista
        os.makedirs(config.DATA_DIR, exist_ok=True)
        self.csv_path = os.path.join(config.DATA_DIR, filename)

        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(self.get_csv_headers())

    @abstractmethod
    def get_csv_headers(self):
        pass

    @abstractmethod
    def load_model(self):
        pass

    @abstractmethod
    def process_frame(self, frame):
        pass

    def write_to_csv(self, row_data):
        if self.csv_path:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)