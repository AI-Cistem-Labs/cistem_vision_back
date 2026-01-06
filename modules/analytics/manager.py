# modules/analytics/manager.py
import threading
import time
from .specialists import AlertsEngine

class AnalyticsManager(threading.Thread):
    def __init__(self, comms, vision):
        super().__init__()
        self.running = False
        self.vision = vision
        self.alerts_engine = AlertsEngine(comms)

    def run(self):
        self.running = True
        while self.running:
            # Pasa el procesador activo al motor de alertas para analizar su CSV
            if self.vision.active_processor:
                self.alerts_engine.analyze(self.vision.active_processor)
            time.sleep(3) # Ciclo de análisis cada 3 seg

    def stop(self):
        self.running = False