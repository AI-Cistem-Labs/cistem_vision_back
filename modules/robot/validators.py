# modules/robot/validators.py
"""
Validadores para los contratos JSON de la plataforma robótica
"""
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class RobotDataValidator:
    """Valida y normaliza datos recibidos del robot según los contratos definidos"""

    @staticmethod
    def validate_camera_info(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Valida datos de información de cámara del robot

        Contrato esperado:
        {
            "camera_info": {
                "cam_id": int,
                "type": str,  // "Robot" o "Camera"
                "location_id": int,
                "device_id": int,
                "label": str,
                "status": bool,
                "streamURL": str
            }
        }
        """
        try:
            if 'camera_info' not in data:
                logger.error("❌ Falta campo 'camera_info'")
                return None

            cam_info = data['camera_info']
            required_fields = ['cam_id', 'type', 'location_id', 'device_id',
                               'label', 'status', 'streamURL']

            for field in required_fields:
                if field not in cam_info:
                    logger.error(f"❌ Falta campo requerido: '{field}' en camera_info")
                    return None

            # Validar tipos
            if not isinstance(cam_info['cam_id'], int):
                logger.error("❌ cam_id debe ser integer")
                return None
            if cam_info['type'] not in ['Robot', 'Camera']:
                logger.error(f"❌ type debe ser 'Robot' o 'Camera', recibido: {cam_info['type']}")
                return None

            logger.info(f"✅ camera_info válido para cam_id: {cam_info['cam_id']}")
            return data

        except Exception as e:
            logger.error(f"❌ Error validando camera_info: {e}")
            return None

    @staticmethod
    def validate_alert(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Valida datos de alerta del robot

        Contrato esperado:
        {
            "alert_id": int,
            "type": str,  // "alert"
            "location_id": int,
            "device_id": int,
            "cam_id": int,
            "datetime": str,  // ISO 8601
            "label": str,  // INFO, WARNING, CRITICAL
            "msg": str,
            "evidence": {
                "type": str,  // image | video | audio
                "url": str,
                "thumbnail_url": str|null
            }
        }
        """
        try:
            required_fields = ['alert_id', 'type', 'location_id', 'device_id',
                               'cam_id', 'datetime', 'label', 'msg', 'evidence']

            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Falta campo requerido: '{field}' en alert")
                    return None

            # Validar tipo de alerta
            if data['type'] != 'alert':
                logger.error(f"❌ type debe ser 'alert', recibido: {data['type']}")
                return None

            # Validar nivel
            if data['label'] not in ['INFO', 'WARNING', 'CRITICAL']:
                logger.error(f"❌ label debe ser INFO/WARNING/CRITICAL, recibido: {data['label']}")
                return None

            # Validar evidence
            evidence = data['evidence']
            if 'type' not in evidence or evidence['type'] not in ['image', 'video', 'audio']:
                logger.error("❌ evidence.type inválido")
                return None
            if 'url' not in evidence:
                logger.error("❌ Falta evidence.url")
                return None

            logger.info(f"✅ alert válido, ID: {data['alert_id']}, nivel: {data['label']}")
            return data

        except Exception as e:
            logger.error(f"❌ Error validando alert: {e}")
            return None

    @staticmethod
    def validate_robot_info(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Valida información del robot (batería y motores)

        Contrato esperado:
        {
            "location_id": int,
            "device_id": int,
            "timestamp": str,  // ISO 8601
            "battery": {
                "soc": float,  // 0-100
                "status": str  // normal | low | critical | charging
            },
            "motors": {
                "max_temp": float,
                "avg_temp": float,
                "motors_warning": int,
                "total_motors": int
            }
        }
        """
        try:
            required_fields = ['location_id', 'device_id', 'timestamp', 'battery', 'motors']

            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Falta campo requerido: '{field}' en robot_info")
                    return None

            # Validar battery
            battery = data['battery']
            if 'soc' not in battery or 'status' not in battery:
                logger.error("❌ battery incompleto")
                return None
            if not 0 <= battery['soc'] <= 100:
                logger.error(f"❌ battery.soc fuera de rango: {battery['soc']}")
                return None
            if battery['status'] not in ['normal', 'low', 'critical', 'charging']:
                logger.error(f"❌ battery.status inválido: {battery['status']}")
                return None

            # Validar motors
            motors = data['motors']
            required_motor_fields = ['max_temp', 'avg_temp', 'motors_warning', 'total_motors']
            for field in required_motor_fields:
                if field not in motors:
                    logger.error(f"❌ Falta campo en motors: {field}")
                    return None

            logger.info(f"✅ robot_info válido, batería: {battery['soc']}%, status: {battery['status']}")
            return data

        except Exception as e:
            logger.error(f"❌ Error validando robot_info: {e}")
            return None

    @staticmethod
    def validate_patrol_command(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Valida comando de patrullaje (recibido del robot como confirmación)

        Contrato esperado:
        {
            "location_id": int,
            "device_id": int,
            "label": str,
            "command": str  // go_home | start_patrol | pause_patrol | resume_patrol | stop_patrol
        }
        """
        try:
            required_fields = ['location_id', 'device_id', 'label', 'command']

            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Falta campo requerido: '{field}' en patrol_command")
                    return None

            valid_commands = ['go_home', 'start_patrol', 'pause_patrol',
                              'resume_patrol', 'stop_patrol']
            if data['command'] not in valid_commands:
                logger.error(f"❌ command inválido: {data['command']}")
                return None

            logger.info(f"✅ patrol_command válido: {data['command']}")
            return data

        except Exception as e:
            logger.error(f"❌ Error validando patrol_command: {e}")
            return None

    @staticmethod
    def validate_robot_state(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Valida estado del robot (retroalimentación)

        Contrato esperado:
        {
            "location_id": int,
            "device_id": int,
            "label": str,
            "state": str  // in_home | to_home | is_patrolling | paused | stopped
        }
        """
        try:
            required_fields = ['location_id', 'device_id', 'label', 'state']

            for field in required_fields:
                if field not in data:
                    logger.error(f"❌ Falta campo requerido: '{field}' en robot_state")
                    return None

            valid_states = ['in_home', 'to_home', 'is_patrolling', 'paused', 'stopped']
            if data['state'] not in valid_states:
                logger.error(f"❌ state inválido: {data['state']}")
                return None

            logger.info(f"✅ robot_state válido: {data['state']}")
            return data

        except Exception as e:
            logger.error(f"❌ Error validando robot_state: {e}")
            return None