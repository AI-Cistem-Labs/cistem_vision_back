import cv2
import threading
import time
import datetime
from .processors.registry import get_processor_class


class VisionManager(threading.Thread):
    def __init__(self, source=0):
        super().__init__()
        self.source = source
        self.running = False

        # Diccionario maestro de cámaras
        self.cameras = {
            1001: {
                "active": False,
                "processor": None,
                "last_frame": None,
                "metadata": {"count": 0},
                "lock": threading.Lock()
            }
        }

    def is_camera_active(self, cam_id):
        """Verifica si la cámara está encendida"""
        return self.cameras.get(cam_id, {}).get("active", False)

    def set_camera_active(self, cam_id, status):
        """Activa/Desactiva el procesamiento"""
        if cam_id in self.cameras:
            self.cameras[cam_id]["active"] = status
            return True
        return False

    def change_processor(self, cam_id, proc_id):
        """Cambia el modelo de IA (ID debe ser int)"""
        proc_class = get_processor_class(proc_id)
        if proc_class and cam_id in self.cameras:
            with self.cameras[cam_id]["lock"]:
                self.cameras[cam_id]["processor"] = proc_class()
            return True
        return False

    def get_latest_frame(self, cam_id):
        """Codifica el frame para el stream MJPEG"""
        camera = self.cameras.get(cam_id)
        if camera and camera["active"]:
            with camera["lock"]:
                frame = camera["last_frame"]
                if frame is not None:
                    ret, buffer = cv2.imencode('.jpg', frame)
                    return buffer.tobytes() if ret else None
        return None

    def get_active_cameras_info(self):
        """Genera la data dinámica para el evento stations"""
        info = []
        for cam_id, data in self.cameras.items():
            info.append({
                "cam_id": int(cam_id),
                "label": f"Cámara {cam_id}",
                "status": data["active"],
                "processors": [
                    {
                        "processor_id": 1,
                        "label": "Conteo de Personas",
                        "description": "Analiza flujo peatonal",
                        "status": (data["processor"] is not None)
                    }
                ]
            })
        return info

    def run(self):
        self.running = True
        cap = cv2.VideoCapture(self.source)

        while self.running:
            # Por ahora gestionamos la cámara local bajo el ID 1001
            cam_id = 1001
            data = self.cameras[cam_id]

            if data["active"]:
                success, frame = cap.read()
                if not success:
                    time.sleep(0.1)
                    continue

                if data["processor"]:
                    # El procesador debe retornar (frame, dict_resultados)
                    annotated_frame, results = data["processor"].process_frame(frame)
                    with data["lock"]:
                        data["last_frame"] = annotated_frame
                        data["metadata"]["count"] = results.get("count", 0)
                else:
                    with data["lock"]:
                        data["last_frame"] = frame
            else:
                time.sleep(0.5)  # Ahorro de CPU si está inactiva

        cap.release()

    def stop(self):
        self.running = False