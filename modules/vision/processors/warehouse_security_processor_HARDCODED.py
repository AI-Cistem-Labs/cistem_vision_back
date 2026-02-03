# modules/vision/processors/warehouse_security_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os
from ultralytics import YOLO
from collections import defaultdict, deque
import numpy as np


class WarehouseSecurityProcessor(BaseProcessor):
    """
    Procesador para Almacén Interno
    Detecta personas con objetos (mochilas, bolsas, maletas)
    Monitorea tiempo de permanencia en zonas restringidas
    Genera alertas de posible sustracción

    CONFIGURACIÓN:
    - ROIs definidos directamente en código (hardcodeados)
    - Coordenadas obtenidas del script define_roi_coordinates.py
    """

    PROCESSOR_ID = 4
    PROCESSOR_LABEL = "Seguridad de Almacén"
    PROCESSOR_DESCRIPTION = "Monitorea acceso al almacén, detecta objetos sospechosos y tiempo de permanencia"

    def __init__(self, cam_id):
        super().__init__(cam_id)

        # Configurar CSV
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/warehouse_security_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # ============================================================
        # CARGAR MODELO YOLO
        # ============================================================
        try:
            # Usar YOLO11s (nuevo y más eficiente)
            model_path = "models/yolo11s.pt"
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                print(f"✅ Modelo YOLO11s cargado: {model_path}")
            else:
                # Fallback a YOLOv8s
                self.model = YOLO('yolov8s.pt')
                print("✅ Modelo YOLOv8s cargado (fallback)")

            # Configuración del modelo
            self.model.conf = 0.40  # Umbral de confianza
            self.model.iou = 0.45  # IoU threshold

        except Exception as e:
            print(f"❌ Error cargando modelo YOLO: {str(e)}")
            self.model = None

        # Clases objetivo de COCO dataset:
        # 0 = persona, 24 = backpack (mochila), 26 = handbag (bolso), 28 = suitcase (maleta)
        self.target_classes = [0, 24, 26, 28]

        self.object_classes = {
            24: 'Mochila',
            26: 'Bolso',
            28: 'Maleta'
        }

        # ============================================================
        # ✅ DEFINIR ROIs HARDCODEADOS
        # ============================================================

        # Desactivar ROI por defecto
        self.use_default_roi = False

        # ROI 1: Zona del Almacén (área principal restringida)
        self.zona_almacen = np.array([
            [1005, 802],
            [1618, 790],
            [1795, 1274],
            [1038, 1223],
            [400, 1199],
            [1040, 1218],
            [573, 839],
            [439, 1106],
        ], dtype=np.int32)

        # ROI 2: Puerta del Almacén (zona de acceso)
        self.puerta_almacen = np.array([
            [952, 12],
            [1018, 794],
            [1552, 443],
            [1716, 14],
        ], dtype=np.int32)

        # ⭐ IMPORTANTE: Definir cual es la zona restringida principal
        # (El código usa self.zona_restringida para las validaciones)
        self.zona_restringida = self.zona_almacen

        print("✅ ROIs cargados:")
        print(f"   - Zona Almacén: {len(self.zona_almacen)} puntos")
        print(f"   - Puerta Almacén: {len(self.puerta_almacen)} puntos")

        # Tracking de personas
        self.track_history = defaultdict(lambda: deque(maxlen=50))
        self.person_times = defaultdict(float)
        self.person_with_object = defaultdict(bool)

        # Tracking de accesos por puerta
        self.person_entered_through_door = defaultdict(bool)

        # Estadísticas
        self.total_alerts_today = 0
        self.current_people_in_zone = 0
        self.total_accesses_today = 0

        # Control de alertas (evitar spam)
        self.last_alert_time = defaultdict(lambda: None)
        self.alert_cooldown = 10  # segundos entre alertas

    def _init_csv(self):
        """Inicializa archivo CSV con headers"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp',
                    'event_type',
                    'person_id',
                    'time_in_zone',
                    'object_detected',
                    'object_type',
                    'alert_level',
                    'description'
                ])

    def process_frame(self, frame):
        """
        Procesa frame y detecta situaciones sospechosas en almacén
        """
        self.increment_frame_count()
        processed_frame = frame.copy()

        h, w = frame.shape[:2]

        # Variables del frame actual
        objects_in_scene = []
        people_in_zone = []
        people_at_door = []
        security_alert = False

        # ============================================================
        # DETECCIÓN CON YOLO
        # ============================================================
        if self.model is not None:
            try:
                results = self.model.track(
                    frame,
                    classes=self.target_classes,
                    persist=True,
                    verbose=False,
                    tracker="bytetrack.yaml"
                )

                if results[0].boxes.id is not None:
                    boxes = results[0].boxes.xyxy.cpu().numpy().astype(int)
                    ids = results[0].boxes.id.cpu().numpy().astype(int)
                    clss = results[0].boxes.cls.cpu().numpy().astype(int)
                    confs = results[0].boxes.conf.cpu().numpy()

                    # Primera pasada: identificar objetos
                    for box, track_id, cls, conf in zip(boxes, ids, clss, confs):
                        if cls in self.object_classes:
                            x1, y1, x2, y2 = box
                            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                            objects_in_scene.append({
                                'type': self.object_classes[cls],
                                'bbox': box,
                                'center': (cx, cy),
                                'conf': conf
                            })

                    # Segunda pasada: procesar personas
                    for box, track_id, cls, conf in zip(boxes, ids, clss, confs):
                        if cls == 0:  # Persona
                            x1, y1, x2, y2 = box
                            cx, cy = (x1 + x2) // 2, y2  # Centro en la base de los pies

                            # Guardar trayectoria
                            self.track_history[track_id].append((float(cx), float(cy)))

                            # Verificar si está en la puerta
                            in_door = cv2.pointPolygonTest(self.puerta_almacen, (cx, cy), False) >= 0
                            if in_door:
                                people_at_door.append(track_id)
                                if not self.person_entered_through_door[track_id]:
                                    self.person_entered_through_door[track_id] = True
                                    self.total_accesses_today += 1

                            # Verificar si está en zona restringida (almacén)
                            in_zone = cv2.pointPolygonTest(self.zona_restringida, (cx, cy), False) >= 0

                            if in_zone:
                                # Incrementar tiempo en zona
                                fps = 30  # Asumir 30 fps
                                self.person_times[track_id] += (1.0 / fps)
                                time_in_zone = self.person_times[track_id]

                                people_in_zone.append(track_id)

                                # Verificar si persona tiene objeto cerca
                                has_object = False
                                object_type = None

                                for obj in objects_in_scene:
                                    obj_cx, obj_cy = obj['center']
                                    # Si objeto está cerca de la persona (dentro de 150px)
                                    if abs(obj_cx - cx) < 100 and abs(obj_cy - cy) < 150:
                                        has_object = True
                                        object_type = obj['type']
                                        self.person_with_object[track_id] = True
                                        break

                                # Determinar estado y color
                                alert_level = "NORMAL"
                                color = (0, 255, 0)  # Verde
                                status_text = "Autorizado"

                                # LÓGICA DE ALERTAS
                                if has_object:
                                    alert_level = "CRITICAL"
                                    color = (0, 0, 255)  # Rojo
                                    status_text = f"ALERTA: {object_type.upper()}"
                                    security_alert = True

                                    # Generar alerta (con cooldown para evitar spam)
                                    current_time = datetime.now()
                                    last_alert = self.last_alert_time[track_id]

                                    if (last_alert is None or
                                            (current_time - last_alert).total_seconds() > self.alert_cooldown):
                                        self.generate_alert(
                                            f"Posible sustracción - Persona #{track_id} con {object_type}",
                                            level="CRITICAL",
                                            context={
                                                "person_id": track_id,
                                                "object_type": object_type,
                                                "time_in_zone": round(time_in_zone, 1),
                                                "location": "Almacén Interno"
                                            }
                                        )

                                        self.last_alert_time[track_id] = current_time
                                        self.total_alerts_today += 1

                                        # Guardar en CSV
                                        self._save_event(
                                            'POSIBLE_SUSTRACCION',
                                            track_id,
                                            time_in_zone,
                                            object_type,
                                            'CRITICAL'
                                        )

                                elif time_in_zone > 30:  # Más de 30 segundos
                                    alert_level = "WARNING"
                                    color = (0, 165, 255)  # Naranja
                                    status_text = "Tiempo prolongado"

                                # ============================================================
                                # DIBUJAR PERSONA
                                # ============================================================

                                # Bounding box
                                cv2.rectangle(processed_frame, (x1, y1), (x2, y2), color, 3)

                                # Etiqueta superior
                                label_top = f"ID:{track_id} {status_text}"
                                cv2.putText(processed_frame, label_top, (x1, y1 - 25),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                                # Tiempo
                                label_time = f"Tiempo: {time_in_zone:.1f}s"
                                cv2.putText(processed_frame, label_time, (x1, y2 + 20),
                                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                                # Trayectoria
                                if len(self.track_history[track_id]) > 2:
                                    points = np.array(list(self.track_history[track_id]),
                                                      dtype=np.int32).reshape((-1, 1, 2))
                                    cv2.polylines(processed_frame, [points], False,
                                                  (255, 255, 0), 2)

                    # Dibujar objetos detectados
                    for obj in objects_in_scene:
                        x1, y1, x2, y2 = obj['bbox']
                        cv2.rectangle(processed_frame, (x1, y1), (x2, y2),
                                      (255, 0, 255), 2)
                        cv2.putText(processed_frame, f"{obj['type'].upper()}",
                                    (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.6, (255, 0, 255), 2)

            except Exception as e:
                print(f"❌ Error en detección: {str(e)}")

        # Actualizar estadísticas
        self.current_people_in_zone = len(people_in_zone)

        # ============================================================
        # DIBUJAR ROIs
        # ============================================================
        overlay = processed_frame.copy()

        # Zona del almacén (restringida)
        color_zona = (0, 0, 200) if security_alert else (0, 0, 255)  # Rojo
        pts_almacen = self.zona_almacen.reshape((-1, 1, 2))
        cv2.fillPoly(overlay, [pts_almacen], color_zona)
        cv2.polylines(processed_frame, [pts_almacen], True, color_zona, 2)

        # Etiqueta zona almacén
        x, y = self.zona_almacen[0]
        cv2.putText(processed_frame, "ZONA RESTRINGIDA", (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_zona, 2)

        # Puerta del almacén
        pts_puerta = self.puerta_almacen.reshape((-1, 1, 2))
        color_puerta = (0, 255, 0)  # Verde
        cv2.fillPoly(overlay, [pts_puerta], color_puerta)
        cv2.polylines(processed_frame, [pts_puerta], True, color_puerta, 2)

        # Etiqueta puerta
        x2, y2 = self.puerta_almacen[0]
        cv2.putText(processed_frame, "ACCESO", (x2, y2 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_puerta, 2)

        # Aplicar overlay semi-transparente
        cv2.addWeighted(overlay, 0.25, processed_frame, 0.75, 0, processed_frame)

        # ============================================================
        # HUD - DASHBOARD DE AUDITORÍA
        # ============================================================

        # Panel principal
        cv2.rectangle(processed_frame, (0, 0), (500, 230), (20, 20, 20), -1)

        # Título
        cv2.putText(processed_frame, "AUDITORIA ALMACEN INTERNO", (15, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Estado de seguridad
        if security_alert:
            cv2.putText(processed_frame, "ALERTA: OBJETO EN MOVIMIENTO", (15, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
            cv2.putText(processed_frame, f"Evento #AL-{self.total_alerts_today:04d}",
                        (15, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        else:
            cv2.putText(processed_frame, "Monitoreo Activo", (15, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(processed_frame, "Sin incidencias detectadas", (15, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1)

        # Estadísticas
        cv2.putText(processed_frame, f"Personas en zona: {self.current_people_in_zone}",
                    (15, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(processed_frame, f"Objetos detectados: {len(objects_in_scene)}",
                    (15, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        cv2.putText(processed_frame, f"Accesos hoy: {self.total_accesses_today}",
                    (15, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(processed_frame, timestamp, (15, 215),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        # Indicador de modelo
        model_status = "YOLO11s" if self.model else "Sin Modelo"
        status_color = (0, 255, 0) if self.model else (0, 0, 255)
        cv2.circle(processed_frame, (w - 30, 30), 15, status_color, -1)
        cv2.putText(processed_frame, model_status, (w - 180, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, status_color, 2)

        return processed_frame

    def _save_event(self, event_type, person_id, time_in_zone, object_type, alert_level):
        """Guarda evento en CSV"""
        description = f"Persona {person_id}"
        if object_type:
            description += f" con {object_type}"

        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                event_type,
                person_id,
                round(time_in_zone, 2),
                object_type if object_type else 'N/A',
                object_type if object_type else 'N/A',
                alert_level,
                description
            ])