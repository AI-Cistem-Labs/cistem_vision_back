# controllers/video_controller.py
"""
Controlador de video para Cistem Vision.

Provee endpoints para obtener URLs de streaming de video, tanto
raw (directo de cámara) como procesado (con IA/bounding boxes).

El video procesado se publica a MediaMTX por el VisionManager,
permitiendo al frontend consumirlo eficientemente via HLS.
"""

from flask_socketio import emit
from extensions import socketio
from config.config_manager import device_config
from modules.vision.manager import VisionManager
from datetime import datetime
from controllers.auth_controller import verify_token
import os

vision_manager = VisionManager()

# Configuración de Tailscale y MediaMTX
TAILSCALE_IP = os.getenv('TAILSCALE_IP', '100.73.141.61')
MEDIAMTX_HLS_PORT = os.getenv('MEDIAMTX_HLS_PORT', '8888')
MEDIAMTX_WEBRTC_PORT = os.getenv('MEDIAMTX_WEBRTC_PORT', '8889')
MEDIAMTX_RTSP_PORT = os.getenv('MEDIAMTX_RTSP_PORT', '8554')


@socketio.on('get_camera_stream_url')
def handle_get_camera_stream_url(data):
    """
    Evento: get_camera_stream_url

    Retorna las URLs de streaming MediaMTX para una cámara.
    Incluye tanto el stream RAW como el stream PROCESADO (con IA).

    Request:
        {
            "token": "jwt_token",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "processed": true  // Opcional: si true, devuelve URL de video procesado
        }

    Response:
        {
            "success": true,
            "cam_id": 1001,
            "streams": {
                "hls": "http://...:8888/cam_1001/index.m3u8",
                "webrtc": "http://...:8889/cam_1001",
                "rtsp": "rtsp://...:8554/cam_1001"
            },
            "processed_streams": {  // Solo si hay procesador activo y cámara encendida
                "hls": "http://...:8888/cam_1001_ai/index.m3u8",
                "webrtc": "http://...:8889/cam_1001_ai",
                "rtsp": "rtsp://...:8554/cam_1001_ai"
            },
            "ai_active": true,
            "processor_id": 1
        }
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('get_camera_stream_url_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')
        want_processed = data.get('processed', True)  # Por defecto queremos procesado

        if not all([location_id, device_id, cam_id]):
            emit('get_camera_stream_url_response', {
                'error': 'Los parámetros location_id, device_id y cam_id son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('get_camera_stream_url_response', {
                'error': 'Cámara no encontrada',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # URLs del stream RAW (directo de la cámara)
        raw_streams = {
            'hls': f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}/index.m3u8',
            'webrtc': f'http://{TAILSCALE_IP}:{MEDIAMTX_WEBRTC_PORT}/cam_{cam_id}',
            'rtsp': f'rtsp://{TAILSCALE_IP}:{MEDIAMTX_RTSP_PORT}/cam_{cam_id}'
        }

        response = {
            'success': True,
            'cam_id': cam_id,
            'streams': raw_streams,
            'ai_active': False,
            'processor_id': None,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        }

        # Si la cámara está activa y tiene procesador, iniciar/verificar el VisionManager
        if camera['status'] and camera.get('active_processor') and want_processed:
            processor_id = camera.get('active_processor')

            # Iniciar VisionManager si no está activo
            if not vision_manager.is_camera_active(cam_id):
                print(f"🚀 Iniciando VisionManager para cámara {cam_id} (procesador {processor_id})...")
                vision_manager.start_camera(cam_id, processor_id)

            # Verificar si el VisionManager está activo
            if vision_manager.is_camera_active(cam_id):
                # URLs del stream PROCESADO (con bounding boxes)
                processed_streams = {
                    'hls': f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}_ai/index.m3u8',
                    'webrtc': f'http://{TAILSCALE_IP}:{MEDIAMTX_WEBRTC_PORT}/cam_{cam_id}_ai',
                    'rtsp': f'rtsp://{TAILSCALE_IP}:{MEDIAMTX_RTSP_PORT}/cam_{cam_id}_ai'
                }

                response['processed_streams'] = processed_streams
                response['ai_active'] = True
                response['processor_id'] = processor_id

                print(f"✅ URLs de streaming (raw + procesado) enviadas para cámara {cam_id}")
            else:
                print(f"⚠️ VisionManager no pudo iniciarse para cámara {cam_id}")
        else:
            print(f"✅ URLs de streaming (solo raw) enviadas para cámara {cam_id}")

        emit('get_camera_stream_url_response', response)

    except Exception as e:
        print(f"❌ Error en get_camera_stream_url: {str(e)}")
        emit('get_camera_stream_url_response', {
            'error': 'Error al obtener URLs de streaming',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('start_ai_processing')
def handle_start_ai_processing(data):
    """
    Evento: start_ai_processing

    Inicia el procesamiento de IA para una cámara específica.
    Esto activa el VisionManager que captura video, lo procesa
    con el procesador seleccionado, y lo republica a MediaMTX.

    Request:
        {
            "token": "jwt_token",
            "location_id": 1,
            "device_id": 101,
            "cam_id": 1001,
            "processor_id": 1  // Opcional: si no se especifica, usa el activo
        }
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        cam_id = data.get('cam_id')
        processor_id = data.get('processor_id')

        if not cam_id:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'El parámetro cam_id es requerido',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe y está activa
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'Cámara no encontrada',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        if not camera['status']:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'La cámara debe estar encendida para iniciar procesamiento IA',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Usar procesador especificado o el activo
        if processor_id is None:
            processor_id = camera.get('active_processor')

        if processor_id is None:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'No hay procesador especificado ni activo para esta cámara',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Detener procesamiento anterior si existe
        if vision_manager.is_camera_active(cam_id):
            vision_manager.stop_camera(cam_id)

        # Iniciar VisionManager
        if vision_manager.start_camera(cam_id, processor_id):
            # URL del stream procesado
            processed_stream_url = f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}_ai/index.m3u8'

            emit('start_ai_processing_response', {
                'success': True,
                'message': 'Procesamiento IA iniciado correctamente',
                'cam_id': cam_id,
                'processor_id': processor_id,
                'stream_url': processed_stream_url,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            print(f"✅ Procesamiento IA iniciado para cámara {cam_id}")
        else:
            emit('start_ai_processing_response', {
                'success': False,
                'error': 'Error al iniciar procesamiento IA',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

    except Exception as e:
        print(f"❌ Error en start_ai_processing: {str(e)}")
        emit('start_ai_processing_response', {
            'success': False,
            'error': 'Error interno al iniciar procesamiento',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('stop_ai_processing')
def handle_stop_ai_processing(data):
    """
    Evento: stop_ai_processing

    Detiene el procesamiento de IA para una cámara.

    Request:
        {
            "token": "jwt_token",
            "cam_id": 1001
        }
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('stop_ai_processing_response', {
                'success': False,
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        cam_id = data.get('cam_id')

        if not cam_id:
            emit('stop_ai_processing_response', {
                'success': False,
                'error': 'El parámetro cam_id es requerido',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Detener VisionManager
        if vision_manager.is_camera_active(cam_id):
            vision_manager.stop_camera(cam_id)
            emit('stop_ai_processing_response', {
                'success': True,
                'message': 'Procesamiento IA detenido correctamente',
                'cam_id': cam_id,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            print(f"✅ Procesamiento IA detenido para cámara {cam_id}")
        else:
            emit('stop_ai_processing_response', {
                'success': True,
                'message': 'El procesamiento IA ya estaba detenido',
                'cam_id': cam_id,
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })

    except Exception as e:
        print(f"❌ Error en stop_ai_processing: {str(e)}")
        emit('stop_ai_processing_response', {
            'success': False,
            'error': 'Error al detener procesamiento',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('get_ai_status')
def handle_get_ai_status(data):
    """
    Evento: get_ai_status

    Obtiene el estado del procesamiento IA de una cámara.

    Request:
        {
            "token": "jwt_token",
            "cam_id": 1001
        }

    Response:
        {
            "success": true,
            "cam_id": 1001,
            "ai_active": true,
            "processor_id": 1,
            "stream_url": "http://..../cam_1001_ai/index.m3u8"
        }
    """
    try:
        token = data.get('token')
        if not verify_token(token):
            emit('get_ai_status_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        cam_id = data.get('cam_id')

        if not cam_id:
            emit('get_ai_status_response', {
                'error': 'El parámetro cam_id es requerido',
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
            response['processor_id'] = camera.get('active_processor') if camera else None
            response['stream_url'] = f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}_ai/index.m3u8'

        emit('get_ai_status_response', response)

    except Exception as e:
        print(f"❌ Error en get_ai_status: {str(e)}")
        emit('get_ai_status_response', {
            'error': 'Error al obtener estado',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })
