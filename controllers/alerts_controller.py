# controllers/alerts_controller.py
from flask_socketio import emit
from extensions import socketio
from modules.analytics.specialists.alerts_engine import alerts_engine
from config.config_manager import device_config
from datetime import datetime
from controllers.auth_controller import verify_token


@socketio.on('get_alerts')
def handle_get_alerts(data):
    """
    Evento: get_alerts
    Obtiene alertas de seguridad de una cámara específica
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('get_alerts_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')

        if not all([location_id, device_id, cam_id]):
            emit('get_alerts_response', {
                'error': 'Los parámetros location_id, device_id y cam_id son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('get_alerts_response', {
                'error': 'Cámara no encontrada con los parámetros proporcionados',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Obtener alertas de la cámara
        alerts = alerts_engine.get_alerts(cam_id)

        emit('get_alerts_response', {
            'data': alerts,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ Alertas enviadas para cámara {cam_id}: {len(alerts)} registros")

    except Exception as e:
        print(f"❌ Error en get_alerts: {str(e)}")
        emit('get_alerts_response', {
            'error': 'Error al obtener alertas',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('mark_alert_read')
def handle_mark_alert_read(data):
    """
    Evento: mark_alert_read
    Marca una alerta específica como leída
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('mark_alert_read_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        alert_id = data.get('alert_id')

        if not alert_id:
            emit('mark_alert_read_response', {
                'error': 'El parámetro alert_id es requerido',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Marcar como leída
        success = alerts_engine.mark_as_read(alert_id)

        if success:
            emit('mark_alert_read_response', {
                'message': 'Notificación marcada como leída',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            print(f"✅ Alerta {alert_id} marcada como leída")
        else:
            emit('mark_alert_read_response', {
                'error': 'Alerta no encontrada',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

    except Exception as e:
        print(f"❌ Error en mark_alert_read: {str(e)}")
        emit('mark_alert_read_response', {
            'error': 'Error al marcar alerta como leída',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('mark_all_alerts_read')
def handle_mark_all_alerts_read(data):
    """
    Evento: mark_all_alerts_read
    Marca todas las alertas como leídas
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('mark_all_alerts_read_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Marcar todas como leídas
        marked_count = alerts_engine.mark_all_as_read()

        emit('mark_all_alerts_read_response', {
            'message': 'Todas las notificaciones marcadas como leídas',
            'markedCount': marked_count,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ {marked_count} alertas marcadas como leídas")

    except Exception as e:
        print(f"❌ Error en mark_all_alerts_read: {str(e)}")
        emit('mark_all_alerts_read_response', {
            'error': 'Error al marcar alertas como leídas',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })