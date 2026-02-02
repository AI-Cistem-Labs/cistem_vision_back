# modules/vision/manager.py
"""
VisionManager con soporte para re-publicar video procesado a MediaMTX.
Version 2: Con soporte para NVENC (Jetson) y mejor manejo de errores.
"""

import threading
import subprocess
import time
import os
import cv2
import numpy as np

from config.config_manager import device_config
from modules.vision.processors import get_processor_class
from modules.analytics.specialists.system_logger import system_logger

# Configuracion de MediaMTX
MEDIAMTX_HOST = os.getenv('TAILSCALE_IP', '127.0.0.1')
MEDIAMTX_RTSP_PORT = os.getenv('MEDIAMTX_RTSP_PORT', '8554')


def check_nvenc_available():
    """Verifica si NVENC (Jetson hardware encoder) esta disponible."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            timeout=10
        )
        return 'h264_nvmpi' in result.stdout or 'h264_v4l2m2m' in result.stdout
    except Exception:
        return False


def check_ffmpeg_codecs():
    """Lista los encoders disponibles."""
    try:
        result = subprocess.run(
            ['ffmpeg', '-encoders'],
            capture_output=True,
            text=True,
            timeout=10
        )
        print("[FFmpeg] Encoders H264 disponibles:")
        for line in result.stdout.split('\n'):
            if 'h264' in line.lower() or '264' in line:
                print(f"  {line.strip()}")
        return result.stdout
    except Exception as e:
        print(f"[FFmpeg] Error listando encoders: {e}")
        return ""


class RTSPPublisher:
    """Publica frames a MediaMTX via FFmpeg."""

    def __init__(self, cam_id, width=None, height=None, fps=None):
        self.cam_id = cam_id
        self.width = width or 1280
        self.height = height or 720
        self.fps = fps or 15
        self.process = None
        self.is_running = False
        self.lock = threading.Lock()
        self.output_url = f"rtsp://{MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}/cam_{cam_id}_ai"
        self.error_count = 0
        self.max_errors = 3

    def _get_ffmpeg_command(self):
        """Genera el comando FFmpeg con el mejor encoder disponible."""

        # Detectar encoder disponible
        encoders_output = ""
        try:
            result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, timeout=5)
            encoders_output = result.stdout
        except Exception:
            pass

        # TEMPORAL: Forzar libx264 hasta resolver problemas de hardware encoder
        # Cambiar use_libx264_only a False cuando quieras probar hardware encoders
        use_libx264_only = True

        if use_libx264_only:
            encoder_args = [
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
            ]
            print(f"[FFmpeg] Usando encoder: libx264 (software - forzado)")
        # Elegir encoder (prioridad: hardware Jetson > software)
        elif 'h264_nvmpi' in encoders_output:
            encoder_args = ['-c:v', 'h264_nvmpi']
            print(f"[FFmpeg] Usando encoder: h264_nvmpi (Jetson hardware)")
        elif 'h264_v4l2m2m' in encoders_output:
            encoder_args = ['-c:v', 'h264_v4l2m2m']
            print(f"[FFmpeg] Usando encoder: h264_v4l2m2m (hardware)")
        elif 'libx264' in encoders_output:
            encoder_args = [
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
            ]
            print(f"[FFmpeg] Usando encoder: libx264 (software)")
        else:
            encoder_args = ['-c:v', 'libx264', '-preset', 'ultrafast']
            print(f"[FFmpeg] Usando encoder: libx264 (fallback)")

        # Comando base
        cmd = [
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f'{self.width}x{self.height}',
            '-r', str(self.fps),
            '-i', '-',
        ]

        # Agregar encoder
        cmd.extend(encoder_args)

        # Parametros de salida
        cmd.extend([
            '-pix_fmt', 'yuv420p',
            '-b:v', '2M',
            '-maxrate', '2M',
            '-bufsize', '4M',
            '-g', str(self.fps * 2),
            '-f', 'rtsp',
            '-rtsp_transport', 'tcp',
            self.output_url
        ])

        return cmd

    def start(self):
        """Inicia FFmpeg."""
        if self.is_running:
            return True

        # Verificar que MediaMTX este accesible
        print(f"[FFmpeg] Verificando conexion a MediaMTX: {MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}")

        try:
            ffmpeg_cmd = self._get_ffmpeg_command()

            print(f"[FFmpeg] Iniciando publisher para cam {self.cam_id}")
            print(f"[FFmpeg] Resolucion: {self.width}x{self.height} @ {self.fps}fps")
            print(f"[FFmpeg] URL salida: {self.output_url}")
            print(f"[FFmpeg] Comando: {' '.join(ffmpeg_cmd)}")

            self.process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=10 ** 8
            )

            # Esperar un momento para ver si hay error inmediato
            time.sleep(0.5)

            if self.process.poll() is not None:
                # Proceso termino inmediatamente - hay error
                stderr = self.process.stderr.read().decode('utf-8', errors='ignore')
                print(f"[FFmpeg] Error al iniciar: {stderr[-500:]}")
                self.process = None
                return False

            self.is_running = True
            self.error_count = 0

            # Thread para monitorear errores
            t = threading.Thread(target=self._monitor_errors, daemon=True)
            t.start()

            print(f"[FFmpeg] Publisher iniciado para cam {self.cam_id}")
            return True

        except Exception as e:
            print(f"[FFmpeg] Error iniciando: {e}")
            self.is_running = False
            return False

    def _monitor_errors(self):
        """Monitorea stderr de FFmpeg."""
        if not self.process or not self.process.stderr:
            return
        try:
            while self.is_running and self.process:
                line = self.process.stderr.readline()
                if not line:
                    break
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str:
                    # Mostrar errores importantes
                    line_lower = line_str.lower()
                    if 'error' in line_lower or 'fatal' in line_lower or 'failed' in line_lower:
                        print(f"[FFmpeg] Error cam {self.cam_id}: {line_str}")
                    elif 'warning' in line_lower:
                        print(f"[FFmpeg] Warning cam {self.cam_id}: {line_str}")
        except Exception:
            pass

    def write_frame(self, frame):
        """Escribe un frame a FFmpeg."""
        if not self.is_running or not self.process:
            return False

        # Verificar si el proceso sigue vivo
        if self.process.poll() is not None:
            print(f"[FFmpeg] Proceso terminado inesperadamente cam {self.cam_id}")
            self.is_running = False
            return False

        try:
            with self.lock:
                h, w = frame.shape[:2]
                if w != self.width or h != self.height:
                    frame = cv2.resize(frame, (self.width, self.height))

                self.process.stdin.write(frame.tobytes())
                self.process.stdin.flush()
                self.error_count = 0
                return True

        except BrokenPipeError:
            self.error_count += 1
            print(f"[FFmpeg] Pipe roto cam {self.cam_id} (error {self.error_count}/{self.max_errors})")
            if self.error_count >= self.max_errors:
                self.stop()
            return False
        except Exception as e:
            self.error_count += 1
            print(f"[FFmpeg] Error escribiendo frame: {e}")
            return False

    def stop(self):
        """Detiene FFmpeg."""
        self.is_running = False
        if self.process:
            try:
                self.process.stdin.close()
            except Exception:
                pass
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            finally:
                self.process = None
        print(f"[FFmpeg] Publisher detenido cam {self.cam_id}")


class VisionManager:
    """Singleton que gestiona camaras y procesadores."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.active_cameras = {}
        self.lock = threading.Lock()
        self._initialized = True

        # Mostrar info de encoders al inicio
        print("[VisionManager] Inicializado con soporte MediaMTX")
        check_ffmpeg_codecs()

    def start_camera(self, cam_id, processor_id=None):
        """Inicia procesamiento de una camara."""
        with self.lock:
            if cam_id in self.active_cameras:
                print(f"[VisionManager] Camara {cam_id} ya activa")
                return True

            camera = device_config.get_camera(cam_id)
            if not camera:
                print(f"[VisionManager] Camara {cam_id} no encontrada")
                return False

            if processor_id is None:
                processor_id = camera.get('active_processor')

            if processor_id is None:
                print(f"[VisionManager] Sin procesador para cam {cam_id}")
                return False

            ProcessorClass = get_processor_class(processor_id)
            if not ProcessorClass:
                print(f"[VisionManager] Procesador {processor_id} no encontrado")
                return False

            rtsp_url = device_config.get_rtsp_url(cam_id)
            if not rtsp_url:
                print(f"[VisionManager] Sin URL RTSP para cam {cam_id}")
                return False

            # No crear el publisher aqui, se crea en el loop cuando sabemos la resolucion
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
                'rtsp_publisher': None,
                'output_url': f"rtsp://{MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}/cam_{cam_id}_ai",
            }

            thread = threading.Thread(
                target=self._camera_loop,
                args=(camera_data,),
                daemon=True
            )
            camera_data['thread'] = thread
            thread.start()

            self.active_cameras[cam_id] = camera_data

            print(f"[VisionManager] Camara {cam_id} iniciada con procesador {processor_id}")
            return True

    def stop_camera(self, cam_id):
        """Detiene procesamiento de una camara."""
        with self.lock:
            if cam_id not in self.active_cameras:
                print(f"[VisionManager] Camara {cam_id} no activa")
                return False

            camera_data = self.active_cameras[cam_id]
            camera_data['stop_flag'] = True

            if camera_data['thread'] and camera_data['thread'].is_alive():
                camera_data['thread'].join(timeout=5.0)

            if camera_data.get('rtsp_publisher'):
                camera_data['rtsp_publisher'].stop()

            if camera_data.get('capture'):
                try:
                    camera_data['capture'].release()
                except Exception:
                    pass

            del self.active_cameras[cam_id]
            print(f"[VisionManager] Camara {cam_id} detenida")
            return True

    def get_processed_frame(self, cam_id):
        """Obtiene ultimo frame procesado."""
        if cam_id not in self.active_cameras:
            return None
        return self.active_cameras[cam_id].get('processed_frame')

    def get_raw_frame(self, cam_id):
        """Obtiene ultimo frame raw."""
        if cam_id not in self.active_cameras:
            return None
        return self.active_cameras[cam_id].get('current_frame')

    def get_processed_stream_url(self, cam_id):
        """Obtiene URL del stream procesado."""
        if cam_id not in self.active_cameras:
            return None
        return self.active_cameras[cam_id].get('output_url')

    def is_camera_active(self, cam_id):
        """Verifica si camara esta activa."""
        return cam_id in self.active_cameras

    def _camera_loop(self, camera_data):
        """Loop principal de captura y procesamiento."""
        cam_id = camera_data['cam_id']
        rtsp_url = camera_data['rtsp_url']
        processor = camera_data['processor']

        print(f"[CameraLoop] Conectando a RTSP: {rtsp_url}")

        # Configurar captura con timeout
        capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Buffer minimo para baja latencia

        if not capture.isOpened():
            print(f"[CameraLoop] Error conectando cam {cam_id}")
            system_logger.rtsp_connection_failed(cam_id)
            return

        camera_data['capture'] = capture

        # Obtener propiedades del video
        input_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        input_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        input_fps = capture.get(cv2.CAP_PROP_FPS)

        # Validar FPS
        if input_fps <= 0 or input_fps > 60:
            input_fps = 15

        print(f"[CameraLoop] Video entrada: {input_width}x{input_height} @ {input_fps:.1f}fps")

        # Crear publisher con la resolucion correcta
        rtsp_publisher = RTSPPublisher(
            cam_id,
            width=input_width,
            height=input_height,
            fps=int(input_fps)
        )
        camera_data['rtsp_publisher'] = rtsp_publisher

        # Iniciar publisher
        if not rtsp_publisher.start():
            print(f"[CameraLoop] No se pudo iniciar publisher cam {cam_id}")
            print(f"[CameraLoop] Continuando sin publicar a MediaMTX...")
            # Continuar sin publisher para que al menos el procesamiento funcione
            rtsp_publisher = None

        system_logger.camera_started(cam_id)
        print(f"[CameraLoop] Camara {cam_id} conectada")

        frame_count = 0
        error_count = 0
        last_fps_check = time.time()
        fps_frame_count = 0
        publisher_retry_count = 0
        max_publisher_retries = 5

        # Control de FPS
        target_fps = int(input_fps) if input_fps > 0 else 15
        frame_interval = 1.0 / target_fps
        last_frame_time = time.time()

        while not camera_data['stop_flag']:
            try:
                ret, frame = capture.read()

                if not ret:
                    error_count += 1
                    if error_count > 30:
                        print(f"[CameraLoop] Muchos errores cam {cam_id}, reconectando...")
                        system_logger.rtsp_connection_failed(cam_id)
                        capture.release()
                        time.sleep(2)
                        capture = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                        if capture.isOpened():
                            camera_data['capture'] = capture
                            error_count = 0
                            system_logger.rtsp_connection_restored(cam_id)
                        else:
                            print(f"[CameraLoop] No se pudo reconectar cam {cam_id}")
                            break
                    time.sleep(0.033)
                    continue

                error_count = 0
                camera_data['current_frame'] = frame.copy()

                # Procesar frame
                try:
                    processed_frame = processor.process_frame(frame)
                    camera_data['processed_frame'] = processed_frame
                except Exception as e:
                    print(f"[CameraLoop] Error procesador cam {cam_id}: {e}")
                    system_logger.processor_error(cam_id, str(e))
                    processed_frame = frame.copy()
                    camera_data['processed_frame'] = processed_frame

                # Publicar frame (si hay publisher)
                if rtsp_publisher and rtsp_publisher.is_running:
                    if not rtsp_publisher.write_frame(processed_frame):
                        publisher_retry_count += 1
                        if publisher_retry_count <= max_publisher_retries:
                            print(
                                f"[CameraLoop] Reintentando publisher cam {cam_id} ({publisher_retry_count}/{max_publisher_retries})...")
                            time.sleep(1)
                            rtsp_publisher.stop()
                            time.sleep(0.5)
                            if not rtsp_publisher.start():
                                print(f"[CameraLoop] No se pudo reiniciar publisher")
                        else:
                            print(f"[CameraLoop] Desactivando publisher para cam {cam_id}")
                            rtsp_publisher.stop()
                            rtsp_publisher = None
                            camera_data['rtsp_publisher'] = None
                else:
                    publisher_retry_count = 0

                frame_count += 1
                fps_frame_count += 1

                # Calcular FPS cada 5 segundos
                current_time = time.time()
                if current_time - last_fps_check >= 5.0:
                    fps = fps_frame_count / 5.0
                    fps_frame_count = 0
                    last_fps_check = current_time

                    status = "con publisher" if (rtsp_publisher and rtsp_publisher.is_running) else "sin publisher"
                    print(f"[CameraLoop] Camara {cam_id}: {fps:.1f} FPS ({status})")

                    if fps < 10:
                        system_logger.low_fps_warning(cam_id, int(fps))

                # Control de FPS
                elapsed = time.time() - last_frame_time
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_frame_time = time.time()

            except Exception as e:
                print(f"[CameraLoop] Error inesperado cam {cam_id}: {e}")
                system_logger.log(cam_id, f"Error en loop: {e}", "ERROR")
                time.sleep(0.5)

        # Limpieza
        if rtsp_publisher:
            rtsp_publisher.stop()
        capture.release()
        print(f"[CameraLoop] Loop cam {cam_id} terminado ({frame_count} frames)")
        system_logger.camera_stopped(cam_id)