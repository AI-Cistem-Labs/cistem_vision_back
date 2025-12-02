from flask import Flask, Response, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import cv2
import time
import supervision as sv
from ultralytics import YOLO
import threading
import datetime
import os
import glob

# --- CONFIGURACIÓN ---
PORT = 5000
MODELS_DIR = 'models'
DEFAULT_MODEL = "nixito_v1"

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- ESTADO GLOBAL ---
global_state = {
    "cameras": {},  # Diccionario de cámaras activas
    "available_models": {},  # Modelos disponibles
    "camera_locks": {},  # Locks por cámara
}

# --- FUNCIONES DE UTILIDAD ---

def scan_available_models():
    """Escanea la carpeta| de modelos y devuelve los disponibles."""
    models = {}
    if os.path.exists(MODELS_DIR):
        for model_file in glob.glob(os.path.join(MODELS_DIR, "*.pt")):
            model_name = os.path.splitext(os.path.basename(model_file))[0]
            models[model_name] = {
                "name": model_name.replace("_", " ").title(),
                "path": model_file,
                "key": model_name
            }
    print(f"[SISTEMA] Modelos encontrados: {list(models.keys())}")
    return models

def scan_available_cameras():
    """Escanea y detecta cuántas cámaras hay disponibles."""
    available_cameras = []
    for i in range(10):  # Probar hasta 10 cámaras
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            available_cameras.append(i)
            cap.release()
            print(f"[SISTEMA] Cámara {i} detectada")
        else:
            break  # Si no hay más cámaras, salir
    return available_cameras

def log_message(message):
    """Log con timestamp."""
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    full_message = f"[{timestamp}] {message}"
    print(full_message)
    socketio.emit('log_message', {'data': full_message})

# --- CLASE PARA MANEJAR CADA CÁMARA ---

class CameraStream:
    def __init__(self, camera_id, model_key):
        self.camera_id = camera_id
        self.model_key = model_key
        self.model = None
        self.video_capture = None
        self.is_active = False
        self.lock = threading.Lock()
        self.box_annotator = sv.BoundingBoxAnnotator(thickness=2)
        self.label_annotator = sv.LabelAnnotator(text_thickness=1, text_scale=0.5)
       
        self.load_model(model_key)
        self.start_camera()
   
    def load_model(self, model_key):
        """Carga un modelo YOLO."""
        with self.lock:
            try:
                model_info = global_state["available_models"].get(model_key)
                if model_info:
                    log_message(f"[CAM-{self.camera_id}] Cargando modelo: {model_info['name']}")
                    self.model = YOLO(model_info['path'])
                    self.model_key = model_key
                    log_message(f"[CAM-{self.camera_id}] Modelo {model_info['name']} cargado")
                else:
                    log_message(f"[CAM-{self.camera_id}] Modelo {model_key} no encontrado")
            except Exception as e:
                log_message(f"[CAM-{self.camera_id}] Error cargando modelo: {e}")
   
    def start_camera(self):
        """Inicia la captura de video."""
        try:
            self.video_capture = cv2.VideoCapture(self.camera_id)
            if self.video_capture.isOpened():
                self.is_active = True
                log_message(f"[CAM-{self.camera_id}] Cámara iniciada")
            else:
                log_message(f"[CAM-{self.camera_id}] Error al abrir cámara")
        except Exception as e:
            log_message(f"[CAM-{self.camera_id}] Error: {e}")
   
    def get_frame(self):
        """Captura y procesa un frame con detecciones."""
        if not self.is_active or not self.video_capture or not self.video_capture.isOpened():
            return None
       
        with self.lock:
            success, frame = self.video_capture.read()
            if not success:
                return None
           
            # Realizar detección si hay modelo cargado
            if self.model:
                try:
                    results = self.model(frame, verbose=False)[0]
                    detections = sv.Detections.from_ultralytics(results)
                   
                    if len(detections) > 0:
                        labels = [
                            f"{self.model.names[class_id]} {confidence:.2f}"
                            for class_id, confidence in zip(detections.class_id, detections.confidence)
                        ]
                        frame = self.box_annotator.annotate(scene=frame, detections=detections)
                        frame = self.label_annotator.annotate(scene=frame, detections=detections, labels=labels)
                       
                        # Enviar detecciones por WebSocket
                        detection_data = {
                            "cameraId": f"cam-{self.camera_id}",
                            "timestamp": int(time.time() * 1000),
                            "detections": [
                                {
                                    "class": self.model.names[class_id],
                                    "confidence": float(confidence),
                                    "bbox": [int(x) for x in bbox]
                                }
                                for bbox, class_id, confidence in zip(
                                    detections.xyxy,
                                    detections.class_id,
                                    detections.confidence
                                )
                            ]
                        }
                        socketio.emit('detections', detection_data)
               
                except Exception as e:
                    log_message(f"[CAM-{self.camera_id}] Error en detección: {e}")
           
            return frame
   
    def stop(self):
        """Detiene la cámara."""
        self.is_active = False
        if self.video_capture:
            self.video_capture.release()
            log_message(f"[CAM-{self.camera_id}] Cámara detenida")

def generate_frames(camera_id):
    """Generador de frames para MJPEG stream."""
    camera = global_state["cameras"].get(camera_id)
    if not camera:
        return
   
    while camera.is_active:
        frame = camera.get_frame()
        if frame is None:
            time.sleep(0.1)
            continue
       
        (flag, buffer) = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not flag:
            continue
       
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- RUTAS HTTP ---

@app.route('/')
def index():
    return jsonify({
        "status": "online",
        "cameras": list(global_state["cameras"].keys()),
        "models": [
            {"key": k, "name": v["name"]}
            for k, v in global_state["available_models"].items()
        ]
    })

@app.route('/stream/<int:camera_id>')
def video_feed(camera_id):
    """Stream de video para una cámara específica."""
    if camera_id not in global_state["cameras"]:
        return "Camera not found", 404
   
    return Response(
        generate_frames(camera_id),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/api/cameras')
def get_cameras():
    """Devuelve lista de cámaras disponibles."""
    cameras_info = []
    for cam_id, camera in global_state["cameras"].items():
        cameras_info.append({
            "id": cam_id,
            "active": camera.is_active,
            "model": camera.model_key
        })
    return jsonify(cameras_info)

@app.route('/api/models')
def get_models():
    """Devuelve lista de modelos disponibles."""
    models_list = [
        {"key": k, "name": v["name"]}
        for k, v in global_state["available_models"].items()
    ]
    return jsonify(models_list)

# --- WEBSOCKET HANDLERS ---

@socketio.on('connect')
def handle_connect():
    log_message("[SOCKETIO] Cliente conectado")
    # Enviar info inicial
    emit('initial_state', {
        'cameras': list(global_state["cameras"].keys()),
        'models': [
            {"key": k, "name": v["name"]}
            for k, v in global_state["available_models"].items()
        ]
    })

@socketio.on('change_model')
def handle_change_model(data):
    """Cambia el modelo de una cámara específica."""
    camera_id = data.get('camera_id')
    model_key = data.get('model_key')
   
    if camera_id in global_state["cameras"]:
        camera = global_state["cameras"][camera_id]
        camera.load_model(model_key)
        emit('model_changed', {
            'camera_id': camera_id,
            'model_key': model_key
        }, broadcast=True)

@socketio.on('toggle_camera')
def handle_toggle_camera(data):
    """Activa/desactiva una cámara."""
    camera_id = data.get('camera_id')
    active = data.get('active', True)
   
    if camera_id in global_state["cameras"]:
        camera = global_state["cameras"][camera_id]
        camera.is_active = active
        log_message(f"[CAM-{camera_id}] {'Activada' if active else 'Pausada'}")
        emit('camera_status', {
            'camera_id': camera_id,
            'active': active
        }, broadcast=True)

@socketio.on('add_camera')
def handle_add_camera(data):
    """Agrega una nueva cámara al sistema."""
    camera_id = data.get('camera_id')
    model_key = data.get('model_key', DEFAULT_MODEL)
   
    if camera_id not in global_state["cameras"]:
        camera = CameraStream(camera_id, model_key)
        global_state["cameras"][camera_id] = camera
        emit('camera_added', {
            'camera_id': camera_id,
            'model_key': model_key
        }, broadcast=True)

@socketio.on('remove_camera')
def handle_remove_camera(data):
    """Remueve una cámara del sistema."""
    camera_id = data.get('camera_id')
   
    if camera_id in global_state["cameras"]:
        camera = global_state["cameras"][camera_id]
        camera.stop()
        del global_state["cameras"][camera_id]
        emit('camera_removed', {'camera_id': camera_id}, broadcast=True)

# --- INICIALIZACIÓN ---

if __name__ == '__main__':
    log_message("=== Sistema de Cámaras CISTEM Labs ===")
   
    # Escanear modelos disponibles
    global_state["available_models"] = scan_available_models()
   
    # Detectar cámaras disponibles
    available_camera_ids = scan_available_cameras()
    log_message(f"[SISTEMA] Cámaras detectadas: {available_camera_ids}")
   
    # Inicializar todas las cámaras detectadas
    for cam_id in available_camera_ids:
        camera = CameraStream(cam_id, DEFAULT_MODEL)
        global_state["cameras"][cam_id] = camera
   
    log_message(f"[SISTEMA] Servidor iniciando en puerto {PORT}")
    log_message(f"[SISTEMA] Endpoints:")
    log_message(f"  - GET  / - Info del sistema")
    log_message(f"  - GET  /stream/<camera_id> - Stream de video")
    log_message(f"  - GET  /api/cameras - Lista de cámaras")
    log_message(f"  - GET  /api/models - Lista de modelos")
    log_message(f"  - WS   / - WebSocket para control")
   
    socketio.run(app, host='0.0.0.0', port=PORT, allow_unsafe_werkzeug=True)

