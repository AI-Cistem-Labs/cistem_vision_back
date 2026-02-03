# modules/vision/processors/flow_cars.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
from ultralytics import YOLO


class FlowCarsProcessor(BaseProcessor):
    """
    Procesador que detecta y cuenta vehículos (autos, camiones, motos)
    Útil para estacionamientos y control de tráfico
    """

    PROCESSOR_ID = 3
    PROCESSOR_LABEL = "Flujo de Vehículos"
    PROCESSOR_DESCRIPTION = "Detecta y cuenta vehículos en tiempo real. Recomendado para estacionamientos y accesos vehiculares"

    def __init__(self, cam_id):
        super().__init__(cam_id)

        # Configurar CSV
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/vehicle_flow_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # ============================================================
        # CARGAR MODELO YOLO PARA DETECCIÓN DE VEHÍCULOS
        # ============================================================
        try:
            # Intentar cargar modelo personalizado primero
            model_path = "models/yolo11n.pt"
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                print(f"✅ Modelo personalizado cargado: {model_path}")
            else:
                # Fallback a modelo preentrenado
                self.model = YOLO('yolov8n.pt')
                print("✅ Modelo YOLO preentrenado cargado")

            # Configuración del modelo
            self.model.conf = 0.40  # Umbral de confianza
            self.model.iou = 0.45  # IoU threshold

        except Exception as e:
            print(f"❌ Error cargando modelo YOLO: {str(e)}")
            self.model = None

        # Clases de vehículos en COCO dataset
        # 2: car, 3: motorcycle, 5: bus, 7: truck
        self.vehicle_classes = {
            2: 'Auto',
            3: 'Moto',
            5: 'Autobus',
            7: 'Camion'
        }

        # Contadores
        self.vehicle_counts = {
            'Auto': 0,
            'Moto': 0,
            'Autobus': 0,
            'Camion': 0
        }

        self.total_vehicles = 0
        self.frames_since_save = 0
        self.max_vehicles_today = 0

        # Línea de conteo
        self.counting_line_y = None
        self.vehicles_in = 0
        self.vehicles_out = 0

    def _init_csv(self):
        """Inicializa archivo CSV con headers"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'total_vehicles',
                    'cars',
                    'motorcycles',
                    'buses',
                    'trucks',
                    'vehicles_in',
                    'vehicles_out',
                    'confidence_avg'
                ])

    def process_frame(self, frame):
        """
        Procesa frame y detecta vehículos usando YOLO
        """
        self.increment_frame_count()
        processed_frame = frame.copy()

        h, w = frame.shape[:2]

        # Definir línea de conteo
        if self.counting_line_y is None:
            self.counting_line_y = h // 2

        # Reset contadores por frame
        current_counts = {
            'Auto': 0,
            'Moto': 0,
            'Autobus': 0,
            'Camion': 0
        }

        total_current = 0
        confidences = []

        # ============================================================
        # DETECCIÓN DE VEHÍCULOS CON YOLO
        # ============================================================
        if self.model is not None:
            try:
                # Realizar detección
                results = self.model(frame, verbose=False)

                # Procesar resultados
                for result in results:
                    boxes = result.boxes

                    for box in boxes:
                        # Obtener clase
                        cls = int(box.cls[0])

                        # Verificar si es un vehículo
                        if cls in self.vehicle_classes:
                            # Obtener confianza
                            conf = float(box.conf[0])
                            confidences.append(conf)

                            # Obtener bounding box
                            x1, y1, x2, y2 = map(int, box.xyxy[0])

                            # Centro del vehículo
                            center_x = (x1 + x2) // 2
                            center_y = (y1 + y2) // 2

                            # Tipo de vehículo
                            vehicle_type = self.vehicle_classes[cls]
                            current_counts[vehicle_type] += 1
                            total_current += 1

                            # ============================================================
                            # DIBUJAR BOUNDING BOX
                            # ============================================================

                            # Color según tipo de vehículo
                            colors = {
                                'Auto': (0, 255, 0),  # Verde
                                'Moto': (255, 0, 255),  # Magenta
                                'Autobus': (0, 165, 255),  # Naranja
                                'Camion': (255, 255, 0)  # Cyan
                            }
                            color = colors.get(vehicle_type, (255, 255, 255))

                            # Rectángulo
                            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color, 3)

                            # Etiqueta
                            label = f"{vehicle_type} {conf:.0%}"
                            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)

                            # Fondo para el texto
                            cv2.rectangle(processed_frame,
                                          (x1, y1 - label_size[1] - 10),
                                          (x1 + label_size[0], y1),
                                          color, -1)

                            # Texto
                            cv2.putText(processed_frame, label, (x1, y1 - 5),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

                            # Punto central
                            cv2.circle(processed_frame, (center_x, center_y), 5, color, -1)

            except Exception as e:
                print(f"❌ Error en detección YOLO: {str(e)}")

        # Actualizar contadores totales
        self.vehicle_counts = current_counts
        self.total_vehicles = total_current

        if total_current > self.max_vehicles_today:
            self.max_vehicles_today = total_current

        # ============================================================
        # DIBUJAR LÍNEA DE CONTEO
        # ============================================================
        cv2.line(processed_frame, (0, self.counting_line_y),
                 (w, self.counting_line_y), (255, 255, 0), 3)
        cv2.putText(processed_frame, "LINEA DE CONTEO",
                    (10, self.counting_line_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        # ============================================================
        # HUD (Heads-Up Display)
        # ============================================================

        # Panel izquierdo - Información general
        overlay = processed_frame.copy()
        cv2.rectangle(overlay, (0, 0), (400, 240), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, processed_frame, 0.3, 0, processed_frame)

        # Título
        cv2.putText(processed_frame, "FLUJO DE VEHICULOS", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

        # Total de vehículos
        cv2.putText(processed_frame, f"Total: {total_current}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Desglose por tipo
        y_offset = 100
        for vehicle_type, count in current_counts.items():
            if count > 0:
                colors = {
                    'Auto': (0, 255, 0),
                    'Moto': (255, 0, 255),
                    'Autobus': (0, 165, 255),
                    'Camion': (255, 255, 0)
                }
                color = colors[vehicle_type]
                cv2.putText(processed_frame, f"{vehicle_type}: {count}",
                            (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                y_offset += 30

        # Timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        cv2.putText(processed_frame, timestamp, (10, 220),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        # Panel derecho - Estadísticas
        overlay2 = processed_frame.copy()
        cv2.rectangle(overlay2, (w - 300, 0), (w, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay2, 0.7, processed_frame, 0.3, 0, processed_frame)

        # Máximo del día
        cv2.putText(processed_frame, f"Max. del dia: {self.max_vehicles_today}",
                    (w - 290, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # Confianza promedio
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            cv2.putText(processed_frame, f"Confianza: {avg_conf:.0%}",
                        (w - 290, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # Entradas/Salidas
        cv2.putText(processed_frame, f"Entradas: {self.vehicles_in}",
                    (w - 290, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(processed_frame, f"Salidas: {self.vehicles_out}",
                    (w - 290, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

        # Indicador de modelo
        model_status = "YOLO" if self.model else "Sin Modelo"
        status_color = (0, 255, 0) if self.model else (0, 0, 255)
        cv2.circle(processed_frame, (w - 30, h - 30), 15, status_color, -1)
        cv2.putText(processed_frame, model_status, (w - 150, h - 23),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)

        # ============================================================
        # GUARDAR EN CSV
        # ============================================================
        self.frames_since_save += 1
        if self.frames_since_save >= 30:  # Cada segundo
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            self._save_to_csv(total_current, current_counts, avg_conf)
            self.frames_since_save = 0

            # Generar alerta si hay congestión
            if total_current > 15:
                self.generate_alert(
                    f"Alta densidad vehicular - {total_current} vehículos detectados",
                    level="PRECAUCION",
                    context={
                        "total": total_current,
                        "breakdown": current_counts,
                        "confidence": round(avg_conf, 2)
                    }
                )

        return processed_frame

    def _save_to_csv(self, total, counts, confidence):
        """Guarda datos en CSV"""
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                total,
                counts['Auto'],
                counts['Moto'],
                counts['Autobus'],
                counts['Camion'],
                self.vehicles_in,
                self.vehicles_out,
                round(confidence, 2)
            ])