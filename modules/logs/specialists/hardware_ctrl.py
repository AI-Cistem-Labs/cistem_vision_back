# modules/logs/specialists/hardware_ctrl.py
import os
import time
import socket
import config
from ..base import BaseLogSpecialist

# Intento de importación segura para entornos de desarrollo (Mac/PC)
try:
    import Jetson.GPIO as GPIO

    IS_JETSON = True
except ImportError:
    IS_JETSON = False


class HardwareCtrl(BaseLogSpecialist):
    def __init__(self, device_name, vision_module):
        super().__init__(device_name)
        self.vision = vision_module
        self._setup_gpio()

    def _setup_gpio(self):
        """Configuración inicial de los pines según el .env"""
        if not IS_JETSON:
            print(
                f"[HARDWARE] Modo Simulación: Pins {config.PIN_LED_PWR}, {config.PIN_LED_NET}, {config.PIN_LED_CAM} configurados.")
            return

        try:
            GPIO.setmode(GPIO.BCM)
            # Configurar LEDs como salida
            GPIO.setup([config.PIN_LED_NET, config.PIN_LED_PWR, config.PIN_LED_CAM], GPIO.OUT, initial=GPIO.LOW)
            # Configurar Botón como entrada con Pull-Up
            GPIO.setup(config.PIN_BTN_OFF, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            # Encender LED de Power fijo al iniciar
            GPIO.output(config.PIN_LED_PWR, GPIO.HIGH)
        except Exception as e:
            print(f"[HARDWARE ERROR] Error en configuración GPIO: {e}")

    def _check_internet(self):
        """Verifica conectividad para el LED de RED"""
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except OSError:
            return False

    def update(self):
        """Ciclo de actualización de hardware"""
        if not IS_JETSON:
            return

        # 1. LED de Red: Encendido si hay internet
        if self._check_internet():
            GPIO.output(config.PIN_LED_NET, GPIO.HIGH)
        else:
            GPIO.output(config.PIN_LED_NET, GPIO.LOW)

        # 2. LED de Cámaras: Encendido si la cámara está enviando video
        if self.vision.is_camera_connected:
            GPIO.output(config.PIN_LED_CAM, GPIO.HIGH)
        else:
            GPIO.output(config.PIN_LED_CAM, GPIO.LOW)

        # 3. Lectura de Botón de Apagado (Lógica Low al presionar)
        if GPIO.input(config.PIN_BTN_OFF) == GPIO.LOW:
            print("[HARDWARE] Botón de apagado detectado. Iniciando secuencia...")
            os.system("sudo shutdown now -h")