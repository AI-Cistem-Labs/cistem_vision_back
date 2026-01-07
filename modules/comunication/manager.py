# modules/comunication/manager.py
from flask import Flask, Response
from flask_socketio import SocketIO
import time
import datetime
import config


class CommunicationManager:
    def __init__(self, port, vision_module):
        self.port = port
        self.vision = vision_module
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        self.video_active = False

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
            print(f"[COMMS] Dashboard conectado. Sincronizando...")
            from modules.vision.processors.registry import get_available_processors
            self.send_data('available_processors', get_available_processors())
            self.send_data('log_event', {
                "type": "log",
                "device": config.DEVICE_NAME,
                "msg": "Conexión exitosa y datos sincronizados."
            })

        @self.socketio.on('toggle_video')
        def handle_video(data):
            self.video_active = data.get("active", False)

        @self.socketio.on('select_processor')
        def handle_proc(data):
            proc_id = data.get("processor_id")
            if proc_id: self.vision.change_processor(proc_id)

    def _generate_frames(self):
        while True:
            if not self.video_active:
                time.sleep(0.5)
                continue
            frame = self.vision.get_latest_frame()
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            else:
                time.sleep(0.05)

    def send_data(self, event, payload):
        """Inyecta automáticamente 'date' en todos los JSON de salida"""
        if isinstance(payload, dict):
            payload["date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        self.socketio.emit(event, payload)

    def start(self):
        self.socketio.run(self.app, host='0.0.0.0', port=self.port, allow_unsafe_werkzeug=True)