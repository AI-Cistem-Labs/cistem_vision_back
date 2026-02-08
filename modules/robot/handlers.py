# modules/robot/handlers.py
"""
Manejadores de eventos recibidos de la plataforma robótica
"""
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from .validators import RobotDataValidator

logger = logging.getLogger(__name__)


class RobotDataHandler:
    """
    Procesa y gestiona los datos recibidos desde la plataforma robótica.

    Este handler recibe 5 tipos de eventos del robot:
    1. camera_info - Información de cámaras del robot
    2. alert - Alertas generadas por el robot
    3. robot_info - Estado de batería y motores
    4. patrol_command - Confirmación de comandos de patrullaje
    5. robot_state - Estado actual del robot
    """

    def __init__(self):
        self.validator = RobotDataValidator()

        # Almacenamiento temporal de datos (en memoria)
        # TODO: Integrar con base de datos o sistema de persistencia
        self.robot_cameras: Dict[int, Dict] = {}
        self.robot_alerts: list = []
        self.robot_status: Dict[int, Dict] = {}
        self.robot_states: Dict[int, str] = {}

        logger.info("🤖 RobotDataHandler inicializado")

    def handle_camera_info(self, data: Dict[str, Any]):
        """
        Procesa información de cámara recibida del robot

        Args:
            data: Diccionario con camera_info del robot
        """
        logger.info("📹 Recibido: camera_info")
        logger.debug(f"   Data: {data}")

        # Validar datos
        validated = self.validator.validate_camera_info(data)
        if not validated:
            logger.error("❌ camera_info inválido, ignorando")
            return

        cam_info = validated['camera_info']
        cam_id = cam_info['cam_id']

        # Aquí el Jetson Orin debe completar campos que faltan
        # según lo que tenga configurado localmente
        completed_data = self._complete_camera_info(cam_info)

        # Almacenar
        self.robot_cameras[cam_id] = completed_data

        logger.info(f"✅ camera_info procesado y almacenado: cam_id={cam_id}, type={cam_info['type']}")

        # TODO: Emitir al frontend via SocketIO

    def handle_alert(self, data: Dict[str, Any]):
        """
        Procesa alertas recibidas del robot

        Args:
            data: Diccionario con datos de alerta
        """
        logger.info("🚨 Recibido: alert")
        logger.debug(f"   Data: {data}")

        # Validar datos
        validated = self.validator.validate_alert(data)
        if not validated:
            logger.error("❌ alert inválido, ignorando")
            return

        alert_id = validated['alert_id']
        level = validated['label']

        # Completar campos que pueda faltar
        completed_data = self._complete_alert_data(validated)

        # Almacenar
        self.robot_alerts.append(completed_data)

        logger.info(f"✅ alert procesado: ID={alert_id}, nivel={level}, msg='{validated['msg'][:50]}...'")

        # TODO: Emitir al frontend via SocketIO

    def handle_robot_info(self, data: Dict[str, Any]):
        """
        Procesa información de estado del robot (batería y motores)

        Args:
            data: Diccionario con robot_info
        """
        logger.info("🔋 Recibido: robot_info")
        logger.debug(f"   Data: {data}")

        # Validar datos
        validated = self.validator.validate_robot_info(data)
        if not validated:
            logger.error("❌ robot_info inválido, ignorando")
            return

        device_id = validated['device_id']
        battery_soc = validated['battery']['soc']
        battery_status = validated['battery']['status']

        # Completar datos
        completed_data = self._complete_robot_info(validated)

        # Almacenar
        self.robot_status[device_id] = completed_data

        logger.info(f"✅ robot_info procesado: device_id={device_id}, batería={battery_soc}% ({battery_status})")

        # TODO: Emitir al frontend via SocketIO

    def handle_patrol_command(self, data: Dict[str, Any]):
        """
        Procesa confirmación de comando de patrullaje

        Args:
            data: Diccionario con patrol_command
        """
        logger.info("🎯 Recibido: patrol_command")
        logger.debug(f"   Data: {data}")

        # Validar datos
        validated = self.validator.validate_patrol_command(data)
        if not validated:
            logger.error("❌ patrol_command inválido, ignorando")
            return

        device_id = validated['device_id']
        command = validated['command']

        logger.info(f"✅ patrol_command procesado: device_id={device_id}, comando={command}")

        # TODO: Actualizar estado interno del robot
        # TODO: Emitir confirmación al frontend

    def handle_robot_state(self, data: Dict[str, Any]):
        """
        Procesa retroalimentación de estado del robot

        Args:
            data: Diccionario con robot_state
        """
        logger.info("🤖 Recibido: robot_state")
        logger.debug(f"   Data: {data}")

        # Validar datos
        validated = self.validator.validate_robot_state(data)
        if not validated:
            logger.error("❌ robot_state inválido, ignorando")
            return

        device_id = validated['device_id']
        state = validated['state']

        # Almacenar estado
        self.robot_states[device_id] = state

        logger.info(f"✅ robot_state procesado: device_id={device_id}, estado={state}")

        # TODO: Emitir al frontend via SocketIO

    # =================================================================
    # MÉTODOS PRIVADOS PARA COMPLETAR DATOS
    # =================================================================

    def _complete_camera_info(self, cam_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Completa información de cámara con datos del Jetson Orin

        Aquí es donde tu Jetson complementa los datos que la plataforma
        robótica no puede enviar.
        """
        # TODO: Integrar con config_manager para obtener datos locales
        # Por ahora retornamos los mismos datos
        return cam_info

    def _complete_alert_data(self, alert_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Completa datos de alerta con información adicional del Jetson
        """
        # TODO: Agregar metadata adicional si es necesario
        return alert_data

    def _complete_robot_info(self, robot_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Completa información del robot con datos adicionales
        """
        # TODO: Agregar campos calculados o metadata
        return robot_info

    # =================================================================
    # MÉTODOS DE CONSULTA
    # =================================================================

    def get_robot_cameras(self) -> Dict[int, Dict]:
        """Retorna todas las cámaras del robot"""
        return self.robot_cameras

    def get_robot_alerts(self, limit: Optional[int] = None) -> list:
        """Retorna alertas del robot"""
        if limit:
            return self.robot_alerts[-limit:]
        return self.robot_alerts

    def get_robot_status(self, device_id: int) -> Optional[Dict]:
        """Retorna estado de un robot específico"""
        return self.robot_status.get(device_id)

    def get_robot_state(self, device_id: int) -> Optional[str]:
        """Retorna el estado actual de un robot"""
        return self.robot_states.get(device_id)