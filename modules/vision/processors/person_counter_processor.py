# modules/vision/processors/person_counter_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
from ultralytics import YOLO


class PersonCounterProcessor(BaseProcessor):
    """
    Procesador que cuenta personas usando YOLO
    Detecta personas reales usando modelo de deep learning
    """

    PROCESSOR_ID = 1
    PROCESSOR_LABEL = "Contador de Personas"
    PROCESSOR_DESCRIPTION = "Análisis de flujo peatonal en tiempo real usando IA"

    def __init__(self, cam_id):
        super().__init__(cam_id)

        # Configurar CSV
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/person_count_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # ============================================================
        # CARGAR MODELO YOLO PARA DETECCIÓN DE PERSONAS
        # ============================================================
        try:
            # Intentar cargar modelo personalizado primero
            model_path = "models/bestpersonas.pt"
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                print(f"✅ Modelo personalizado cargado: {model_path}")
            else:
                # Fallback a modelo preentrenado de YOLO
                self.model = YOLO('yolov8n.pt')  # Nano model (más rápido)
                print("✅ Modelo YOLO preentrenado cargado")

            # Configuración del modelo
            self.model.conf = 0.45  # Umbral de confianza (45%)
            self.model.iou = 0.45  # IoU threshold para NMS

        except Exception as e:
            print(f"❌ Error cargando modelo YOLO: {str(e)}")
            self.model = None

        # Variables para estadísticas
        self.last_count = 0
        self.frames_since_save = 0
        self.max_count_today = 0

        # Línea de conteo (horizontal, mitad del frame)
        self.counting_line_y = None
        self.people_crossed_up = 0
        self.people_crossed_down = 0

        # Tracking simple para evitar contar la misma persona varias veces
        self.tracked_people = {}  # {person_id: {"last_y": y, "counted": bool}}
        self.next_person_id = 0

    def _init_csv(self):
        """Inicializa archivo CSV con headers"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'person_count',
                    'people_crossed_up',
                    'people_crossed_down',
                    'alert_level',
                    'confidence_avg'
                ])

    def process_frame(self, frame):
        """
        Procesa frame y cuenta personas usando YOLO
        """
        self.increment_frame_count()
        processed_frame = frame.copy()

        h, w = frame.shape[:2]

        # Definir línea de conteo en primer frame
        if self.counting_line_y is None:
            self.counting_line_y = h // 2

        person_count = 0
        confidences = []
        detections = []

        # ============================================================
        # DETECCIÓN DE PERSONAS CON YOLO
        # ============================================================
        if self.model is not None:
            try:
                # Realizar detección
                results = self.model(frame, verbose=False)

                # Procesar resultados
                for result in results:
                    boxes = result.boxes

                    for box in boxes:
                        # Obtener clase detectada
                        cls = int(box.cls[0])

                        # Clase 0 = persona en COCO dataset
                        if cls == 0:
                            # Obtener confianza
                            conf = float(box.conf[0])
                            confidences.append(conf)

                            # Obtener bounding box
                            x1, y1, x2, y2 = map(int, box.xyxy[0])

                            # Centro de la persona
                            center_x = (x1 + x2) // 2
                            center_y = (y1 + y2) // 2

                            detections.append({
                                'bbox': (x1, y1, x2, y2),
                                'center': (center_x, center_y),
                                'conf': conf
                            })

                            person_count += 1

                            # ============================================================
                            # DIBUJAR BOUNDING BOX
                            # ============================================================

                            # Color según confianza (verde alto, amarillo medio, rojo bajo)
                            if conf > 0.7:
                                color = (0, 255, 0)  # Verde
                            elif conf > 0.5:
                                color = (0, 255, 255)  # Amarillo
                            else:
                                color = (0, 165, 255)  # Naranja

                            # Rectángulo alrededor de la persona
                            cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color, 3)

                            # Etiqueta con confianza
                            label = f"Persona {conf:.0%}"
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
                # Continuar sin modelo
                pass

        # Actualizar estadísticas
        self.last_count = person_count
        if person_count > self.max_count_today:
            self.max_count_today = person_count

        # ============================================================
        # DIBUJAR LÍNEA DE CONTEO
        # ============================================================
        cv2.line(processed_frame, (0, self.counting_line_y),
                 (w, self.counting_line_y), (0, 255, 255), 3)
        cv2.putText(processed_frame, "LINEA DE CONTEO",
                    (10, self.counting_line_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

        # ============================================================
        # HUD (Heads-Up Display)
        # ============================================================

        # Fondo semi-transparente
        overlay = processed_frame.copy()
        cv2.rectangle(overlay, (0, 0), (500, 180), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, processed_frame, 0.3, 0, processed_frame)

        # Título
        cv2.putText(processed_frame, "CONTADOR DE PERSONAS - YOLO", (10, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Personas detectadas
        cv2.putText(processed_frame, f"Personas detectadas: {person_count}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Máximo del día
        cv2.putText(processed_frame, f"Maximo del dia: {self.max_count_today}", (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # Confianza promedio
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            cv2.putText(processed_frame, f"Confianza: {avg_conf:.0%}", (10, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 2)

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(processed_frame, timestamp, (10, 160),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        # Indicador de modelo activo
        model_status = "YOLO Activo" if self.model else "Sin Modelo"
        status_color = (0, 255, 0) if self.model else (0, 0, 255)
        cv2.circle(processed_frame, (w - 30, 30), 15, status_color, -1)
        cv2.putText(processed_frame, model_status, (w - 150, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, status_color, 2)

        # ============================================================
        # GUARDAR EN CSV
        # ============================================================
        self.frames_since_save += 1
        if self.frames_since_save >= 30:  # Cada segundo (~30fps)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0
            self._save_to_csv(person_count, avg_conf)
            self.frames_since_save = 0

            # Generar alerta si hay aglomeración
            if person_count > 10:
                self.generate_alert(
                    f"Aglomeración detectada - {person_count} personas",
                    level="PRECAUCION",
                    context={
                        "count": person_count,
                        "confidence": round(avg_conf, 2)
                    }
                )

        return processed_frame

    def _save_to_csv(self, count, confidence):
        """Guarda datos en CSV"""
        alert_level = "NORMAL"
        if count > 20:
            alert_level = "CRITICAL"
        elif count > 10:
            alert_level = "WARNING"

        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                count,
                self.people_crossed_up,
                self.people_crossed_down,
                alert_level,
                round(confidence, 2)
            ])


# ============================================================
# CLASE ALTERNATIVA: FlowPersonsProcessor
# (Para mantener compatibilidad con registry.py existente)
# ============================================================
class FlowPersonsProcessor(PersonCounterProcessor):
    """
    Alias para mantener compatibilidad con código existente
    """
    pass