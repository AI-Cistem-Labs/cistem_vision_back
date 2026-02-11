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
    Detector de vehículos INFALIBLE + OPTIMIZADO

    🛡️ INFALIBLE:
    ✅ Try-catch exhaustivo en todas las operaciones
    ✅ Fallback si YOLO falla robusto
    ✅ Separación Process/Draw para evitar crashes en Manager

    🚀 OPTIMIZADO:
    ✅ Frame skipping (5x menos inferencias)
    ✅ Resize inteligente (6.6x menos píxeles)
    ✅ Clasificación de 4 tipos de vehículos
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

        # Device
        self.device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
        self.use_half = torch.cuda.is_available()
        self.model = None
        self.model_loaded = False

        print(f"🔥 Flow Cars OPTIMIZADO Cam {cam_id} - Device: {self.device}")

        self._init_model()

        # Clases de vehículos COCO: 2=car, 3=motorcycle, 5=bus, 7=truck
        self.vehicle_classes = {
            2: 'Auto',
            3: 'Moto',
            5: 'Autobus',
            7: 'Camion'
        }

        # Colores RGB (OpenCV usa BGR, invertiremos al dibujar si necesario, pero definimos BGR aquí)
        self.vehicle_colors = {
            'Auto': (0, 255, 0),       # Verde
            'Moto': (255, 0, 255),     # Magenta
            'Autobus': (0, 165, 255),  # Naranja
            'Camion': (255, 255, 0)    # Cyan
        }

        # Contadores
        self.vehicle_counts = {'Auto': 0, 'Moto': 0, 'Autobus': 0, 'Camion': 0}
        self.total_vehicles = 0
        self.max_vehicles_today = 0
        self.frames_since_save = 0

        # Frame skipping
        self._detection_interval = 5
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
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries and not self.model_loaded:
            try:
                # Intentar cargar modelo optimizado o fallback standard
                model_list = ["models/yolo11s.pt", "models/yolov8n.pt", "yolov8n.pt"]
                selected_model = None

                for m in model_list:
                    if os.path.exists(m) or not m.startswith("models/"):
                        selected_model = m
                        break
                
                if not selected_model:
                     selected_model = "yolov8n.pt"

                print(f"📦 Cargando YOLO: {selected_model}")
                self.model = YOLO(selected_model)

                # Config
                self.model.conf = 0.55
                self.model.iou = 0.45

                # Warmup
                if self.device == 'cuda:0':
                    print(f"🔥 Warmup GPU...")
                    dummy = np.zeros((640, 640, 3), dtype=np.uint8)
                    self.model(dummy, verbose=False, device=self.device, half=True, imgsz=640)
                    print(f"✅ GPU ready")

                self.model_loaded = True
                print(f"✅ YOLO cargado correctamente")
                return

            except Exception as e:
                retry_count += 1
                print(f"❌ Error cargando YOLO (intento {retry_count}): {e}")
                time.sleep(2)
        
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
            result['breakdown'] = self.vehicle_counts

            # 🔥 Alerta >= 2 vehículos
            if self.total_vehicles >= 2:
                result['intrusion'] = True
                result['alert_message'] = f"PRESENCIA: {self.total_vehicles} Vehículos"

            return result

        except Exception as e:
            print(f"❌ Error en process_frame: {e}")
            return result

    def _run_detection(self, original_frame, original_width, original_height):
        try:
            if self.model is None or not self.model_loaded: return

            detection_width = 640
            detection_height = 480
            
            try:
                small_frame = cv2.resize(original_frame, (detection_width, detection_height), interpolation=cv2.INTER_LINEAR)
            except:
                return

            scale_x = original_width / detection_width
            scale_y = original_height / detection_height

            try:
                # Filtrar clases de vehículos
                results = self.model.predict(
                    small_frame,
                    verbose=False,
                    classes=[2, 3, 5, 7], 
                    half=self.use_half,
                    device=self.device,
                    imgsz=640,
                    max_det=30
                )
            except Exception as e:
                self._detection_errors += 1
                if self._detection_errors % 10 == 0:
                    print(f"⚠️ YOLO Inference error: {e}")
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

                    cv2.rectangle(frame, (x1, y1-lh-12), (x1+lw+10, y1), (0,0,0), -1)
                    cv2.rectangle(frame, (x1, y1-lh-10), (x1+lw+8, y1-2), color, -1)

                    cv2.putText(frame, label, (x1+4, y1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 2, cv2.LINE_AA)
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

            cv2.putText(frame, "VEHICULOS", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,0), 2, cv2.LINE_AA)
            cv2.putText(frame, f"Total: {self.total_vehicles}", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255,255,255), 2, cv2.LINE_AA)

            y_off = 110
            for v_type, count in self.vehicle_counts.items():
                col = self.vehicle_colors.get(v_type, (255,255,255))
                cv2.putText(frame, f"{v_type}: {count}", (10, y_off), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2, cv2.LINE_AA)
                y_off += 30

            cv2.putText(frame, datetime.now().strftime("%H:%M:%S"), (10, y_off+20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150,150,150), 1, cv2.LINE_AA)

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