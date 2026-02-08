#!/usr/bin/env python3
"""
Servidor SocketIO que recibe datos del robot Go2
Este archivo va en tu Jetson backend
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_socketio import SocketIO
from modules.robot.handlers import RobotDataHandler
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Crear app Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = 'cistem_robot_secret_2026'

# Crear SocketIO con CORS habilitado
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

# Handler para procesar datos del robot
handler = RobotDataHandler()


# ============================================================================
# EVENTOS DE CONEXIÓN
# ============================================================================
@socketio.on('connect')
def handle_connect():
    logger.info("=" * 70)
    logger.info("🤖 ✅ ROBOT GO2 CONECTADO")
    logger.info("=" * 70)


@socketio.on('disconnect')
def handle_disconnect():
    logger.warning("🤖 ⚠️ Robot Go2 desconectado")


# ============================================================================
# EVENTOS DEL ROBOT
# ============================================================================
@socketio.on('camera_info')
def handle_camera_info(data):
    """Recibe información de cámara del robot"""
    logger.info("📹 Recibido: camera_info del robot Go2")
    logger.debug(f"   Data: {data}")
    handler.handle_camera_info(data)


@socketio.on('alert')
def handle_alert(data):
    """Recibe alertas del robot"""
    logger.info("🚨 Recibido: alert del robot Go2")
    logger.debug(f"   Data: {data}")
    handler.handle_alert(data)


@socketio.on('robot_info')
def handle_robot_info(data):
    """Recibe información del estado del robot"""
    logger.info("🔋 Recibido: robot_info del robot Go2")
    logger.debug(f"   Data: {data}")
    handler.handle_robot_info(data)


# ============================================================================
# RUTA HTTP DE SALUD
# ============================================================================
@app.route('/')
def index():
    return {
        'service': 'Cistem Vision - Robot Receiver',
        'status': 'running',
        'robot_cameras': len(handler.get_robot_cameras()),
        'robot_alerts': len(handler.get_robot_alerts()),
    }


@app.route('/health')
def health():
    return {
        'status': 'healthy',
        'robot_connected': True,  # TODO: implementar check real
        'cameras': handler.get_robot_cameras(),
        'alerts_count': len(handler.get_robot_alerts()),
    }


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🎯 SERVIDOR RECEPTOR - Esperando datos del robot Go2")
    print("=" * 70)
    print("Puerto: 5000")
    print("Protocolo: SocketIO")
    print("Eventos: camera_info, alert, robot_info")
    print("=" * 70)
    print("\n⏳ Esperando conexión del robot...\n")

    # Iniciar servidor
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=False,
        allow_unsafe_werkzeug=True
    )