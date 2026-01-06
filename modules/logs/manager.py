# modules/logs/manager.py
import threading
import time
import config
from .specialists import SystemLogger, HardwareCtrl


class LogManager(threading.Thread):
    def __init__(self, comms, vision):
        super().__init__()
        self.running = False
        # Instanciamos a los especialistas
        self.logger = SystemLogger(config.DEVICE_NAME, comms)
        self.hardware = HardwareCtrl(config.DEVICE_NAME, vision)

    def run(self):
        self.running = True
        self.logger.update("Todos los módulos funcionando correctamente")

        while self.running:
            # Actualizar hardware (LEDs de red, cámara y chequeo de botón)
            self.hardware.update()

            # Aquí se pueden agregar chequeos periódicos de recursos (RAM/Disco)
            time.sleep(2)

    def stop(self):
        self.running = False