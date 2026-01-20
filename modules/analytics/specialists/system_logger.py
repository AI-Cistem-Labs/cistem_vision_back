from datetime import datetime
from extensions import socketio
from config.config_manager import device_config
from collections import deque


class SystemLogger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Buffer de logs por cámara (últimos 50)
        self.logs_buffer = {}  # {cam_id: deque(maxlen=50)}
        self._initialized = True

    def _get_camera_buffer(self, cam_id):
        if cam_id not in self.logs_buffer:
            self.logs_buffer[cam_id] = deque(maxlen=50)
        return self.logs_buffer[cam_id]

    def log(self, cam_id, message, level="INFO"):
        """
        Registra un log y lo envía al frontend

        Args:
            cam_id: ID de la cámara
            message: Mensaje del log
            level: INFO, WARNING, ERROR
        """
        device_info = device_config.get_device_info()
        location_info = device_config.get_location_info()

        log_entry = {
            "log_id": len(self._get_camera_buffer(cam_id)) + 1,
            "location_id": location_info["location_id"],
            "device_id": device_info["device_id"],
            "cam_id": cam_id,
            "datetime": datetime.utcnow().isoformat() + "Z",
            "msg": message,
            "label": level
        }

        # Guardar en buffer
        self._get_camera_buffer(cam_id).append(log_entry)

        # Emitir al frontend via SocketIO
        socketio.emit('new_log', log_entry)

        # Log en consola
        icon = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "📝")
        print(f"{icon} [{level}] Cam {cam_id}: {message}")

        return log_entry

    def get_logs(self, cam_id, limit=None):
        """Obtiene logs de una cámara"""
        logs = list(self._get_camera_buffer(cam_id))
        if limit:
            return logs[-limit:]
        return logs

    # === Códigos de autodiagnóstico predefinidos ===

    def camera_started(self, cam_id):
        return self.log(cam_id, "Cámara iniciada correctamente", "INFO")

    def camera_stopped(self, cam_id):
        return self.log(cam_id, "Cámara detenida", "INFO")

    def rtsp_connection_failed(self, cam_id):
        return self.log(cam_id, "Error de conexión RTSP", "ERROR")

    def rtsp_connection_restored(self, cam_id):
        return self.log(cam_id, "Conexión RTSP restablecida", "INFO")

    def frame_drop_detected(self, cam_id):
        return self.log(cam_id, "Pérdida momentánea de frames detectada", "WARNING")

    def processor_changed(self, cam_id, processor_name):
        return self.log(cam_id, f"Procesador cambiado a '{processor_name}'", "INFO")

    def processor_error(self, cam_id, error_msg):
        return self.log(cam_id, f"Error en procesador: {error_msg}", "ERROR")

    def low_fps_warning(self, cam_id, fps):
        return self.log(cam_id, f"FPS bajo detectado: {fps} FPS", "WARNING")

    def high_cpu_usage(self, cam_id, usage):
        return self.log(cam_id, f"Uso alto de CPU: {usage}%", "WARNING")

    def system_healthy(self, cam_id):
        return self.log(cam_id, "Sistema funcionando normalmente", "INFO")


# Singleton global
system_logger = SystemLogger()