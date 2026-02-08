#!/usr/bin/env python3
"""
Servidor SocketIO que RECIBE datos del robot Y ENVÍA comandos
Versión bidireccional completa
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit
from modules.robot.handlers import RobotDataHandler
import logging
from datetime import datetime, timezone

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

# Almacenar SID del robot conectado
robot_sid = None


# ============================================================================
# EVENTOS DE CONEXIÓN
# ============================================================================
@socketio.on('connect')
def handle_connect():
    global robot_sid
    robot_sid = request.sid
    logger.info("=" * 70)
    logger.info(f"🤖 ✅ ROBOT GO2 CONECTADO (SID: {robot_sid})")
    logger.info("=" * 70)


@socketio.on('disconnect')
def handle_disconnect():
    global robot_sid
    logger.warning(f"🤖 ⚠️ Robot Go2 desconectado (SID: {robot_sid})")
    robot_sid = None


# ============================================================================
# EVENTOS DEL ROBOT (RECEPCIÓN)
# ============================================================================
@socketio.on('camera_info')
def handle_camera_info(data):
    """Recibe información de cámara del robot"""
    logger.info("📹 Recibido: camera_info del robot Go2")
    handler.handle_camera_info(data)


@socketio.on('alert')
def handle_alert(data):
    """Recibe alertas del robot"""
    logger.info("🚨 Recibido: alert del robot Go2")
    handler.handle_alert(data)


@socketio.on('robot_info')
def handle_robot_info(data):
    """Recibe información del estado del robot"""
    logger.info("🔋 Recibido: robot_info del robot Go2")
    handler.handle_robot_info(data)


@socketio.on('robot_state')
def handle_robot_state(data):
    """Recibe estado/retroalimentación del robot"""
    logger.info("🤖 Recibido: robot_state del robot Go2")
    logger.info(f"   Estado actual: {data.get('state')}")
    handler.handle_robot_state(data)


# ============================================================================
# COMANDOS AL ROBOT (ENVÍO)
# ============================================================================
def send_command_to_robot(command: str, device_id: int = 1, location_id: int = 1):
    """
    Envía comando de patrullaje al robot

    Args:
        command: Comando a enviar (go_home, start_patrol, pause_patrol, resume_patrol, stop_patrol)
        device_id: ID del dispositivo
        location_id: ID de la ubicación

    Returns:
        dict con success y message
    """
    global robot_sid

    # Validar que el robot esté conectado
    if robot_sid is None:
        logger.error("❌ No se puede enviar comando: robot no conectado")
        return {
            'success': False,
            'error': 'Robot no conectado'
        }

    # Validar comando
    valid_commands = ['go_home', 'start_patrol', 'pause_patrol', 'resume_patrol', 'stop_patrol']
    if command not in valid_commands:
        logger.error(f"❌ Comando inválido: {command}")
        return {
            'success': False,
            'error': f'Comando inválido. Válidos: {valid_commands}'
        }

    # Preparar datos del comando
    command_data = {
        "location_id": location_id,
        "device_id": device_id,
        "label": "Robot Oficina",  # TODO: obtener del config
        "command": command,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

    try:
        # Enviar comando al robot
        socketio.emit('patrol_command', command_data, room=robot_sid)
        logger.info(f"✅ Comando '{command}' enviado al robot (SID: {robot_sid})")

        return {
            'success': True,
            'message': f'Comando {command} enviado correctamente',
            'command_data': command_data
        }

    except Exception as e:
        logger.error(f"❌ Error al enviar comando: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# ENDPOINTS HTTP PARA ENVIAR COMANDOS
# ============================================================================
@app.route('/robot/command', methods=['POST'])
def send_command():
    """
    Endpoint HTTP para enviar comandos al robot

    Body JSON:
    {
        "command": "start_patrol",
        "device_id": 1,
        "location_id": 1
    }
    """
    data = request.get_json()

    if not data or 'command' not in data:
        return jsonify({
            'success': False,
            'error': 'Falta campo "command" en el body'
        }), 400

    command = data['command']
    device_id = data.get('device_id', 1)
    location_id = data.get('location_id', 1)

    result = send_command_to_robot(command, device_id, location_id)

    status_code = 200 if result['success'] else 400
    return jsonify(result), status_code


@app.route('/robot/status', methods=['GET'])
def get_robot_status():
    """Obtiene el estado actual del robot"""
    global robot_sid

    device_id = request.args.get('device_id', 1, type=int)

    status = handler.get_robot_status(device_id)
    state = handler.get_robot_state(device_id)
    cameras = handler.get_robot_cameras()

    return jsonify({
        'connected': robot_sid is not None,
        'robot_sid': robot_sid,
        'device_id': device_id,
        'status': status,
        'state': state,
        'cameras': cameras
    })


@app.route('/')
def index():
    """Página de inicio con controles"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Robot Commander</title>
        <style>
            body { 
                font-family: Arial; 
                max-width: 800px; 
                margin: 50px auto; 
                padding: 20px;
                background: #f5f5f5;
            }
            .status {
                background: white;
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .commands {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            button { 
                padding: 12px 24px; 
                margin: 5px;
                font-size: 16px;
                cursor: pointer;
                border: none;
                border-radius: 4px;
                color: white;
                transition: all 0.3s;
            }
            .btn-success { background: #28a745; }
            .btn-danger { background: #dc3545; }
            .btn-warning { background: #ffc107; color: #333; }
            .btn-info { background: #17a2b8; }
            button:hover { opacity: 0.8; transform: translateY(-2px); }
            button:active { transform: translateY(0); }
            #result { 
                margin-top: 20px; 
                padding: 15px;
                background: #f8f9fa;
                border-radius: 4px;
                border-left: 4px solid #007bff;
            }
            h1 { color: #333; }
            h2 { color: #666; margin-top: 0; }
        </style>
    </head>
    <body>
        <div class="status">
            <h1>🤖 Robot Commander</h1>
            <p><strong>Backend:</strong> Cistem Vision</p>
            <p><strong>Estado:</strong> <span id="status">Verificando...</span></p>
        </div>

        <div class="commands">
            <h2>Comandos de Patrullaje</h2>

            <button class="btn-success" onclick="sendCommand('start_patrol')">
                ▶️ Iniciar Patrullaje
            </button>

            <button class="btn-warning" onclick="sendCommand('pause_patrol')">
                ⏸️ Pausar
            </button>

            <button class="btn-info" onclick="sendCommand('resume_patrol')">
                ▶️ Reanudar
            </button>

            <button class="btn-danger" onclick="sendCommand('stop_patrol')">
                ⏹️ Detener
            </button>

            <button class="btn-info" onclick="sendCommand('go_home')">
                🏠 Volver a Base
            </button>

            <div id="result"></div>
        </div>

        <script>
            // Verificar estado al cargar
            fetch('/robot/status')
                .then(r => r.json())
                .then(data => {
                    const connected = data.connected;
                    document.getElementById('status').innerHTML = 
                        connected 
                        ? '<span style="color: green;">✅ Robot Conectado</span>' 
                        : '<span style="color: red;">❌ Robot Desconectado</span>';
                });

            function sendCommand(cmd) {
                const resultDiv = document.getElementById('result');
                resultDiv.innerHTML = '⏳ Enviando comando...';

                fetch('/robot/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        command: cmd,
                        device_id: 1,
                        location_id: 1
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        resultDiv.innerHTML = '✅ <strong>Comando enviado:</strong> ' + cmd;
                        resultDiv.style.borderLeftColor = '#28a745';
                    } else {
                        resultDiv.innerHTML = '❌ <strong>Error:</strong> ' + data.error;
                        resultDiv.style.borderLeftColor = '#dc3545';
                    }
                })
                .catch(err => {
                    resultDiv.innerHTML = '❌ <strong>Error:</strong> ' + err;
                    resultDiv.style.borderLeftColor = '#dc3545';
                });
            }
        </script>
    </body>
    </html>
    '''


# ============================================================================
# MAIN
# ============================================================================
if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🎯 ROBOT COMMANDER - Recepción y Envío de Comandos")
    print("=" * 70)
    print("Puerto: 5000")
    print("Protocolo: SocketIO + HTTP")
    print("")
    print("📥 RECIBE del robot: camera_info, alert, robot_info, robot_state")
    print("📤 ENVÍA al robot: patrol_command")
    print("")
    print("🌐 Interfaz web: http://localhost:5000")
    print("📡 API: POST http://localhost:5000/robot/command")
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