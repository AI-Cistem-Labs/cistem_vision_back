import datetime
from flask import request
from app import socketio, vision_module
from modules.storage.specialists.csv_specialist import CSVStorageSpecialist
from modules.auth.specialists.auth_specialist import AuthSpecialist

storage = CSVStorageSpecialist()
auth_service = AuthSpecialist()


def validate_auth(data):
    """Verifica el token JWT antes de cada operación"""
    token = data.get('token')
    return auth_service.verify_token(token)


@socketio.on('camera/status')
def handle_camera_status(data):
    if not validate_auth(data):
        socketio.emit('error_response', {"error": "No autorizado"}, room=request.sid)
        return

    cam_id, active = data.get('cam_id'), data.get('active')
    success = vision_module.set_camera_active(cam_id, active)

    socketio.emit('camera_status_response', {
        "success": success,
        "active": active,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    })


@socketio.on('get_camera_alerts')
def handle_get_alerts(data):
    if not validate_auth(data): return
    cam_id = data.get('cam_id')
    alerts = storage.load_data(cam_id, "alert")
    socketio.emit('alerts_response', {"data": alerts, "datetime": datetime.datetime.utcnow().isoformat() + "Z"})


@socketio.on('alerts/read')
def handle_mark_read(data):
    if not validate_auth(data): return
    cam_id, alert_id = data.get('cam_id'), data.get('alert_id')
    if storage.mark_as_read(cam_id, alert_id):
        socketio.emit('alerts_read_response', {"success": True, "alert_id": alert_id})


@socketio.on('alerts/read-all')
def handle_mark_all_read(data):
    if not validate_auth(data): return
    cam_id = data.get('cam_id')
    count = storage.mark_all_as_read(cam_id)
    socketio.emit('alerts_read_all_response', {"success": True, "markedCount": count})


@socketio.on('alerts/delete')
def handle_delete_alert(data):
    """Evento para eliminar una alerta específica"""
    if not validate_auth(data): return
    cam_id, alert_id = data.get('cam_id'), data.get('alert_id')

    if storage.delete_alert(cam_id, alert_id):
        socketio.emit('alerts_delete_response', {
            "success": True,
            "message": "Alerta eliminada correctamente",
            "alert_id": alert_id,
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
    else:
        socketio.emit('error_response', {"error": "No se pudo eliminar la alerta"}, room=request.sid)