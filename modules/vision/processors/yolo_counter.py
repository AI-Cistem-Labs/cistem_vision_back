# modules/vision/processors/yolo_counter.py
import datetime
import csv
import os
import cv2
from ultralytics import YOLO
import supervision as sv
from .base import BaseVisionProcessor


class YoloCounterProcessor(BaseVisionProcessor):
    def __init__(self, model_path, csv_path):
        self.csv_path = csv_path
        self._initialize_csv()
        # Inicializar anotadores de Supervision
        self.box_annotator = sv.RoundBoxAnnotator()
        self.label_annotator = sv.LabelAnnotator()
        super().__init__(model_path)

    def _initialize_csv(self):
        """Crea el CSV con encabezados si no existe."""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp', 'Class', 'Confidence', 'BBox'])

    def load_model(self):
        print(f"[VISION] Cargando modelo YOLO: {self.model_path}")
        self.model = YOLO(self.model_path)

    def process_frame(self, frame):
        # 1. Inferencia
        results = self.model(frame, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)

        # 2. Anotación Visual
        annotated_frame = frame.copy()
        annotated_frame = self.box_annotator.annotate(scene=annotated_frame, detections=detections)
        annotated_frame = self.label_annotator.annotate(scene=annotated_frame, detections=detections)

        # 3. Extracción de Datos para CSV
        csv_data = []
        if len(detections) > 0:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            for i in range(len(detections)):
                class_name = self.model.names[detections.class_id[i]]
                confidence = float(detections.confidence[i])
                bbox = detections.xyxy[i].tolist()

                # Guardar fila en memoria (el Manager o este proceso escriben al disco)
                row = [timestamp, class_name, f"{confidence:.2f}", str(bbox)]
                csv_data.append(row)

                # Escritura directa al CSV (puedes mover esto al modulo Analítica si prefieres
                # que Vision solo genere datos y Analítica escriba, pero por ahora cumple tu req)
                self._write_to_csv(row)

        return annotated_frame, csv_data

    def _write_to_csv(self, row):
        try:
            with open(self.csv_path, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(row)
        except Exception as e:
            print(f"[VISION ERROR] No se pudo escribir CSV: {e}")