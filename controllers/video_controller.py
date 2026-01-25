# controllers/video_controller.py
from flask_socketio import emit
from extensions import socketio
from config.config_manager import device_config
from modules.vision.manager import VisionManager
from datetime import datetime
from controllers.auth_controller import verify_token
import threading
import time
import cv2
import base64

vision_manager = VisionManager()

# Diccionario para rastrear clientes activos de streaming
active_streams = {}  # {cam_id: {client_id: thread}}


@socketio.on('get_camera_feed')
def handle_get_camera_feed(data):
    """
    Evento: get_camera_feed
    Inicia streaming de video procesado de una cámara
    """
    try:
        # Verificar autenticación
        token = data.get('token')
        if not verify_token(token):
            emit('get_camera_feed_response', {
                'error': 'Token inválido o expirado',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Validar parámetros
        location_id = data.get('location_id')
        device_id = data.get('device_id')
        cam_id = data.get('cam_id')

        if not all([location_id, device_id, cam_id]):
            emit('get_camera_feed_response', {
                'error': 'Los parámetros location_id, device_id y cam_id son requeridos',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara existe
        camera = device_config.get_camera(cam_id)
        if not camera:
            emit('get_camera_feed_response', {
                'error': 'Cámara no encontrada con los parámetros proporcionados',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que la cámara está encendida
        if not camera['status']:
            emit('get_camera_feed_response', {
                'error': 'La cámara está apagada. Active la cámara antes de solicitar el stream de video',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Verificar que hay un procesador activo
        if not camera.get('active_processor'):
            emit('get_camera_feed_response', {
                'error': 'No hay un procesador activo seleccionado para esta cámara',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Obtener ID del cliente (SocketIO request)
        from flask import request
        client_id = request.sid

        # Iniciar thread de streaming para este cliente
        if cam_id not in active_streams:
            active_streams[cam_id] = {}

        # Detener stream anterior si existe
        if client_id in active_streams[cam_id]:
            active_streams[cam_id][client_id]['stop'] = True

        # Crear control de thread
        stream_control = {'stop': False}
        active_streams[cam_id][client_id] = stream_control

        # Iniciar thread de streaming
        thread = threading.Thread(
            target=stream_video,
            args=(cam_id, client_id, stream_control)
        )
        thread.daemon = True
        thread.start()

        emit('get_camera_feed_response', {
            'streaming': True,
            'format': 'MJPEG',
            'location_id': location_id,
            'device_id': device_id,
            'cam_id': cam_id,
            'resolution': '1920x1080',  # Ajustar según configuración
            'fps': 30,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ Streaming iniciado para cámara {cam_id} - Cliente {client_id}")

    except Exception as e:
        print(f"❌ Error en get_camera_feed: {str(e)}")
        emit('get_camera_feed_response', {
            'error': 'Error al iniciar stream de video. Intente nuevamente',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


def stream_video(cam_id, client_id, stream_control):
    """
    Thread que envía frames de video procesado al cliente
    """
    try:
        start_time = time.time()
        frame_count = 0

        while not stream_control['stop']:
            # Obtener frame procesado del VisionManager
            frame = vision_manager.get_processed_frame(cam_id)

            if frame is not None:
                # Convertir frame a base64 para enviar por SocketIO
                _, buffer = cv2.imencode('.jpg', frame)
                frame_base64 = base64.b64encode(buffer).decode('utf-8')

                # Calcular tiempo activo
                elapsed_time = int(time.time() - start_time)
                hours = elapsed_time // 3600
                minutes = (elapsed_time % 3600) // 60
                seconds = elapsed_time % 60
                time_active = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                # Emitir frame al cliente específico
                socketio.emit('video_frame', {
                    'cam_id': cam_id,
                    'frame': frame_base64,
                    'time_active': time_active,
                    'frame_number': frame_count
                }, room=client_id)

                frame_count += 1

            # Control de FPS (30 FPS = ~33ms por frame)
            time.sleep(0.033)

        print(f"✅ Streaming detenido para cámara {cam_id} - Cliente {client_id}")

    except Exception as e:
        print(f"❌ Error en stream_video: {str(e)}")
    finally:
        # Limpiar
        if cam_id in active_streams and client_id in active_streams[cam_id]:
            del active_streams[cam_id][client_id]


@socketio.on('stop_camera_feed')
def handle_stop_camera_feed(data):
    """
    Evento: stop_camera_feed
    Detiene el streaming de video de una cámara
    """
    try:
        cam_id = data.get('cam_id')

        if not cam_id:
            emit('stop_camera_feed_response', {
                'success': False,
                'error': 'El parámetro cam_id es requerido',
                'datetime': datetime.utcnow().isoformat() + 'Z'
            })
            return

        # Obtener ID del cliente
        from flask import request
        client_id = request.sid

        # Detener streaming
        if cam_id in active_streams and client_id in active_streams[cam_id]:
            active_streams[cam_id][client_id]['stop'] = True

        emit('stop_camera_feed_response', {
            'success': True,
            'message': 'Streaming detenido correctamente',
            'cam_id': cam_id,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ Streaming detenido manualmente para cámara {cam_id}")

    except Exception as e:
        print(f"❌ Error en stop_camera_feed: {str(e)}")
        emit('stop_camera_feed_response', {
            'success': False,
            'error': 'Error al detener streaming',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })


@socketio.on('disconnect')
def handle_disconnect():
    """
    Maneja desconexión de cliente - limpia streams activos
    """
    from flask import request
    client_id = request.sid

    # Detener todos los streams de este cliente
    for cam_id in list(active_streams.keys()):
        if client_id in active_streams[cam_id]:
            active_streams[cam_id][client_id]['stop'] = True
            print(f"🔌 Cliente {client_id} desconectado - Stream de cámara {cam_id} detenido")


# ============================================================
# STREAMING VÍA MEDIAMTX (HLS/WebRTC)
# ============================================================

import os

# Configuración de Tailscale y MediaMTX
TAILSCALE_IP = os.getenv('TAILSCALE_IP', '100.73.141.61')  # ⬅️ CAMBIA ESTA IP
MEDIAMTX_HLS_PORT = os.getenv('MEDIAMTX_HLS_PORT', '8888')
MEDIAMTX_WEBRTC_PORT = os.getenv('MEDIAMTX_WEBRTC_PORT', '8889')
MEDIAMTX_RTSP_PORT = os.getenv('MEDIAMTX_RTSP_PORT', '8554')


@socketio.on('get_camera_stream_url')
def handle_get_camera_stream_url(data):
    """
    Evento: get_camera_stream_url
    Retorna las URLs de streaming MediaMTX para una cámara específica
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

        # Construir URLs de streaming vía MediaMTX
        stream_urls = {
            'hls': f'http://{TAILSCALE_IP}:{MEDIAMTX_HLS_PORT}/cam_{cam_id}/index.m3u8',
            'webrtc': f'http://{TAILSCALE_IP}:{MEDIAMTX_WEBRTC_PORT}/cam_{cam_id}',
            'rtsp': f'rtsp://{TAILSCALE_IP}:{MEDIAMTX_RTSP_PORT}/cam_{cam_id}'
        }

        emit('get_camera_stream_url_response', {
            'success': True,
            'cam_id': cam_id,
            'streams': stream_urls,
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })

        print(f"✅ URLs de streaming MediaMTX enviadas para cámara {cam_id}")

    except Exception as e:
        print(f"❌ Error en get_camera_stream_url: {str(e)}")
        emit('get_camera_stream_url_response', {
            'error': 'Error al obtener URLs de streaming',
            'datetime': datetime.utcnow().isoformat() + 'Z'
        })