# modules/analytics/manager.py
import threading
import time
import datetime


class AnalyticsManager(threading.Thread):
    def __init__(self, vision_module, storage_specialist, socketio_instance):  # <-- Recibimos socketio aquí
        super().__init__()
        self.vision = vision_module
        self.storage = storage_specialist
        self.socketio = socketio_instance  # <-- Lo guardamos en el objeto
        self.running = True

    def run(self):
        while self.running:
            for cam_id, data in self.vision.cameras.items():
                if data["active"]:
                    count = data["metadata"].get("count", 0)

                    if count > 5:
                        alert_data = {
                            "type": "alert",
                            "location_id": 1,
                            "device_id": 101,
                            "cam_id": cam_id,
                            "date": datetime.datetime.utcnow().isoformat() + "Z",
                            "level": "CRITICAL",
                            "msg": f"Aglomeración detectada: {count} personas."
                        }

                        saved_alert = self.storage.save_event(cam_id, alert_data)

                        # Usamos la instancia local, no la importada
                        if self.socketio:
                            self.socketio.emit('alert_event', saved_alert)

            time.sleep(5)