import datetime
import time
from flask import Response, request
from app import socketio, app, vision_module

# 1. Evento WebSocket solicitado para iniciar el feed
@socketio.on('get_camera_feed')
def handle_get_camera_feed(data):
    """
    Recibe location_id, device_id, cam_id.
    Verifica que la cámara esté activa antes de permitir la transmisión.
    """
    loc_id = data.get('location_id')
    dev_id = data.get('device_id')
    cam_id = data.get('cam_id')

    # Lógica de validación: Verificar si la cámara está activa en el módulo de visión
    # (Asumiendo que vision_module tiene un diccionario o estado de sus cámaras)
    if not vision_module.is_camera_active(cam_id):
        socketio.emit('camera_feed_response', {
            "success": False,
            "error": "La cámara está apagada. Active la cámara antes de solicitar el stream de video",
            "code": 400,
            "datetime": datetime.datetime.utcnow().isoformat() + "Z"
        })
        return

    # Si está activa, notificamos al frontend que el stream está listo
    socketio.emit('camera_feed_response', {
        "success": True,
        "streaming": True,
        "format": "MJPEG",
        "location_id": loc_id,
        "device_id": dev_id,
        "cam_id": cam_id,
        "datetime": datetime.datetime.utcnow().isoformat() + "Z"
    })

# 2. Endpoint HTTP para el stream binario MJPEG (consumido por la etiqueta <img> de Next.js)
@app.route('/camera/feed')
def stream_video():
    """
    Implementación del streaming MJPEG.
    Solo transmite si hay clientes conectados para optimizar recursos.
    """
    loc_id = request.args.get('location_id')
    dev_id = request.args.get('device_id')
    cam_id = request.args.get('cam_id')

    # Verificación de seguridad adicional
    if not vision_module.is_camera_active(cam_id):
        return {"error": "Cámara no activa"}, 400

    def generate():
        while True:
            frame = vision_module.get_latest_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                time.sleep(0.05)

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')