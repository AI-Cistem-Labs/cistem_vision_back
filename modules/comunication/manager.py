# modules/comunication/manager.py
from flask import Flask, Response
from flask_socketio import SocketIO
import threading
import time


class CommunicationManager:
    def __init__(self, port, vision_module):
        self.port = port
        self.vision_module = vision_module

        self.app = Flask(__name__)
        # Habilitar CORS para que Next.js pueda conectarse sin problemas
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        self._setup_routes()
        self._setup_socket_events()

    def _setup_routes(self):
        @self.app.route('/video_feed')
        def video_feed():
            return Response(self._generate_frames(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

    def _setup_socket_events(self):
        @self.socketio.on('connect')
        def handle_connect():
            print("[COMMS] Dashboard conectado.")
            # Al conectar, podríamos enviar la lista de procesadores disponibles
            from modules.vision.processors.registry import get_available_processors
            self.socketio.emit('available_processors', get_available_processors())

        # --- EVENTO CLAVE: Cambio de Procesador ---
        @self.socketio.on('change_processor')
        def handle_change_processor(data):
            # 'data' debe ser un dict: {"processor_id": "flow_persons_v1"}
            proc_id = data.get('processor_id')
            if proc_id:
                success = self.vision_module.change_processor(proc_id)
                if success:
                    self.send_data("log_event", {"msg": f"Cambiando a script: {proc_id}"})

    def _generate_frames(self):
        while True:
            frame_bytes = self.vision_module.get_latest_frame()
            if frame_bytes is None:
                time.sleep(0.04)  # ~25 FPS
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    def send_data(self, event_name, data_payload):
        """Método para que otros módulos (Logs, Analytics) envíen datos al Front"""
        self.socketio.emit(event_name, data_payload)

    def start(self):
        print(f"[COMMS] Servidor escuchando en puerto {self.port}...")
        self.socketio.run(self.app, host='0.0.0.0', port=self.port, allow_unsafe_werkzeug=True)