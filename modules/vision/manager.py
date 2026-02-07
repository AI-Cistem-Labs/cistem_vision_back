# modules/vision/manager.py
import threading
import time
import subprocess
from config.config_manager import device_config
from modules.vision.processors import get_processor_class
from modules.analytics.specialists.system_logger import system_logger
from modules.analytics.specialists.alerts_engine import alerts_engine
import cv2


class VisionManager:
    """
    Singleton que gestiona cámaras y publica video procesado a MediaMTX
    ✅ MODIFICADO: Publica frames con boxes a MediaMTX vía FFmpeg
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

        self.active_cameras = {}
        self.lock = threading.Lock()
        self._initialized = True
        print("✅ VisionManager inicializado")

    def start_camera(self, cam_id, processor_id=None):
        """Inicia captura y procesamiento de una cámara"""
        with self.lock:
            if cam_id in self.active_cameras:
                print(f"⚠️ Cámara {cam_id} ya está activa")
                return False

            camera = device_config.get_camera(cam_id)
            if not camera:
                print(f"❌ Cámara {cam_id} no encontrada")
                return False

            if processor_id is None:
                processor_id = camera.get('active_processor')

            if processor_id is None:
                print(f"❌ No hay procesador asignado")
                return False

            ProcessorClass = get_processor_class(processor_id)
            if not ProcessorClass:
                print(f"❌ Procesador {processor_id} no encontrado")
                return False

            rtsp_url = device_config.get_rtsp_url(cam_id)
            if not rtsp_url:
                print(f"❌ URL RTSP no configurada")
                system_logger.log(cam_id, "URL RTSP no configurada", "ERROR")
                return False

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
                'ffmpeg_process': None  # ✅ NUEVO
            }

            thread = threading.Thread(
                target=self._camera_loop,
                args=(camera_data,),
                daemon=True
            )
            camera_data['thread'] = thread
            thread.start()

            self.active_cameras[cam_id] = camera_data

            print(f"✅ Cámara {cam_id} iniciada con procesador {processor_id}")
            return True

    def stop_camera(self, cam_id):
        """Detiene captura y procesamiento"""
        with self.lock:
            if cam_id not in self.active_cameras:
                print(f"⚠️ Cámara {cam_id} no está activa")
                return False

            camera_data = self.active_cameras[cam_id]
            camera_data['stop_flag'] = True

            if camera_data['thread'].is_alive():
                camera_data['thread'].join(timeout=2.0)

            if camera_data['capture']:
                camera_data['capture'].release()

            # ✅ NUEVO: Detener FFmpeg
            if camera_data['ffmpeg_process']:
                try:
                    camera_data['ffmpeg_process'].stdin.close()
                    camera_data['ffmpeg_process'].terminate()
                    camera_data['ffmpeg_process'].wait(timeout=2)
                except:
                    try:
                        camera_data['ffmpeg_process'].kill()
                    except:
                        pass

            del self.active_cameras[cam_id]

            print(f"✅ Cámara {cam_id} detenida")
            return True

    def get_processed_frame(self, cam_id):
        """Obtiene último frame procesado"""
        if cam_id not in self.active_cameras:
            return None
        return self.active_cameras[cam_id].get('processed_frame')

    def get_raw_frame(self, cam_id):
        """Obtiene último frame sin procesar"""
        if cam_id not in self.active_cameras:
            return None
        return self.active_cameras[cam_id].get('current_frame')

    def is_camera_active(self, cam_id):
        """Verifica si cámara está activa"""
        return cam_id in self.active_cameras

    def _start_ffmpeg(self, cam_id, width, height, fps):
        """
        ✅ NUEVO: Inicia FFmpeg para publicar a MediaMTX

        Args:
            cam_id: ID de la cámara
            width, height: Dimensiones del video
            fps: Frames por segundo

        Returns:
            subprocess.Popen o None
        """
        try:
            mediamtx_url = f"rtsp://localhost:8554/camera_{cam_id}_ai"

            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{width}x{height}',
                '-r', str(fps),
                '-i', '-',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-pix_fmt', 'yuv420p',
                '-g', str(fps * 2),
                '-b:v', '2M',
                '-maxrate', '2M',
                '-bufsize', '4M',
                '-f', 'rtsp',
                mediamtx_url
            ]

            process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            print(f"✅ FFmpeg iniciado para cámara {cam_id}")
            print(f"   📡 Publicando en: {mediamtx_url}")
            return process

        except Exception as e:
            print(f"❌ Error al iniciar FFmpeg: {str(e)}")
            return None

    def _camera_loop(self, camera_data):
        """
        Loop principal de captura y procesamiento
        ✅ MODIFICADO: Publica frames procesados a MediaMTX
        """
        cam_id = camera_data['cam_id']
        rtsp_url = camera_data['rtsp_url']
        processor = camera_data['processor']

        print(f"🔌 Conectando a RTSP: {rtsp_url}")
        capture = cv2.VideoCapture(rtsp_url)

        if not capture.isOpened():
            print(f"❌ Error conectando a RTSP de cámara {cam_id}")
            system_logger.rtsp_connection_failed(cam_id)
            return

        camera_data['capture'] = capture
        system_logger.camera_started(cam_id)
        print(f"✅ Cámara {cam_id} conectada exitosamente")

        # ✅ NUEVO: Iniciar FFmpeg para publicar en MediaMTX
        fps = int(capture.get(cv2.CAP_PROP_FPS)) or 30
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        ffmpeg_process = self._start_ffmpeg(cam_id, width, height, fps)
        camera_data['ffmpeg_process'] = ffmpeg_process

        frame_count = 0
        error_count = 0
        last_fps_check = time.time()
        fps_frame_count = 0

        while not camera_data['stop_flag']:
            try:
                ret, frame = capture.read()

                if not ret:
                    error_count += 1

                    if error_count > 10:
                        print(f"❌ Demasiados errores en cámara {cam_id}, reconectando...")
                        system_logger.rtsp_connection_failed(cam_id)

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

                error_count = 0

                # Guardar frame raw
                camera_data['current_frame'] = frame.copy()

                # ✅ PROCESAR FRAME CON IA (aquí se añaden los boxes)
                try:
                    processed_frame = processor.process_frame(frame)
                    camera_data['processed_frame'] = processed_frame
                except Exception as e:
                    print(f"❌ Error en procesador de cámara {cam_id}: {str(e)}")
                    system_logger.processor_error(cam_id, str(e))
                    processed_frame = frame.copy()
                    camera_data['processed_frame'] = processed_frame

                # ✅ NUEVO: PUBLICAR FRAME PROCESADO A MEDIAMTX
                if ffmpeg_process and ffmpeg_process.poll() is None:
                    try:
                        ffmpeg_process.stdin.write(processed_frame.tobytes())
                    except BrokenPipeError:
                        print(f"❌ FFmpeg pipe roto para cámara {cam_id}")
                        # Intentar reiniciar FFmpeg
                        ffmpeg_process = self._start_ffmpeg(cam_id, width, height, fps)
                        camera_data['ffmpeg_process'] = ffmpeg_process
                    except Exception as e:
                        print(f"❌ Error escribiendo a FFmpeg: {str(e)}")

                frame_count += 1
                fps_frame_count += 1

                # Calcular FPS cada 5 segundos
                if time.time() - last_fps_check >= 5.0:
                    current_fps = fps_frame_count / 5.0
                    fps_frame_count = 0
                    last_fps_check = time.time()

                    if current_fps < 10:
                        system_logger.low_fps_warning(cam_id, int(current_fps))

                time.sleep(0.001)

            except Exception as e:
                print(f"❌ Error inesperado en loop de cámara {cam_id}: {str(e)}")
                system_logger.log(cam_id, f"Error en loop: {str(e)}", "ERROR")
                time.sleep(0.5)

        # Limpieza al salir
        capture.release()

        # ✅ NUEVO: Cerrar FFmpeg
        if ffmpeg_process:
            try:
                ffmpeg_process.stdin.close()
                ffmpeg_process.terminate()
                ffmpeg_process.wait(timeout=2)
            except:
                try:
                    ffmpeg_process.kill()
                except:
                    pass

        print(f"🛑 Loop de cámara {cam_id} terminado ({frame_count} frames procesados)")
        system_logger.camera_stopped(cam_id)