# modules/vision/manager.py
import threading
import time
from config.config_manager import device_config
from modules.vision.processors import get_processor_class
from modules.analytics.specialists.system_logger import system_logger
from modules.analytics.specialists.alerts_engine import alerts_engine
import cv2


class VisionManager:
    """
    Singleton que gestiona todas las cámaras y sus procesadores
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
        print("✅ VisionManager inicializado")

    def start_camera(self, cam_id, processor_id=None):
        """
        Inicia captura y procesamiento de una cámara

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
                'capture': None
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
            return True

    def stop_camera(self, cam_id):
        """
        Detiene captura y procesamiento de una cámara

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
                camera_data['thread'].join(timeout=2.0)

            # Liberar recursos
            if camera_data['capture']:
                camera_data['capture'].release()

            # Eliminar del diccionario
            del self.active_cameras[cam_id]

            print(f"✅ Cámara {cam_id} detenida")
            return True

    def get_processed_frame(self, cam_id):
        """
        Obtiene el último frame procesado de una cámara

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
        Obtiene el último frame sin procesar de una cámara

        Args:
            cam_id: ID de la cámara

        Returns:
            numpy.ndarray: Frame raw o None
        """
        if cam_id not in self.active_cameras:
            return None

        return self.active_cameras[cam_id].get('current_frame')

    def is_camera_active(self, cam_id):
        """Verifica si una cámara está activa"""
        return cam_id in self.active_cameras

    def _camera_loop(self, camera_data):
        """
        Loop principal de captura y procesamiento (ejecuta en thread separado)

        Args:
            camera_data: Diccionario con datos de la cámara
        """
        cam_id = camera_data['cam_id']
        rtsp_url = camera_data['rtsp_url']
        processor = camera_data['processor']

        # Intentar conectar a RTSP
        print(f"🔌 Conectando a RTSP: {rtsp_url}")
        capture = cv2.VideoCapture(rtsp_url)

        if not capture.isOpened():
            print(f"❌ Error conectando a RTSP de cámara {cam_id}")
            system_logger.rtsp_connection_failed(cam_id)
            return

        camera_data['capture'] = capture
        system_logger.camera_started(cam_id)
        print(f"✅ Cámara {cam_id} conectada exitosamente")

        # Contadores para diagnóstico
        frame_count = 0
        error_count = 0
        last_fps_check = time.time()
        fps_frame_count = 0

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
                    camera_data['processed_frame'] = frame.copy()

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

                # Control de CPU (no procesar más rápido de lo necesario)
                time.sleep(0.001)

            except Exception as e:
                print(f"❌ Error inesperado en loop de cámara {cam_id}: {str(e)}")
                system_logger.log(cam_id, f"Error en loop: {str(e)}", "ERROR")
                time.sleep(0.5)

        # Limpieza al salir
        capture.release()
        print(f"🛑 Loop de cámara {cam_id} terminado ({frame_count} frames procesados)")
        system_logger.camera_stopped(cam_id)