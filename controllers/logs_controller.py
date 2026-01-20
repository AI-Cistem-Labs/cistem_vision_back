# controllers/logs_controller.py
from flask_socketio import emit
from extensions import socketio
from modules.analytics.specialists.system_logger import system_logger
from config.config_manager import device_config
from datetime import datetime
from controllers.auth_controller import verify_token


@socketio.on('get_logs')
def handle_get_logs(data):
    """
    Evento: get_logs
    Obtiene logs de autodiagnóstico de una cámara específica
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('get_logs_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')

        if not all([location_id, device_id, cam_id]):
            emit('get_logs_response', {
                'error': 'Los parámetros location_id, device_id y cam_id son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('get_logs_response', {
                'error': 'Cámara no encontrada con los parámetros proporcionados',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Obtener logs de la cámara
        logs = system_logger.get_logs(cam_id)

        emit('get_logs_response', {
            'data': logs,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ Logs enviados para cámara {cam_id}: {len(logs)} registros")

    except Exception as e:
        print(f"❌ Error en get_logs: {str(e)}")
        emit('get_logs_response', {
            'error': 'Error al obtener logs',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })