import datetime
import json
import base64
from flask import request
from extensions import socketio

print("=" * 60)
print("🎥 VIDEO CONTROLLER CARGADO")
print("=" * 60)

# Base de datos mock de cámaras
CAMERAS_DB = {
    "1_101_1001": {
        "location_id": 1,
        "device_id": 101,
        "cam_id": 1001,
        "label": "Cámara Acceso Principal",
        "status": True,
        "resolution": "1920x1080",
        "fps": 30
    },
    "1_101_1002": {
        "location_id": 1,
        "device_id": 101,
        "cam_id": 1002,
        "label": "Cámara Pasillo Norte",
        "status": False,
        "resolution": "1280x720",
        "fps": 25
    },
    "2_201_2001": {
        "location_id": 2,
        "device_id": 201,
        "cam_id": 2001,
        "label": "Cámara Andén 1",
        "status": True,
        "resolution": "1920x1080",
        "fps": 30
    }
}


def validate_token(token):
    return token and len(token) > 20


@socketio.on('get_camera_feed')
def handle_get_camera_feed(data):
    print("\n" + "=" * 60)
    print("🎥 EVENTO 'get_camera_feed' RECIBIDO")
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
        socketio.emit('camera_feed_response', {
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
    if location_id is None or device_id is None or cam_id is None:
        print("❌ Parámetros faltantes")
        socketio.emit('camera_feed_response', {
            "error": "Los parámetros location_id, device_id y cam_id son requeridos",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Buscar cámara
    key = f"{location_id}_{device_id}_{cam_id}"
    camera = CAMERAS_DB.get(key)

    if not camera:
        print("❌ Cámara no encontrada")
        socketio.emit('camera_feed_response', {
            "error": "Cámara no encontrada con los parámetros proporcionados",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Verificar que la cámara esté encendida
    if not camera['status']:
        print("❌ Cámara apagada")
        socketio.emit('camera_feed_response', {
            "error": "La cámara está apagada. Active la cámara antes de solicitar el stream de video",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    print(f"✅ Iniciando stream de {camera['label']}")

    # En producción, aquí irían los frames reales del video
    # Por ahora, enviamos metadata del stream
    response = {
        "streaming": True,
        "format": "MJPEG",
        "location_id": location_id,
        "device_id": device_id,
        "cam_id": cam_id,
        "time_active": "00:05:23",  # Tiempo que lleva activa
        "resolution": camera['resolution'],
        "fps": camera['fps'],
        "datetime": datetime.datetime.utcnow().isoformat() + "Z",
        "note": "Stream de video iniciado. Los frames se enviarán mediante eventos 'video_frame'"
    }

    print(f"📤 Emitiendo 'camera_feed_response'")
    socketio.emit('camera_feed_response', response, room=request.sid)

    # Simular envío de frames (en producción, esto sería un loop continuo)
    print("📹 Stream activo. Para enviar frames reales, implemente el loop de transmisión")
    print("=" * 60)
    print()


# Evento adicional para detener el stream
@socketio.on('stop_camera_feed')
def handle_stop_camera_feed(data):
    print("\n" + "=" * 60)
    print("🛑 EVENTO 'stop_camera_feed' RECIBIDO")
    print("=" * 60)

    print(f"📦 Datos recibidos: {data}")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            pass

    location_id = data.get('location_id')
    device_id = data.get('device_id')
    cam_id = data.get('cam_id')

    print(f"🛑 Deteniendo stream: {location_id}_{device_id}_{cam_id}")

    response = {
        "success": True,
        "message": "Stream de video detenido",
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    socketio.emit('stop_feed_response', response, room=request.sid)
    print("=" * 60)
    print()


print("✅ Handlers registrados: 'get_camera_feed', 'stop_camera_feed'")
print("=" * 60)