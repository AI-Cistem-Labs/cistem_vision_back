# modules/vision/processors/intrusion_detector_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
from ultralytics import YOLO
import numpy as np
import torch


class IntrusionDetectorProcessor(BaseProcessor):
    """Detector de intrusiones - Stream fluido con detección optimizada"""

    PROCESSOR_ID = 2
    PROCESSOR_LABEL = "Detector de Intrusos"
    PROCESSOR_DESCRIPTION = "Detecta personas en zonas restringidas"

    def __init__(self, cam_id):
        super().__init__(cam_id)
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/intrusion_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        print(f"🔥 Dispositivo: {self.device}")

        try:
            model_path = "models/yolo11s.pt"
            self.model = YOLO(model_path) if os.path.exists(model_path) else YOLO('yolov8n.pt')
            self.model.conf = 0.5
            self.model.iou = 0.45

            if self.device == 'cuda:0':
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                self.model(dummy, verbose=False, device=self.device, half=True)

            print(f"✅ YOLO cargado")
        except Exception as e:
            print(f"❌ Error YOLO: {e}")
            self.model = None

        self.zone_defined = False
        self.restricted_zone = None
        self.current_intruders = 0

        # ✅ DETECCIÓN cada 5 frames (optimización)
        self._frame_skip = 5
        self._detection_counter = 0
        self._last_boxes = []  # Cache de última detección

        self.csv_buffer = []
        self.max_buffer_size = 100

    def _init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'intruders'])

    def _define_zone(self, width, height):
        mx = int(width * 0.25)
        my = int(height * 0.25)
        self.restricted_zone = np.array([
            [mx, my],
            [width - mx, my],
            [width - mx, height - my],
            [mx, height - my]
        ], dtype=np.int32)
        self.zone_defined = True

    def process_frame(self, frame):
        """
        ✅ CLAVE: NO modifica el frame original
        Solo detecta y guarda las coordenadas de los boxes
        """
        self.increment_frame_count()

        if frame is None or frame.size == 0:
            return frame  # ✅ Retornar frame original sin procesar

        h, w = frame.shape[:2]

        if not self.zone_defined:
            self._define_zone(w, h)

        # ✅ DETECCIÓN cada 5 frames (en frame reducido para velocidad)
        self._detection_counter += 1
        should_detect = (self._detection_counter % self._frame_skip == 0)

        if should_detect and self.model:
            try:
                # ✅ Detectar en versión pequeña
                small = cv2.resize(frame, (640, 360), interpolation=cv2.INTER_LINEAR)

                results = self.model.predict(
                    small,
                    verbose=False,
                    classes=[0],
                    half=True if self.device == 'cuda:0' else False,
                    device=self.device,
                    imgsz=640,
                    max_det=15
                )

                # ✅ Escalar boxes a tamaño original
                scale_x = w / 640
                scale_y = h / 360

                boxes_data = []
                self.current_intruders = 0

                for result in results:
                    if result.boxes is not None:
                        for box in result.boxes:
                            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()

                            x1 = int(x1 * scale_x)
                            x2 = int(x2 * scale_x)
                            y1 = int(y1 * scale_y)
                            y2 = int(y2 * scale_y)

                            conf = float(box.conf[0].cpu().numpy())
                            cx = (x1 + x2) // 2
                            cy = (y1 + y2) // 2

                            in_zone = cv2.pointPolygonTest(
                                self.restricted_zone,
                                (float(cx), float(cy)),
                                False
                            ) >= 0

                            if in_zone:
                                self.current_intruders += 1

                            boxes_data.append({
                                'bbox': (x1, y1, x2, y2),
                                'conf': conf,
                                'in_zone': in_zone
                            })

                # ✅ GUARDAR detecciones (NO dibujar todavía)
                self._last_boxes = boxes_data

                if self.current_intruders > 0:
                    self.generate_alert(
                        f"{self.current_intruders} intruso(s)",
                        level="CRITICAL",
                        context={"cam_id": self.cam_id}
                    )

                self.csv_buffer.append([
                    datetime.now().isoformat(),
                    self.current_intruders
                ])
                if len(self.csv_buffer) >= self.max_buffer_size:
                    self._flush_csv()

            except Exception as e:
                print(f"❌ YOLO: {e}")

        # ✅ RETORNAR FRAME ORIGINAL SIN MODIFICAR
        return frame

    def _draw_on_frame(self, frame):
        """Dibuja ROI y boxes directamente en el frame"""
        roi_color = (0, 0, 255) if self.current_intruders > 0 else (0, 255, 0)
        cv2.polylines(
            frame,
            [self.restricted_zone.reshape((-1, 1, 2))],
            True,
            roi_color,
            3
        )

        for box_data in self._last_boxes:
            x1, y1, x2, y2 = box_data['bbox']
            in_zone = box_data['in_zone']

            color = (0, 0, 255) if in_zone else (0, 255, 0)
            thickness = 4 if in_zone else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        if self.current_intruders > 0:
            cv2.putText(
                frame,
                f"ALERTA: {self.current_intruders}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                3
            )

    def _flush_csv(self):
        if not self.csv_buffer:
            return
        try:
            with open(self.csv_file, 'a', newline='') as f:
                csv.writer(f).writerows(self.csv_buffer)
            self.csv_buffer.clear()
        except:
            pass

    def __del__(self):
        self._flush_csv()