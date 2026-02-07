# modules/vision/processors/intrusion_detector_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
from ultralytics import YOLO
import numpy as np


class IntrusionDetectorProcessor(BaseProcessor):
    """Detector de intrusiones con YOLO11s y boxes"""

    PROCESSOR_ID = 2
    PROCESSOR_LABEL = "Detector de Intrusos"
    PROCESSOR_DESCRIPTION = "Detecta personas en zonas restringidas"

    def __init__(self, cam_id):
        super().__init__(cam_id)
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/intrusion_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # Cargar YOLO
        try:
            model_path = "models/yolo11s.pt"
            self.model = YOLO(model_path) if os.path.exists(model_path) else YOLO('yolov8n.pt')
            self.model.conf, self.model.iou = 0.40, 0.45
            print(f"✅ Modelo cargado para Intrusion Detector")
        except Exception as e:
            print(f"❌ Error cargando YOLO: {e}")
            self.model = None

        self.zone_defined = False
        self.restricted_zone = None
        self.intrusions_today = 0
        self.current_intruders = 0
        self.frames_since_save = 0

    def _init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'person_count', 'intrusions_today', 'alert_level'])

    def _define_zone(self, width, height):
        margin_x, margin_y = int(width * 0.25), int(height * 0.25)
        self.restricted_zone = np.array([
            [margin_x, margin_y],
            [width - margin_x, margin_y],
            [width - margin_x, height - margin_y],
            [margin_x, height - margin_y]
        ], dtype=np.int32)
        self.zone_defined = True

    def process_frame(self, frame):
        self.increment_frame_count()
        processed_frame = frame.copy()
        h, w = frame.shape[:2]

        if not self.zone_defined:
            self._define_zone(w, h)

        self.current_intruders = 0

        # Detectar personas
        if self.model:
            try:
                results = self.model(frame, verbose=False, classes=[0])
                for result in results:
                    for box in result.boxes:
                        conf = float(box.conf[0])
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                        in_zone = cv2.pointPolygonTest(self.restricted_zone, (cx, cy), False) >= 0

                        if in_zone:
                            self.current_intruders += 1
                            # ✅ BOX ROJO - Intruso
                            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                            label = f"INTRUSO {conf:.0%}"
                            cv2.rectangle(processed_frame, (x1, y1 - 25), (x1 + 150, y1), (0, 0, 255), -1)
                            cv2.putText(processed_frame, label, (x1, y1 - 5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                            # Alerta
                            if self.frame_count % 30 == 0:
                                self.generate_alert(
                                    f"Intruso detectado en área restringida",
                                    level="CRITICAL",
                                    context={"cam_id": self.cam_id, "count": self.current_intruders}
                                )
                        else:
                            # ✅ BOX VERDE - Fuera de zona
                            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                            cv2.putText(processed_frame, f"Persona {conf:.0%}", (x1, y1 - 5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            except Exception as e:
                print(f"❌ Error YOLO: {e}")

        # Dibujar zona
        overlay = processed_frame.copy()
        color = (0, 0, 200) if self.current_intruders > 0 else (0, 100, 200)
        pts = self.restricted_zone.reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts], color)
        cv2.polylines(processed_frame, [pts], True, color, 3)
        cv2.addWeighted(overlay, 0.3, processed_frame, 0.7, 0, processed_frame)

        x, y = self.restricted_zone[0]
        cv2.putText(processed_frame, "ZONA RESTRINGIDA", (x + 10, y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # HUD
        cv2.rectangle(processed_frame, (0, 0), (350, 150), (0, 0, 0), -1)
        cv2.putText(processed_frame, "DETECTOR DE INTRUSOS", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        status_text = "ALERTA: INTRUSION" if self.current_intruders > 0 else "Sin intrusiones"
        status_color = (0, 0, 255) if self.current_intruders > 0 else (0, 255, 0)
        cv2.putText(processed_frame, status_text, (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

        cv2.putText(processed_frame, f"Intrusos: {self.current_intruders}", (10, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(processed_frame, datetime.now().strftime("%H:%M:%S"), (10, 140),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (150, 150, 150), 1)

        # Guardar CSV
        self.frames_since_save += 1
        if self.frames_since_save >= 30:
            self._save_to_csv()
            self.frames_since_save = 0
            if self.current_intruders > 0:
                self.intrusions_today += 1

        return processed_frame

    def _save_to_csv(self):
        alert_level = "CRITICAL" if self.current_intruders > 0 else "NORMAL"
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                self.current_intruders,
                self.intrusions_today,
                alert_level
            ])