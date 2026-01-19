import datetime
import json
from flask import request
from extensions import socketio

print("=" * 60)
print("🚨 ALERTS CONTROLLER CARGADO")
print("=" * 60)

# Base de datos mock de alertas
ALERTS_DB = {
    "1_101_1001": [
        {
            "alert_id": 1,
            "type": "alert",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:31:45.000Z",
            "level": "CRITICAL",
            "read": False,
            "msg": "Intruso detectado en área restringida - Sector A3"
        },
        {
            "alert_id": 2,
            "type": "alert",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:25:30.000Z",
            "level": "PRECAUCIÓN",
            "read": False,
            "msg": "Se ha detectado actividad inusual en el área"
        },
        {
            "alert_id": 3,
            "type": "alert",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:18:12.000Z",
            "level": "CRITICAL",
            "read": False,
            "msg": "Objeto abandonado detectado - Posible amenaza"
        },
        {
            "alert_id": 4,
            "type": "alert",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "date": "2026-01-09T14:10:05.000Z",
            "level": "PRECAUCIÓN",
            "read": False,
            "msg": "Aglomeración de personas detectada - Nivel moderado"
        }
    ]
}


def validate_token(token):
    return token and len(token) > 20


@socketio.on('get_alerts')
def handle_get_alerts(data):
    print("\n" + "=" * 60)
    print("🚨 EVENTO 'get_alerts' RECIBIDO")
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
        socketio.emit('alerts_response', {
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
        socketio.emit('alerts_response', {
            "error": "Los parámetros location_id, device_id y cam_id son requeridos",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Buscar alertas
    key = f"{location_id}_{device_id}_{cam_id}"
    alerts = ALERTS_DB.get(key, [])

    if not alerts and key not in ALERTS_DB:
        print("❌ Cámara no encontrada")
        socketio.emit('alerts_response', {
            "error": "Cámara no encontrada con los parámetros proporcionados",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    print(f"✅ Enviando {len(alerts)} alertas")

    response = {
        "data": alerts,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'alerts_response'")
    socketio.emit('alerts_response', response, room=request.sid)
    print("=" * 60)
    print()


@socketio.on('mark_alert_read')
def handle_mark_alert_read(data):
    print("\n" + "=" * 60)
    print("✅ EVENTO 'mark_alert_read' RECIBIDO")
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
        socketio.emit('alert_read_response', {
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    alert_id = data.get('alert_id')

    if not alert_id:
        print("❌ alert_id faltante")
        socketio.emit('alert_read_response', {
            "error": "El parámetro alert_id es requerido",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    print(f"🆔 alert_id: {alert_id}")

    # Buscar y marcar como leída
    found = False
    for key in ALERTS_DB:
        for alert in ALERTS_DB[key]:
            if alert['alert_id'] == alert_id:
                alert['read'] = True
                found = True
                break
        if found:
            break

    if not found:
        print("❌ Alerta no encontrada")
        socketio.emit('alert_read_response', {
            "error": "Alerta no encontrada",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    print(f"✅ Alerta {alert_id} marcada como leída")

    response = {
        "message": "Notificación marcada como leída",
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'alert_read_response'")
    socketio.emit('alert_read_response', response, room=request.sid)
    print("=" * 60)
    print()


@socketio.on('mark_all_alerts_read')
def handle_mark_all_alerts_read(data):
    print("\n" + "=" * 60)
    print("✅ EVENTO 'mark_all_alerts_read' RECIBIDO")
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
        socketio.emit('all_alerts_read_response', {
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    # Marcar todas como leídas
    count = 0
    for key in ALERTS_DB:
        for alert in ALERTS_DB[key]:
            if not alert['read']:
                alert['read'] = True
                count += 1

    print(f"✅ {count} alertas marcadas como leídas")

    response = {
        "message": "Todas las notificaciones marcadas como leídas",
        "markedCount": count,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'all_alerts_read_response'")
    socketio.emit('all_alerts_read_response', response, room=request.sid)
    print("=" * 60)
    print()


print("✅ Handlers registrados: 'get_alerts', 'mark_alert_read', 'mark_all_alerts_read'")
print("=" * 60)