import threading
import time
import psutil
import socket
import datetime
import os

# Intento de importar GPIO (Seguro para desarrollo en Mac/PC)
try:
    import Jetson.GPIO as GPIO

    IS_JETSON = True
except ImportError:
    IS_JETSON = False


class LogManager(threading.Thread):
    def __init__(self, comms_module, vision_module, device_name="Jetson-01"):
        super().__init__()
        self.comms = comms_module
        self.vision = vision_module
        self.device_name = device_name
        self.running = False

        # Configuración de Pines (Ajustar según tu esquema eléctrico)
        self.PIN_LED_NET = 18  # Verde: Red
        self.PIN_LED_PWR = 23  # Blanco: Encendido
        self.PIN_LED_CAM = 24  # Azul: Cámaras OK
        self.PIN_BTN_OFF = 25  # Botón: Apagado

        self._setup_gpio()
        self._send_log("Conexión Exitosa con el Ecosistema")  # Log inicial

    def _setup_gpio(self):
        if not IS_JETSON: return
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup([self.PIN_LED_NET, self.PIN_LED_PWR, self.PIN_LED_CAM], GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(self.PIN_BTN_OFF, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pull-up interno

            # Encender LED de Power inmediatamente
            GPIO.output(self.PIN_LED_PWR, GPIO.HIGH)
        except Exception as e:
            print(f"[GPIO ERROR] {e}")

    def _get_timestamp(self):
        return datetime.datetime.now().strftime("%H:%M:%S")

    def _send_log(self, message):
        """Formato Estricto: [Dispositivo], [Hora], [Mensaje]"""
        formatted_msg = f"[{self.device_name}], [{self._get_timestamp()}], [{message}]"
        self.comms.send_data("log_event", {"msg": formatted_msg})
        print(f"[LOG] {formatted_msg}")

    def check_resources(self):
        # RAM
        ram_percent = psutil.virtual_memory().percent
        if ram_percent >= 85:
            self._send_log(f"Llegó al {ram_percent}% de RAM")

        # Disco
        disk_percent = psutil.disk_usage('/').percent
        if disk_percent >= 90:
            self._send_log(f"Llegó al {disk_percent}% de almacenamiento")

    def check_network(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            if IS_JETSON: GPIO.output(self.PIN_LED_NET, GPIO.HIGH)
            return True
        except OSError:
            if IS_JETSON: GPIO.output(self.PIN_LED_NET, GPIO.LOW)
            self._send_log("Desconectado de la red")
            return False

    def check_shutdown_button(self):
        if IS_JETSON and GPIO.input(self.PIN_BTN_OFF) == GPIO.LOW:  # Presionado (si es pull-up)
            self._send_log("Botón de apagado presionado. Apagando...")
            time.sleep(2)
            os.system("shutdown now -h")

    def run(self):
        self.running = True
        self._send_log("Todos los módulos funcionando correctamente")

        while self.running:
            # 1. Chequeos de Sistema
            self.check_resources()
            is_net = self.check_network()
            self.check_shutdown_button()

            # 2. Estado de Cámara (Para log y LED)
            cameras_ok = self.vision.is_camera_connected
            if cameras_ok:
                if IS_JETSON: GPIO.output(self.PIN_LED_CAM, GPIO.HIGH)
            else:
                if IS_JETSON: GPIO.output(self.PIN_LED_CAM, GPIO.LOW)
                self._send_log("Desconexión de Cámara (i)")

            # 3. Log de tiempo activo (Opcional, puede saturar si es muy frecuente)
            # self._send_log("TIME") 

            time.sleep(5)  # Ciclo de revisión

    def stop(self):
        self.running = False
        if IS_JETSON: GPIO.cleanup()