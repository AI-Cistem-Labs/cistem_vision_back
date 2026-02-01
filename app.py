# app.py
from flask import Flask, send_from_directory
from flask_cors import CORS
from extensions import socketio
from dotenv import load_dotenv
import os

# Cargar variables de entorno
load_dotenv()

# Crear aplicación Flask con carpeta static
app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET', 'cistem_secret_key_2025')

# Configurar CORS
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Inicializar SocketIO con la app
socketio.init_app(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    ping_timeout=60,
    ping_interval=25
)

# Importar controladores (esto registra los eventos)
print("📡 Registrando controladores SocketIO...")
import controllers.auth_controller
import controllers.station_controller
import controllers.logs_controller
import controllers.alerts_controller
import controllers.camera_controller
# import controllers.video_controller  <-- YA NO LO IMPORTES ASÍ SOLAMENTE

# Importar y Registrar Blueprint de Video


print("✅ Controladores registrados\n")

# Evento de conexión
@socketio.on('connect')
def handle_connect():
    print("🔌 Cliente conectado")


@socketio.on('disconnect')
def handle_disconnect():
    print("🔌 Cliente desconectado")


# ============================================================
# RUTAS HTTP
# ============================================================

@app.route('/')
def index():
    """Ruta raíz con información del servicio"""
    return {
        'service': 'Cistem Vision Backend',
        'version': '1.1',
        'status': 'running',
        'protocol': 'SocketIO'
    }


@app.route('/health')
def health():
    """Endpoint de health check"""
    from config.config_manager import device_config
    from modules.vision.processors import get_available_processors

    device_info = device_config.get_device_info()
    processors = get_available_processors()

    return {
        'status': 'healthy',
        'device': device_info,
        'processors_count': len(processors),
        'processors': list(processors.keys())
    }


# ============================================================
# NUEVA RUTA: SERVIR MAPAS
# ============================================================
@app.route('/home/nix/PycharmProjects/cistem_vision_back/static/maps/mapanix.jpeg')
def serve_map(filename):
    """
    Sirve imágenes de mapas desde static/maps/

    Ejemplo de uso:
    http://localhost:5000/static/maps/laboratorio_principal.png
    """
    try:
        return send_from_directory('static/maps', filename)
    except FileNotFoundError:
        return {'error': 'Mapa no encontrado'}, 404


# ============================================================
# INICIAR SERVIDOR
# ============================================================

if __name__ == '__main__':
    PORT = int(os.getenv('PORT', 5000))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'

    print("=" * 60)
    print("🎥 CISTEM VISION BACKEND v1.1")
    print("=" * 60)
    print(f"🚀 Servidor iniciando en puerto {PORT}")
    print(f"🐛 Modo debug: {DEBUG}")
    print(f"📡 Protocolo: SocketIO")
    print("=" * 60)
    print()

    # Cargar configuración del dispositivo
    from config.config_manager import device_config

    device_info = device_config.get_device_info()
    location_info = device_config.get_location_info()
    cameras = device_config.get_cameras()

    print(f"📱 Dispositivo: {device_info['label']} (ID: {device_info['device_id']})")
    print(f"📍 Ubicación: {location_info['label']}")
    print(f"📹 Cámaras configuradas: {len(cameras)}")

    # Mostrar procesadores disponibles
    from modules.vision.processors import get_available_processors

    processors = get_available_processors()
    print(f"🤖 Procesadores disponibles: {len(processors)}")
    for proc_id, proc_info in processors.items():
        print(f"   - [{proc_id}] {proc_info['label']}")

    print()
    print("=" * 60)
    print(f"✅ Servidor listo en http://localhost:{PORT}")
    print(f"✅ WebSocket en ws://localhost:{PORT}")
    print(f"🗺️  Mapas en http://localhost:{PORT}/static/maps/")
    print("=" * 60)
    print()

    # Iniciar servidor
    socketio.run(
        app,
        host='0.0.0.0',
        port=PORT,
        debug=DEBUG,
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )