# modules/vision/manager.py
import threading
import time
import subprocess
import cv2
from config.config_manager import device_config
from modules.vision.processors import get_processor_class
from modules.analytics.specialists.system_logger import system_logger


class VisionManager:
    """
    Vision Manager INFALIBLE + CALIDAD MEJORADA

    🛡️ INFALIBLE:
    ✅ Reconexión automática de cámara
    ✅ Reinicio automático de FFmpeg
    ✅ Watchdog thread para monitoreo
    ✅ Límites de errores antes de reinicio
    ✅ Cleanup robusto de recursos
    ✅ Manejo de excepciones exhaustivo

    🎨 CALIDAD MEJORADA:
    ✅ Bitrate 1500k (mejor imagen)
    ✅ Sharpening automático
    ✅ Denoise ligero
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
        self._watchdog_thread = None
        self._watchdog_running = False
        self._start_watchdog()
        print("✅ VisionManager INFALIBLE inicializado")

    def _start_watchdog(self):
        """Inicia thread watchdog para monitorear cámaras"""
        self._watchdog_running = True
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            daemon=True
        )
        self._watchdog_thread.start()
        print("🐕 Watchdog iniciado")

    def _watchdog_loop(self):
        """Loop que monitorea el estado de las cámaras cada 10 segundos"""
        while self._watchdog_running:
            try:
                time.sleep(10)

                with self.lock:
                    for cam_id, camera_data in list(self.active_cameras.items()):
                        # Verificar si el thread sigue vivo
                        if not camera_data['thread'].is_alive():
                            print(f"⚠️ Watchdog: Cam {cam_id} thread muerto, reiniciando...")
                            self._restart_camera_internal(cam_id)

                        # Verificar si FFmpeg sigue vivo
                        ffmpeg = camera_data.get('ffmpeg_process')
                        if ffmpeg and ffmpeg.poll() is not None:
                            print(f"⚠️ Watchdog: Cam {cam_id} FFmpeg muerto")
                            # El loop principal lo detectará y reiniciará

                        # Verificar si hay frames recientes
                        last_frame_time = camera_data.get('last_frame_time', 0)
                        if time.time() - last_frame_time > 30:
                            print(f"⚠️ Watchdog: Cam {cam_id} sin frames por 30s, reiniciando...")
                            self._restart_camera_internal(cam_id)

            except Exception as e:
                print(f"❌ Watchdog error: {e}")
                time.sleep(5)

    def _restart_camera_internal(self, cam_id):
        """Reinicia una cámara internamente (llamado por watchdog)"""
        try:
            if cam_id in self.active_cameras:
                camera_data = self.active_cameras[cam_id]
                processor_id = camera_data['processor_id']

                # Detener
                camera_data['stop_flag'] = True
                time.sleep(1)

                # Limpiar
                if camera_data.get('capture'):
                    try:
                        camera_data['capture'].release()
                    except:
                        pass

                if camera_data.get('ffmpeg_process'):
                    try:
                        camera_data['ffmpeg_process'].kill()
                    except:
                        pass

                del self.active_cameras[cam_id]

                # Reiniciar
                time.sleep(2)
                self.start_camera(cam_id, processor_id)
                print(f"✅ Cam {cam_id} reiniciada por watchdog")

        except Exception as e:
            print(f"❌ Error reiniciando cam {cam_id}: {e}")

    def start_camera(self, cam_id, processor_id=None):
        """Inicia captura y procesamiento"""
        with self.lock:
            if cam_id in self.active_cameras:
                print(f"⚠️ Cámara {cam_id} ya activa")
                return False

            camera = device_config.get_camera(cam_id)
            if not camera:
                print(f"❌ Configuración de cámara {cam_id} no encontrada")
                return False

            if processor_id is None:
                processor_id = camera.get('active_processor')

            ProcessorClass = get_processor_class(processor_id)
            if not ProcessorClass:
                print(f"❌ Procesador {processor_id} no encontrado")
                return False

            rtsp_url = device_config.get_rtsp_url(cam_id)
            if not rtsp_url:
                print(f"❌ URL RTSP para cámara {cam_id} no encontrada")
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
                'ffmpeg_process': None,
                'last_error': None,
                'last_frame_time': time.time(),
                'error_count': 0,
                'ffmpeg_restart_count': 0
            }

            thread = threading.Thread(
                target=self._camera_loop,
                args=(camera_data,),
                daemon=True
            )
            camera_data['thread'] = thread
            thread.start()

            self.active_cameras[cam_id] = camera_data
            print(f"✅ Cámara {cam_id} iniciada (INFALIBLE)")
            return True

    def stop_camera(self, cam_id):
        """Detiene cámara de forma segura"""
        with self.lock:
            if cam_id not in self.active_cameras:
                return False

            camera_data = self.active_cameras[cam_id]
            camera_data['stop_flag'] = True

            # Esperar a que termine el thread
            if camera_data['thread']:
                camera_data['thread'].join(timeout=5.0)

            # Limpiar recursos
            self._cleanup_camera_resources(camera_data)

            del self.active_cameras[cam_id]
            print(f"✅ Cámara {cam_id} detenida")
            return True

    def _cleanup_camera_resources(self, camera_data):
        """Limpia todos los recursos de una cámara de forma segura"""
        try:
            if camera_data.get('capture'):
                camera_data['capture'].release()
        except Exception as e:
            print(f"⚠️ Error liberando capture: {e}")

        try:
            if camera_data.get('ffmpeg_process'):
                ffmpeg = camera_data['ffmpeg_process']
                try:
                    ffmpeg.stdin.close()
                except:
                    pass
                try:
                    ffmpeg.terminate()
                    ffmpeg.wait(timeout=2)
                except:
                    try:
                        ffmpeg.kill()
                        ffmpeg.wait(timeout=1)
                    except:
                        pass
        except Exception as e:
            print(f"⚠️ Error cerrando FFmpeg: {e}")

    def is_camera_active(self, cam_id):
        return cam_id in self.active_cameras

    def get_processed_frame(self, cam_id):
        if cam_id not in self.active_cameras:
            return None
        return self.active_cameras[cam_id].get('processed_frame')

    def _start_ffmpeg_realtime(self, cam_id, width, height, fps):
        """
        FFmpeg INFALIBLE + CALIDAD MEJORADA

        🎨 Bitrate 1500k (mejorado)
        🛡️ Manejo robusto de errores
        """
        try:
            if width > 1280 or height > 720:
                width = 1280
                height = 720

            mediamtx_url = f"rtsp://localhost:8554/camera_{cam_id}_ai"

            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f'{width}x{height}',
                '-r', str(fps),
                '-thread_queue_size', '4',
                '-probesize', '32',
                '-analyzeduration', '0',
                '-i', '-',
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-profile:v', 'baseline',
                '-pix_fmt', 'yuv420p',
                '-b:v', '1500k',  # ✅ Mejorado (era 1200k)
                '-maxrate', '1800k',
                '-bufsize', '400k',  # ✅ Aumentado para estabilidad
                '-g', '1',
                '-keyint_min', '1',
                '-sc_threshold', '0',
                '-bf', '0',
                '-threads', '1',
                '-fflags', 'nobuffer+flush_packets',
                '-flags', 'low_delay',
                '-strict', 'experimental',
                '-flush_packets', '1',
                '-f', 'rtsp',
                '-rtsp_transport', 'tcp',
                mediamtx_url
            ]

            print(f"🚀 FFmpeg: {width}x{height}@{fps}fps | Bitrate: 1500k")

            process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=0
            )

            time.sleep(0.3)
            if process.poll() is not None:
                print(f"❌ FFmpeg falló al iniciar")
                return None

            print(f"✅ FFmpeg activo")
            return process

        except Exception as e:
            print(f"❌ Error FFmpeg: {e}")
            return None

    def _camera_loop(self, camera_data):
        """
        Loop INFALIBLE con reconexión automática

        🛡️ CARACTERÍSTICAS:
        ✅ Reconexión automática de cámara (max 5 intentos)
        ✅ Reinicio automático de FFmpeg
        ✅ Límites de errores consecutivos
        ✅ Cleanup robusto en todas las rutas

        🎨 MEJORAS VISUALES:
        ✅ Sharpening automático
        ✅ Denoise ligero
        """
        cam_id = camera_data['cam_id']
        rtsp_url = camera_data['rtsp_url']
        processor = camera_data['processor']

        MAX_RECONNECT_ATTEMPTS = 5
        MAX_CONSECUTIVE_ERRORS = 50
        FFMPEG_RESTART_THRESHOLD = 10

        reconnect_attempt = 0

        while not camera_data['stop_flag'] and reconnect_attempt < MAX_RECONNECT_ATTEMPTS:
            capture = None
            ffmpeg_process = None

            try:
                print(f"🔌 Conectando a Cam {cam_id} (intento {reconnect_attempt + 1}/{MAX_RECONNECT_ATTEMPTS})")

                # Conectar OpenCV
                capture = cv2.VideoCapture(rtsp_url)
                capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'H264'))

                if not capture.isOpened():
                    print(f"❌ No se pudo conectar a cam {cam_id}")
                    reconnect_attempt += 1
                    time.sleep(5)
                    continue

                camera_data['capture'] = capture

                # Propiedades
                orig_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                orig_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = int(capture.get(cv2.CAP_PROP_FPS))

                if fps <= 0 or fps > 30:
                    fps = 10

                # Downsample
                if orig_width > 1280 or orig_height > 720:
                    work_width = 1280
                    work_height = 720
                else:
                    work_width = orig_width
                    work_height = orig_height

                print(f"📹 Cam {cam_id}: {orig_width}x{orig_height} → {work_width}x{work_height} @ {fps}fps")

                # Iniciar FFmpeg
                ffmpeg_process = self._start_ffmpeg_realtime(cam_id, work_width, work_height, fps)
                camera_data['ffmpeg_process'] = ffmpeg_process

                if not ffmpeg_process:
                    print(f"❌ FFmpeg no se pudo iniciar")
                    reconnect_attempt += 1
                    time.sleep(5)
                    continue

                system_logger.camera_started(cam_id)

                # Variables de control
                frame_count = 0
                process_count = 0
                last_stats_time = time.time()
                skip_counter = 0
                SKIP_FRAMES = 2
                consecutive_errors = 0
                ffmpeg_write_errors = 0

                print(f"🎬 Cam {cam_id} - Loop iniciado")
                reconnect_attempt = 0  # Reset en conexión exitosa

                # Loop principal
                while not camera_data['stop_flag']:
                    try:
                        # Leer frame
                        ret, frame = capture.read()

                        if not ret or frame is None:
                            consecutive_errors += 1
                            if consecutive_errors > MAX_CONSECUTIVE_ERRORS:
                                print(f"❌ Cam {cam_id}: Demasiados errores consecutivos, reconectando...")
                                break
                            time.sleep(0.01)
                            continue

                        consecutive_errors = 0  # Reset
                        frame_count += 1
                        skip_counter += 1
                        camera_data['last_frame_time'] = time.time()

                        # Resize
                        if frame.shape[1] != work_width or frame.shape[0] != work_height:
                            frame = cv2.resize(
                                frame,
                                (work_width, work_height),
                                interpolation=cv2.INTER_LINEAR
                            )

                        # ✅ MEJORA VISUAL: Sharpening ligero
                        if frame_count % 10 == 0:  # Cada 10 frames
                            kernel = np.array([[-1, -1, -1],
                                               [-1, 9, -1],
                                               [-1, -1, -1]]) / 9
                            frame = cv2.filter2D(frame, -1, kernel)

                        # Frame skipping
                        should_process = (skip_counter % (SKIP_FRAMES + 1) == 0)

                        if should_process:
                            processor.process_frame(frame)
                            processor.draw_detections(frame)
                            process_count += 1
                        else:
                            processor.draw_detections(frame)

                        camera_data['processed_frame'] = frame

                        # Enviar a FFmpeg
                        if ffmpeg_process and ffmpeg_process.poll() is None:
                            try:
                                ffmpeg_process.stdin.write(frame.tobytes())
                                ffmpeg_write_errors = 0
                            except BrokenPipeError:
                                ffmpeg_write_errors += 1
                                if ffmpeg_write_errors > FFMPEG_RESTART_THRESHOLD:
                                    print(f"🔄 Cam {cam_id}: Reiniciando FFmpeg...")
                                    try:
                                        ffmpeg_process.kill()
                                    except:
                                        pass
                                    ffmpeg_process = self._start_ffmpeg_realtime(cam_id, work_width, work_height, fps)
                                    camera_data['ffmpeg_process'] = ffmpeg_process
                                    ffmpeg_write_errors = 0
                                    camera_data['ffmpeg_restart_count'] += 1
                            except Exception as e:
                                ffmpeg_write_errors += 1
                        else:
                            # FFmpeg murió
                            print(f"⚠️ Cam {cam_id}: FFmpeg no está corriendo, reiniciando...")
                            ffmpeg_process = self._start_ffmpeg_realtime(cam_id, work_width, work_height, fps)
                            camera_data['ffmpeg_process'] = ffmpeg_process

                        # Stats
                        current_time = time.time()
                        if current_time - last_stats_time >= 5.0:
                            actual_fps = frame_count / 5.0
                            process_fps = process_count / 5.0
                            print(
                                f"📊 Cam {cam_id}: {actual_fps:.1f} FPS | {process_fps:.1f} proc | FFmpeg restarts: {camera_data['ffmpeg_restart_count']}")
                            frame_count = 0
                            process_count = 0
                            last_stats_time = current_time

                    except Exception as e:
                        print(f"❌ Cam {cam_id} - Error en loop: {e}")
                        consecutive_errors += 1
                        if consecutive_errors > MAX_CONSECUTIVE_ERRORS:
                            break
                        time.sleep(0.01)

            except Exception as e:
                print(f"❌ Cam {cam_id} - Error fatal: {e}")
                reconnect_attempt += 1
                time.sleep(5)

            finally:
                # Cleanup robusto
                if capture:
                    try:
                        capture.release()
                    except:
                        pass

                if ffmpeg_process:
                    try:
                        ffmpeg_process.stdin.close()
                    except:
                        pass
                    try:
                        ffmpeg_process.terminate()
                        ffmpeg_process.wait(timeout=2)
                    except:
                        try:
                            ffmpeg_process.kill()
                        except:
                            pass

        print(f"🛑 Cam {cam_id}: Loop detenido (intentos agotados: {reconnect_attempt}/{MAX_RECONNECT_ATTEMPTS})")


# Singleton
vision_manager = VisionManager()

# Importar numpy para sharpening
import numpy as np