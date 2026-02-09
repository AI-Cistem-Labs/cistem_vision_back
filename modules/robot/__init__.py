# modules/robot/__init__.py
"""
Módulo de integración con plataforma robótica
"""
from .client import RobotSocketClient
from .handlers import RobotDataHandler

__all__ = ['RobotSocketClient', 'RobotDataHandler']