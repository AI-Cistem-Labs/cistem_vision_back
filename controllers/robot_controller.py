# controllers/robot_controller.py
# Versión simplificada - El robot usa HLS via MediaMTX

from flask import request
from extensions import socketio
from datetime import datetime
import os
import base64

# Base de datos temporal en memoria para el robot
robot_data = {
    'camera_info': None,
    'last_update': None,
    'is_active': False
}

# Configuración
EVIDENCE_BASE_DIR = "/home/nix/PycharmProjects/cistem_vision_back/evidence"
BACKEND_URL = "http://10.223.237.210:5000"

os.makedirs(EVIDENCE_BASE_DIR, exist_ok=True)


def save_evidence_file(base64_data, alert_id, file_type="image"):
    """Guarda evidencia desde base64"""
    try:
        extension = "jpg" if file_type == "image" else "mp4"
        now = datetime.now()
        evidence_dir = os.path.join(EVIDENCE_BASE_DIR, now.strftime("%Y/%m/%d"))
        os.makedirs(evidence_dir, exist_ok=True)

        filename = f"alert_{alert_id}.{extension}"
        filepath = os.path.join(evidence_dir, filename)

        with open(filepath, 'wb') as f:
            f.write(base64.b64decode(base64_data))

        # Generar ruta relativa para la URL
        relative_path = f"{now.strftime('%Y/%m/%d')}/{filename}"
        url = f"{BACKEND_URL}/api/evidence/{relative_path}"
        print(f"✅ Evidencia guardada: {url}")
        return url
    except Exception as e:
        print(f"❌ Error guardando evidencia: {e}")
        return None


def register_robot_routes(app):
    """Registra rutas HTTP del robot"""

    @app.route('/api/robot/data', methods=['POST'])
    def robot_data_endpoint():
        """Recibe datos del robot"""
        try:
            data = request.get_json()
            if not data:
                return {'error': 'No data'}, 400

            # Camera info
            if 'camera_info' in data:
                robot_data['camera_info'] = data['camera_info']
                robot_data['last_update'] = datetime.now().isoformat()
                robot_data['is_active'] = True
                print(f"📹 Robot camera updated: {data['camera_info'].get('label')}")

            # ============================================================
            # LOGS
            # ============================================================
            if 'logs' in data and len(data['logs']) > 0:
                # ✅ Obtener IDs de la cámara del robot
                from config.config_manager import device_config
                location_info = device_config.get_location_info()
                device_info = device_config.get_device_info()

                for log in data.get('logs', []):
                    socketio.emit('new_log', {
                        'location_id': location_info['location_id'],  # ✅ NUEVO
                        'device_id': device_info['device_id'],  # ✅ NUEVO
                        'cam_id': robot_data['camera_info'].get('cam_id', 108),  # ✅ NUEVO
                        'datetime': log.get('datetime', datetime.now().isoformat()),
                        'label': log.get('label', 'INFO'),
                        'msg': log.get('msg', '')
                    }, namespace='/')

            # ============================================================
            # ALERTS
            # ============================================================
            if 'alerts' in data and len(data['alerts']) > 0:
                # ✅ Obtener IDs de la cámara del robot
                from config.config_manager import device_config
                location_info = device_config.get_location_info()
                device_info = device_config.get_device_info()

                for alert in data['alerts']:
                    alert_data = {
                        'alert_id': alert.get('alert_id'),
                        'location_id': location_info['location_id'],  # ✅ NUEVO
                        'device_id': device_info['device_id'],  # ✅ NUEVO
                        'cam_id': robot_data['camera_info'].get('cam_id', 108),  # ✅ NUEVO
                        'datetime': alert.get('datetime', datetime.now().isoformat()),
                        'label': alert.get('label', 'INFO'),
                        'msg': alert.get('msg', '')
                    }

                    # ✅ GUARDAR EVIDENCIA si viene en base64
                    if 'evidence_base64' in alert:
                        alert_data['evidence'] = f"data:image/jpeg;base64,{alert['evidence_base64']}"

                    socketio.emit('new_alert', alert_data, namespace='/')
                    print(f"🚨 Alert: {alert_data['msg']}")

            return {'success': True}, 200

        except Exception as e:
            print(f"❌ Error: {e}")
            return {'error': str(e)}, 500

    @app.route('/api/evidence/<path:filepath>')
    def serve_evidence(filepath):
        """Sirve archivos de evidencia"""
        from flask import send_from_directory
        try:
            # Construir ruta completa
            full_path = os.path.join(EVIDENCE_BASE_DIR, filepath)

            if not os.path.exists(full_path):
                return {'error': 'Not found'}, 404

            # Servir desde el directorio base con la ruta relativa
            directory = os.path.dirname(full_path)
            filename = os.path.basename(full_path)

            # ✅ IMPORTANTE: Agregar headers CORS
            response = send_from_directory(directory, filename)
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Cache-Control'] = 'no-cache'
            return response
        except Exception as e:
            print(f"❌ Error sirviendo evidencia: {e}")
            return {'error': str(e)}, 500

    print("🤖 Robot routes registered")


def get_robot_camera_data():
    """
    Retorna datos del robot para station_controller
    streamUrl se genera automáticamente
    """
    if not robot_data.get('camera_info'):
        return None

    info = robot_data['camera_info']
    return {
        'cam_id': info.get('cam_id', 108),  # ✅ cam_108 como las demás
        'label': info.get('label', 'Robot Móvil'),
        'status': info.get('status', False),
        'position': info.get('position', {'x': 100, 'y': 200}),
        'processors': [],
        'logs': []
    }