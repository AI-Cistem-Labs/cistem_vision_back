import os
import datetime
from flask import Flask
from flask_socketio import SocketIO
from flask_cors import CORS
from dotenv import load_dotenv

# 1. Configuración de entorno
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("JWT_SECRET", "cistem_secret_2026")
CORS(app)

# 2. Inicialización de SocketIO con manejo flexible de async_mode
# Si 'eventlet' falla, Flask-SocketIO intentará usar 'threading' automáticamente
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 3. Importar e inicializar módulos (Inyección de dependencias)
from modules.vision.manager import VisionManager
from modules.storage.specialists.csv_specialist import CSVStorageSpecialist
from modules.analytics.manager import AnalyticsManager

# Instancias compartidas
vision_module = VisionManager(source=int(os.getenv("CAMERA_INDEX", 0)))
vision_module.start()

storage = CSVStorageSpecialist()

# Pasamos socketio para evitar importaciones circulares
analytics = AnalyticsManager(vision_module, storage, socketio)
analytics.start()

# 4. Registrar Controladores (Se encargan de los eventos de Postman)
import controllers.auth_controller
import controllers.station_controller
import controllers.camera_controller
import controllers.video_controller

# Evento dinámico solicitado para Cams Stations
@socketio.on('stations')
def handle_get_stations():
    # Esta es la base que automatizaremos en el siguiente paso
    data = [
        {
            "location_id": 1,
            "label": "Estación Insurgentes",
            "devices": [{
                "device_id": 101,
                "label": "Jetson-Orin-01",
                "cameras": vision_module.get_active_cameras_info() # Llamada al método dinámico
            }]
        }
    ]
    socketio.emit('stations_response', {
        "data": data,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    })

if __name__ == '__main__':
    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Servidor Cistem Vision en puerto {port}")
    socketio.run(app, host='0.0.0.0', port=port)