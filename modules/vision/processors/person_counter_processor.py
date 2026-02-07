# modules/vision/processors/person_counter_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
from ultralytics import YOLO


class PersonCounterProcessor(BaseProcessor):
    """Contador de personas con YOLO11s y boxes"""

    PROCESSOR_ID = 1
    PROCESSOR_LABEL = "Contador de Personas"
    PROCESSOR_DESCRIPTION = "Cuenta personas en tiempo real"

    def __init__(self, cam_id):
        super().__init__(cam_id)
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/person_count_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # Cargar YOLO
        try:
            model_path = "models/yolo11s.pt"
            self.model = YOLO(model_path) if os.path.exists(model_path) else YOLO('yolov8n.pt')
            self.model.conf, self.model.iou = 0.40, 0.45
            print(f"✅ Modelo cargado para Person Counter")
        except Exception as e:
            print(f"❌ Error cargando YOLO: {e}")
            self.model = None

        self.current_count = 0
        self.max_count_today = 0
        self.total_detections = 0
        self.frames_since_save = 0

    def _init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'person_count', 'max_today', 'total_detections', 'avg_confidence'])

    def process_frame(self, frame):
        self.increment_frame_count()
        processed_frame = frame.copy()
        h, w = frame.shape[:2]

        self.current_count = 0
        confidences = []

        # Detectar personas
        if self.model:
            try:
                results = self.model(frame, verbose=False, classes=[0])
                for result in results:
                    for box in result.boxes:
                        self.current_count += 1
                        conf = float(box.conf[0])
                        confidences.append(conf)

                        x1, y1, x2, y2 = map(int, box.xyxy[0])

                        # ✅ BOX VERDE
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)

                        label = f"Persona #{self.current_count} {conf:.0%}"
                        cv2.rectangle(processed_frame, (x1, y1 - 25), (x1 + 200, y1), (0, 255, 0), -1)
                        cv2.putText(processed_frame, label, (x1, y1 - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

                        # Punto central
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                        cv2.circle(processed_frame, (cx, cy), 5, (0, 255, 0), -1)
            except Exception as e:
                print(f"❌ Error YOLO: {e}")

        # Actualizar máximo
        if self.current_count > self.max_count_today:
            self.max_count_today = self.current_count

        self.total_detections += self.current_count

        # HUD
        overlay = processed_frame.copy()
        cv2.rectangle(overlay, (0, 0), (350, 200), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, processed_frame, 0.3, 0, processed_frame)

        cv2.putText(processed_frame, "CONTADOR DE PERSONAS", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        cv2.putText(processed_frame, f"Personas: {self.current_count}", (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.putText(processed_frame, f"Max. hoy: {self.max_count_today}", (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            cv2.putText(processed_frame, f"Confianza: {avg_conf:.0%}", (10, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        cv2.putText(processed_frame, datetime.now().strftime("%H:%M:%S"), (10, 175),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        # Panel derecho
        overlay2 = processed_frame.copy()
        cv2.rectangle(overlay2, (w - 250, 0), (w, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay2, 0.7, processed_frame, 0.3, 0, processed_frame)

        cv2.putText(processed_frame, "ESTADISTICAS", (w - 240, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)
        cv2.putText(processed_frame, f"Frames: {self.frame_count}", (w - 240, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(processed_frame, f"Total: {self.total_detections}", (w - 240, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        # Indicador modelo
        model_status = "YOLO11s" if self.model else "Sin Modelo"
        status_color = (0, 255, 0) if self.model else (0, 0, 255)
        cv2.circle(processed_frame, (w - 30, h - 30), 15, status_color, -1)
        cv2.putText(processed_frame, model_status, (w - 150, h - 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)

        # Alertas
        if self.current_count > 10 and self.frame_count % 30 == 0:
            self.generate_alert(
                f"Alta concentración - {self.current_count} personas",
                level="WARNING",
                context={"cam_id": self.cam_id, "count": self.current_count}
            )

        # CSV
        self.frames_since_save += 1
        if self.frames_since_save >= 30:
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            self._save_to_csv(avg_conf)
            self.frames_since_save = 0

        return processed_frame

    def _save_to_csv(self, avg_confidence):
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                self.current_count,
                self.max_count_today,
                self.total_detections,
                round(avg_confidence, 2)
            ])