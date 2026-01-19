import datetime
import json
from flask import request
from extensions import socketio

print("=" * 60)
print("📹 CAMERA CONTROLLER CARGADO")
print("=" * 60)

# Base de datos mock de cámaras
CAMERAS_DB = {
    "1_101_1001": {
        "location_id": 1,
        "device_id": 101,
        "cam_id": 1001,
        "label": "Cámara Acceso Principal",
        "status": True,
        "active_processor": 2,
        "processors": [1, 2, 3]
    },
    "1_101_1002": {
        "location_id": 1,
        "device_id": 101,
        "cam_id": 1002,
        "label": "Cámara Pasillo Norte",
        "status": False,
        "active_processor": None,
        "processors": [1]
    },
    "2_201_2001": {
        "location_id": 2,
        "device_id": 201,
        "cam_id": 2001,
        "label": "Cámara Andén 1",
        "status": True,
        "active_processor": 2,
        "processors": [2]
    }
}

PROCESSORS_DB = {
    1: {"label": "Detección de Intrusos", "description": "Monitorea áreas restringidas"},
    2: {"label": "Conteo de Personas", "description": "Análisis de flujo peatonal"},
    3: {"label": "Detección de Objetos Abandonados", "description": "Identifica objetos dejados"}
}


def validate_token(token):
    return token and len(token) > 20


@socketio.on('update_camera_status')
def handle_update_camera_status(data):
    print("\n" + "=" * 60)
    print("🔄 EVENTO 'update_camera_status' RECIBIDO")
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
        socketio.emit('camera_status_response', {
            "success": False,
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Extraer parámetros
    location_id = data.get('location_id')
    device_id = data.get('device_id')
    cam_id = data.get('cam_id')
    active = data.get('active')

    print(f"📍 location_id: {location_id}")
    print(f"🖥️  device_id: {device_id}")
    print(f"📹 cam_id: {cam_id}")
    print(f"⚡ active: {active}")

    # Validar parámetros
    if location_id is None or device_id is None or cam_id is None or active is None:
        print("❌ Parámetros faltantes")
        socketio.emit('camera_status_response', {
            "success": False,
            "error": "Los parámetros location_id, device_id, cam_id y active son requeridos",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Buscar cámara
    key = f"{location_id}_{device_id}_{cam_id}"
    camera = CAMERAS_DB.get(key)

    if not camera:
        print("❌ Cámara no encontrada")
        socketio.emit('camera_status_response', {
            "success": False,
            "error": "Cámara no encontrada con los parámetros proporcionados",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Actualizar estado
    camera['status'] = bool(active)
    action = "encendida" if active else "apagada"

    print(f"✅ Cámara {action} correctamente")

    response = {
        "success": True,
        "message": f"Cámara {action} correctamente",
        "location_id": location_id,
        "device_id": device_id,
        "cam_id": cam_id,
        "active": bool(active),
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'camera_status_response'")
    socketio.emit('camera_status_response', response, room=request.sid)
    print("=" * 60)
    print()


@socketio.on('select_processor')
def handle_select_processor(data):
    print("\n" + "=" * 60)
    print("🤖 EVENTO 'select_processor' RECIBIDO")
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
        socketio.emit('processor_response', {
            "success": False,
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Extraer parámetros
    location_id = data.get('location_id')
    device_id = data.get('device_id')
    cam_id = data.get('cam_id')
    processor_id = data.get('processor_id')

    print(f"📍 location_id: {location_id}")
    print(f"🖥️  device_id: {device_id}")
    print(f"📹 cam_id: {cam_id}")
    print(f"🤖 processor_id: {processor_id}")

    # Validar parámetros
    if location_id is None or device_id is None or cam_id is None or processor_id is None:
        print("❌ Parámetros faltantes")
        socketio.emit('processor_response', {
            "success": False,
            "error": "Los parámetros location_id, device_id, cam_id y processor_id son requeridos",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Buscar cámara
    key = f"{location_id}_{device_id}_{cam_id}"
    camera = CAMERAS_DB.get(key)

    if not camera:
        print("❌ Cámara no encontrada")
        socketio.emit('processor_response', {
            "success": False,
            "error": "Cámara no encontrada con los parámetros proporcionados",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Validar que el procesador existe y está disponible para esta cámara
    if processor_id not in camera['processors']:
        print("❌ Procesador no disponible para esta cámara")
        socketio.emit('processor_response', {
            "success": False,
            "error": "Modelo no encontrado con los parámetros proporcionados",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Actualizar procesador activo
    camera['active_processor'] = processor_id

    print(f"✅ Procesador {processor_id} seleccionado correctamente")

    response = {
        "success": True,
        "message": "Modelo seleccionado correctamente",
        "location_id": location_id,
        "device_id": device_id,
        "cam_id": cam_id,
        "processor_id": processor_id,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'processor_response'")
    socketio.emit('processor_response', response, room=request.sid)
    print("=" * 60)
    print()


print("✅ Handlers registrados: 'update_camera_status', 'select_processor'")
print("=" * 60)