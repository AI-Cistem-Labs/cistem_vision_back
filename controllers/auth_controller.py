import datetime
from flask import request
from app import socketio
from modules.auth.specialists.auth_specialist import AuthSpecialist

auth_service = AuthSpecialist()


@socketio.on('login')
def handle_login(json_data):
    # Log para ver en la terminal de PyCharm
    print(f"🔑 Intento de login recibido: {json_data}")

    email = json_data.get('email')
    password = json_data.get('password')

    token = auth_service.generate_token(email, password)

    if token:
        print(f"✅ Login exitoso para {email}")
        socketio.emit('login_response', {
            "success": True,
            "token": token,
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
    else:
        print(f"❌ Login fallido para {email}")
        socketio.emit('login_response', {
            "success": False,
            "error": "Credenciales inválidas",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)


@socketio.on('profile')
def handle_profile(data):
    print("👤 Petición de perfil recibida")
    token = data.get('token')
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