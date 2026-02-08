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
        ✅ ULTRA LOW LATENCY - Mínimo delay
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

                # ✅ ENCODING ULTRA RÁPIDO
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-profile:v', 'baseline',
                '-pix_fmt', 'yuv420p',

                # ✅ KEYFRAME CADA 10 FRAMES (1 segundo)
                '-g', '10',
                '-keyint_min', '10',
                '-sc_threshold', '0',

                # ✅ BITRATE MUY BAJO (menos calidad, menos delay)
                '-b:v', '600k',  # ✅ Reducido de 2000k
                '-maxrate', '700k',
                '-bufsize', '300k',  # ✅ Buffer mínimo

                # ✅ 1 THREAD (menos latencia)
                '-threads', '1',

                # ✅ NO BUFFERING
                '-flags', 'low_delay',
                '-fflags', 'nobuffer',

                # ✅ RTSP
                '-f', 'rtsp',
                '-rtsp_transport', 'tcp',

                mediamtx_url
            ]

            process = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                bufsize=0  # ✅ Sin buffer en pipe
            )

            print(f"✅ FFmpeg LOW LATENCY: {cam_id}")
            return process

        except Exception as e:
            print(f"❌ FFmpeg error: {e}")
            return None

    def _draw_detections(self, frame, processor):
        """
        ✅ Dibuja ROI y boxes en el frame
        Usa las detecciones guardadas en el processor
        """
        if not processor.zone_defined:
            return

        # ✅ ROI
        roi_color = (0, 0, 255) if processor.current_intruders > 0 else (0, 255, 0)
        cv2.polylines(
            frame,
            [processor.restricted_zone.reshape((-1, 1, 2))],
            True,
            roi_color,
            3
        )

        # ✅ BOXES
        for box_data in processor._last_boxes:
            x1, y1, x2, y2 = box_data['bbox']
            in_zone = box_data['in_zone']

            color = (0, 0, 255) if in_zone else (0, 255, 0)
            thickness = 4 if in_zone else 2
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        # ✅ ALERTA
        if processor.current_intruders > 0:
            cv2.putText(
                frame,
                f"ALERTA: {processor.current_intruders}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 0, 255),
                3
            )

    def _camera_loop(self, camera_data):
        """
        ✅ CRÍTICO: Mantener dimensiones consistentes
        """
        cam_id = camera_data['cam_id']
        rtsp_url = camera_data['rtsp_url']
        processor = camera_data['processor']

        print(f"🔌 Conectando: {rtsp_url}")
        capture = cv2.VideoCapture(rtsp_url)

        if not capture.isOpened():
            print(f"❌ Error RTSP {cam_id}")
            system_logger.rtsp_connection_failed(cam_id)
            return

        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        camera_data['capture'] = capture
        system_logger.camera_started(cam_id)

        # ✅ FORZAR dimensiones fijas
        FIXED_WIDTH = 1280
        FIXED_HEIGHT = 720
        FIXED_FPS = 10

        ffmpeg_process = self._start_ffmpeg(cam_id, FIXED_WIDTH, FIXED_HEIGHT, FIXED_FPS)
        camera_data['ffmpeg_process'] = ffmpeg_process

        processed_count = 0
        error_count = 0
        last_fps_check = time.time()

        print(f"⚡ Cam {cam_id}: {FIXED_WIDTH}x{FIXED_HEIGHT} @ {FIXED_FPS}fps")

        while not camera_data['stop_flag']:
            try:
                # ✅ Leer frame
                ret, frame = capture.read()

                if not ret:
                    error_count += 1
                    if error_count > 30:
                        print(f"❌ Reconectando {cam_id}...")
                        capture.release()
                        time.sleep(2)
                        capture = cv2.VideoCapture(rtsp_url)
                        if capture.isOpened():
                            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                            camera_data['capture'] = capture
                            error_count = 0
                        else:
                            break
                    time.sleep(0.05)
                    continue

                error_count = 0

                # ✅ RESIZE OBLIGATORIO a dimensiones fijas
                if frame.shape[1] != FIXED_WIDTH or frame.shape[0] != FIXED_HEIGHT:
                    frame = cv2.resize(frame, (FIXED_WIDTH, FIXED_HEIGHT))

                camera_data['current_frame'] = frame.copy()

                # ✅ Detección (NO modifica frame)
                try:
                    processor.process_frame(frame)
                except Exception as e:
                    print(f"❌ Processor: {e}")

                # ✅ Copiar para dibujar
                display_frame = frame.copy()

                # ✅ Dibujar detecciones
                if processor.zone_defined:
                    # ROI
                    roi_color = (0, 0, 255) if processor.current_intruders > 0 else (0, 255, 0)
                    cv2.polylines(
                        display_frame,
                        [processor.restricted_zone.reshape((-1, 1, 2))],
                        True,
                        roi_color,
                        3
                    )

                    # BOXES
                    for box_data in processor._last_boxes:
                        x1, y1, x2, y2 = box_data['bbox']
                        in_zone = box_data['in_zone']
                        color = (0, 0, 255) if in_zone else (0, 255, 0)
                        thickness = 4 if in_zone else 2
                        cv2.rectangle(display_frame, (x1, y1), (x2, y2), color, thickness)

                    # ALERTA
                    if processor.current_intruders > 0:
                        cv2.putText(
                            display_frame,
                            f"ALERTA: {processor.current_intruders}",
                            (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0,
                            (0, 0, 255),
                            3
                        )

                camera_data['processed_frame'] = display_frame

                # ✅ VERIFICAR dimensiones antes de enviar
                if display_frame.shape[1] != FIXED_WIDTH or display_frame.shape[0] != FIXED_HEIGHT:
                    print(f"⚠️ Dimensión incorrecta: {display_frame.shape}, resizing...")
                    display_frame = cv2.resize(display_frame, (FIXED_WIDTH, FIXED_HEIGHT))

                # ✅ Enviar a FFmpeg
                if ffmpeg_process and ffmpeg_process.poll() is None:
                    try:
                        ffmpeg_process.stdin.write(display_frame.tobytes())
                        processed_count += 1
                    except BrokenPipeError:
                        ffmpeg_process = self._start_ffmpeg(cam_id, FIXED_WIDTH, FIXED_HEIGHT, FIXED_FPS)
                        camera_data['ffmpeg_process'] = ffmpeg_process
                    except Exception as e:
                        pass

                # Stats
                current_time = time.time()
                if current_time - last_fps_check >= 10.0:
                    actual_fps = processed_count / 10.0
                    processed_count = 0
                    last_fps_check = current_time
                    print(f"📊 Cam {cam_id}: {actual_fps:.1f} FPS")

            except Exception as e:
                print(f"❌ Loop error: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.5)

        # LIMPIEZA
        capture.release()
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

        print(f"🛑 Cam {cam_id} detenida")
        system_logger.camera_stopped(cam_id)