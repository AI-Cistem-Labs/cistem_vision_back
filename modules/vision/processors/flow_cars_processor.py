# modules/vision/processors/flow_cars_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
import time
from ultralytics import YOLO
import numpy as np
import torch


class FlowCarsProcessor(BaseProcessor):
    """
    Detector de vehículos OPTIMIZADO para Orin Nano 8GB

    🚀 OPTIMIZACIONES:
    ✅ GPU Manager con prioridad 80
    ✅ Frame skipping adaptativo (GPU: 5, CPU: 7)
    ✅ Warmup mínimo (256x256) + limpieza agresiva
    ✅ Resize adaptativo según device (GPU: 640x480, CPU: 480x360)
    ✅ YOLOv8n (más ligero que yolo11s)
    ✅ Max detections adaptativo (GPU: 15, CPU: 10)
    ✅ 4 clases de vehículos (car, motorcycle, bus, truck)
    """

    PROCESSOR_ID = 3
    PROCESSOR_LABEL = "Flujo de Vehículos"
    PROCESSOR_DESCRIPTION = "Detecta y cuenta vehículos (autos, motos, camiones)"

    def __init__(self, cam_id):
        super().__init__(cam_id)

        # CSV
        self.csv_enabled = True
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/vehicle_flow_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # ⭐ NUEVO: GPU Manager con prioridad
        from modules.vision.gpu_manager import get_gpu_manager

        gpu_mgr = get_gpu_manager()
        processor_id = self.PROCESSOR_ID
        self.device, self.use_half = gpu_mgr.get_recommended_device(cam_id, processor_id)

        self.model = None
        self.model_loaded = False

        # ⭐ Frame skipping adaptativo
        if self.device == 'cpu':
            self._detection_interval = 7  # CPU: cada 7 frames
            print(f"⚙️ [Cam {cam_id}] CPU mode - Frame skip: 7")
        else:
            self._detection_interval = 5  # GPU: cada 5 frames
            print(f"⚡ [Cam {cam_id}] GPU mode - Frame skip: 5")

        print(f"🔥 Flow Cars OPTIMIZADO Cam {cam_id} - Device: {self.device}")

        # Mostrar memoria GPU
        gpu_info = gpu_mgr.get_gpu_memory_info()
        if gpu_info:
            print(
                f"📊 GPU: {gpu_info['usage_percent']:.1f}% | Slots: {gpu_info['slots_used']}/{gpu_info['slots_max']} | Cams: {gpu_info['assigned_cams']}")

        self._init_model()

        # Clases de vehículos COCO: 2=car, 3=motorcycle, 5=bus, 7=truck
        self.vehicle_classes = {
            2: 'Auto',
            3: 'Moto',
            5: 'Autobus',
            7: 'Camion'
        }

        # Colores BGR
        self.vehicle_colors = {
            'Auto': (0, 255, 0),  # Verde
            'Moto': (255, 0, 255),  # Magenta
            'Autobus': (0, 165, 255),  # Naranja
            'Camion': (255, 255, 0)  # Cyan
        }

        # Contadores
        self.vehicle_counts = {'Auto': 0, 'Moto': 0, 'Autobus': 0, 'Camion': 0}
        self.total_vehicles = 0
        self.max_vehicles_today = 0
        self.frames_since_save = 0

        # Frame skipping
        self._frame_counter = 0
        self._cached_detections = []

        # Stats
        self._detection_errors = 0

    def _init_csv(self):
        try:
            if not os.path.exists(self.csv_file):
                with open(self.csv_file, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(['timestamp', 'total', 'cars', 'motorcycles', 'buses', 'trucks', 'avg_confidence'])
        except Exception as e:
            print(f"⚠️ Error inicializando CSV: {e}")
            self.csv_enabled = False

    def _init_model(self):
        """Carga ULTRA OPTIMIZADA para Orin Nano"""
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries and not self.model_loaded:
            try:
                # ⭐ Preferir YOLOv8n (más ligero)
                model_list = ["models/yolov8n.pt", "yolov8n.pt"]
                selected_model = None

                for m in model_list:
                    if os.path.exists(m) or not m.startswith("models/"):
                        selected_model = m
                        break

                if not selected_model:
                    selected_model = "yolov8n.pt"

                print(f"📦 Cargando YOLO: {selected_model}")
                self.model = YOLO(selected_model)

                if self.model is None:
                    raise Exception("Modelo YOLO es None")

                # Config optimizada
                self.model.conf = 0.60  # ⭐ Aumentado para menos detecciones
                self.model.iou = 0.50  # ⭐ NMS más agresivo

                # ⭐ Warmup MÍNIMO (crítico para memoria)
                if self.device == 'cuda:0':
                    print(f"🔥 Warmup GPU (ultra minimal)...")
                    try:
                        # Imagen TINY 256x256 (vs 640x640)
                        dummy = np.zeros((256, 256, 3), dtype=np.uint8)

                        # Sin half precision en warmup
                        self.model(dummy, verbose=False, device=self.device, half=False, imgsz=256)

                        # Limpieza agresiva post-warmup
                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                            torch.cuda.ipc_collect()
                        import gc
                        gc.collect()

                        print(f"✅ GPU ready (minimal footprint)")
                    except Exception as e:
                        print(f"⚠️ Warmup error: {e}")

                self.model_loaded = True
                print(f"✅ YOLO cargado correctamente")

                # Limpieza final
                import gc
                gc.collect()

                return

            except Exception as e:
                retry_count += 1
                print(f"❌ Error cargando YOLO (intento {retry_count}): {e}")

                # Limpieza antes de reintentar
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.ipc_collect()
                import gc
                gc.collect()

                time.sleep(3)

        if not self.model_loaded:
            self.model = None

    def process_frame(self, frame):
        """
        Procesamiento lógico. Retorna DICT.
        """
        result = {'count': 0, 'breakdown': {}}

        try:
            self.increment_frame_count()

            if frame is None or frame.size == 0:
                return result

            h, w = frame.shape[:2]

            self._frame_counter += 1
            should_detect = (self._frame_counter % self._detection_interval == 0)

            if should_detect and self.model_loaded:
                self._run_detection(frame, w, h)

            # CSV Logic
            self.frames_since_save += 1
            if self.frames_since_save >= 30 and self.csv_enabled:
                self._save_to_csv()
                self.frames_since_save = 0

            result['count'] = self.total_vehicles
            result['breakdown'] = self.vehicle_counts.copy()

            # Alerta >= 2 vehículos
            if self.total_vehicles >= 2:
                result['intrusion'] = True
                result['alert_message'] = f"PRESENCIA: {self.total_vehicles} Vehículos detectados"

            return result

        except Exception as e:
            print(f"❌ Error en process_frame: {e}")
            return result

    def _run_detection(self, original_frame, original_width, original_height):
        """Detección con resize adaptativo"""
        try:
            if self.model is None or not self.model_loaded:
                return

            # ⭐ Resize adaptativo según device
            if self.device == 'cpu':
                detection_width = 480  # CPU: más pequeño
                detection_height = 360
            else:
                detection_width = 640  # GPU: normal
                detection_height = 480

            try:
                small_frame = cv2.resize(original_frame, (detection_width, detection_height),
                                         interpolation=cv2.INTER_LINEAR)
            except:
                return

            scale_x = original_width / detection_width
            scale_y = original_height / detection_height

            # ⭐ Max detections según device
            max_det = 10 if self.device == 'cpu' else 15

            try:
                # Filtrar clases de vehículos
                results = self.model.predict(
                    small_frame,
                    verbose=False,
                    classes=[2, 3, 5, 7],  # car, motorcycle, bus, truck
                    half=self.use_half,
                    device=self.device,
                    imgsz=detection_width,
                    max_det=max_det
                )
            except Exception as e:
                self._detection_errors += 1
                if self._detection_errors % 10 == 0:
                    print(f"⚠️ YOLO error ({self._detection_errors}): {e}")
                return

            detections = []
            current_counts = {'Auto': 0, 'Moto': 0, 'Autobus': 0, 'Camion': 0}
            total_v = 0

            for result in results:
                if result.boxes is None: continue
                for box in result.boxes:
                    try:
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        if any(np.isnan([x1, y1, x2, y2])): continue

                        x1 = int(x1 * scale_x)
                        y1 = int(y1 * scale_y)
                        x2 = int(x2 * scale_x)
                        y2 = int(y2 * scale_y)

                        x1 = max(0, min(x1, original_width))
                        x2 = max(0, min(x2, original_width))
                        y1 = max(0, min(y1, original_height))
                        y2 = max(0, min(y2, original_height))

                        cls = int(box.cls[0].cpu().numpy())
                        conf = float(box.conf[0].cpu().numpy())

                        if cls not in self.vehicle_classes: continue

                        v_type = self.vehicle_classes[cls]
                        current_counts[v_type] += 1
                        total_v += 1

                        detections.append({
                            'bbox': (x1, y1, x2, y2),
                            'confidence': conf,
                            'type': v_type,
                            'color': self.vehicle_colors[v_type]
                        })
                    except:
                        continue

            self._cached_detections = detections
            self.vehicle_counts = current_counts
            self.total_vehicles = total_v

            if self.total_vehicles > self.max_vehicles_today:
                self.max_vehicles_today = self.total_vehicles

        except Exception as e:
            print(f"❌ Error en _run_detection: {e}")

    def draw_detections(self, frame):
        """
        Dibuja sobre el frame (In-Place) usando datos cacheados
        """
        try:
            if frame is None or frame.size == 0:
                return

            h, w = frame.shape[:2]

            # Boxes
            for det in self._cached_detections:
                try:
                    x1, y1, x2, y2 = det['bbox']
                    conf = det['confidence']
                    v_type = det['type']
                    color = det['color']

                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

                    label = f"{v_type} {conf:.0%}"
                    (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

                    cv2.rectangle(frame, (x1, y1 - lh - 12), (x1 + lw + 10, y1), (0, 0, 0), -1)
                    cv2.rectangle(frame, (x1, y1 - lh - 10), (x1 + lw + 8, y1 - 2), color, -1)

                    cv2.putText(frame, label, (x1 + 4, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
                                cv2.LINE_AA)
                except:
                    continue

            # HUD
            self._draw_hud(frame, w, h)

        except Exception as e:
            print(f"❌ Error en draw_detections: {e}")

    def _draw_hud(self, frame, width, height):
        try:
            # Panel izquierdo
            overlay = frame.copy()
            hud_height = 200 + (len(self.vehicle_classes) * 30)
            cv2.rectangle(overlay, (0, 0), (350, hud_height), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

            cv2.putText(frame, "VEHICULOS", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(frame, f"Total: {self.total_vehicles}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (255, 255, 255), 2, cv2.LINE_AA)

            y_off = 110
            for v_type, count in self.vehicle_counts.items():
                col = self.vehicle_colors.get(v_type, (255, 255, 255))
                cv2.putText(frame, f"{v_type}: {count}", (10, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2,
                            cv2.LINE_AA)
                y_off += 30

            cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), (10, y_off + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (150, 150, 150), 1, cv2.LINE_AA)

        except:
            pass

    def _save_to_csv(self):
        try:
            if not self.csv_enabled: return

            avg = 0
            if self._cached_detections:
                avg = sum(d['confidence'] for d in self._cached_detections) / len(self._cached_detections)

            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    self.total_vehicles,
                    self.vehicle_counts['Auto'],
                    self.vehicle_counts['Moto'],
                    self.vehicle_counts['Autobus'],
                    self.vehicle_counts['Camion'],
                    round(avg, 2)
                ])
        except:
            pass