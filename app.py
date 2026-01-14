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

# 2. Inicialización de SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# 3. Importar e inicializar módulos (Definición global)
from modules.vision.manager import VisionManager
from modules.storage.specialists.csv_specialist import CSVStorageSpecialist
from modules.analytics.manager import AnalyticsManager

# Definimos las variables pero no las iniciamos aún para evitar duplicidad
vision_module = VisionManager(source=int(os.getenv("CAMERA_INDEX", 0)))
storage = CSVStorageSpecialist()
analytics = AnalyticsManager(vision_module, storage, socketio)

# 4. Registrar Controladores
# Importante: Aquí se registran los eventos @socketio.on
import controllers.auth_controller
import controllers.station_controller
import controllers.camera_controller
import controllers.video_controller


@socketio.on('stations')
def handle_get_stations():
    print("📩 Petición de estaciones recibida")
    data = [
        {
            "location_id": 1,
            "label": "Estación Insurgentes",
            "devices": [{
                "device_id": 101,
                "label": "Jetson-Orin-01",
                "cameras": vision_module.get_active_cameras_info()
            }]
        }
    ]
    socketio.emit('stations_response', {
        "data": data,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    })


if __name__ == '__main__':
    # Iniciamos los módulos de hardware solo en el proceso principal
    print("📸 Iniciando módulos de Visión y Analítica...")
    vision_module.start()
    analytics.start()

    port = int(os.getenv("PORT", 5000))
    print(f"🚀 Servidor Cistem Vision corriendo en http://localhost:{port}")
    socketio.run(app, host='0.0.0.0', port=port)