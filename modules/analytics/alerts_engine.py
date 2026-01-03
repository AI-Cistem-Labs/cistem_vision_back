import pandas as pd
import time
import threading
from datetime import datetime


class AlertsEngine(threading.Thread):
    def __init__(self, comms_module, vision_module):
        super().__init__()
        self.comms = comms_module
        self.vision = vision_module
        self.running = True

    def run(self):
        print("[ALERTS] Motor de alertas activo...")
        while self.running:
            # 1. Obtener la ruta del CSV del procesador actual
            if self.vision.active_processor:
                csv_path = self.vision.active_processor.csv_path

                try:
                    # Leer las últimas líneas del CSV
                    df = pd.read_csv(csv_path)
                    if not df.empty:
                        last_row = df.iloc[-1]

                        # --- LÓGICA DE ALERTA 1: Intrusión fuera de horario ---
                        now = datetime.now()
                        if now.hour >= 20 or now.hour <= 6:  # Entre 8pm y 6am
                            if last_row['Count'] > 0:
                                self._trigger_alert("CRITICAL", "Movimiento detectado en horario no autorizado")

                        # --- LÓGICA DE ALERTA 2: Aforo excedido ---
                        if last_row['Count'] > 15:
                            self._trigger_alert("WARNING", "Capacidad máxima de aula superada")

                except Exception:
                    pass

            time.sleep(3)  # Revisar cada 3 segundos

    def _trigger_alert(self, level, message):
        """Envía la alerta al Front End vía Socket.IO"""
        payload = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "device": "Aula B",  # Esto puede venir de un config
            "level": level,
            "msg": message
        }
        self.comms.send_data("new_alert", payload)