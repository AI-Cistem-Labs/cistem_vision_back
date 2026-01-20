import json
import os
from datetime import datetime


class DeviceConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.config_path = "config/device.json"
        self.config = self._load_config()
        self._initialized = True

    def _load_config(self):
        if not os.path.exists(self.config_path):
            return self._create_default_config()

        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _create_default_config(self):
        """Crea configuración por defecto si no existe"""
        default = {
            "device_id": 101,
            "device_label": "Dispositivo-01",
            "device_type": "jetson_orin",
            "location": {
                "location_id": 1,
                "label": "Ubicación Principal",
                "description": "",
                "mapImageUrl": "",
                "isActive": True
            },
            "cameras": []
        }
        os.makedirs('config', exist_ok=True)
        self._save_config(default)
        return default

    def _save_config(self, config=None):
        """Guarda configuración en disco"""
        if config is None:
            config = self.config

        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

    # === Métodos públicos ===

    def get_device_info(self):
        return {
            "device_id": self.config["device_id"],
            "label": self.config["device_label"],
            "type": self.config["device_type"]
        }

    def get_location_info(self):
        return self.config["location"]

    def get_cameras(self):
        return self.config["cameras"]

    def get_camera(self, cam_id):
        for cam in self.config["cameras"]:
            if cam["cam_id"] == cam_id:
                return cam
        return None

    def update_camera_status(self, cam_id, status):
        for cam in self.config["cameras"]:
            if cam["cam_id"] == cam_id:
                cam["status"] = status
                self._save_config()
                return True
        return False

    def update_camera_position(self, cam_id, position):
        for cam in self.config["cameras"]:
            if cam["cam_id"] == cam_id:
                cam["position"] = position
                self._save_config()
                return True
        return False

    def update_active_processor(self, cam_id, processor_id):
        for cam in self.config["cameras"]:
            if cam["cam_id"] == cam_id:
                cam["active_processor"] = processor_id
                self._save_config()
                return True
        return False

    def get_rtsp_url(self, cam_id):
        cam = self.get_camera(cam_id)
        return cam["rtsp_url"] if cam else None


# Singleton global
device_config = DeviceConfig()