# controllers/station_controller.py
from flask_socketio import emit
from extensions import socketio
from config.config_manager import device_config
from modules.vision.processors import get_available_processors
from modules.analytics.specialists.system_logger import system_logger
from datetime import datetime
from controllers.auth_controller import verify_token

# Variable global para acceder al handler del robot (se setea desde robot_commander.py)
robot_data_handler = None


def set_robot_handler(handler):
    """Función para inyectar el handler del robot desde robot_commander.py"""
    global robot_data_handler
    robot_data_handler = handler


@socketio.on('get_stations')
def handle_get_stations(data):
    """
    Evento: get_stations
    Retorna la jerarquía completa: location → device → cameras → processors
    Incluye cámaras normales Y cámaras del robot
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

        # 1. Agregar cámaras normales (del Jetson)
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
                'type': cam.get('type', 'Camera'),  # ⭐ Tipo de cámara
                'label': cam['label'],
                'status': cam['status'],
                'position': cam['position'],
                'processors': processors_list,
                'logs': recent_logs
            })

        # 2. ⭐ NUEVO: Agregar cámaras del robot
        if robot_data_handler:
            try:
                robot_cameras = robot_data_handler.get_robot_cameras()

                for cam_id, cam_info in robot_cameras.items():
                    cameras_data.append({
                        'cam_id': cam_info['cam_id'],
                        'type': cam_info.get('type', 'Robot'),  # ⭐ Siempre "Robot"
                        'label': cam_info['label'],
                        'status': cam_info['status'],
                        'position': cam_info.get('position', [50, 50]),  # Posición por defecto en el centro
                        'processors': [],  # Los robots no tienen procesadores de IA locales
                        'logs': []  # TODO: implementar logs del robot si es necesario
                    })

                print(f"✅ Cámaras del robot agregadas: {len(robot_cameras)}")
            except Exception as e:
                print(f"⚠️ Error al obtener cámaras del robot: {e}")

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
        print(f"✅ Estaciones enviadas: {len(cameras_data)} cámaras (incluye robots)")

    except Exception as e:
        print(f"❌ Error en get_stations: {str(e)}")
        emit('get_stations_response', {
            'error': 'Error al obtener información de estaciones',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })