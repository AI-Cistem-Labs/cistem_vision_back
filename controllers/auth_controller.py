import datetime
import json
from flask import request
from extensions import socketio

print("=" * 60)
print("🔐 AUTH CONTROLLER CARGADO")
print("=" * 60)

# Datos de prueba
VALID_CREDENTIALS = {
    "admin@cistem.com": "admin123",
    "admin@cistemlabs.ai": "secure_password",
    "user@cistem.com": "user123"
}

USERS_DB = {
    "admin@cistemlabs.ai": {
        "name": "Juan Pérez",
        "photo_url": "https://example.com/photo.jpg",
        "email": "admin@cistemlabs.ai"
    },
    "admin@cistem.com": {
        "name": "Admin User",
        "photo_url": "https://example.com/admin.jpg",
        "email": "admin@cistem.com"
    }
}


def generate_mock_token(email):
    import hashlib
    timestamp = datetime.datetime.utcnow().isoformat()
    raw = f"{email}:{timestamp}:cistem_secret_2026"
    return hashlib.sha256(raw.encode()).hexdigest()


def validate_token(token):
    """Valida el token JWT (versión simplificada)"""
    if not token or len(token) < 20:
        return None
    # En producción, usa JWT real. Aquí simulamos extrayendo email del token
    for email in VALID_CREDENTIALS.keys():
        mock_token = generate_mock_token(email)
        if token == mock_token:
            return email
    return None


@socketio.on('login')
def handle_login(data):
    print("\n" + "=" * 60)
    print("🔑 EVENTO 'login' RECIBIDO")
    print("=" * 60)

    print(f"📦 Tipo de datos: {type(data)}")
    print(f"📦 Datos raw: {data}")

    if isinstance(data, str):
        try:
            data = json.loads(data)
            print("✅ JSON parseado correctamente")
        except json.JSONDecodeError as e:
            print(f"❌ Error parseando JSON: {e}")
            socketio.emit('login_response', {
                "success": False,
                "error": "JSON inválido"
            }, room=request.sid)
            return

    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    print(f"📧 Email: {email}")
    print(f"🔒 Password: {'*' * len(password)}")

    if not email or not password:
        print("❌ Credenciales vacías")
        response = {
            "success": False,
            "error": "Email y password son requeridos",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }
        print(f"📤 Emitiendo 'login_response': {response}")
        socketio.emit('login_response', response, room=request.sid)
        return

    if email in VALID_CREDENTIALS and VALID_CREDENTIALS[email] == password:
        token = generate_mock_token(email)
        print(f"✅ LOGIN EXITOSO para {email}")

        response = {
            "success": True,
            "token": token,
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }

        print(f"📤 Emitiendo 'login_response' exitoso")
        print(f"🎫 Token generado: {token[:20]}...")

    else:
        print(f"❌ LOGIN FALLIDO para {email}")

        response = {
            "success": False,
            "error": "Credenciales inválidas",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }

        print(f"📤 Emitiendo 'login_response' de error")

    socketio.emit('login_response', response, room=request.sid)
    print("=" * 60)
    print()


@socketio.on('get_profile')
def handle_get_profile(data):
    print("\n" + "=" * 60)
    print("👤 EVENTO 'get_profile' RECIBIDO")
    print("=" * 60)

    print(f"📦 Datos recibidos: {data}")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            pass

    # Extraer token del campo 'token' o 'authorization'
    token = data.get('token') or data.get('authorization', '')

    # Limpiar el Bearer si viene
    if token.startswith('Bearer '):
        token = token.replace('Bearer ', '')

    print(f"🎫 Token recibido: {token[:20] if token else 'NONE'}...")

    if not token:
        print("❌ Token faltante")
        socketio.emit('profile_response', {
            "error": "Token de autorización no proporcionado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    email = validate_token(token)

    if not email or email not in USERS_DB:
        print("❌ Token inválido o usuario no encontrado")
        socketio.emit('profile_response', {
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    user_data = USERS_DB[email]
    print(f"✅ Perfil encontrado para {email}")

    response = {
        "name": user_data["name"],
        "photo_url": user_data["photo_url"],
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'profile_response'")
    socketio.emit('profile_response', response, room=request.sid)
    print("=" * 60)
    print()


print("✅ Handlers registrados: 'login', 'get_profile'")
print("=" * 60)