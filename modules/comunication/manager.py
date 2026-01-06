from flask import Flask, Response
from flask_socketio import SocketIO
import time
import datetime
import config  # Importamos para usar DEVICE_NAME y otras variables del .env


class CommunicationManager:
    def __init__(self, port, vision_module):
        self.port = port
        self.vision = vision_module

        # Inicialización de Flask y SocketIO con CORS abierto para Next.js
        self.app = Flask(__name__)
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        # Estado de eficiencia: El video inicia pausado hasta que el Front lo pida
        self.video_active = False

        self._setup_routes()
        self._setup_socket_events()

    def _setup_routes(self):
        """Ruta para el streaming de video mediante MJPEG"""

        @self.app.route('/video_feed')
        def video_feed():
            return Response(self._generate_frames(),
                            mimetype='multipart/x-mixed-replace; boundary=frame')

    def _setup_socket_events(self):
        """Manejo de eventos de entrada (Desde Next.js hacia la Jetson)"""

        @self.socketio.on('connect')
        def handle_connect():
            print(f"[COMMS] Dashboard conectado. Sincronizando configuración...")

            # 1. Enviar lista de procesadores disponibles para el Combobox
            from modules.vision.processors.registry import get_available_processors
            processors = get_available_processors()
            self.send_data('available_processors', processors)

            # 2. Enviar log de bienvenida confirmando conexión
            self.send_data('log_event', {
                "type": "log",
                "device": config.DEVICE_NAME,
                "msg": "Conexión exitosa. Esperando instrucciones de video o modelo."
            })

        @self.socketio.on('disconnect')
        def handle_disconnect():
            print("[COMMS] Dashboard desconectado.")
            self.video_active = False  # Pausar video si no hay nadie viendo

        @self.socketio.on('toggle_video')
        def handle_video_request(data):
            """Activa/Desactiva el flujo de video: {'active': true/false}"""
            self.video_active = data.get("active", False)
            estado = "Iniciada" if self.video_active else "Pausada"
            print(f"[COMMS] Transmisión de video {estado} por solicitud del usuario.")

        @self.socketio.on('select_processor')
        def handle_processor_change(data):
            """Cambia el script de detección: {'processor_id': 'id_del_script'}"""
            proc_id = data.get("processor_id")
            if proc_id:
                success = self.vision.change_processor(proc_id)
                if success:
                    self.send_data('log_event', {
                        "type": "log",
                        "device": config.DEVICE_NAME,
                        "msg": f"Cambio de procesador exitoso: {proc_id}"
                    })

    def _generate_frames(self):
        """Generador de frames eficiente para el streaming"""
        while True:
            # Si nadie está viendo el video, no consumimos CPU procesando imágenes
            if not self.video_active:
                time.sleep(0.5)
                continue

            frame_bytes = self.vision.get_latest_frame()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                time.sleep(0.05)

    def send_data(self, event_name, payload):
        """
        Envía datos al Front End asegurando que todos los JSON
        incluyan la fecha actual según el estándar solicitado.
        """
        if isinstance(payload, dict):
            # Inyectar fecha y día automáticamente
            now = datetime.datetime.now()
            payload["date"] = now.strftime("%Y-%m-%d")
            # Opcional: puedes agregar el campo "time" si lo necesitas por separado
            # payload["time"] = now.strftime("%H:%M:%S")

        self.socketio.emit(event_name, payload)

    def start(self):
        """Inicia el servidor en el puerto configurado"""
        print(f"[COMMS] Servidor iniciado en puerto {self.port} (Modo: Robust)")
        self.socketio.run(self.app, host='0.0.0.0', port=self.port, allow_unsafe_werkzeug=True)