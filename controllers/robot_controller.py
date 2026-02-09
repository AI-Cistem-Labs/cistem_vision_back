# controllers/robot_controller.py
"""
Controlador para gestionar comunicación bidireccional con el robot
Integrado en el servidor principal app.py
"""
from flask import request, jsonify
from flask_socketio import emit
from extensions import socketio
from modules.robot.handlers import RobotDataHandler
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Instancia global del handler
robot_handler = RobotDataHandler()

# Almacenar SID de clientes robot conectados
# key = (location_id, device_id, client_type) -> sid
robot_sids = {}


def _key(location_id: int, device_id: int, client_type: str):
    """Genera clave única para identificar cliente robot"""
    return (int(location_id), int(device_id), str(client_type))


def _find_key_by_sid(sid: str):
    """Busca la clave asociada a un SID"""
    for k, v in robot_sids.items():
        if v == sid:
            return k
    return None


# ============================================================================
# SOCKETIO: EVENTOS DE CONEXIÓN DEL ROBOT
# ============================================================================
@socketio.on('connect')
def handle_robot_connect(auth):
    """
    Maneja conexión de clientes robot
    Los clientes robot se identifican con auth: {device_id, location_id, client_type}
    Frontend/navegadores se conectan sin auth
    """
    sid = request.sid
    auth = auth or {}

    device_id = auth.get('device_id')
    location_id = auth.get('location_id')
    client_type = auth.get('client_type', 'unknown')

    # Si no tiene auth, es un cliente frontend normal
    if device_id is None or location_id is None:
        logger.info(f"🌐 Cliente frontend conectado (SID: {sid})")
        print(f"🔌 Cliente conectado")
        return

    # Registrar cliente robot
    k = _key(location_id, device_id, client_type)
    robot_sids[k] = sid

    logger.info("=" * 70)
    logger.info(f"🤖 ✅ ROBOT CLIENT CONECTADO {k} (SID: {sid})")
    logger.info("=" * 70)
    print(f"🤖 Robot conectado: {client_type} (device_id={device_id}, location_id={location_id})")


@socketio.on('disconnect')
def handle_robot_disconnect():
    """Maneja desconexión de clientes"""
    sid = request.sid
    k = _find_key_by_sid(sid)

    if k:
        robot_sids.pop(k, None)
        logger.warning(f"🤖 ⚠️ Robot client desconectado {k} (SID: {sid})")
        print(f"🔌 Robot desconectado")
    else:
        print(f"🔌 Cliente desconectado")


# ============================================================================
# SOCKETIO: EVENTOS DEL ROBOT (ENTRADA - Recepción de datos)
# ============================================================================
@socketio.on('camera_info')
def handle_camera_info(data):
    """Recibe información de cámaras del robot"""
    logger.info("📹 Recibido: camera_info del robot")
    robot_handler.handle_camera_info(data)


@socketio.on('alert')
def handle_alert(data):
    """Recibe alertas del robot"""
    logger.info("🚨 Recibido: alert del robot")
    robot_handler.handle_alert(data)

    # Broadcast al frontend
    emit('alert', data, broadcast=True)


@socketio.on('robot_info')
def handle_robot_info(data):
    """Recibe telemetría del robot (batería, motores)"""
    logger.info("🔋 Recibido: robot_info")
    robot_handler.handle_robot_info(data)

    # Broadcast al frontend
    emit('robot_info', data, broadcast=True)


@socketio.on('robot_state')
def handle_robot_state(data):
    """Recibe estado del robot (en base, patrullando, etc)"""
    logger.info("🤖 Recibido: robot_state")
    logger.info(f"   Estado: {data.get('state')}")
    robot_handler.handle_robot_state(data)

    # Broadcast al frontend
    emit('robot_state', data, broadcast=True)


@socketio.on('patrol_feedback')
def handle_patrol_feedback(data):
    """Recibe retroalimentación de patrullaje"""
    logger.info("📡 Recibido: patrol_feedback")
    logger.info(f"   Estado: {data.get('state')}")
    robot_handler.handle_robot_state(data)

    # Broadcast al frontend
    emit('patrol_feedback', data, broadcast=True)


# ============================================================================
# COMANDOS AL ROBOT (SALIDA - Envío de comandos)
# ============================================================================
def send_command_to_robot(command: str, device_id: int = 1, location_id: int = 1):
    """
    Envía comando de patrullaje al robot

    Args:
        command: Comando (go_home, start_patrol, pause_patrol, resume_patrol, stop_patrol)
        device_id: ID del dispositivo
        location_id: ID de la ubicación

    Returns:
        dict con success y message
    """
    valid_commands = ['go_home', 'start_patrol', 'pause_patrol', 'resume_patrol', 'stop_patrol']
    if command not in valid_commands:
        return {
            'success': False,
            'error': f'Comando inválido. Válidos: {valid_commands}'
        }

    # Buscar SID del cliente patrol
    patrol_sid = robot_sids.get(_key(location_id, device_id, 'patrol'))
    if patrol_sid is None:
        logger.error(f"❌ Patrol client no conectado ({location_id},{device_id})")
        return {
            'success': False,
            'error': 'Patrol client no conectado'
        }

    command_data = {
        'location_id': int(location_id),
        'device_id': int(device_id),
        'label': 'Robot Oficina',
        'command': command,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    try:
        socketio.emit('patrol_command', command_data, to=patrol_sid)
        logger.info(f"✅ Comando '{command}' enviado a patrol SID={patrol_sid}")
        return {
            'success': True,
            'message': 'Comando enviado correctamente',
            'command_data': command_data
        }
    except Exception as e:
        logger.error(f"❌ Error al enviar comando: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# ENDPOINTS HTTP (para frontend)
# ============================================================================
def register_robot_routes(app):
    """Registra rutas HTTP del robot en la app Flask"""

    @app.route('/robot/command', methods=['POST'])
    def http_send_command():
        """Endpoint para enviar comandos al robot vía HTTP"""
        data = request.get_json()

        if not data or 'command' not in data:
            return jsonify({
                'success': False,
                'error': 'Falta campo "command"'
            }), 400

        command = data['command']
        device_id = data.get('device_id', 1)
        location_id = data.get('location_id', 1)

        result = send_command_to_robot(command, device_id, location_id)
        return jsonify(result), (200 if result.get('success') else 400)

    @app.route('/robot/status', methods=['GET'])
    def get_robot_status():
        """Obtiene estado actual del robot"""
        device_id = request.args.get('device_id', 1, type=int)
        location_id = request.args.get('location_id', 1, type=int)

        telemetry_connected = _key(location_id, device_id, 'telemetry') in robot_sids
        patrol_connected = _key(location_id, device_id, 'patrol') in robot_sids

        status = robot_handler.get_robot_status(device_id)
        state = robot_handler.get_robot_state(device_id)
        cameras = robot_handler.get_robot_cameras()

        return jsonify({
            'connected': telemetry_connected or patrol_connected,
            'telemetry_connected': telemetry_connected,
            'patrol_connected': patrol_connected,
            'device_id': device_id,
            'location_id': location_id,
            'status': status,
            'state': state,
            'cameras': cameras
        })

    @app.route('/robot/alerts', methods=['GET'])
    def get_robot_alerts():
        """Obtiene alertas del robot con evidencias guardadas"""
        limit = request.args.get('limit', 10, type=int)
        device_id = request.args.get('device_id', type=int)

        alerts = robot_handler.get_robot_alerts(limit=limit)

        if device_id:
            alerts = [a for a in alerts if a.get('device_id') == device_id]

        return jsonify({
            'success': True,
            'count': len(alerts),
            'alerts': alerts
        })

    @app.route('/robot/cameras', methods=['GET'])
    def get_robot_cameras():
        """Obtiene cámaras del robot"""
        cameras = robot_handler.get_robot_cameras()

        return jsonify({
            'success': True,
            'count': len(cameras),
            'cameras': cameras
        })

    @app.route('/debug/robot_sids', methods=['GET'])
    def debug_robot_sids():
        """Debug: ver SIDs de robots conectados"""
        return jsonify({
            'robot_sids': {str(k): v for k, v in robot_sids.items()}
        })


# Exportar handler para uso en station_controller
def get_robot_handler():
    """Retorna la instancia del handler del robot"""
    return robot_handler