# modules/robot/client.py
"""
Cliente SocketIO para conectarse a la plataforma robótica
y recibir datos en tiempo real
"""
import socketio
import logging
from typing import Optional, Dict, Any, Callable
import os

logger = logging.getLogger(__name__)


class RobotSocketClient:
    """Cliente SocketIO para recibir datos de la plataforma robótica"""

    def __init__(self, robot_url: Optional[str] = None):
        """
        Inicializa el cliente SocketIO para la plataforma robótica

        Args:
            robot_url: URL del servidor SocketIO del robot (ej: http://192.168.1.100:8000)
        """
        self.robot_url = robot_url or os.getenv('ROBOT_SOCKET_URL', 'http://localhost:8000')
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # Infinitos intentos
            reconnection_delay=1,
            reconnection_delay_max=10,
            logger=False,
            engineio_logger=False
        )

        # Estado de conexión
        self.connected = False
        self.handlers: Dict[str, Callable] = {}

        # Registrar eventos básicos
        self._register_base_events()

    def _register_base_events(self):
        """Registra eventos básicos de conexión"""

        @self.sio.event
        def connect():
            self.connected = True
            logger.info(f"🤖 ✅ Conectado a plataforma robótica: {self.robot_url}")

        @self.sio.event
        def disconnect():
            self.connected = False
            logger.warning(f"🤖 ⚠️ Desconectado de plataforma robótica")

        @self.sio.event
        def connect_error(data):
            logger.error(f"🤖 ❌ Error de conexión: {data}")

    def register_handler(self, event_name: str, handler: Callable):
        """
        Registra un manejador para un evento específico del robot

        Args:
            event_name: Nombre del evento (ej: 'camera_info', 'alert', etc)
            handler: Función que procesará los datos recibidos
        """
        self.handlers[event_name] = handler
        self.sio.on(event_name, handler)
        logger.info(f"📝 Handler registrado para evento: '{event_name}'")

    def connect_to_robot(self) -> bool:
        """
        Establece conexión con la plataforma robótica

        Returns:
            True si la conexión fue exitosa
        """
        try:
            logger.info(f"🤖 Intentando conectar a: {self.robot_url}")
            self.sio.connect(
                self.robot_url,
                wait_timeout=10,
                transports=['polling']  # Usar solo polling para compatibilidad
            )
            return True
        except Exception as e:
            logger.error(f"❌ Error al conectar con robot: {e}")
            return False

    def disconnect_from_robot(self):
        """Cierra la conexión con el robot"""
        if self.connected:
            self.sio.disconnect()
            logger.info("🤖 Desconectado del robot")

    def emit_to_robot(self, event: str, data: Dict[str, Any]):
        """
        Envía datos al robot (para futura implementación de comandos)

        Args:
            event: Nombre del evento
            data: Datos a enviar
        """
        if self.connected:
            self.sio.emit(event, data)
            logger.info(f"📤 Enviado a robot [{event}]: {data}")
        else:
            logger.warning("⚠️ No se puede enviar, no hay conexión con el robot")

    def is_connected(self) -> bool:
        """Retorna el estado de conexión"""
        return self.connected

    def wait(self):
        """Mantiene la conexión activa (para pruebas)"""
        self.sio.wait()