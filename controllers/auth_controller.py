import datetime
from flask import request
from app import socketio
from modules.auth.specialists.auth_specialist import AuthSpecialist

auth_service = AuthSpecialist()


@socketio.on('login')
def handle_login(json_data):
    """Atiende la petición de login de Postman"""
    email = json_data.get('email')
    password = json_data.get('password')

    token = auth_service.generate_token(email, password)

    if token:
        # Formato exacto solicitado en Postman
        socketio.emit('login_response', {
            "success": True,
            "token": token,
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
    else:
        socketio.emit('login_response', {
            "success": False,
            "error": "Credenciales inválidas",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)


@socketio.on('profile')
def handle_profile(data):
    """Valida el token antes de entregar información sensible"""
    token = data.get('token')  # O extraído de headers si usas middleware
    user_data = auth_service.verify_token(token)

    if user_data:
        socketio.emit('profile_response', {
            "name": "Juan Pérez",
            "photo_url": "https://example.com/photo.jpg",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
    else:
        socketio.emit('profile_response', {
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)