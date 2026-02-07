# modules/vision/processors/flow_cars_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
from ultralytics import YOLO


class FlowCarsProcessor(BaseProcessor):
    """Detector de vehículos con YOLO11s y boxes"""

    PROCESSOR_ID = 3
    PROCESSOR_LABEL = "Flujo de Vehículos"
    PROCESSOR_DESCRIPTION = "Detecta y cuenta vehículos (autos, motos, camiones)"

    def __init__(self, cam_id):
        super().__init__(cam_id)
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/vehicle_flow_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # Cargar YOLO
        try:
            model_path = "models/yolo11s.pt"
            self.model = YOLO(model_path) if os.path.exists(model_path) else YOLO('yolov8n.pt')
            self.model.conf, self.model.iou = 0.40, 0.45
            print(f"✅ Modelo cargado para Flow Cars")
        except Exception as e:
            print(f"❌ Error cargando YOLO: {e}")
            self.model = None

        # Clases de vehículos COCO: 2=car, 3=motorcycle, 5=bus, 7=truck
        self.vehicle_classes = {
            2: 'Auto',
            3: 'Moto',
            5: 'Autobus',
            7: 'Camion'
        }

        self.vehicle_counts = {'Auto': 0, 'Moto': 0, 'Autobus': 0, 'Camion': 0}
        self.total_vehicles = 0
        self.max_vehicles_today = 0
        self.frames_since_save = 0

    def _init_csv(self):
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'total', 'cars', 'motorcycles', 'buses', 'trucks', 'avg_confidence'])

    def process_frame(self, frame):
        self.increment_frame_count()
        processed_frame = frame.copy()
        h, w = frame.shape[:2]

        # Reset contadores
        current_counts = {'Auto': 0, 'Moto': 0, 'Autobus': 0, 'Camion': 0}
        self.total_vehicles = 0
        confidences = []

        # Detectar vehículos
        if self.model:
            try:
                results = self.model(frame, verbose=False, classes=[2, 3, 5, 7])
                for result in results:
                    for box in result.boxes:
                        cls = int(box.cls[0])
                        if cls in self.vehicle_classes:
                            conf = float(box.conf[0])
                            confidences.append(conf)

                            x1, y1, x2, y2 = map(int, box.xyxy[0])
                            vehicle_type = self.vehicle_classes[cls]
                            current_counts[vehicle_type] += 1
                            self.total_vehicles += 1

                            # ✅ COLORES POR TIPO
                            colors = {
                                'Auto': (0, 255, 0),  # Verde
                                'Moto': (255, 0, 255),  # Magenta
                                'Autobus': (0, 165, 255),  # Naranja
                                'Camion': (255, 255, 0)  # Cyan
                            }
                            color = colors.get(vehicle_type, (255, 255, 255))

                            # BOX
                            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color, 3)

                            # Label
                            label = f"{vehicle_type} {conf:.0%}"
                            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                            cv2.rectangle(processed_frame, (x1, y1 - label_size[1] - 10),
                                          (x1 + label_size[0], y1), color, -1)
                            cv2.putText(processed_frame, label, (x1, y1 - 5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

                            # Punto central
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                            cv2.circle(processed_frame, (cx, cy), 5, color, -1)
            except Exception as e:
                print(f"❌ Error YOLO: {e}")

        # Actualizar máximo
        if self.total_vehicles > self.max_vehicles_today:
            self.max_vehicles_today = self.total_vehicles

        self.vehicle_counts = current_counts

        # HUD Panel izquierdo
        overlay = processed_frame.copy()
        cv2.rectangle(overlay, (0, 0), (400, 280), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, processed_frame, 0.3, 0, processed_frame)

        cv2.putText(processed_frame, "FLUJO DE VEHICULOS", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

        cv2.putText(processed_frame, f"Total: {self.total_vehicles}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Desglose
        y_offset = 100
        for v_type, count in current_counts.items():
            if count > 0:
                colors = {'Auto': (0, 255, 0), 'Moto': (255, 0, 255),
                          'Autobus': (0, 165, 255), 'Camion': (255, 255, 0)}
                color = colors[v_type]
                cv2.putText(processed_frame, f"{v_type}: {count}", (10, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                y_offset += 30

        cv2.putText(processed_frame, datetime.now().strftime("%H:%M:%S"), (10, 260),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        # Panel derecho
        overlay2 = processed_frame.copy()
        cv2.rectangle(overlay2, (w - 300, 0), (w, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay2, 0.7, processed_frame, 0.3, 0, processed_frame)

        cv2.putText(processed_frame, f"Max. del dia: {self.max_vehicles_today}", (w - 290, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            cv2.putText(processed_frame, f"Confianza: {avg_conf:.0%}", (w - 290, 65),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # Indicador modelo
        model_status = "YOLO11s" if self.model else "Sin Modelo"
        status_color = (0, 255, 0) if self.model else (0, 0, 255)
        cv2.circle(processed_frame, (w - 30, h - 30), 15, status_color, -1)
        cv2.putText(processed_frame, model_status, (w - 180, h - 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)

        # Alertas
        if self.total_vehicles > 5 and self.frame_count % 30 == 0:
            self.generate_alert(
                f"Alta densidad vehicular - {self.total_vehicles} vehículos",
                level="WARNING",
                context={"cam_id": self.cam_id, "total": self.total_vehicles, "breakdown": current_counts}
            )

        # CSV
        self.frames_since_save += 1
        if self.frames_since_save >= 30:
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            self._save_to_csv(current_counts, avg_conf)
            self.frames_since_save = 0

        return processed_frame

    def _save_to_csv(self, counts, avg_confidence):
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                self.total_vehicles,
                counts['Auto'],
                counts['Moto'],
                counts['Autobus'],
                counts['Camion'],
                round(avg_confidence, 2)
            ])