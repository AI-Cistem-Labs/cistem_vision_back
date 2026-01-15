import os
from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
from extensions import socketio

print("=" * 60)
print("🚀 INICIANDO APLICACIÓN SOCKETIO")
print("=" * 60)

load_dotenv()
print("✅ Variables de entorno cargadas")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET", "cistem_secret_2026")
print(f"✅ Flask app creada con SECRET_KEY configurado")

CORS(app)
print("✅ CORS habilitado")

# Vincular socketio a la app
socketio.init_app(app)
print("✅ SocketIO vinculado a la app")
print(f"   - CORS: permitido desde cualquier origen")
print(f"   - Async mode: threading")
print(f"   - Logger: activado")

# AHORA importar controladores (los decoradores ya funcionarán)
print("\n📦 Cargando controladores...")
import controllers.auth_controller

print("✅ Controladores cargados\n")


@socketio.on('connect')
def handle_connect():
    print("=" * 60)
    print("🔌 NUEVA CONEXIÓN ESTABLECIDA")
    print("=" * 60)


@socketio.on('disconnect')
def handle_disconnect():
    print("=" * 60)
    print("🔌 CLIENTE DESCONECTADO")
    print("=" * 60)


@app.route('/health')
def health():
    return {"status": "ok", "service": "Cistem Vision SocketIO"}, 200


if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))

    print("=" * 60)
    print(f"🌐 SERVIDOR INICIANDO EN http://0.0.0.0:{port}")
    print("=" * 60)
    print(f"📡 Esperando conexiones SocketIO...")
    print(f"🔑 Evento registrado: 'login'")
    print("=" * 60)
    print()

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )