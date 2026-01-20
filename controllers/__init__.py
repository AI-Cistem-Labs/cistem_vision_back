# controllers/__init__.py
"""
Controladores SocketIO para Cistem Vision Backend

Este módulo importa todos los controladores para registrar
los eventos SocketIO automáticamente.
"""

# La simple importación registra los eventos @socketio.on()
from . import auth_controller
from . import station_controller
from . import logs_controller
from . import alerts_controller
from . import camera_controller
from . import video_controller

__all__ = [
    'auth_controller',
    'station_controller',
    'logs_controller',
    'alerts_controller',
    'camera_controller',
    'video_controller'
]