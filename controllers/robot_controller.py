# controllers/robot_controller.py
from flask import request, redirect
from extensions import socketio
from datetime import datetime
import os
import base64
import uuid

# Base de datos temporal en memoria para el robots
robot_data = {
    'camera_info': None,
    'last_update': None,
    'is_active': False
}

# ============================================================
# CONFIGURACIÓN DE EVIDENCIAS
# ============================================================

EVIDENCE_BASE_DIR = "/home/nix/PycharmProjects/cistem_vision_back/evidence"
BACKEND_URL = "http://10.223.237.210:5000"  # Cambiar si es necesario

# Crear directorio de evidencias si no existe
os.makedirs(EVIDENCE_BASE_DIR, exist_ok=True)


# ============================================================
# FUNCIONES DE EVIDENCIAS
# ============================================================

def save_evidence_file(base64_data, alert_id, file_type="image"):
    """
    Guarda un archivo de evidencia desde base64

    Args:
        base64_data: Datos en base64 (sin el prefijo data:image/jpeg;base64,)
        alert_id: ID de la alerta
        file_type: "image" o "video"

    Returns:
        str: URL del archivo guardado
    """
    try:
        # Determinar extensión
        extension = "jpg" if file_type == "image" else "mp4"

        # Crear estructura de carpetas por fecha
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        day = now.strftime("%d")

        evidence_dir = os.path.join(EVIDENCE_BASE_DIR, year, month, day)
        os.makedirs(evidence_dir, exist_ok=True)

        # Generar nombre de archivo
        filename = f"alert_{alert_id}.{extension}"
        filepath = os.path.join(evidence_dir, filename)

        # Decodificar y guardar
        file_data = base64.b64decode(base64_data)
        with open(filepath, 'wb') as f:
            f.write(file_data)

        # Generar URL pública
        url = f"{BACKEND_URL}/api/evidence/{year}/{month}/{day}/{filename}"

        print(f"✅ Evidencia guardada: {filepath}")
        print(f"📍 URL: {url}")

        return url

    except Exception as e:
        print(f"❌ Error guardando evidencia: {e}")
        import traceback
        traceback.print_exc()
        return None


def register_robot_routes(app):
    """
    Registra rutas HTTP para el robot
    """

    @app.route('/api/robot/data', methods=['POST'])
    def receive_robot_data():
        """
        Endpoint HTTP: POST /api/robot/data
        Recibe datos del robot (cámara, logs, alertas)

        NUEVO: Acepta evidencias en base64
        """
        try:
            data = request.get_json()

            if not data:
                return {'success': False, 'error': 'No se recibieron datos'}, 400

            # Actualizar información de la cámara del robot
            if 'camera_info' in data:
                robot_data['camera_info'] = data['camera_info']
                robot_data['is_active'] = data['camera_info'].get('status', False)
                robot_data['last_update'] = datetime.utcnow().isoformat() + 'Z'
                print(f"📹 Información de cámara del robot actualizada: {data['camera_info'].get('label')}")

            # Procesar y reenviar logs del robot
            if 'logs' in data and isinstance(data['logs'], list):
                for log_entry in data['logs']:
                    log_data = {
                        'location_id': 1,
                        'device_id': 99,
                        'cam_id': data.get('camera_info', {}).get('cam_id', 2001),
                        'datetime': log_entry.get('datetime', datetime.utcnow().isoformat() + 'Z'),
                        'label': log_entry.get('label', 'INFO'),
                        'msg': log_entry.get('msg', 'Log del robot')
                    }
                    socketio.emit('new_log', log_data)
                    print(f"📝 Log del robot reenviado: [{log_data['label']}] {log_data['msg']}")

            # ✅ NUEVO: Procesar alertas con evidencias en base64
            if 'alerts' in data and isinstance(data['alerts'], list):
                for alert_entry in data['alerts']:
                    alert_id = alert_entry.get('alert_id', int(datetime.utcnow().timestamp()))

                    # Procesar evidencia si viene en base64
                    evidence_data = None
                    if 'evidence_base64' in alert_entry:
                        evidence_base64 = alert_entry['evidence_base64']
                        file_type = alert_entry.get('evidence_type', 'image')

                        # Guardar evidencia y obtener URL
                        evidence_url = save_evidence_file(evidence_base64, alert_id, file_type)

                        if evidence_url:
                            evidence_data = {
                                'type': file_type,
                                'url': evidence_url
                            }

                    # Si no viene en base64, usar la URL directamente
                    elif 'evidence' in alert_entry:
                        evidence_data = alert_entry['evidence']

                    # Crear alerta
                    alert_data = {
                        'alert_id': alert_id,
                        'location_id': 1,
                        'device_id': 99,
                        'cam_id': data.get('camera_info', {}).get('cam_id', 2001),
                        'datetime': alert_entry.get('datetime', datetime.utcnow().isoformat() + 'Z'),
                        'label': alert_entry.get('label', 'INFO'),
                        'msg': alert_entry.get('msg', 'Alerta del robot'),
                        'read': False,
                        'evidence': evidence_data
                    }

                    # Emitir alerta
                    socketio.emit('new_alert', alert_data)
                    print(f"🚨 Alerta del robot reenviada: [{alert_data['label']}] {alert_data['msg']}")
                    if evidence_data:
                        print(f"   📸 Con evidencia: {evidence_data['url']}")

            return {
                'success': True,
                'message': 'Datos del robot recibidos correctamente',
                'logs_count': len(data.get('logs', [])),
                'alerts_count': len(data.get('alerts', [])),
                'datetime': datetime.utcnow().isoformat() + 'Z'
            }, 200

        except Exception as e:
            print(f"❌ Error en receive_robot_data: {str(e)}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': f'Error: {str(e)}'}, 500

    @app.route('/api/evidence/<path:filepath>')
    def serve_evidence(filepath):
        """
        ✅ NUEVO: Sirve archivos de evidencia guardados en el backend

        Ejemplo: /api/evidence/2025/02/02/alert_5001.jpg
        """
        try:
            from flask import send_from_directory
            return send_from_directory(EVIDENCE_BASE_DIR, filepath)
        except FileNotFoundError:
            return {'error': 'Evidencia no encontrada'}, 404
        except Exception as e:
            print(f"❌ Error sirviendo evidencia: {e}")
            return {'error': 'Error al obtener evidencia'}, 500

    @app.route('/api/robot/stream')
    def robot_stream():
        """
        Endpoint HTTP: GET /api/robot/stream
        Redirige al stream MJPEG del robot
        """
        try:
            if not robot_data.get('camera_info'):
                return {'error': 'Robot no conectado'}, 404

            stream_url = robot_data['camera_info'].get('stream_url')
            if not stream_url:
                return {'error': 'Stream no disponible'}, 404

            return redirect(stream_url)

        except Exception as e:
            print(f"❌ Error en robot_stream: {e}")
            return {'error': 'Error al obtener stream del robot'}, 500

    @app.route('/api/robot/test', methods=['POST'])
    def test_robot_integration():
        """
        Endpoint de prueba para simular datos del robot
        """
        try:
            # Generar una imagen de prueba en base64
            import numpy as np
            import cv2

            # Crear imagen de prueba
            test_image = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(test_image, "TEST EVIDENCE", (50, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 3)

            # Convertir a base64
            _, buffer = cv2.imencode('.jpg', test_image)
            evidence_base64 = base64.b64encode(buffer).decode('utf-8')

            test_data = {
                "camera_info": {
                    "cam_id": 2001,
                    "label": "Robot Móvil - TEST",
                    "type": "mobile",
                    "status": True,
                    "stream_url": "http://robot-test:8080/stream.mjpg"
                },
                "logs": [
                    {"label": "INFO", "msg": "TEST: Sistema iniciado"},
                    {"label": "WARNING", "msg": "TEST: Batería al 50%"}
                ],
                "alerts": [
                    {
                        "alert_id": 9999,
                        "label": "CRITICAL",
                        "msg": "TEST: Obstáculo detectado con evidencia guardada en backend",
                        "evidence_base64": evidence_base64,  # ✅ Enviando base64
                        "evidence_type": "image"
                    }
                ]
            }

            # Actualizar datos del robot
            robot_data['camera_info'] = test_data['camera_info']
            robot_data['is_active'] = True
            robot_data['last_update'] = datetime.utcnow().isoformat() + 'Z'

            # Emitir logs de prueba
            for log_entry in test_data['logs']:
                log_data = {
                    'location_id': 1,
                    'device_id': 99,
                    'cam_id': 2001,
                    'datetime': datetime.utcnow().isoformat() + 'Z',
                    'label': log_entry['label'],
                    'msg': log_entry['msg']
                }
                socketio.emit('new_log', log_data)
                print(f"📝 [TEST] Log emitido: {log_data['msg']}")

            # Emitir alertas de prueba con evidencia
            for alert_entry in test_data['alerts']:
                alert_id = alert_entry['alert_id']

                # Guardar evidencia
                evidence_url = save_evidence_file(
                    alert_entry['evidence_base64'],
                    alert_id,
                    alert_entry['evidence_type']
                )

                alert_data = {
                    'alert_id': alert_id,
                    'location_id': 1,
                    'device_id': 99,
                    'cam_id': 2001,
                    'datetime': datetime.utcnow().isoformat() + 'Z',
                    'label': alert_entry['label'],
                    'msg': alert_entry['msg'],
                    'read': False,
                    'evidence': {
                        'type': 'image',
                        'url': evidence_url
                    } if evidence_url else None
                }
                socketio.emit('new_alert', alert_data)
                print(f"🚨 [TEST] Alerta emitida: {alert_data['msg']}")
                if evidence_url:
                    print(f"   📸 Evidencia guardada en: {evidence_url}")

            return {
                'success': True,
                'message': 'Datos de prueba enviados correctamente',
                'test_data': test_data
            }, 200

        except Exception as e:
            print(f"❌ Error en test_robot_integration: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}, 500


def get_robot_camera_data():
    """
    Retorna la cámara del robot en formato compatible con get_stations
    """
    if not robot_data.get('camera_info'):
        return None

    camera_info = robot_data['camera_info']

    return {
        'cam_id': camera_info.get('cam_id', 2001),
        'label': camera_info.get('label', 'Robot Móvil'),
        'type': camera_info.get('type', 'mobile'),
        'status': camera_info.get('status', False),
        'position': camera_info.get('position', {'x': 100, 'y': 200}),
        'stream_url': camera_info.get('stream_url'),
        'processors': [],
        'logs': []
    }