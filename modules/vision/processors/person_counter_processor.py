# modules/vision/processors/person_counter_processor.py
from .base_processor import BaseProcessor
import cv2
import csv
from datetime import datetime
import os


class PersonCounterProcessor(BaseProcessor):
    """
    Procesador que cuenta personas en el frame
    (Versión simplificada para piloto - usa detección de movimiento)
    """

    PROCESSOR_ID = 1
    PROCESSOR_LABEL = "Contador de Personas"
    PROCESSOR_DESCRIPTION = "Análisis de flujo peatonal en tiempo real"

    def __init__(self, cam_id):
        super().__init__(cam_id)

        # Configurar CSV
        os.makedirs('data', exist_ok=True)
        self.csv_file = f"data/person_count_{cam_id}_{datetime.now().strftime('%Y-%m-%d')}.csv"
        self._init_csv()

        # Variables para detección simple
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=True
        )
        self.last_count = 0
        self.frames_since_save = 0

    def _init_csv(self):
        """Inicializa archivo CSV con headers"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'person_count', 'alert_level'])

    def process_frame(self, frame):
        """
        Procesa frame y cuenta personas (versión simplificada)

        Args:
            frame: Frame BGR de OpenCV

        Returns:
            Frame con anotaciones visuales
        """
        self.increment_frame_count()
        processed_frame = frame.copy()

        # Aplicar substracción de fondo
        fg_mask = self.background_subtractor.apply(frame)

        # Limpiar ruido
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

        # Encontrar contornos (personas)
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filtrar contornos por área mínima (personas)
        person_count = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > 1000:  # Área mínima para considerar como persona
                person_count += 1

                # Dibujar rectángulo alrededor de la persona
                x, y, w, h = cv2.boundingRect(contour)
                cv2.rectangle(processed_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # Actualizar contador
        self.last_count = person_count

        # Dibujar información en el frame
        cv2.putText(processed_frame, f"Personas: {person_count}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.putText(processed_frame, f"Frame: {self.frame_count}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Guardar en CSV cada 30 frames (~1 segundo a 30fps)
        self.frames_since_save += 1
        if self.frames_since_save >= 30:
            self._save_to_csv(person_count)
            self.frames_since_save = 0

            # Generar alerta si hay aglomeración
            if person_count > 10:
                self.generate_alert(
                    f"Aglomeración detectada - {person_count} personas",
                    level="PRECAUCION",
                    context={"count": person_count}
                )

        return processed_frame

    def _save_to_csv(self, count):
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
                alert_level
            ])