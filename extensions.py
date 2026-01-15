from flask_socketio import SocketIO

print("🔧 Creando instancia de SocketIO en extensions.py")

# Crear socketio SIN vincular a ninguna app todavía
socketio = SocketIO(
    cors_allowed_origins="*",
    async_mode='threading',
    logger=True,
    engineio_logger=True
)

print("✅ SocketIO creado (sin app vinculada aún)")