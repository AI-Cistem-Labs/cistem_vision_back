import datetime
import json
from flask import request
from extensions import socketio

print("=" * 60)
print("📋 LOGS CONTROLLER CARGADO")
print("=" * 60)

# Base de datos mock de logs
LOGS_DB = {
    "1_101_1001": [
        {
            "log_id": 1,
            "type": "log",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:28:00.000Z",
            "msg": "Sistema funcionando normalmente",
            "label": "INFO"
        },
        {
            "log_id": 2,
            "type": "log",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:20:00.000Z",
            "msg": "Pérdida momentánea de frames detectada",
            "label": "WARNING"
        },
        {
            "log_id": 3,
            "type": "log",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:15:00.000Z",
            "msg": "Error de conexión con servidor de procesamiento",
            "label": "ERROR"
        },
        {
            "log_id": 4,
            "type": "log",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:10:00.000Z",
            "msg": "Procesador de IA cambiado a Detección de Intrusos",
            "label": "INFO"
        },
        {
            "log_id": 5,
            "type": "log",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:05:00.000Z",
            "msg": "Reinicio automático completado",
            "label": "INFO"
        }
    ]
}


def validate_token(token):
    return token and len(token) > 20


@socketio.on('get_logs')
def handle_get_logs(data):
    print("\n" + "=" * 60)
    print("📋 EVENTO 'get_logs' RECIBIDO")
    print("=" * 60)

    print(f"📦 Datos recibidos: {data}")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            pass

    # Validar token
    token = data.get('token') or data.get('authorization', '')
    if token.startswith('Bearer '):
        token = token.replace('Bearer ', '')

    if not validate_token(token):
        print("❌ Token inválido")
        socketio.emit('logs_response', {
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Extraer parámetros
    location_id = data.get('location_id')
    device_id = data.get('device_id')
    cam_id = data.get('cam_id')

    print(f"📍 location_id: {location_id}")
    print(f"🖥️  device_id: {device_id}")
    print(f"📹 cam_id: {cam_id}")

    # Validar parámetros
    if not all([location_id, device_id, cam_id]):
        print("❌ Parámetros faltantes")
        socketio.emit('logs_response', {
            "error": "Los parámetros location_id, device_id y cam_id son requeridos",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Buscar logs
    key = f"{location_id}_{device_id}_{cam_id}"
    logs = LOGS_DB.get(key, [])

    if not logs and key not in LOGS_DB:
        print("❌ Cámara no encontrada")
        socketio.emit('logs_response', {
            "error": "Cámara no encontrada con los parámetros proporcionados",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    print(f"✅ Enviando {len(logs)} logs")

    response = {
        "data": logs,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'logs_response'")
    socketio.emit('logs_response', response, room=request.sid)
    print("=" * 60)
    print()


print("✅ Handler registrado: 'get_logs'")
print("=" * 60)