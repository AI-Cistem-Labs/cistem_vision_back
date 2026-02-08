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
    """Detector de intrusiones ULTRA-OPTIMIZADO - ZERO LATENCY"""

    PROCESSOR_ID = 2
    PROCESSOR_LABEL = "Detector de Intrusos"
    PROCESSOR_DESCRIPTION = "Detecta personas en zonas restringidas"

    def __init__(self, cam_id):
        super().__init__(cam_id)
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/intrusion_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # ✅ CUDA CHECK
        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        print(f"🔥 Usando dispositivo: {self.device}")

        # ✅ Cargar YOLO OPTIMIZADO
        try:
            model_path = "models/yolo11s.pt"
            self.model = YOLO(model_path) if os.path.exists(model_path) else YOLO('yolov8n.pt')
            self.model.conf = 0.5  # ✅ Bajado para detectar mejor
            self.model.iou = 0.45

            # ✅ Warmup GPU
            if self.device == 'cuda:0':
                dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                self.model(dummy, verbose=False, device=self.device, half=True)

            print(f"✅ YOLO cargado en {self.device}")
        except Exception as e:
            print(f"❌ Error: {e}")
            self.model = None

        self.zone_defined = False
        self.restricted_zone = None
        self.current_intruders = 0

        # ✅ SKIP FRAMES (detectar cada 3 frames para mejor respuesta)
        self._frame_skip = 3
        self._detection_counter = 0
        self._last_boxes = []

        # ✅ CSV Buffer
        self.csv_buffer = []
        self.max_buffer_size = 100

    def _init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'intruders'])

    def _define_zone(self, width, height):
        """Define ROI una sola vez - zona más pequeña para mejor detección"""
        mx = int(width * 0.25)
        my = int(height * 0.25)
        self.restricted_zone = np.array([
            [mx, my],
            [width - mx, my],
            [width - mx, height - my],
            [mx, height - my]
        ], dtype=np.int32)
        self.zone_defined = True
        print(f"🎯 ROI definido: {self.restricted_zone.tolist()}")

    def process_frame(self, frame):
        """
        🚀 PROCESAMIENTO OPTIMIZADO
        RETORNA: Frame SIEMPRE (nunca None)
        """
        self.increment_frame_count()

        # ✅ VALIDACIÓN CRÍTICA
        if frame is None or frame.size == 0:
            print(f"⚠️ Frame inválido recibido")
            return np.zeros((720, 1280, 3), dtype=np.uint8)  # Frame negro

        h, w = frame.shape[:2]

        if not self.zone_defined:
            self._define_zone(w, h)

        # ✅ Copiar frame para no modificar el original
        output_frame = frame.copy()

        # ✅ DETECTAR cada N frames
        self._detection_counter += 1
        should_detect = (self._detection_counter % self._frame_skip == 0)

        if should_detect and self.model:
            try:
                # ✅ YOLO en frame completo (mejor detección)
                results = self.model.predict(
                    frame,
                    verbose=False,
                    classes=[0],  # Solo personas
                    half=True if self.device == 'cuda:0' else False,
                    device=self.device,
                    imgsz=640,
                    max_det=15
                )

                # ✅ Procesar detecciones
                boxes_data = []
                self.current_intruders = 0

                for result in results:
                    if result.boxes is not None and len(result.boxes) > 0:
                        for box in result.boxes:
                            # ✅ Coordenadas directas (ya están en escala correcta)
                            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                            conf = float(box.conf[0].cpu().numpy())

                            # ✅ Centro del bbox
                            cx = (x1 + x2) // 2
                            cy = (y1 + y2) // 2

                            # ✅ Check si está en zona restringida
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

                self._last_boxes = boxes_data

                # ✅ Log detecciones
                if self.current_intruders > 0:
                    print(f"🚨 {self.current_intruders} INTRUSO(S) DETECTADO(S)")
                    self.generate_alert(
                        f"{self.current_intruders} intruso(s)",
                        level="CRITICAL",
                        context={"cam_id": self.cam_id}
                    )

                # ✅ CSV buffer
                self.csv_buffer.append([
                    datetime.now().isoformat(),
                    self.current_intruders
                ])
                if len(self.csv_buffer) >= self.max_buffer_size:
                    self._flush_csv()

            except Exception as e:
                print(f"❌ YOLO error: {e}")

        # ✅ DIBUJAR (SIEMPRE, incluso sin detecciones nuevas)
        self._draw_on_frame(output_frame)

        return output_frame

    def _draw_on_frame(self, frame):
        """
        🎨 DIBUJA DIRECTAMENTE EN EL FRAME (in-place)
        - ROI siempre visible
        - Boxes de detecciones
        """
        # ✅ 1. DIBUJAR ROI (zona restringida)
        roi_color = (0, 0, 255) if self.current_intruders > 0 else (0, 255, 0)
        cv2.polylines(
            frame,
            [self.restricted_zone.reshape((-1, 1, 2))],
            True,
            roi_color,
            3  # Línea más gruesa para visibilidad
        )

        # ✅ 2. DIBUJAR BOXES
        for box_data in self._last_boxes:
            x1, y1, x2, y2 = box_data['bbox']
            conf = box_data['conf']
            in_zone = box_data['in_zone']

            if in_zone:
                # INTRUSO - Rojo grueso
                color = (0, 0, 255)
                thickness = 4
            else:
                # PERSONA OK - Verde
                color = (0, 255, 0)
                thickness = 2

            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # ✅ 3. INDICADOR SIMPLE (opcional, sin HUD complejo)
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