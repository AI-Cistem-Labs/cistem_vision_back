# controllers/video_controller.py
"""
Controlador de video para Cistem Vision.
Provee endpoints para obtener URLs de streaming.
"""

import os
from datetime import datetime
from flask_socketio import emit
from extensions import socketio
from config.config_manager import device_config
from modules.vision.manager import VisionManager
from controllers.auth_controller import verify_token

vision_manager = VisionManager()

# Configuracion de MediaMTX
TAILSCALE_IP = os.getenv('TAILSCALE_IP', '100.73.141.61')
MEDIAMTX_HLS_PORT = os.getenv('MEDIAMTX_HLS_PORT', '8888')
MEDIAMTX_WEBRTC_PORT = os.getenv('MEDIAMTX_WEBRTC_PORT', '8889')
MEDIAMTX_RTSP_PORT = os.getenv('MEDIAMTX_RTSP_PORT', '8554')


@socketio.on('get_camera_stream_url')
def handle_get_camera_stream_url(data):
    """
    Retorna URLs del stream PROCESADO con IA.
    El frontend siempre consume el stream procesado (_ai).
    """
    try:
        token = data.get('token')
        if not verify_token(token):
            emit('get_camera_stream_url_response', {
                'error': 'Token invalido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')
        # Nota: processed siempre será True desde el frontend, pero lo dejamos por compatibilidad
        want_processed = data.get('processed', True)

        if not all([location_id, device_id, cam_id]):
            emit('get_camera_stream_url_response', {
                'error': 'Parametros location_id, device_id y cam_id requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('get_camera_stream_url_response', {
                'error': 'Camara no encontrada',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # ✅ SIEMPRE devolver URLs del stream procesado (_ai)
        # El VisionManager publica a cam_{cam_id}_ai
        processed_streams = {
            'hls': f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}_ai/index.m3u8',
            'webrtc': f'http://{TAILSCALE_IP}:{MEDIAMTX_WEBRTC_PORT}/cam_{cam_id}_ai',
            'rtsp': f'rtsp://{TAILSCALE_IP}:{MEDIAMTX_RTSP_PORT}/cam_{cam_id}_ai'
        }

        response = {
            'success': True,
            'cam_id': cam_id,
            'streams': processed_streams,  # ✅ Cambio principal: streams ahora apunta al procesado
            'ai_active': False,
            'processor_id': None,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        }

        # Si cámara activa con procesador, iniciar VisionManager
        if camera.get('status') and camera.get('active_processor'):
            processor_id = camera.get('active_processor')

            # ✅ Asegurar que VisionManager esté corriendo
            if not vision_manager.is_camera_active(cam_id):
                print(f"[VideoCtrl] Iniciando VisionManager para cam {cam_id}...")
                vision_manager.start_camera(cam_id, processor_id)

            # ✅ Verificar si está activo
            if vision_manager.is_camera_active(cam_id):
                response['ai_active'] = True
                response['processor_id'] = processor_id
                print(f"[VideoCtrl] URLs procesadas enviadas para cam {cam_id}")
            else:
                print(f"[VideoCtrl] ADVERTENCIA: VisionManager no pudo iniciarse para cam {cam_id}")
                response['error'] = 'VisionManager no pudo iniciarse'
        else:
            print(f"[VideoCtrl] ADVERTENCIA: Cámara {cam_id} sin procesador activo o desactivada")
            response['error'] = 'Cámara sin procesador activo'

        emit('get_camera_stream_url_response', response)

    except Exception as e:
        print(f"[VideoCtrl] Error get_camera_stream_url: {e}")
        import traceback
        traceback.print_exc()
        emit('get_camera_stream_url_response', {
            'error': 'Error al obtener URLs de streaming',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('start_ai_processing')
def handle_start_ai_processing(data):
    """Inicia procesamiento de IA para una camara."""
    try:
        token = data.get('token')
        if not verify_token(token):
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'Token invalido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        cam_id = data.get('cam_id')
        processor_id = data.get('processor_id')

        if not cam_id:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'Parametro cam_id requerido',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'Camara no encontrada',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        if not camera.get('status'):
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'La camara debe estar encendida',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        if processor_id is None:
            processor_id = camera.get('active_processor')

        if processor_id is None:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'No hay procesador especificado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        if vision_manager.is_camera_active(cam_id):
            vision_manager.stop_camera(cam_id)

        if vision_manager.start_camera(cam_id, processor_id):
            stream_url = f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}_ai/index.m3u8'
            emit('start_ai_processing_response', {
                'success': True,
                'message': 'Procesamiento IA iniciado',
                'cam_id': cam_id,
                'processor_id': processor_id,
                'stream_url': stream_url,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            print(f"[VideoCtrl] IA iniciada para cam {cam_id}")
        else:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'Error al iniciar procesamiento IA',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

    except Exception as e:
        print(f"[VideoCtrl] Error start_ai_processing: {e}")
        emit('start_ai_processing_response', {
            'success': False,
            'error': 'Error interno',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('stop_ai_processing')
def handle_stop_ai_processing(data):
    """Detiene procesamiento de IA para una camara."""
    try:
        token = data.get('token')
        if not verify_token(token):
            emit('stop_ai_processing_response', {
                'success': False,
                'error': 'Token invalido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        cam_id = data.get('cam_id')

        if not cam_id:
            emit('stop_ai_processing_response', {
                'success': False,
                'error': 'Parametro cam_id requerido',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        if vision_manager.is_camera_active(cam_id):
            vision_manager.stop_camera(cam_id)
            emit('stop_ai_processing_response', {
                'success': True,
                'message': 'Procesamiento IA detenido',
                'cam_id': cam_id,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            print(f"[VideoCtrl] IA detenida para cam {cam_id}")
        else:
            emit('stop_ai_processing_response', {
                'success': True,
                'message': 'Procesamiento ya estaba detenido',
                'cam_id': cam_id,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

    except Exception as e:
        print(f"[VideoCtrl] Error stop_ai_processing: {e}")
        emit('stop_ai_processing_response', {
            'success': False,
            'error': 'Error al detener procesamiento',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('get_ai_status')
def handle_get_ai_status(data):
    """Obtiene estado del procesamiento IA."""
    try:
        token = data.get('token')
        if not verify_token(token):
            emit('get_ai_status_response', {
                'error': 'Token invalido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        cam_id = data.get('cam_id')

        if not cam_id:
            emit('get_ai_status_response', {
                'error': 'Parametro cam_id requerido',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        is_active = vision_manager.is_camera_active(cam_id)

        response = {
            'success': True,
            'cam_id': cam_id,
            'ai_active': is_active,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        }

        if is_active:
            camera = device_config.get_camera(cam_id)
            if camera:
                response['processor_id'] = camera.get('active_processor')
            response['stream_url'] = f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}_ai/index.m3u8'

        emit('get_ai_status_response', response)

    except Exception as e:
        print(f"[VideoCtrl] Error get_ai_status: {e}")
        emit('get_ai_status_response', {
            'error': 'Error al obtener estado',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })