# modules/vision/processors/flow_persons.py
from .base import BaseVisionProcessor
from ultralytics import YOLO
import os
import config
import datetime
import supervision as sv


class FlowPersonsProcessor(BaseVisionProcessor):
    def __init__(self):
        super().__init__(model_filename="NixitoS.pt", csv_prefix="flujo_personas")
        self.box_annotator = sv.RoundBoxAnnotator()

    def get_csv_headers(self):
        return ['Timestamp', 'Count', 'Status']

    def load_model(self):
        path = os.path.join(config.MODELS_DIR, self.model_filename)
        self.model = YOLO(path)

    def process_frame(self, frame):
        results = self.model(frame, verbose=False)[0]
        detections = sv.Detections.from_ultralytics(results)
        annotated_frame = self.box_annotator.annotate(scene=frame.copy(), detections=detections)

        data = [datetime.datetime.now().strftime("%H:%M:%S"), len(detections), "OK"]
        return annotated_frame, data