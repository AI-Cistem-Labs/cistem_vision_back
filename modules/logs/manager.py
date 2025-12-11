# modules/logs/manager.py
import threading
import time
import psutil
import socket
import os

# Intentar importar GPIO, si falla (estamos en Mac/PC), usamos un Mock simulado
try:
    import Jetson.GPIO as GPIO

    IS_JETSON = True
except ImportError:
    IS_JETSON = False


class LogManager(threading.Thread):
    def __init__(self, comms_module, interval=10):
        super().__init__()
        self.comms = comms_module
        self.interval = interval
        self.running = False

        # Configuración de Pines GPIO (Ejemplo: Pin 18=Verde, Pin 24=Rojo)
        self.PIN_OK = 18
        self.PIN_ERROR = 24
        self._setup_gpio()

    def _setup_gpio(self):
        if IS_JETSON:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setup(self.PIN_OK, GPIO.OUT, initial=GPIO.LOW)
                GPIO.setup(self.PIN_ERROR, GPIO.OUT, initial=GPIO.LOW)
            except Exception as e:
                print(f"[LOGS GPIO ERROR] {e}")
        else:
            print("[LOGS] Modo Simulación: No se detectó Jetson.GPIO")

    def set_led_status(self, status):
        """
        status: 'ok', 'error', 'off'
        """
        if not IS_JETSON:
            return  # En Mac no hacemos nada físico

        try:
            if status == 'ok':
                GPIO.output(self.PIN_OK, GPIO.HIGH)
                GPIO.output(self.PIN_ERROR, GPIO.LOW)
            elif status == 'error':
                GPIO.output(self.PIN_OK, GPIO.LOW)
                GPIO.output(self.PIN_ERROR, GPIO.HIGH)
            else:
                GPIO.output(self.PIN_OK, GPIO.LOW)
                GPIO.output(self.PIN_ERROR, GPIO.LOW)
        except Exception:
            pass

    def check_internet(self):
        """Intenta conectar a Google DNS para verificar salida real"""
        try:
            # Timeout corto para no bloquear
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def run(self):
        self.running = True
        print("[LOGS] Iniciando monitor de sistema...")

        # Encender LED verde al iniciar
        self.set_led_status('ok')

        while self.running:
            try:
                # 1. Recopilar Métricas
                cpu_usage = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                internet_connected = self.check_internet()

                # 2. Controlar LED's según estado
                if not internet_connected or cpu_usage > 95:
                    self.set_led_status('error')
                else:
                    self.set_led_status('ok')

                # 3. Empaquetar Datos
                health_packet = {
                    "type": "system_health",
                    "data": {
                        "cpu_percent": cpu_usage,
                        "ram_percent": ram.percent,
                        "disk_percent": disk.percent,
                        "internet": internet_connected,
                        "temperature": "N/A"  # En Jetson se lee de /sys/class/thermal
                    }
                }

                # 4. Enviar a Dashboard
                self.comms.send_data("health_event", health_packet)

                # Log local ligero
                # print(f"[LOGS] CPU: {cpu_usage}% | RAM: {ram.percent}% | NET: {internet_connected}")

            except Exception as e:
                print(f"[LOGS ERROR] {e}")

            time.sleep(self.interval)

        # Apagar LEDs al salir
        self.set_led_status('off')
        if IS_JETSON:
            GPIO.cleanup()
        print("[LOGS] Detenido.")

    def stop(self):
        self.running = False