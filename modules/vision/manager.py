# modules/vision/manager.py
import cv2
import threading
import time
from .processors.registry import get_processor_class


class VisionManager(threading.Thread):
    def __init__(self, source=0):
        super().__init__()
        self.source = source
        self.running = False
        self.current_frame = None
        self.is_camera_connected = False
        self.lock = threading.Lock()
        self.active_processor = None

        # Iniciar con un procesador por defecto
        self.change_processor("flow_persons_v1")

    def change_processor(self, processor_id):
        processor_class = get_processor_class(processor_id)
        if processor_class:
            with self.lock:
                # El nuevo procesador crea su propio CSV internamente
                self.active_processor = processor_class()
            print(f"[VISION] 🔄 Cambiando a especialista: {processor_id}")
            return True
        return False

    def run(self):
        self.running = True
        cap = cv2.VideoCapture(self.source)

        while self.running:
            if not cap.isOpened():
                self.is_camera_connected = False
                time.sleep(2)
                cap = cv2.VideoCapture(self.source)
                continue

            success, frame = cap.read()
            if not success:
                self.is_camera_connected = False
                continue

            self.is_camera_connected = True

            if self.active_processor:
                # El especialista hace su trabajo y devuelve el frame anotado
                annotated_frame, csv_data = self.active_processor.process_frame(frame)
                self.active_processor.write_to_csv(csv_data)

                with self.lock:
                    self.current_frame = annotated_frame
            else:
                with self.lock:
                    self.current_frame = frame

        cap.release()

    def get_latest_frame(self):
        with self.lock:
            if self.current_frame is None: return None
            ret, buffer = cv2.imencode('.jpg', self.current_frame)
            return buffer.tobytes() if ret else None

    def stop(self):
        self.running = False