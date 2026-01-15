import datetime
import json
from flask import request
from extensions import socketio  # IMPORTAR DESDE extensions.py

print("=" * 60)
print("🔐 AUTH CONTROLLER CARGADO")
print("=" * 60)

VALID_CREDENTIALS = {
    "admin@cistem.com": "admin123",
    "admin@cistemlabs.ai": "secure_password",
    "user@cistem.com": "user123"
}


def generate_mock_token(email):
    import hashlib
    timestamp = datetime.datetime.utcnow().isoformat()
    raw = f"{email}:{timestamp}:cistem_secret_2026"
    return hashlib.sha256(raw.encode()).hexdigest()


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
            "user": {
                "email": email,
                "name": email.split('@')[0].title()
            },
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


print("✅ Handler 'login' registrado con decorador @socketio.on")
print("=" * 60)