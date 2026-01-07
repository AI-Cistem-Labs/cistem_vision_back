import os
from dotenv import load_dotenv

load_dotenv()

DEVICE_NAME = os.getenv("DEVICE_NAME", "Jetson-Default")
PORT = int(os.getenv("SERVER_PORT", 5000))
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", 0))
MODELS_DIR = os.getenv("MODELS_DIR", "./models")
DATA_DIR = os.getenv("DATA_DIR", "./data")

# GPIO Pins
PIN_LED_NET = int(os.getenv("PIN_LED_NET", 18))
PIN_LED_PWR = int(os.getenv("PIN_LED_PWR", 23))
PIN_LED_CAM = int(os.getenv("PIN_LED_CAM", 24))
PIN_BTN_OFF = int(os.getenv("PIN_BTN_OFF", 25))