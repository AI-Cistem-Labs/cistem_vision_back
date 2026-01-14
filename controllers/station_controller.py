from app import socketio
import datetime

@socketio.on('stations')
def handle_get_stations():
    # Estructura jerárquica solicitada en Postman
    data = [
        {
            "location_id": 1,
            "label": "Estación Insurgentes",
            "devices": [{
                "device_id": 101,
                "label": "Jetson-Nano-01",
                "cameras": [{
                    "cam_id": 1001,
                    "label": "Cámara Acceso Principal",
                    "status": True,
                    "processors": [
                        {"processor_id": 1, "label": "Detección de Intrusos", "status": False},
                        {"processor_id": 2, "label": "Conteo de Personas", "status": True}
                    ],
                    "logs": [] # Aquí puedes jalar logs reales
                }]
            }]
        }
    ]
    socketio.emit('stations_response', {"data": data, "datetime": datetime.datetime.utcnow().isoformat() + "Z"})