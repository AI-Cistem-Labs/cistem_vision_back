# modules/communication/manager.py
from flask import Flask, Response
from flask_socketio import SocketIO
import threading
import time


class CommunicationManager:
    def __init__(self, port, vision_module):
        self.port = port
        self.vision_module = vision_module  # Guardamos referencia al módulo de visión

        # Inicializar Flask y SocketIO
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Configurar rutas y eventos
        self._setup_routes()
        self._setup_socket_events()

    def send_data(self, event_name, data_payload):
        """
        Permite a otros módulos (como Analytics) enviar eventos JSON
        arbitrarios al frontend.
        """
        # Emitir vía SocketIO
        self.socketio.emit(event_name, data_payload)

        # Opcional: Imprimir en consola para debug ligero
        # print(f"[COMMS SEND] {event_name}: {data_payload}")


    def _setup_routes(self):
        """Define las rutas HTTP (endpoints)"""

        @self.app.route('/video_feed')
        def video_feed():
            return Response(self._generate_frames(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

        @self.app.route('/status')
        def status():
            return {"status": "online", "module": "communication"}

    def _setup_socket_events(self):
        """Define los eventos de WebSocket"""

        @self.socketio.on('connect')
        def handle_connect():
            print("[COMMS] Cliente conectado (Dashboard)")
            # Aquí podríamos enviar el estado inicial
            self.socketio.emit('log_message', {'data': 'Conexión establecida con Jetson.'})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            print("[COMMS] Cliente desconectado")

        # Aquí agregaremos más eventos: 'change_model', 'toggle_camera', etc.

    def _generate_frames(self):
        """Generador que pide frames al módulo de visión y los sirve"""
        while True:
            # Pedimos el frame codificado al módulo de visión
            frame_bytes = self.vision_module.get_latest_frame()

            if frame_bytes is None:
                time.sleep(0.05)  # Esperar un poco si no hay frame listo
                continue

            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    def send_log(self, message):
        """Métdo público para que otros módulos envíen logs a la web"""
        print(f"[COMMS LOG] {message}")
        self.socketio.emit('log_message', {'data': message})

    def start(self):
        """Inicia el servidor (Bloqueante)"""
        print(f"[COMMS] Iniciando servidor en el puerto {self.port}...")
        # allow_unsafe_werkzeug=True es necesario para desarrollo/pruebas
        self.socketio.run(self.app, host='0.0.0.0', port=self.port, allow_unsafe_werkzeug=True)