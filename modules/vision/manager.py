# modules/vision/manager.py
"""
VisionManager con soporte para re-publicar video procesado a MediaMTX.

Este manager captura video de las cámaras via RTSP, procesa cada frame
con los procesadores de IA (bounding boxes, zonas, etc.), y re-publica
el video procesado a MediaMTX como un nuevo stream.

Flujo:
  Cámara (RTSP) → VisionManager → Procesador IA → FFmpeg → MediaMTX (RTSP)
                                                              ↓
                                                         Frontend (HLS)
"""

import threading
import subprocess
import time
import os
from config.config_manager import device_config
from modules.vision.processors import get_processor_class
from modules.analytics.specialists.system_logger import system_logger
from modules.analytics.specialists.alerts_engine import alerts_engine
import cv2
import numpy as np

# Configuración de MediaMTX desde variables de entorno
MEDIAMTX_HOST = os.getenv('TAILSCALE_IP', '127.0.0.1')
MEDIAMTX_RTSP_PORT = os.getenv('MEDIAMTX_RTSP_PORT', '8554')

# Configuración de FFmpeg para publicar streams
FFMPEG_CONFIG = {
    'fps': 25,  # FPS del stream de salida
    'width': 1280,  # Ancho del video (ajustar según necesidad)
    'height': 720,  # Alto del video
    'bitrate': '2M',  # Bitrate del video
    'preset': 'ultrafast',  # Preset de encoding (ultrafast para baja latencia)
    'tune': 'zerolatency',  # Optimización para streaming en vivo
}


class RTSPPublisher:
    """
    Clase auxiliar que maneja la publicación de frames a MediaMTX via FFmpeg.

    Crea un proceso FFmpeg que recibe frames via pipe y los publica como RTSP.
    """

    def __init__(self, cam_id: int, width: int = None, height: int = None, fps: int = None):
        """
        Args:
            cam_id: ID de la cámara (se usará para nombrar el stream)
            width: Ancho del video
            height: Alto del video
            fps: Frames por segundo
        """
        self.cam_id = cam_id
        self.width = width or FFMPEG_CONFIG['width']
        self.height = height or FFMPEG_CONFIG['height']
        self.fps = fps or FFMPEG_CONFIG['fps']
        self.process = None
        self.is_running = False
        self.lock = threading.Lock()

        # URL de salida: stream procesado con sufijo _ai
        self.output_url = f"rtsp://{MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}/cam_{cam_id}_ai"

    def start(self):
        """Inicia el proceso FFmpeg para publicar el stream."""
        if self.is_running:
            return True

        try:
            # Comando FFmpeg para recibir frames raw y publicar como RTSP
            ffmpeg_cmd = [
                'ffmpeg',
                '-y',  # Sobrescribir sin preguntar
                '-f', 'rawvideo',  # Formato de entrada: video raw
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',  # Formato de píxeles (OpenCV usa BGR)
                '-s', f'{self.width}x{self.height}',  # Resolución
                '-r', str(self.fps),  # FPS de entrada
                '-i', '-',  # Entrada desde stdin (pipe)
                '-c:v', 'libx264',  # Codec de video
                '-preset', FFMPEG_CONFIG['preset'],
                '-tune', FFMPEG_CONFIG['tune'],
                '-b:v', FFMPEG_CONFIG['bitrate'],
                '-maxrate', FFMPEG_CONFIG['bitrate'],
                '-bufsize', '4M',
                '-pix_fmt', 'yuv420p',  # Formato de salida estándar
                '-g', str(self.fps * 2),  # GOP size (keyframe cada 2 segundos)
                '-f', 'rtsp',  # Formato de salida: RTSP
                '-rtsp_transport', 'tcp',  # Usar TCP para mayor estabilidad
                self.output_url
            ]

            print(f"🎬 Iniciando FFmpeg publisher para cámara {self.cam_id}")
            print(f"   Resolución: {self.width}x{self.height} @ {self.fps}fps")
            print(f"   URL salida: {self.output_url}")

            # Iniciar proceso FFmpeg
            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=10 ** 8  # Buffer grande para evitar bloqueos
            )

            self.is_running = True

            # Thread para monitorear errores de FFmpeg
            error_thread = threading.Thread(
                target=self._monitor_errors,
                daemon=True
            )
            error_thread.start()

            print(f"✅ FFmpeg publisher iniciado para cámara {self.cam_id}")
            return True

        except Exception as e:
            print(f"❌ Error iniciando FFmpeg: {str(e)}")
            self.is_running = False
            return False

    def _monitor_errors(self):
        """Monitorea stderr de FFmpeg para detectar errores."""
        if not self.process:
            return

        try:
            for line in self.process.stderr:
                line_str = line.decode('utf-8', errors='ignore').strip()
                # Solo mostrar errores importantes, ignorar info de progreso
                if 'error' in line_str.lower() or 'fatal' in line_str.lower():
                    print(f"⚠️ FFmpeg [{self.cam_id}]: {line_str}")
        except:
            pass

    def write_frame(self, frame: np.ndarray):
        """
        Escribe un frame al proceso FFmpeg.

        Args:
            frame: Frame de OpenCV (numpy array BGR)
        """
        if not self.is_running or not self.process:
            return False

        try:
            with self.lock:
                # Redimensionar frame si es necesario
                h, w = frame.shape[:2]
                if w != self.width or h != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))

                # Escribir frame al pipe de FFmpeg
                self.process.stdin.write(frame.tobytes())
                return True

        except BrokenPipeError:
            print(f"❌ Pipe roto en FFmpeg publisher {self.cam_id}")
            self.stop()
            return False
        except Exception as e:
            print(f"❌ Error escribiendo frame: {str(e)}")
            return False

    def stop(self):
        """Detiene el proceso FFmpeg."""
        self.is_running = False

        if self.process:
            try:
                self.process.stdin.close()
                self.process.terminate()
                self.process.wait(timeout=5)
            except:
                self.process.kill()
            finally:
                self.process = None

        print(f"🛑 FFmpeg publisher detenido para cámara {self.cam_id}")


class VisionManager:
    """
    Singleton que gestiona todas las cámaras y sus procesadores.

    Ahora incluye soporte para re-publicar video procesado a MediaMTX,
    permitiendo que el frontend consuma el video con bounding boxes
    via HLS/WebRTC de manera eficiente.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Diccionario de cámaras activas: {cam_id: camera_thread_data}
        self.active_cameras = {}

        # Lock para thread-safety
        self.lock = threading.Lock()

        self._initialized = True
        print("✅ VisionManager inicializado (con soporte MediaMTX)")

    def start_camera(self, cam_id, processor_id=None):
        """
        Inicia captura, procesamiento y re-publicación de una cámara.

        Args:
            cam_id: ID de la cámara
            processor_id: ID del procesador (si None, usa el activo en config)
        """
        with self.lock:
            # Verificar si ya está activa
            if cam_id in self.active_cameras:
                print(f"⚠️ Cámara {cam_id} ya está activa")
                return False

            # Obtener configuración de la cámara
            camera = device_config.get_camera(cam_id)
            if not camera:
                print(f"❌ Cámara {cam_id} no encontrada en configuración")
                return False

            # Determinar procesador a usar
            if processor_id is None:
                processor_id = camera.get('active_processor')

            if processor_id is None:
                print(f"❌ No hay procesador asignado a cámara {cam_id}")
                return False

            # Obtener clase del procesador
            ProcessorClass = get_processor_class(processor_id)
            if not ProcessorClass:
                print(f"❌ Procesador {processor_id} no encontrado")
                return False

            # Obtener URL RTSP
            rtsp_url = device_config.get_rtsp_url(cam_id)
            if not rtsp_url:
                print(f"❌ URL RTSP no configurada para cámara {cam_id}")
                system_logger.log(cam_id, "URL RTSP no configurada", "ERROR")
                return False

            # Crear publisher de RTSP
            rtsp_publisher = RTSPPublisher(cam_id)

            # Crear control de thread
            camera_data = {
                'cam_id': cam_id,
                'rtsp_url': rtsp_url,
                'processor_id': processor_id,
                'processor': ProcessorClass(cam_id),
                'stop_flag': False,
                'current_frame': None,
                'processed_frame': None,
                'thread': None,
                'capture': None,
                'rtsp_publisher': rtsp_publisher,  # Nuevo: publisher
                'output_url': rtsp_publisher.output_url,  # URL del stream procesado
            }

            # Crear y arrancar thread
            thread = threading.Thread(
                target=self._camera_loop,
                args=(camera_data,),
                daemon=True
            )
            camera_data['thread'] = thread
            thread.start()

            # Registrar en diccionario
            self.active_cameras[cam_id] = camera_data

            print(f"✅ Cámara {cam_id} iniciada con procesador {processor_id}")
            print(f"   Stream procesado disponible en: {rtsp_publisher.output_url}")
            return True

    def stop_camera(self, cam_id):
        """
        Detiene captura, procesamiento y publicación de una cámara.

        Args:
            cam_id: ID de la cámara
        """
        with self.lock:
            if cam_id not in self.active_cameras:
                print(f"⚠️ Cámara {cam_id} no está activa")
                return False

            # Señalizar detención
            camera_data = self.active_cameras[cam_id]
            camera_data['stop_flag'] = True

            # Esperar a que termine el thread
            if camera_data['thread'].is_alive():
                camera_data['thread'].join(timeout=3.0)

            # Detener publisher RTSP
            if camera_data.get('rtsp_publisher'):
                camera_data['rtsp_publisher'].stop()

            # Liberar recursos
            if camera_data['capture']:
                camera_data['capture'].release()

            # Eliminar del diccionario
            del self.active_cameras[cam_id]

            print(f"✅ Cámara {cam_id} detenida")
            return True

    def get_processed_frame(self, cam_id):
        """
        Obtiene el último frame procesado de una cámara.

        Args:
            cam_id: ID de la cámara

        Returns:
            numpy.ndarray: Frame procesado o None
        """
        if cam_id not in self.active_cameras:
            return None

        return self.active_cameras[cam_id].get('processed_frame')

    def get_raw_frame(self, cam_id):
        """
        Obtiene el último frame sin procesar de una cámara.

        Args:
            cam_id: ID de la cámara

        Returns:
            numpy.ndarray: Frame raw o None
        """
        if cam_id not in self.active_cameras:
            return None

        return self.active_cameras[cam_id].get('current_frame')

    def get_processed_stream_url(self, cam_id):
        """
        Obtiene la URL del stream procesado para una cámara.

        Args:
            cam_id: ID de la cámara

        Returns:
            str: URL RTSP del stream procesado o None
        """
        if cam_id not in self.active_cameras:
            return None

        return self.active_cameras[cam_id].get('output_url')

    def is_camera_active(self, cam_id):
        """Verifica si una cámara está activa"""
        return cam_id in self.active_cameras

    def _camera_loop(self, camera_data):
        """
        Loop principal de captura, procesamiento y publicación.

        Ejecuta en thread separado para cada cámara.

        Args:
            camera_data: Diccionario con datos de la cámara
        """
        cam_id = camera_data['cam_id']
        rtsp_url = camera_data['rtsp_url']
        processor = camera_data['processor']
        rtsp_publisher = camera_data['rtsp_publisher']

        # Intentar conectar a RTSP de entrada
        print(f"🔌 Conectando a RTSP: {rtsp_url}")
        capture = cv2.VideoCapture(rtsp_url)

        if not capture.isOpened():
            print(f"❌ Error conectando a RTSP de cámara {cam_id}")
            system_logger.rtsp_connection_failed(cam_id)
            return

        camera_data['capture'] = capture

        # Obtener resolución del video de entrada
        input_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        input_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        input_fps = capture.get(cv2.CAP_PROP_FPS) or 25

        print(f"📹 Video de entrada: {input_width}x{input_height} @ {input_fps:.1f}fps")

        # Configurar publisher con la resolución correcta
        rtsp_publisher.width = input_width
        rtsp_publisher.height = input_height
        rtsp_publisher.fps = int(input_fps)

        # Iniciar publisher
        if not rtsp_publisher.start():
            print(f"❌ No se pudo iniciar publisher para cámara {cam_id}")
            capture.release()
            return

        system_logger.camera_started(cam_id)
        print(f"✅ Cámara {cam_id} conectada y publicando")

        # Contadores para diagnóstico
        frame_count = 0
        error_count = 0
        last_fps_check = time.time()
        fps_frame_count = 0

        # Control de timing para mantener FPS estable
        frame_time = 1.0 / rtsp_publisher.fps
        last_frame_time = time.time()

        while not camera_data['stop_flag']:
            try:
                # Capturar frame
                ret, frame = capture.read()

                if not ret:
                    error_count += 1

                    if error_count > 10:
                        print(f"❌ Demasiados errores en cámara {cam_id}, reconectando...")
                        system_logger.rtsp_connection_failed(cam_id)

                        # Intentar reconectar
                        capture.release()
                        time.sleep(2)
                        capture = cv2.VideoCapture(rtsp_url)

                        if capture.isOpened():
                            camera_data['capture'] = capture
                            error_count = 0
                            system_logger.rtsp_connection_restored(cam_id)
                        else:
                            print(f"❌ No se pudo reconectar cámara {cam_id}")
                            break

                    time.sleep(0.1)
                    continue

                # Reset error counter si captura exitosa
                error_count = 0

                # Guardar frame raw
                camera_data['current_frame'] = frame.copy()

                # Procesar frame con el procesador de IA
                try:
                    processed_frame = processor.process_frame(frame)
                    camera_data['processed_frame'] = processed_frame
                except Exception as e:
                    print(f"❌ Error en procesador de cámara {cam_id}: {str(e)}")
                    system_logger.processor_error(cam_id, str(e))
                    # Usar frame original si falla el procesamiento
                    processed_frame = frame.copy()
                    camera_data['processed_frame'] = processed_frame

                # Publicar frame procesado a MediaMTX
                if not rtsp_publisher.write_frame(processed_frame):
                    # Intentar reiniciar publisher si falla
                    print(f"⚠️ Reiniciando publisher para cámara {cam_id}...")
                    rtsp_publisher.stop()
                    time.sleep(0.5)
                    rtsp_publisher.start()

                frame_count += 1
                fps_frame_count += 1

                # Calcular FPS cada 5 segundos
                if time.time() - last_fps_check >= 5.0:
                    fps = fps_frame_count / 5.0
                    fps_frame_count = 0
                    last_fps_check = time.time()

                    # Advertir si FPS es bajo
                    if fps < 10:
                        system_logger.low_fps_warning(cam_id, int(fps))
                    else:
                        print(f"📊 Cámara {cam_id}: {fps:.1f} FPS")

                # Control de timing para mantener FPS estable
                current_time = time.time()
                elapsed = current_time - last_frame_time
                sleep_time = frame_time - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_frame_time = time.time()

            except Exception as e:
                print(f"❌ Error inesperado en loop de cámara {cam_id}: {str(e)}")
                system_logger.log(cam_id, f"Error en loop: {str(e)}", "ERROR")
                time.sleep(0.5)

        # Limpieza al salir
        rtsp_publisher.stop()
        capture.release()
        print(f"🛑 Loop de cámara {cam_id} terminado ({frame_count} frames procesados)")
        system_logger.camera_stopped(cam_id)
