from flask import Blueprint, Response, request, stream_with_context
from config.config_manager import device_config
from modules.vision.manager import VisionManager
from controllers.auth_controller import verify_token
import cv2
import time

# Crear Blueprint para rutas HTTP de video
video_bp = Blueprint('video', __name__)

vision_manager = VisionManager()


def generate_frames(cam_id):
    """Generador que obtiene frames procesados y los envía como MJPEG"""
    while True:
        # Obtener frame ya procesado (con cajas dibujadas)
        frame = vision_manager.get_processed_frame(cam_id)

        if frame is None:
            # Si no hay frame procesado, intentar con el raw
            frame = vision_manager.get_raw_frame(cam_id)

        if frame is not None:
            # Codificar a JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_bytes = buffer.tobytes()
                # Yield en formato multipart MJPEG estándar
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

        # Control de FPS para no saturar (aprox 30 FPS)
        time.sleep(0.033)


@video_bp.route('/feed/<int:cam_id>')
def video_feed(cam_id):
    """
    Endpoint HTTP para streaming MJPEG
    Uso: <img src="http://localhost:5000/video/feed/1001?token=XYZ">
    """
    # 1. Validar Token (enviado por query param por la etiqueta img)
    token = request.args.get('token')
    if not verify_token(token):
        return "Unauthorized", 401

    # 2. Validar Cámara
    camera = device_config.get_camera(cam_id)
    if not camera:
        return "Camera not found", 404

    if not camera['status']:
        # Podrías devolver una imagen estática de "Cámara Apagada"
        return "Camera is off", 503

    # 3. Retornar respuesta Streaming
    return Response(stream_with_context(generate_frames(cam_id)),
                    mimetype='multipart/x-mixed-replace; boundary=frame')