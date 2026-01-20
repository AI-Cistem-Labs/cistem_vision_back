# controllers/camera_controller.py
from flask_socketio import emit
from extensions import socketio
from config.config_manager import device_config
from modules.analytics.specialists.system_logger import system_logger
from modules.vision.manager import VisionManager
from modules.vision.processors import get_available_processors
from datetime import datetime
from controllers.auth_controller import verify_token

vision_manager = VisionManager()


@socketio.on('update_camera_status')
def handle_update_camera_status(data):
    """
    Evento: update_camera_status
    Enciende o apaga una cámara específica
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('update_camera_status_response', {
                'success': False,
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')
        active = data.get('active')

        if not all([location_id is not None, device_id is not None, cam_id is not None, active is not None]):
            emit('update_camera_status_response', {
                'success': False,
                'error': 'Los parámetros location_id, device_id, cam_id y active son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('update_camera_status_response', {
                'success': False,
                'error': 'Cámara no encontrada con los parámetros proporcionados',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Actualizar estado
        device_config.update_camera_status(cam_id, active)

        # Registrar en logs
        if active:
            system_logger.camera_started(cam_id)
            message = "Cámara encendida correctamente"

            # Iniciar captura de video si hay procesador activo
            if camera.get('active_processor'):
                vision_manager.start_camera(cam_id)
        else:
            system_logger.camera_stopped(cam_id)
            message = "Cámara apagada correctamente"

            # Detener captura de video
            vision_manager.stop_camera(cam_id)

        emit('update_camera_status_response', {
            'success': True,
            'message': message,
            'location_id': location_id,
            'device_id': device_id,
            'cam_id': cam_id,
            'active': active,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ Estado de cámara {cam_id} actualizado: {'ON' if active else 'OFF'}")

    except Exception as e:
        print(f"❌ Error en update_camera_status: {str(e)}")
        emit('update_camera_status_response', {
            'success': False,
            'error': 'Error al actualizar estado de cámara',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('update_camera_position')
def handle_update_camera_position(data):
    """
    Evento: update_camera_position (NUEVO)
    Actualiza la posición de una cámara en el mapa
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('update_camera_position_response', {
                'success': False,
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')
        position = data.get('position')

        if not all([location_id, device_id, cam_id, position]):
            emit('update_camera_position_response', {
                'success': False,
                'error': 'Los parámetros location_id, device_id, cam_id y position[] son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar formato de posición
        if not isinstance(position, list) or len(position) != 2:
            emit('update_camera_position_response', {
                'success': False,
                'error': 'El parámetro position debe ser un array de 2 elementos [x, y]',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('update_camera_position_response', {
                'success': False,
                'error': 'Cámara no encontrada con los parámetros proporcionados',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Actualizar posición
        success = device_config.update_camera_position(cam_id, position)

        if success:
            emit('update_camera_position_response', {
                'success': True,
                'message': 'Posición modificada correctamente',
                'location_id': location_id,
                'device_id': device_id,
                'cam_id': cam_id,
                'position': position,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

            print(f"✅ Posición de cámara {cam_id} actualizada: {position}")
        else:
            emit('update_camera_position_response', {
                'success': False,
                'message': 'Error modificando la posición',
                'location_id': location_id,
                'device_id': device_id,
                'cam_id': cam_id,
                'position': camera['position'],
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

    except Exception as e:
        print(f"❌ Error en update_camera_position: {str(e)}")
        emit('update_camera_position_response', {
            'success': False,
            'error': 'Error al actualizar posición de cámara',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('select_processor')
def handle_select_processor(data):
    """
    Evento: select_processor
    Cambia el procesador de IA activo de una cámara
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('select_processor_response', {
                'success': False,
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')
        processor_id = data.get('processor_id')

        if not all([location_id, device_id, cam_id, processor_id is not None]):
            emit('select_processor_response', {
                'success': False,
                'error': 'Los parámetros location_id, device_id, cam_id y processor_id son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('select_processor_response', {
                'success': False,
                'error': 'Cámara no encontrada con los parámetros proporcionados',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que el procesador existe
        available_processors = get_available_processors()
        if processor_id not in available_processors:
            emit('select_processor_response', {
                'success': False,
                'error': 'Modelo no encontrado con los parámetros proporcionados',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Detener procesador actual si existe
        if camera.get('active_processor'):
            vision_manager.stop_camera(cam_id)

        # Actualizar procesador activo
        device_config.update_active_processor(cam_id, processor_id)

        # Iniciar nuevo procesador si la cámara está activa
        if camera['status']:
            vision_manager.start_camera(cam_id, processor_id)

        # Registrar en logs
        processor_name = available_processors[processor_id]['label']
        system_logger.processor_changed(cam_id, processor_name)

        emit('select_processor_response', {
            'success': True,
            'message': 'Modelo seleccionado correctamente',
            'location_id': location_id,
            'device_id': device_id,
            'cam_id': cam_id,
            'processor_id': processor_id,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ Procesador {processor_id} seleccionado para cámara {cam_id}")

    except Exception as e:
        print(f"❌ Error en select_processor: {str(e)}")
        emit('select_processor_response', {
            'success': False,
            'error': 'Error al seleccionar procesador',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })