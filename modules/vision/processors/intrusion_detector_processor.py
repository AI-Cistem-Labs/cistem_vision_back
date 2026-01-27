# modules/vision/processors/intrusion_detector_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os


class IntrusionDetectorProcessor(BaseProcessor):
    """
    Procesador que detecta intrusos en zonas restringidas
    """

    PROCESSOR_ID = 2
    PROCESSOR_LABEL = "Detector de Intrusos"
    PROCESSOR_DESCRIPTION = "Monitorea áreas restringidas y detecta personas no autorizadas"

    def __init__(self, cam_id):
        super().__init__(cam_id)

        # Configurar CSV
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/intrusion_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # Zona restringida (centro del frame)
        self.restricted_zone = None

        # Background subtractor
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=32,
            detectShadows=True
        )

        self.intrusion_detected = False
        self.frames_with_intrusion = 0
        self.last_alert_time = None

    def _init_csv(self):
        """Inicializa archivo CSV"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'intrusion_detected', 'confidence', 'zone'])

    def process_frame(self, frame):
        """
        Detecta intrusiones en zona restringida
        IMPORTANTE: Dibuja la zona y las detecciones
        """
        self.increment_frame_count()
        processed_frame = frame.copy()

        h, w = frame.shape[:2]

        # Definir zona restringida (centro del frame) en primer frame
        if self.restricted_zone is None:
            zone_w = w // 3
            zone_h = h // 3
            zone_x = (w - zone_w) // 2
            zone_y = (h - zone_h) // 2
            self.restricted_zone = (zone_x, zone_y, zone_w, zone_h)

        x, y, zone_w, zone_h = self.restricted_zone

        # ============================================================
        # DIBUJAR ZONA RESTRINGIDA
        # ============================================================
        color = (0, 0, 255) if self.intrusion_detected else (255, 165, 0)  # Rojo si intrusión, naranja si no
        thickness = 4 if self.intrusion_detected else 2

        # Rectángulo de la zona
        cv2.rectangle(processed_frame, (x, y), (x + zone_w, y + zone_h), color, thickness)

        # Rellenar zona con transparencia si hay intrusión
        if self.intrusion_detected:
            overlay = processed_frame.copy()
            cv2.rectangle(overlay, (x, y), (x + zone_w, y + zone_h), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.2, processed_frame, 0.8, 0, processed_frame)

        # Etiqueta de la zona
        cv2.putText(processed_frame, "ZONA RESTRINGIDA", (x + 10, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # Aplicar substracción de fondo
        fg_mask = self.background_subtractor.apply(frame)

        # Extraer ROI (región de interés) de la zona restringida
        roi_mask = fg_mask[y:y + zone_h, x:x + zone_w]

        # Contar píxeles blancos (movimiento) en la zona
        white_pixels = cv2.countNonZero(roi_mask)
        total_pixels = zone_w * zone_h
        movement_percentage = (white_pixels / total_pixels) * 100

        # Detectar intrusión si hay más del 5% de movimiento
        if movement_percentage > 5:
            self.intrusion_detected = True
            self.frames_with_intrusion += 1

            # Generar alerta después de 10 frames consecutivos
            if self.frames_with_intrusion == 10:
                current_time = datetime.now()

                # Evitar spam de alertas (una cada 10 segundos)
                if (self.last_alert_time is None or
                        (current_time - self.last_alert_time).seconds > 10):
                    self.generate_alert(
                        "Intruso detectado en área restringida - Sector A3",
                        level="CRITICAL",
                        context={
                            "zone": "Sector A3",
                            "confidence": round(movement_percentage, 2)
                        }
                    )
                    self.last_alert_time = current_time

                    # Guardar en CSV
                    self._save_to_csv(True, movement_percentage)
        else:
            if self.intrusion_detected:
                # Fin de intrusión
                self._save_to_csv(False, 0)

            self.intrusion_detected = False
            self.frames_with_intrusion = 0

        # ============================================================
        # DIBUJAR HUD (Heads-Up Display)
        # ============================================================

        # Fondo semi-transparente
        overlay = processed_frame.copy()
        cv2.rectangle(overlay, (0, 0), (500, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.6, processed_frame, 0.4, 0, processed_frame)

        # Título
        cv2.putText(processed_frame, "DETECTOR DE INTRUSOS", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

        # Estado
        status_text = "INTRUSION DETECTADA!" if self.intrusion_detected else "Sistema Activo"
        status_color = (0, 0, 255) if self.intrusion_detected else (0, 255, 0)
        cv2.putText(processed_frame, status_text, (10, 65),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, status_color, 2)

        # Nivel de movimiento
        cv2.putText(processed_frame, f"Movimiento: {movement_percentage:.1f}%", (10, 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(processed_frame, timestamp, (10, 130),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150, 150, 150), 1)

        # Indicador de alerta en la esquina
        if self.intrusion_detected:
            cv2.circle(processed_frame, (w - 30, 30), 20, (0, 0, 255), -1)
            cv2.putText(processed_frame, "!", (w - 40, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3)

        return processed_frame

    def _save_to_csv(self, intrusion, confidence):
        """Guarda evento en CSV"""
        with open(self.csv_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                intrusion,
                round(confidence, 2),
                "Sector A3"
            ])