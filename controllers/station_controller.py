import datetime
import json
from flask import request
from extensions import socketio

print("=" * 60)
print("🏢 STATION CONTROLLER CARGADO")
print("=" * 60)

# Datos mock de estaciones
STATIONS_DATA = [
    {
        "location_id": 1,
        "label": "Estación Insurgentes",
        "devices": [
            {
                "device_id": 101,
                "label": "Jetson-Nano-01",
                "cameras": [
                    {
                        "cam_id": 1001,
                        "label": "Cámara Acceso Principal",
                        "status": True,
                        "processors": [
                            {
                                "processor_id": 1,
                                "label": "Detección de Intrusos",
                                "description": "Monitorea áreas restringidas y detecta personas no autorizadas",
                                "status": False
                            },
                            {
                                "processor_id": 2,
                                "label": "Conteo de Personas",
                                "description": "Análisis de flujo peatonal en tiempo real",
                                "status": True
                            },
                            {
                                "processor_id": 3,
                                "label": "Detección de Objetos Abandonados",
                                "description": "Identifica objetos dejados en área monitoreada",
                                "status": False
                            }
                        ],
                        "logs": [
                            {
                                "type": "log",
                                "date": "2026-01-09T14:25:00.000Z",
                                "msg": "Cámara iniciada correctamente",
                                "label": "INFO"
                            },
                            {
                                "type": "log",
                                "date": "2026-01-09T14:20:00.000Z",
                                "msg": "Pérdida momentánea de frames detectada",
                                "label": "WARNING"
                            }
                        ]
                    },
                    {
                        "cam_id": 1002,
                        "label": "Cámara Pasillo Norte",
                        "status": False,
                        "processors": [
                            {
                                "processor_id": 1,
                                "label": "Detección de Intrusos",
                                "description": "Monitorea áreas restringidas y detecta personas no autorizadas",
                                "status": False
                            }
                        ],
                        "logs": []
                    }
                ]
            }
        ]
    },
    {
        "location_id": 2,
        "label": "Estación Zócalo",
        "devices": [
            {
                "device_id": 201,
                "label": "Jetson-Orin-01",
                "cameras": [
                    {
                        "cam_id": 2001,
                        "label": "Cámara Andén 1",
                        "status": True,
                        "processors": [
                            {
                                "processor_id": 2,
                                "label": "Conteo de Personas",
                                "description": "Análisis de flujo peatonal en tiempo real",
                                "status": True
                            }
                        ],
                        "logs": [
                            {
                                "type": "log",
                                "date": "2026-01-09T14:28:00.000Z",
                                "msg": "Procesador de IA actualizado correctamente",
                                "label": "INFO"
                            }
                        ]
                    }
                ]
            }
        ]
    }
]


def validate_token(token):
    """Valida el token (versión simplificada)"""
    return token and len(token) > 20


@socketio.on('get_stations')
def handle_get_stations(data):
    print("\n" + "=" * 60)
    print("🏢 EVENTO 'get_stations' RECIBIDO")
    print("=" * 60)

    print(f"📦 Datos recibidos: {data}")

    if isinstance(data, str):
        try:
            data = json.loads(data)
        except:
            pass

    # Validar token
    token = data.get('token') or data.get('authorization', '')
    if token.startswith('Bearer '):
        token = token.replace('Bearer ', '')

    print(f"🎫 Token: {token[:20] if token else 'NONE'}...")

    if not validate_token(token):
        print("❌ Token inválido o faltante")
        socketio.emit('stations_response', {
            "error": "Token inválido o expirado",
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        }, room=request.sid)
        return

    print(f"✅ Enviando {len(STATIONS_DATA)} estaciones")

    response = {
        "data": STATIONS_DATA,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    }

    print(f"📤 Emitiendo 'stations_response'")
    socketio.emit('stations_response', response, room=request.sid)
    print("=" * 60)
    print()


print("✅ Handler registrado: 'get_stations'")
print("=" * 60)