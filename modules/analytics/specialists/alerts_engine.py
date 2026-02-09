# modules/analytics/specialists/alerts_engine.py
from datetime import datetime
from extensions import socketio
from config.config_manager import device_config
from collections import deque


class AlertsEngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Buffer de alertas por cámara (últimas 100)
        self.alerts_buffer = {}  # {cam_id: deque(maxlen=100)}
        self._alert_counter = 0
        self._initialized = True

    def _get_alerts_buffer(self, cam_id):
        if cam_id not in self.alerts_buffer:
            self.alerts_buffer[cam_id] = deque(maxlen=100)
        return self.alerts_buffer[cam_id]

    def _emit_to_frontend(self, event, data):
        """
        Emite evento al frontend solo si socketio está conectado
        """
        try:
            # Verificar que socketio tiene servidor activo
            if socketio.server is not None:
                socketio.emit(event, data)
        except Exception as e:
            # En modo test o sin servidor, solo ignorar
            pass

    def create_alert(self, cam_id, message, level="PRECAUCION", context=None):
        """
        Crea y envía una alerta al frontend

        Args:
            cam_id: ID de la cámara
            message: Mensaje de la alerta
            level: CRITICAL o PRECAUCION
            context: Datos adicionales del contexto
        """
        device_info = device_config.get_device_info()
        location_info = device_config.get_location_info()

        self._alert_counter += 1

        alert = {
            "alert_id": self._alert_counter,
            "location_id": location_info["location_id"],
            "device_id": device_info["device_id"],
            "cam_id": cam_id,
            "datetime": datetime.utcnow().isoformat() + "Z",
            "label": level,
            "read": False,
            "msg": message,
            "context": context or {},
            "evidence": None
        }

        if context and ("video" in context or "thumbnail" in context):
            evidence = {}
            if "video" in context:
                evidence["type"] = "video"
                evidence["url"] = context["video"]
            
            if "thumbnail" in context:
                evidence["thumbnail_url"] = context["thumbnail"]
                # Si solo hay thumbnail y no video (ej. snapshot), ajustamos el tipo
                if "type" not in evidence:
                     evidence["type"] = "image"
            
            alert["evidence"] = evidence

        # Guardar en buffer
        self._get_alerts_buffer(cam_id).append(alert)

        # Emitir al frontend INMEDIATAMENTE (solo si está disponible)
        self._emit_to_frontend('new_alert', alert)

        # Log en consola
        icon = "🚨" if level == "CRITICAL" else "⚠️"
        print(f"{icon} [{level}] Cam {cam_id}: {message}")

        return alert

    def get_alerts(self, cam_id):
        """Obtiene alertas de una cámara"""
        return list(self._get_alerts_buffer(cam_id))

    def mark_as_read(self, alert_id):
        """Marca una alerta como leída"""
        for cam_id in self.alerts_buffer:
            for alert in self.alerts_buffer[cam_id]:
                if alert["alert_id"] == alert_id:
                    alert["read"] = True
                    return True
        return False

    def mark_all_as_read(self):
        """Marca todas las alertas como leídas"""
        count = 0
        for cam_id in self.alerts_buffer:
            for alert in self.alerts_buffer[cam_id]:
                if not alert["read"]:
                    alert["read"] = True
                    count += 1
        return count

    # === Alertas predefinidas ===

    def intrusion_detected(self, cam_id, zone):
        return self.create_alert(
            cam_id,
            f"Intruso detectado en área restringida - {zone}",
            "CRITICAL",
            {"zone": zone, "type": "intrusion"}
        )

    def object_abandoned(self, cam_id, location):
        return self.create_alert(
            cam_id,
            f"Objeto abandonado detectado - {location}",
            "CRITICAL",
            {"location": location, "type": "abandoned_object"}
        )

    def crowd_detected(self, cam_id, count):
        return self.create_alert(
            cam_id,
            f"Aglomeración de personas detectada - {count} personas",
            "PRECAUCION",
            {"count": count, "type": "crowd"}
        )

    def unusual_activity(self, cam_id, description):
        return self.create_alert(
            cam_id,
            f"Actividad inusual detectada: {description}",
            "PRECAUCION",
            {"description": description, "type": "unusual"}
        )


# Singleton global
alerts_engine = AlertsEngine()