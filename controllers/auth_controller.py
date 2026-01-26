# controllers/auth_controller.py
from flask_socketio import emit
from extensions import socketio
from datetime import datetime, timedelta
import jwt
import os

# Almacenamiento temporal de tokens (memoria)
ACTIVE_TOKENS = {}

# Usuario demo para piloto
DEMO_USER = {
    "id_profile": 1,
    "email": "admin@cistemlabs.ai",
    "password": "123456",
    "name": "Juan Pérez",
    "role": "Administrador",
    "photo_url": "https://ui-avatars.com/api/?name=Juan+Perez&size=200"
}

JWT_SECRET = os.getenv('JWT_SECRET', 'cistem_secret_key_2025')
JWT_EXPIRATION_HOURS = 24


def generate_token(email):
    """Genera token JWT válido por 24 horas"""
    expiration = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        'email': email,
        'exp': expiration
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm='HS256')

    # Guardar en memoria
    ACTIVE_TOKENS[token] = {
        'email': email,
        'created_at': datetime.utcnow(),
        'expires_at': expiration
    }

    return token


def verify_token(token):
    """Verifica si el token es válido"""
    if not token:
        return None

    # Verificar en memoria
    if token not in ACTIVE_TOKENS:
        return None

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        # Token expirado, limpiar de memoria
        if token in ACTIVE_TOKENS:
            del ACTIVE_TOKENS[token]
        return None
    except jwt.InvalidTokenError:
        return None


@socketio.on('login')
def handle_login(data):
    """
    Evento: login
    Autentica usuario y genera token JWT
    """
    try:
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            emit('login_response', {
                'success': False,
                'error': 'Email y password son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar credenciales (demo)
        if email == DEMO_USER['email'] and password == DEMO_USER['password']:
            token = generate_token(email)

            emit('login_response', {
                'success': True,
                'token': token,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

            print(f"✅ Login exitoso: {email}")
        else:
            emit('login_response', {
                'success': False,
                'error': 'Credenciales inválidas',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

            print(f"❌ Login fallido: {email}")

    except Exception as e:
        print(f"❌ Error en login: {str(e)}")
        emit('login_response', {
            'success': False,
            'error': 'Error interno del servidor',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('get_profile')
def handle_get_profile(data):
    """
    Evento: get_profile
    Obtiene información del perfil del usuario autenticado
    """
    try:
        # Extraer token del header Authorization
        token = data.get('token')

        if not token:
            emit('get_profile_response', {
                'error': 'Token de autorización no proporcionado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar token
        payload = verify_token(token)

        if not payload:
            emit('get_profile_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Retornar perfil completo
        emit('get_profile_response', {
            'id_profile': DEMO_USER['id_profile'],
            'name': DEMO_USER['name'],
            'email': DEMO_USER['email'],
            'role': DEMO_USER['role'],
            'photo_url': DEMO_USER['photo_url'],
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ Perfil consultado: {payload['email']}")

    except Exception as e:
        print(f"❌ Error en get_profile: {str(e)}")
        emit('get_profile_response', {
            'error': 'Error interno del servidor',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('logout')
def handle_logout(data):
    """
    Evento: logout
    Invalida el token del usuario
    """
    try:
        token = data.get('token')

        if token and token in ACTIVE_TOKENS:
            email = ACTIVE_TOKENS[token]['email']
            del ACTIVE_TOKENS[token]
            print(f"✅ Logout exitoso: {email}")

        emit('logout_response', {
            'success': True,
            'message': 'Sesión cerrada correctamente',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

    except Exception as e:
        print(f"❌ Error en logout: {str(e)}")
        emit('logout_response', {
            'success': False,
            'error': 'Error al cerrar sesión',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })