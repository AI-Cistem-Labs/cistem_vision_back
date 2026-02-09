# controllers/robot_controller.py
"""
Controlador para gestionar comunicación bidireccional con el robot
Integrado en el servidor principal app.py
✅ CORREGIDO: Manejo de auth y conexiones según patrón funcional
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

# 🔧 Estructura para rastrear conexiones
# Formato: {(location_id, device_id): {"telemetry": sid, "patrol": sid, "main": sid}}
robot_connections = {}


def _get_robot_key(location_id, device_id):
    """Genera clave única para identificar un robot"""
    return (int(location_id), int(device_id))


def _register_connection(location_id, device_id, client_type, sid):
    """Registra una conexión de robot"""
    key = _get_robot_key(location_id, device_id)
    if key not in robot_connections:
        robot_connections[key] = {}
    robot_connections[key][client_type] = sid
    logger.info(f"📝 Registrado: Robot {key} - {client_type} -> SID {sid}")


def _unregister_connection(sid: str):
    """Elimina una conexión cuando se desconecta"""
    for key, connections in list(robot_connections.items()):
        for client_type, stored_sid in list(connections.items()):
            if stored_sid == sid:
                del connections[client_type]
                logger.info(f"🗑️ Desregistrado: Robot {key} - {client_type} (SID {sid})")
                if not connections:
                    del robot_connections[key]
                return key, client_type
    return None, None


def _get_robot_sid(location_id, device_id):
    """
    Obtiene el SID del robot para enviar comandos.
    Prioridad: patrol > main > telemetry
    """
    key = _get_robot_key(location_id, device_id)
    connections = robot_connections.get(key, {})
    
    # Intentar en orden de prioridad
    for client_type in ["patrol", "main", "telemetry"]:
        if client_type in connections:
            return connections[client_type], client_type
    
    return None, None


def _auto_register_robot(device_id: int, location_id: int, client_type: str = 'main'):
    """
    Auto-registra un robot cuando envía datos (fallback si no se conectó con auth)
    """
    _register_connection(location_id, device_id, client_type, request.sid)


def _emit_robot_status(device_id: int, location_id: int):
    """
    Emite el estado combinado del robot (telemetría + estado de patrullaje)
    vía SocketIO para el consumo del frontend.
    """
    try:
        status = robot_handler.get_robot_status(device_id)
        state = robot_handler.get_robot_state(device_id)

        status_payload = {
            'device_id': device_id,
            'location_id': location_id,
            'status': status,
            'state': state,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Emitir a todos (broadcast)
        socketio.emit('robot_status', status_payload)
        logger.info(f"📡 Emitido robot_status para device_id={device_id}: {state}")
    except Exception as e:
        logger.error(f"❌ Error al emitir robot_status: {e}")


# ============================================================================
# SOCKETIO: EVENTOS DE CONEXIÓN DEL ROBOT
# ============================================================================
@socketio.on('connect')
def handle_robot_connect(auth=None):
    """
    ✅ CORREGIDO: Maneja conexión inicial con auth
    Flask-SocketIO pasa auth como parámetro opcional
    """
    sid = request.sid
    
    # ✅ CRÍTICO: Intentar obtener auth de múltiples fuentes
    # 1. Como parámetro de la función
    if auth is None:
        auth = {}
    
    # 2. Desde request.args (algunas versiones de Flask-SocketIO)
    if not auth and hasattr(request, 'args'):
        auth = dict(request.args)
    
    # 3. Logging para debug
    logger.debug(f"🔍 Auth recibido: {auth}")
    logger.debug(f"🔍 Request SID: {sid}")

    device_id = auth.get('device_id')
    location_id = auth.get('location_id')
    client_type = auth.get('client_type', 'main')

    # Si no tiene auth, es probablemente un frontend
    if device_id is None or location_id is None:
        logger.info(f"🌐 Cliente conectado sin auth (SID: {sid})")
        return

    # ✅ Convertir a int si vienen como string
    try:
        device_id = int(device_id)
        location_id = int(location_id)
    except (ValueError, TypeError):
        logger.warning(f"⚠️ device_id o location_id inválidos: {device_id}, {location_id}")
        return

    _register_connection(location_id, device_id, client_type, sid)
    
    logger.info("=" * 70)
    logger.info(f"🤖 ✅ ROBOT CONECTADO")
    logger.info(f"   Location ID: {location_id}")
    logger.info(f"   Device ID: {device_id}")
    logger.info(f"   Client Type: {client_type}")
    logger.info(f"   SID: {sid}")
    logger.info(f"   Conexiones activas: {robot_connections.get(_get_robot_key(location_id, device_id), {})}")
    logger.info("=" * 70)
    
    # ✅ NUEVO: Enviar ACK de confirmación al robot
    try:
        socketio.emit('connection_ack', {
            'success': True,
            'device_id': device_id,
            'location_id': location_id,
            'client_type': client_type,
            'sid': sid,
            'message': 'Conexión registrada correctamente'
        }, to=sid)
        logger.info(f"📤 ACK enviado al robot (SID: {sid})")
    except Exception as e:
        logger.error(f"❌ Error enviando ACK: {e}")


@socketio.on('disconnect')
def handle_robot_disconnect():
    """Maneja desconexión"""
    sid = request.sid
    key, client_type = _unregister_connection(sid)
    
    if key:
        logger.warning(f"🤖 ⚠️ Robot desconectado: {key} - {client_type} (SID: {sid})")
    else:
        logger.info(f"🔌 Cliente desconectado (SID: {sid})")


# ============================================================================
# SOCKETIO: EVENTOS DEL ROBOT (ENTRADA - Recepción de datos)
# ============================================================================
@socketio.on('camera_info')
def handle_camera_info(data):
    """Recibe información de cámaras del robot"""
    logger.info("📹 Recibido: camera_info del robot")
    
    # Auto-registrar robot si envía datos
    cam_info = data.get('camera_info', {})
    device_id = cam_info.get('device_id')
    location_id = cam_info.get('location_id')
    if device_id and location_id:
        _auto_register_robot(device_id, location_id, 'main')
    
    robot_handler.handle_camera_info(data)
    emit('camera_info', data, broadcast=True)


@socketio.on('alert')
def handle_alert(data):
    """Recibe alertas del robot"""
    logger.info("🚨 Recibido: alert del robot")
    robot_handler.handle_alert(data)
    emit('alert', data, broadcast=True)


@socketio.on('robot_info')
def handle_robot_info(data):
    """Recibe telemetría del robot (batería, motores)"""
    logger.info("🔋 Recibido: robot_info")
    
    # Auto-registrar robot si envía datos
    device_id = data.get('device_id')
    location_id = data.get('location_id')
    if device_id and location_id:
        _auto_register_robot(device_id, location_id, 'main')
    
    robot_handler.handle_robot_info(data)
    emit('robot_info', data, broadcast=True)

    # Emitir estado combinado
    if device_id and location_id:
        _emit_robot_status(device_id, location_id)


@socketio.on('robot_state')
def handle_robot_state(data):
    """Recibe estado del robot (en base, patrullando, etc)"""
    logger.info("🤖 Recibido: robot_state")
    logger.info(f"   Estado: {data.get('state')}")
    
    # Auto-registrar robot si envía datos
    device_id = data.get('device_id')
    location_id = data.get('location_id')
    if device_id and location_id:
        _auto_register_robot(device_id, location_id, 'patrol')
    
    robot_handler.handle_robot_state(data)
    emit('robot_state', data, broadcast=True)

    # Emitir estado combinado
    if device_id and location_id:
        _emit_robot_status(device_id, location_id)


@socketio.on('patrol_feedback')
def handle_patrol_feedback(data):
    """Recibe retroalimentación de patrullaje"""
    logger.info("📡 Recibido: patrol_feedback")
    logger.info(f"   Estado: {data.get('state')}")
    
    # Auto-registrar robot si envía datos
    device_id = data.get('device_id')
    location_id = data.get('location_id')
    if device_id and location_id:
        _auto_register_robot(device_id, location_id, 'patrol')
    
    robot_handler.handle_robot_state(data)
    emit('patrol_feedback', data, broadcast=True)

    # Emitir estado combinado
    if device_id and location_id:
        _emit_robot_status(device_id, location_id)


@socketio.on('send_command')
def handle_send_command(data):
    """
    ✅ CORREGIDO: Recibe comando del frontend y reenvía al robot
    """
    command = data.get('command')
    device_id = data.get('device_id', 1)
    location_id = data.get('location_id', 1)
    
    logger.info(f"🎮 Recibido SocketIO 'send_command': {command} para {location_id}-{device_id}")
    logger.info(f"🔍 Conexiones actuales: {robot_connections}")
    
    result = send_command_to_robot(command, device_id, location_id)
    
    if result.get('success'):
        emit('command_sent', result)
    else:
        emit('command_error', result)


# ============================================================================
# COMANDOS AL ROBOT (SALIDA - Envío de comandos)
# ============================================================================
def send_command_to_robot(command: str, device_id: int = 1, location_id: int = 1):
    """
    ✅ CORREGIDO: Envía comando al robot
    Basado en el patrón funcional del documento 7

    Args:
        command: Comando (go_home, start_patrol, pause_patrol, resume_patrol, stop_patrol)
        device_id: ID del dispositivo
        location_id: ID de la ubicación

    Returns:
        dict con success y message
    """
    logger.info(f"📥 Recibido comando: {command} para device_id={device_id}, location_id={location_id}")
    logger.info(f"🔍 robot_connections actual: {robot_connections}")
    
    valid_commands = ['go_home', 'start_patrol', 'pause_patrol', 'resume_patrol', 'stop_patrol']
    if command not in valid_commands:
        return {
            'success': False,
            'error': f'Comando inválido. Válidos: {valid_commands}'
        }

    # Obtener el mejor SID disponible (Prioridad: patrol > main > telemetry)
    robot_sid, client_type = _get_robot_sid(location_id, device_id)
    
    logger.info(f"🔍 _get_robot_sid retornó: SID={robot_sid}, client_type={client_type}")
    
    if robot_sid is None:
        logger.error(f"❌ Robot no conectado: location_id={location_id}, device_id={device_id}")
        logger.error(f"   robot_connections: {robot_connections}")
        return {
            'success': False,
            'error': f'Robot no conectado (location_id={location_id}, device_id={device_id})'
        }

    command_data = {
        'location_id': int(location_id),
        'device_id': int(device_id),
        'label': 'Robot Oficina',
        'command': command,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }

    try:
        # ✅ CRÍTICO: Enviar comando al robot específico usando el patrón funcional
        logger.info(f"📤 Emitiendo 'patrol_command' al SID: {robot_sid}")
        logger.info(f"📤 Datos del comando: {command_data}")
        
        # ✅ Usar to=robot_sid para enviar SOLO a ese robot específico
        socketio.emit('patrol_command', command_data, to=robot_sid)
        
        logger.info("=" * 70)
        logger.info(f"✅ COMANDO ENVIADO AL ROBOT")
        logger.info(f"   Comando: {command}")
        logger.info(f"   Robot: location_id={location_id}, device_id={device_id}")
        logger.info(f"   Vía: {client_type} (SID: {robot_sid})")
        logger.info("=" * 70)
        
        # También broadcast para que los frontends sepan que se envió un comando
        socketio.emit('command_sent', command_data)
        
        return {
            'success': True,
            'message': f'Comando enviado correctamente vía {client_type}',
            'command_data': command_data,
            'sent_to_sid': robot_sid,
            'client_type': client_type
        }
    except Exception as e:
        logger.error(f"❌ Error al enviar comando: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
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
        logger.info(f"📥 HTTP POST /robot/command: {data}")

        if not data or 'command' not in data:
            logger.warning("⚠️ Petición HTTP recibida sin campo 'command'")
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

        key = _get_robot_key(location_id, device_id)
        connections = robot_connections.get(key, {})
        
        telemetry_connected = "telemetry" in connections
        patrol_connected = "patrol" in connections
        main_connected = "main" in connections

        status = robot_handler.get_robot_status(device_id)
        state = robot_handler.get_robot_state(device_id)
        cameras = robot_handler.get_robot_cameras()

        return jsonify({
            'connected': bool(connections),
            'telemetry_connected': telemetry_connected,
            'patrol_connected': patrol_connected,
            'main_connected': main_connected,
            'active_connections': list(connections.keys()),
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

    @app.route('/debug/robot_connections', methods=['GET'])
    def debug_robot_connections():
        """Debug: ver conexiones de robots"""
        debug_info = {}
        for key, conns in robot_connections.items():
            location_id, device_id = key
            debug_info[f"robot_{location_id}_{device_id}"] = conns
        
        return jsonify({
            'total_robots': len(robot_connections),
            'connections': debug_info
        })


# Exportar handler para uso en station_controller
def get_robot_handler():
    """Retorna la instancia del handler del robot"""
    return robot_handler