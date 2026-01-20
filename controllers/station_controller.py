# controllers/station_controller.py
from flask_socketio import emit
from extensions import socketio
from config.config_manager import device_config
from modules.vision.processors import get_available_processors
from modules.analytics.specialists.system_logger import system_logger
from datetime import datetime
from controllers.auth_controller import verify_token


@socketio.on('get_stations')
def handle_get_stations(data):
    """
    Evento: get_stations
    Retorna la jerarquía completa: location → device → cameras → processors
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('get_stations_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Obtener información del dispositivo
        device_info = device_config.get_device_info()
        location_info = device_config.get_location_info()
        cameras = device_config.get_cameras()

        # Obtener procesadores disponibles
        available_processors = get_available_processors()

        # Construir estructura de cámaras con procesadores y logs
        cameras_data = []
        for cam in cameras:
            cam_id = cam['cam_id']

            # Obtener procesadores para esta cámara
            processors_list = []
            for proc_id in cam.get('available_processors', []):
                proc_info = available_processors.get(proc_id)
                if proc_info:
                    processors_list.append({
                        'processor_id': proc_id,
                        'label': proc_info['label'],
                        'description': proc_info['description'],
                        'status': cam.get('active_processor') == proc_id
                    })

            # Obtener últimos logs de esta cámara
            recent_logs = system_logger.get_logs(cam_id, limit=5)

            cameras_data.append({
                'cam_id': cam['cam_id'],
                'label': cam['label'],
                'status': cam['status'],
                'position': cam['position'],
                'processors': processors_list,
                'logs': recent_logs
            })

        # Construir respuesta jerárquica
        response = {
            'data': [
                {
                    'location_id': location_info['location_id'],
                    'label': location_info['label'],
                    'description': location_info['description'],
                    'mapImageUrl': location_info['mapImageUrl'],
                    'isActive': location_info['isActive'],
                    'devices': [
                        {
                            'device_id': device_info['device_id'],
                            'label': device_info['label'],
                            'cameras': cameras_data
                        }
                    ]
                }
            ],
            'datetime': datetime.utcnow().isoformat() + 'Z'
        }

        emit('get_stations_response', response)
        print(f"✅ Estaciones enviadas: {len(cameras_data)} cámaras")

    except Exception as e:
        print(f"❌ Error en get_stations: {str(e)}")
        emit('get_stations_response', {
            'error': 'Error al obtener información de estaciones',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })