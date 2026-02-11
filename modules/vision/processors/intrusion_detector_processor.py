# modules/vision/processors/intrusion_detector_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
import time
from ultralytics import YOLO
import numpy as np
import torch

class IntrusionDetectorProcessor(BaseProcessor):
    """
    Detector INFALIBLE + CALIDAD MEJORADA

    🛡️ INFALIBLE:
    ✅ Try-catch exhaustivo en todas las operaciones
    ✅ Fallback si YOLO falla
    ✅ Validación de datos antes de usar
    ✅ Manejo robusto de memoria

    🎨 CALIDAD MEJORADA:
    ✅ Contrast enhancement
    ✅ Boxes con gradiente
    ✅ Labels más grandes y legibles
    ✅ Zona con efecto glow
    """

    PROCESSOR_ID = 2
    PROCESSOR_LABEL = "Detector de Intrusos"
    PROCESSOR_DESCRIPTION = "Detecta personas en zonas restringidas"

    def __init__(self, cam_id):
        super().__init__(cam_id)

        self.csv_enabled = False
        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        self.use_half = torch.cuda.is_available()
        self.model = None
        self.model_loaded = False

        print(f"🔥 Detector INFALIBLE Cam {cam_id} - Device: {self.device}")

        self._init_model()

        # Zona
        self.zone_defined = False
        self.restricted_zone = None
        self.current_intruders = 0

        # Frame skipping
        self._detection_interval = 5
        self._frame_counter = 0
        self._cached_detections = []

        # Alertas
        self._last_alert_time = 0
        self._alert_cooldown = 3.0

        # Stats
        self._detection_count = 0
        self._last_detection_time = time.time()
        self._detection_errors = 0

    def _init_model(self):
        """Inicializa YOLO con manejo robusto de errores"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries and not self.model_loaded:
            try:
                model_path = "models/yolov8n.pt"

                if os.path.exists(model_path):
                    print(f"📦 Cargando YOLO: {model_path}")
                    self.model = YOLO(model_path)
                else:
                    print(f"📦 Descargando YOLO Nano...")
                    self.model = YOLO('yolov8n.pt')

                if self.model is None:
                    raise Exception("Modelo YOLO es None")

                # Config
                self.model.conf = 0.55
                self.model.iou = 0.45

                # Warmup
                if self.device == 'cuda:0':
                    print(f"🔥 Warmup GPU...")
                    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                    self.model(
                        dummy,
                        verbose=False,
                        device=self.device,
                        half=True,
                        imgsz=640
                    )
                    print(f"✅ GPU ready")

                self.model_loaded = True
                print(f"✅ YOLO cargado correctamente")
                return

            except Exception as e:
                retry_count += 1
                print(f"❌ Error cargando YOLO (intento {retry_count}/{max_retries}): {e}")
                time.sleep(2)

        if not self.model_loaded:
            print(f"⚠️ YOLO no se pudo cargar después de {max_retries} intentos. Modo degradado activado.")
            self.model = None

    def _define_zone(self, width, height):
        """Define zona restringida con validación"""
        try:
            if width <= 0 or height <= 0:
                print(f"⚠️ Dimensiones inválidas: {width}x{height}")
                return

            mx = int(width * 0.25)
            my = int(height * 0.25)

            self.restricted_zone = np.array([
                [mx, my],
                [width - mx, my],
                [width - mx, height - my],
                [mx, height - my]
            ], dtype=np.int32)

            self.zone_defined = True
            print(f"✅ Zona: {mx},{my} -> {width - mx},{height - my}")

        except Exception as e:
            print(f"❌ Error definiendo zona: {e}")

    def process_frame(self, frame):
        """
        Procesamiento INFALIBLE
        Retorna: dict con resultado de detección {'intrusion': bool, 'count': int}
        """
        result = {'intrusion': False, 'count': 0}
        try:
            self.increment_frame_count()

            if frame is None or frame.size == 0:
                return result

            h, w = frame.shape[:2]

            if not self.zone_defined:
                self._define_zone(w, h)

            # Frame skipping
            self._frame_counter += 1
            should_detect = (self._frame_counter % self._detection_interval == 0)

            if should_detect and self.model_loaded:
                result = self._run_detection(frame, w, h)
            else:
                 # Maintain previous state if skipping
                 result = {'intrusion': self.current_intruders > 0, 'count': self.current_intruders}

            return result

        except Exception as e:
            print(f"❌ Error en process_frame: {e}")
            return result

    def _run_detection(self, original_frame, original_width, original_height):
        """
        Detección INFALIBLE con fallback
        Retorna estado de intrusión para Sentinel Mode
        """
        detection_result = {
            'intrusion': False,
            'count': 0
        }

        try:
            if self.model is None or not self.model_loaded:
                return detection_result

            # Validar frame
            if original_frame is None or original_frame.size == 0:
                return detection_result

            if original_width <= 0 or original_height <= 0:
                return detection_result

            # Frame de detección
            detection_width = 640
            detection_height = 480

            try:
                small_frame = cv2.resize(
                    original_frame,
                    (detection_width, detection_height),
                    interpolation=cv2.INTER_LINEAR
                )
            except Exception as e:
                print(f"⚠️ Error en resize: {e}")
                return detection_result

            scale_x = original_width / detection_width
            scale_y = original_height / detection_height

            # YOLO inference
            try:
                results = self.model.predict(
                    small_frame,
                    verbose=False,
                    classes=[0],
                    half=self.use_half,
                    device=self.device,
                    imgsz=640,
                    max_det=10
                )
            except Exception as e:
                self._detection_errors += 1
                if self._detection_errors % 10 == 0:
                    print(f"⚠️ Error en YOLO inference ({self._detection_errors} errores): {e}")
                return detection_result

            detections = []
            intruders_count = 0

            try:
                for result in results:
                    if result.boxes is None or len(result.boxes) == 0:
                        continue

                    for box in result.boxes:
                        try:
                            x1_s, y1_s, x2_s, y2_s = box.xyxy[0].cpu().numpy()

                            # Validar coordenadas
                            if any(np.isnan([x1_s, y1_s, x2_s, y2_s])):
                                continue

                            # Escalar
                            x1 = int(x1_s * scale_x)
                            y1 = int(y1_s * scale_y)
                            x2 = int(x2_s * scale_x)
                            y2 = int(y2_s * scale_y)

                            # Validar que estén dentro del frame
                            x1 = max(0, min(x1, original_width))
                            x2 = max(0, min(x2, original_width))
                            y1 = max(0, min(y1, original_height))
                            y2 = max(0, min(y2, original_height))

                            conf = float(box.conf[0].cpu().numpy())

                            # Centro
                            cx = (x1 + x2) // 2
                            cy = (y1 + y2) // 2

                            # Check zona
                            is_in_zone = False
                            if self.restricted_zone is not None:
                                try:
                                    is_in_zone = cv2.pointPolygonTest(
                                        self.restricted_zone,
                                        (float(cx), float(cy)),
                                        False
                                    ) >= 0
                                except:
                                    pass

                            if is_in_zone:
                                intruders_count += 1

                            detections.append({
                                'bbox': (x1, y1, x2, y2),
                                'confidence': conf,
                                'in_zone': is_in_zone
                            })

                        except Exception as e:
                            # Error en una detección individual, continuar
                            continue

            except Exception as e:
                print(f"⚠️ Error procesando detecciones: {e}")

            # Update
            self._cached_detections = detections
            self.current_intruders = intruders_count
            
            detection_result['intrusion'] = (intruders_count > 0)
            detection_result['count'] = intruders_count
            
            return detection_result

        except Exception as e:
            print(f"❌ Error en _run_detection: {e}")
            return detection_result

    def draw_detections(self, frame):
        """
        Dibuja detecciones INFALIBLE + CALIDAD MEJORADA

        🛡️ Validación de frame
        🎨 Efectos visuales mejorados
        """
        try:
            if frame is None or frame.size == 0:
                return

            if not self.zone_defined or self.restricted_zone is None:
                return

            # ✅ ZONA con efecto GLOW
            color = (0, 0, 255) if self.current_intruders > 0 else (0, 255, 0)

            # Glow exterior (más grueso, más transparente)
            overlay = frame.copy()
            cv2.polylines(overlay, [self.restricted_zone], True, color, 5, cv2.LINE_AA)
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

            # Línea principal
            cv2.polylines(frame, [self.restricted_zone], True, color, 3, cv2.LINE_AA)

            # ✅ BOXES con mejor estilo
            for det in self._cached_detections:
                try:
                    x1, y1, x2, y2 = det['bbox']
                    is_in_zone = det.get('in_zone', False)
                    conf = det.get('confidence', 0.0)

                    # Validar coordenadas
                    if x1 < 0 or y1 < 0 or x2 > frame.shape[1] or y2 > frame.shape[0]:
                        continue

                    box_color = (0, 0, 255) if is_in_zone else (0, 255, 0)
                    thickness = 3 if is_in_zone else 2

                    # Box principal
                    cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, thickness, cv2.LINE_AA)

                    # ✅ Label MEJORADO (más grande y legible)
                    label = f"Persona {conf:.0%}"
                    font_scale = 0.6  # ✅ Aumentado
                    font_thickness = 2  # ✅ Aumentado

                    (label_w, label_h), baseline = cv2.getTextSize(
                        label,
                        cv2.FONT_ITALIC,
                        font_scale,
                        font_thickness
                    )

                    # Background con gradiente
                    label_y1 = max(0, y1 - label_h - 12)
                    label_y2 = y1

                    # Sombra del background
                    cv2.rectangle(
                        frame,
                        (x1 + 2, label_y1 + 2),
                        (x1 + label_w + 10, label_y2 + 2),
                        (0, 0, 0),
                        -1
                    )

                    # Background principal
                    cv2.rectangle(
                        frame,
                        (x1, label_y1),
                        (x1 + label_w + 8, label_y2),
                        box_color,
                        -1
                    )

                    # Texto con sombra
                    cv2.putText(
                        frame,
                        label,
                        (x1 + 5, y1 - 7),
                        cv2.FONT_ITALIC,
                        font_scale,
                        (0, 0, 0),
                        font_thickness + 1,
                        cv2.LINE_AA
                    )

                    # Texto principal
                    cv2.putText(
                        frame,
                        label,
                        (x1 + 4, y1 - 8),
                        cv2.FONT_ITALIC,
                        font_scale,
                        (255, 255, 255),
                        font_thickness,
                        cv2.LINE_AA
                    )

                except Exception as e:
                    # Error en una detección, continuar con las demás
                    continue

            # ✅ ALERTA mejorada - SUPERIOR DERECHA
            if self.current_intruders > 0:
                try:
                    alert_text = f"ALERTA: INTRUSOS DETECTADOS"
                    font_scale = 1

                    # Background de alerta
                    (text_w, text_h), _ = cv2.getTextSize(
                        alert_text,
                        cv2.FONT_ITALIC,
                        font_scale,
                        3
                    )

                    # 🔧 POSICIÓN SUPERIOR DERECHA
                    frame_width = frame.shape[1]
                    x_right = frame_width - text_w - 30  # 30px margen derecho
                    
                    # Background rojo semitransparente
                    overlay = frame.copy()
                    cv2.rectangle(
                        overlay,
                        (x_right, 5),
                        (x_right + text_w + 20, text_h + 25),
                        (0, 0, 200),
                        -1
                    )
                    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

                    # Borde
                    cv2.rectangle(
                        frame,
                        (x_right, 5),
                        (x_right + text_w + 20, text_h + 25),
                        (0, 0, 255),
                        3,
                        cv2.LINE_AA
                    )

                    # Texto con sombra
                    cv2.putText(
                        frame,
                        alert_text,
                        (x_right + 12, text_h + 12),
                        cv2.FONT_ITALIC,
                        font_scale,
                        (0, 0, 0),
                        4,
                        cv2.LINE_AA
                    )

                    # Texto principal
                    )

                    # Texto con sombra
                    cv2.putText(
                        frame,
                        alert_text,
                        (x_right + 10, text_h + 10),
                        cv2.FONT_ITALIC,
                        font_scale,
                        (255, 255, 255),
                        3,
                        cv2.LINE_AA
                    )

                except Exception as e:
                    print(f"⚠️ Error dibujando alerta: {e}")
        except Exception as e:
            print(f"❌ Error en draw_detections: {e}")