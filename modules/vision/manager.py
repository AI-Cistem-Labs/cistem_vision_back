# modules/vision/manager.py
import cv2
import threading
import time
from .processors.yolo_counter import YoloCounterProcessor


class VisionManager(threading.Thread):
    def __init__(self, source=0, model_path="models/NixitoS.pt", csv_output="data/detecciones.csv"):
        super().__init__()
        self.source = source
        self.running = False
        self.current_frame = None
        self.lock = threading.Lock()

        # Aquí instanciamos la estrategia (el algoritmo)
        # En el futuro, esto podría cambiar dinámicamente según un comando
        self.processor = YoloCounterProcessor(model_path, csv_output)

    def run(self):
        """Código que se ejecuta al llamar a start()"""
        self.running = True
        print("[VISION] Iniciando captura de cámara...")

        cap = cv2.VideoCapture(self.source)

        while self.running:
            if not cap.isOpened():
                print("[VISION] Cámara desconectada. Reintentando en 2s...")
                time.sleep(2)
                cap = cv2.VideoCapture(self.source)
                continue

            success, frame = cap.read()
            if not success:
                continue

            # --- DELEGAR LA LÓGICA AL PROCESADOR ---
            # Aquí ocurre la magia. No importa qué algoritmo sea,
            # siempre devuelve frame procesado y datos.
            processed_frame, data = self.processor.process_frame(frame)

            # Actualizar el frame disponible para streaming (Thread-safe)
            with self.lock:
                self.current_frame = processed_frame

            # (Opcional) Aquí podríamos poner los datos en una Cola (Queue)
            # para que el Módulo de Comunicación los recoja sin leer el CSV.

        cap.release()
        print("[VISION] Hilo de visión detenido.")

    def get_latest_frame(self):
        """Método para que el Módulo de Comunicación obtenga el video"""
        with self.lock:
            if self.current_frame is None:
                return None
            # Retornar codificado para streaming web inmediato
            ret, buffer = cv2.imencode('.jpg', self.current_frame)
            return buffer.tobytes() if ret else None

    def stop(self):
        self.running = False